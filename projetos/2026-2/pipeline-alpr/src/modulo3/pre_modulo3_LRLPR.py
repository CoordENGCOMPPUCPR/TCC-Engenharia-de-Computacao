# pre-modulo 3 (LRLPR) — preparacao do LRLPR-26 para o pipeline
# le o split oficial (split-train-val.json) e organiza as imagens
# no formato que o modulo IV espera para treino/validacao
#
# imagens copiadas puras (sem retificacao de perspectiva)
#
# uso:
#   python3 pre_modulo3_LRLPR.py \
#     --lrlpr ../Datasets/LRLPR-26-5opEvJTW \
#     --saida ../lrlpr_preparado
#
# entrada:
#   LRLPR-26-5opEvJTW/
#     train/
#       Scenario-A/Brazilian/track_XXXXX/  (5 lr + 5 hr + annotations.json)
#       Scenario-A/Mercosur/track_XXXXX/
#       Scenario-B/Brazilian/track_XXXXX/
#       Scenario-B/Mercosur/track_XXXXX/
#     split-train-val.json
#
# saida:
#   lrlpr_preparado/
#     train/
#       AVL5215_00001_lr001.png
#       AVL5215_00001_hr001.png
#     val/
#     train.txt   (imagem.png,PLACA)
#     val.txt
#     pre_modulo3_report.txt

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

# import cv2
# import numpy as np

_IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


# RETIFICACAO (desativada — imagens puras por enquanto) ------------------

# def rectify_plate(img_path, corners, target_w=128, target_h=64):
#     img = cv2.imread(str(img_path))
#     if img is None:
#         return None
#     src = np.array([
#         corners["top-left"],
#         corners["top-right"],
#         corners["bottom-right"],
#         corners["bottom-left"],
#     ], dtype=np.float32)
#     dst = np.array([
#         [0, 0], [target_w - 1, 0],
#         [target_w - 1, target_h - 1], [0, target_h - 1],
#     ], dtype=np.float32)
#     M = cv2.getPerspectiveTransform(src, dst)
#     return cv2.warpPerspective(img, M, (target_w, target_h), flags=cv2.INTER_CUBIC)


# PROCESSAMENTO DE TRACKS -----------------------------------------------

# copia imagens dos tracks para dest_dir, retorna lista de nomes gerados
def process_tracks(track_paths: list[str], lrlpr_train_dir: Path,
                   dest_dir: Path) -> list[str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    names = []
    skipped = 0

    for rel_path in track_paths:
        track_dir = lrlpr_train_dir / rel_path.rstrip("/")

        if not track_dir.exists():
            skipped += 1
            continue

        ann_file = track_dir / "annotations.json"
        if not ann_file.exists():
            skipped += 1
            continue

        with ann_file.open() as f:
            ann = json.load(f)

        plate_text = ann.get("plate_text", "")
        if not plate_text:
            skipped += 1
            continue

        # corners = ann.get("corners", {})

        track_id = track_dir.name.replace("track_", "")

        for img_file in sorted(track_dir.iterdir()):
            if not img_file.is_file() or img_file.suffix.lower() not in _IMG_EXTS:
                continue

            # lr-001.png -> lr001, hr-003.jpg -> hr003
            img_tag = img_file.stem.replace("-", "")
            dst_name = f"{plate_text}_{track_id}_{img_tag}{img_file.suffix}"

            # copia pura (sem retificacao)
            shutil.copy2(img_file, dest_dir / dst_name)

            # alternativa com retificacao (descomentar quando necessario):
            # img_key = img_file.name
            # if img_key in corners:
            #     rectified = rectify_plate(img_file, corners[img_key])
            #     if rectified is not None:
            #         cv2.imwrite(str(dest_dir / dst_name), rectified)
            #         names.append(dst_name)
            #     continue

            names.append(dst_name)

    if skipped:
        print(f"  AVISO: {skipped} tracks pulados (inexistentes ou sem anotacao)")

    return names


# INDICE -----------------------------------------------------------------

# gera arquivo de indice no formato imagem.png,PLACA
def generate_index(filenames: list[str], output_path: Path) -> None:
    with open(output_path, "w") as f:
        for name in sorted(filenames):
            # PLACA_trackID_lr001.png -> PLACA
            plate = Path(name).stem.split("_", 1)[0]
            f.write(f"{name},{plate}\n")


# MAIN -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="pre-modulo 3 - prepara LRLPR-26 para o pipeline",
    )
    parser.add_argument("--lrlpr", type=str, required=True,
                        help="diretorio raiz do LRLPR-26 (contem train/, test/, split-train-val.json)")
    parser.add_argument("--saida", type=str, default="lrlpr_preparado",
                        help="diretorio de saida (default: lrlpr_preparado)")

    args = parser.parse_args()

    lrlpr_dir = Path(args.lrlpr)
    dir_saida = Path(args.saida)

    split_file = lrlpr_dir / "split-train-val.json"
    if not split_file.exists():
        print(f"ERRO: split-train-val.json nao encontrado em {lrlpr_dir}")
        return

    train_dir = lrlpr_dir / "train"
    if not train_dir.exists():
        print(f"ERRO: pasta train/ nao encontrada em {lrlpr_dir}")
        return

    print("lendo split-train-val.json...")
    with split_file.open() as f:
        split = json.load(f)

    all_train_tracks = []
    all_val_tracks = []

    for scenario in sorted(split.keys()):
        scenario_data = split[scenario]
        train_tracks = scenario_data.get("train", [])
        val_tracks = scenario_data.get("val", [])
        all_train_tracks.extend(train_tracks)
        all_val_tracks.extend(val_tracks)
        print(f"  {scenario}: {len(train_tracks)} train, {len(val_tracks)} val")

    print(f"  total: {len(all_train_tracks)} train, {len(all_val_tracks)} val")

    print("\ncopiando imagens de treino...")
    train_names = process_tracks(all_train_tracks, train_dir, dir_saida / "train")
    print(f"  {len(train_names)} imagens copiadas para train/")

    print("\ncopiando imagens de validacao...")
    val_names = process_tracks(all_val_tracks, train_dir, dir_saida / "val")
    print(f"  {len(val_names)} imagens copiadas para val/")

    print("\ngerando indices...")
    generate_index(train_names, dir_saida / "train.txt")
    generate_index(val_names, dir_saida / "val.txt")

    report_path = dir_saida / "pre_modulo3_report.txt"
    with open(report_path, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("  pre-modulo 3 - relatorio de preparacao do LRLPR-26\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"LRLPR-26:  {args.lrlpr}\n")
        f.write(f"saida:     {args.saida}\n")
        f.write(f"split:     {split_file}\n\n")
        f.write(f"train:     {len(train_names)} imagens\n")
        f.write(f"val:       {len(val_names)} imagens\n")
        f.write(f"retificacao: desativada (imagens puras)\n")

    print(f"\n{'='*40}")
    print(f"  LRLPR-26 preparado em: {dir_saida}")
    print(f"  train: {len(train_names)} imagens")
    print(f"  val:   {len(val_names)} imagens")
    print(f"  relatorio: {report_path}")
    print(f"{'='*40}")


if __name__ == "__main__":
    main()
