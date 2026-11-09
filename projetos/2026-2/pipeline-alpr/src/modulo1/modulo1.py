# modulo 1 — aquisicao, pre-processamento e extracao
# le imagens brutas com anotacoes, extrai e retifica as placas
#
# uso:
#   python modulo1.py --entrada /caminho/dataset --pesos_yolo yolo.pt --pesos_pose pose.pt
#
# entrada esperada:
#   entrada/
#     train/
#       img_000001.jpg
#       img_000001.txt   <- plate e corners
#     val/
#     test/
#
# saida:
#   dataset_limpas/
#     train/
#       ABC1234_img_000001.png   <- crop retificado 128x64
#       img_000001.txt           <- corners usados
#     val/
#     test/
#     modulo1_report.txt
#
# setup servidor:
#   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
#   pip install ultralytics opencv-python tqdm numpy
#
# executar:
#   nohup python modulo1.py \
#     --entrada /caminho/dataset \
#     --pesos_yolo "Modulo I/YOLO/YOLO26n/weights/best.pt" \
#     --pesos_pose "Modulo I/YOLO POSE/YOLO POSE UFPR LRLPR/YOLO26n POSE/weights/best.pt" \
#     > modulo1.log 2>&1 &

import argparse
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import torch
from tqdm import tqdm
from ultralytics import YOLO

TARGET_W = 128
TARGET_H = 64
DEFAULT_MARGIN = 0.15
DEFAULT_CONF = 0.6
MIN_QUAD_AREA = 100

SPLITS = ["train", "val", "test"]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


# LEITURA DE ANOTACAO ----------------------------------------------------

def parse_annotation(txt_path: Path) -> tuple[list | None, str | None]:
    if not txt_path.exists():
        return None, None

    corners = None
    plate = None

    for line in txt_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("corners:"):
            raw = line.split(":", 1)[1].strip()
            try:
                pairs = raw.split()
                if len(pairs) == 4:
                    corners = [tuple(float(v) for v in p.split(",")) for p in pairs]
            except ValueError:
                corners = None
        elif line.startswith("plate:"):
            plate = line.split(":", 1)[1].strip() or None

    return corners, plate


# PROCESSAMENTO GEOMETRICO -----------------------------------------------

# recorta bbox expandida por margin, clampada aos limites da imagem
def crop_with_margin(img: np.ndarray, bbox: np.ndarray, margin: float) -> tuple[np.ndarray, int, int]:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    bw = x2 - x1
    bh = y2 - y1

    x1m = max(0, int(x1 - bw * margin))
    y1m = max(0, int(y1 - bh * margin))
    x2m = min(w, int(x2 + bw * margin))
    y2m = min(h, int(y2 + bh * margin))

    return img[y1m:y2m, x1m:x2m], x1m, y1m


# roda YOLO-Pose no recorte, retorna 4 corners (TL, TR, BR, BL) ou None
def detect_corners(pose_model: YOLO, crop: np.ndarray, conf: float) -> list | None:
    results = pose_model(crop, conf=conf, verbose=False)
    result = results[0]

    if result.keypoints is None or len(result.keypoints) == 0:
        return None

    kpts = result.keypoints.xy[0].cpu().numpy()  # (4, 2): TL TR BR BL
    if kpts.shape[0] < 4:
        return None

    return [tuple(kpts[i]) for i in range(4)]


# verifica se os 4 cantos formam quadrilatero com area minima aceitavel
def validate_quadrilateral(corners: list) -> bool:
    pts = np.array(corners, dtype=np.float32)
    n = len(pts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2 > MIN_QUAD_AREA


# retifica perspectiva com 4 corners e redimensiona para (w, h)
def rectify_and_resize(img: np.ndarray, corners: list, w: int, h: int) -> np.ndarray:
    src = np.array(corners, dtype=np.float32)
    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (w, h), flags=cv2.INTER_CUBIC)


# recorta bbox com margem, ajusta para (w, h) com padding cinza, sem retificacao
def crop_bbox_and_pad(img: np.ndarray, corners: list, w: int, h: int,
                      margin: float = 0.10) -> np.ndarray | None:
    pts = np.array(corners, dtype=np.float32)
    H, W = img.shape[:2]
    x1, y1 = pts.min(axis=0)
    x2, y2 = pts.max(axis=0)
    bw, bh = x2 - x1, y2 - y1
    x1 = max(0, int(x1 - bw * margin))
    x2 = min(W, int(np.ceil(x2 + bw * margin)))
    y1 = max(0, int(y1 - bh * margin))
    y2 = min(H, int(np.ceil(y2 + bh * margin)))
    if x2 <= x1 or y2 <= y1:
        return None

    crop = img[y1:y2, x1:x2]
    ch, cw = crop.shape[:2]
    escala = min(w / cw, h / ch)
    nw = max(1, round(cw * escala))
    nh = max(1, round(ch * escala))
    interp = cv2.INTER_CUBIC if escala > 1 else cv2.INTER_AREA
    redim = cv2.resize(crop, (nw, nh), interpolation=interp)

    tela = np.full((h, w, 3), (128, 128, 128), dtype=np.uint8)
    x0 = (w - nw) // 2
    y0 = (h - nh) // 2
    tela[y0:y0 + nh, x0:x0 + nw] = redim
    return tela


# PERSISTENCIA -----------------------------------------------------------

# salva corners usados para rastreabilidade
def save_corners_txt(path: Path, corners: list) -> None:
    parts = [f"{x:.1f},{y:.1f}" for x, y in corners]
    path.write_text(f"corners: {' '.join(parts)}\n")


# PROCESSAMENTO POR SPLIT ------------------------------------------------

def process_split(
    split: str,
    dir_entrada: Path,
    dir_saida: Path,
    yolo_model: YOLO,
    pose_model: YOLO,
    conf: float,
    margin: float,
    sem_retificacao: bool = False,
) -> dict:
    split_in = dir_entrada / split
    split_out = dir_saida / split

    if not split_in.exists():
        print(f"[{split}] pasta nao encontrada, ignorando.")
        return {"split": split, "skip_reason": "pasta nao encontrada"}

    split_out.mkdir(parents=True, exist_ok=True)

    images = sorted(p for p in split_in.iterdir() if p.suffix.lower() in IMAGE_EXTS)

    stats = {
        "split": split,
        "ok": 0,
        "sem_txt": 0,
        "sem_plate": 0,
        "sem_deteccao_yolo": 0,
        "cantos_degenerados": 0,
        "erro_leitura": 0,
    }

    for img_path in tqdm(images, desc=split, unit="img"):
        txt_path = img_path.with_suffix(".txt")

        if not txt_path.exists():
            stats["sem_txt"] += 1
            continue

        corners, plate = parse_annotation(txt_path)

        if not plate:
            stats["sem_plate"] += 1
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            stats["erro_leitura"] += 1
            continue

        # corners anotados: retifica direto da imagem original
        if corners:
            img_base = img
            used_corners = corners

        # sem corners: YOLO26n -> crop -> YOLO-Pose
        else:
            det_results = yolo_model(img, conf=conf, verbose=False)
            det = det_results[0]

            if det.boxes is None or len(det.boxes) == 0:
                stats["sem_deteccao_yolo"] += 1
                continue

            best_idx = int(det.boxes.conf.argmax())
            bbox = det.boxes.xyxy[best_idx].cpu().numpy()

            crop, x_off, y_off = crop_with_margin(img, bbox, margin)
            kpts = detect_corners(pose_model, crop, conf)

            if kpts is None:
                stats["sem_deteccao_yolo"] += 1
                continue

            img_base = crop
            used_corners = kpts

        if not validate_quadrilateral(used_corners):
            stats["cantos_degenerados"] += 1
            continue

        if sem_retificacao:
            plate_img = crop_bbox_and_pad(img_base, used_corners, TARGET_W, TARGET_H)
            if plate_img is None:
                stats["cantos_degenerados"] += 1
                continue
        else:
            plate_img = rectify_and_resize(img_base, used_corners, TARGET_W, TARGET_H)

        out_name = f"{plate}_{img_path.stem}.png"
        cv2.imwrite(str(split_out / out_name), plate_img)
        save_corners_txt(split_out / f"{img_path.stem}.txt", used_corners)

        stats["ok"] += 1

    return stats


# RELATORIO --------------------------------------------------------------

def save_report(all_stats: list, dir_saida: Path) -> None:
    lines = [
        "=== modulo 1 - relatorio de processamento ===",
        f"gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    total_ok = 0
    total_puladas = 0

    for s in all_stats:
        if "skip_reason" in s:
            lines.append(f"[{s['split']}] ignorado - {s['skip_reason']}")
            lines.append("")
            continue

        puladas = sum(v for k, v in s.items() if k not in ("split", "ok"))
        total_ok += s["ok"]
        total_puladas += puladas

        lines += [
            f"[{s['split']}]",
            f"  processadas         : {s['ok']}",
            f"  puladas             : {puladas}",
            f"    sem .txt          : {s['sem_txt']}",
            f"    sem plate         : {s['sem_plate']}",
            f"    sem deteccao YOLO : {s['sem_deteccao_yolo']}",
            f"    cantos degenerados: {s['cantos_degenerados']}",
            f"    erro de leitura   : {s['erro_leitura']}",
            "",
        ]

    lines.append(f"total: {total_ok} processadas | {total_puladas} puladas")

    report_path = dir_saida / "modulo1_report.txt"
    report_path.write_text("\n".join(lines))
    print(f"relatorio salvo em: {report_path}")


# ENTRADA ----------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="modulo 1 - extracao e retificacao de placas")
    parser.add_argument("--entrada",    required=True,  help="diretorio raiz com train/val/test")
    parser.add_argument("--pesos_yolo", required=True,  help="pesos YOLO26n (deteccao de placa)")
    parser.add_argument("--pesos_pose", required=True,  help="pesos YOLO26n-Pose (deteccao de cantos)")
    parser.add_argument("--saida",      default="dataset_limpas", help="diretorio de saida (default: dataset_limpas)")
    parser.add_argument("--conf",       type=float, default=DEFAULT_CONF,   help=f"confianca minima dos modelos (default: {DEFAULT_CONF})")
    parser.add_argument("--margem",     type=float, default=DEFAULT_MARGIN, help=f"margem de expansao da bbox (default: {DEFAULT_MARGIN})")
    parser.add_argument("--sem_retificacao", action="store_true",
                        help="recorta bbox com padding em vez de retificar perspectiva")
    args = parser.parse_args()

    dir_entrada = Path(args.entrada)
    dir_saida   = Path(args.saida)
    dir_saida.mkdir(parents=True, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    print("carregando YOLO26n...")
    yolo_model = YOLO(args.pesos_yolo)

    print("carregando YOLO26n-Pose...")
    pose_model = YOLO(args.pesos_pose)

    all_stats = []
    for split in SPLITS:
        stats = process_split(
            split, dir_entrada, dir_saida,
            yolo_model, pose_model,
            args.conf, args.margem,
            sem_retificacao=args.sem_retificacao,
        )
        all_stats.append(stats)

    save_report(all_stats, dir_saida)
    print("concluido.")


if __name__ == "__main__":
    main()
