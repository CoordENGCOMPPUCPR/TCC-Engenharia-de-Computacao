# modulo 2 — degradacao sintetica parametrica (opencv + albumentations)
# recebe crops limpos retificados (saida do modulo 1) e gera versoes
# sinteticamente degradadas via blur + downscale + compressao jpeg.
#
# uso:
#   python modulo2.py --dir_limpas ../dataset_limpas/train --saida ../dir_sinteticas
#
# entrada esperada:
#   dir_limpas/
#     ABC1234_img_000001.png   <- crop retificado 128x64
#
# saida:
#   dir_sinteticas/
#     ABC1234_img_000001.png   <- crop degradado 128x64
#     modulo2_report.txt
#
# importante: somente imagens do split de treino devem ser degradadas.
# imagens de val/test nao devem passar por este modulo (data leakage).

import argparse
import random
import time
from datetime import datetime
from pathlib import Path

import albumentations as A
import cv2
import numpy as np

IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}

# parametros fixos de degradacao (calibrados no notebook RodoSol)
BLUR_SIGMA = (0.0, 0.4)
ALTURA_LR = (14, 16)
JPEG_Q = (85, 95)


# DEGRADACAO ----------------------------------------------------------------

# aplica blur + downscale + jpeg + upscale (nearest) de volta ao tamanho original
def degradar(image: np.ndarray) -> np.ndarray:
    h_orig, w_orig = image.shape[:2]
    x = image.copy()

    # blur
    sigma = random.uniform(*BLUR_SIGMA)
    if sigma > 0.05:
        sigma_y = sigma * random.uniform(0.8, 1.2)
        x = cv2.GaussianBlur(x, (0, 0), sigmaX=sigma, sigmaY=sigma_y)

    # downscale
    h_lr = random.randint(*ALTURA_LR)
    w_lr = max(4, round(w_orig * h_lr / h_orig))
    x = cv2.resize(x, (w_lr, h_lr), interpolation=cv2.INTER_CUBIC)

    # compressao jpeg
    q = random.randint(*JPEG_Q)
    x = A.ImageCompression(
        compression_type="jpeg", quality_range=(q, q), p=1.0
    )(image=x)["image"]

    # upscale de volta ao tamanho original
    x = cv2.resize(x, (w_orig, h_orig), interpolation=cv2.INTER_NEAREST)

    return x


# LISTAGEM ------------------------------------------------------------------

def list_images(directory: Path) -> list[Path]:
    return sorted(
        f for f in directory.iterdir()
        if f.is_file() and f.suffix.lower() in IMG_EXTS
    )


# RELATORIO -----------------------------------------------------------------

def save_report(args, stats: dict, dir_saida: Path) -> None:
    lines = [
        "=== modulo 2 - relatorio de degradacao parametrica ===",
        f"gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"dir_limpas: {args.dir_limpas}",
        f"saida:      {args.saida}",
        "",
        "parametros (fixos):",
        f"  blur_sigma: {list(BLUR_SIGMA)}",
        f"  altura_lr:  {list(ALTURA_LR)} px",
        f"  jpeg_q:     {list(JPEG_Q)}",
        "",
        "contagens:",
        f"  encontradas:  {stats['n_encontradas']}",
        f"  geradas:      {stats['n_geradas']}",
        f"  ja existiam:  {stats['n_existentes']}",
        f"  erros:        {stats['n_erros']}",
        f"  tempo:        {stats['tempo']:.1f}s",
    ]

    report_path = dir_saida / "modulo2_report.txt"
    report_path.write_text("\n".join(lines))
    print(f"relatorio salvo em: {report_path}")


# ENTRADA -------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="modulo 2 - degradacao sintetica parametrica")
    parser.add_argument("--dir_limpas", required=True, help="diretorio com imagens limpas 128x64 (somente treino)")
    parser.add_argument("--saida", default="dir_sinteticas", help="diretorio de saida (default: dir_sinteticas)")
    args = parser.parse_args()

    dir_limpas = Path(args.dir_limpas)
    dir_saida = Path(args.saida)

    if not dir_limpas.exists():
        print(f"erro: dir_limpas nao existe: {dir_limpas}")
        return

    imagens = list_images(dir_limpas)
    print(f"imagens encontradas: {len(imagens)}")

    if not imagens:
        print("nenhuma imagem encontrada. encerrando.")
        return

    dir_saida.mkdir(parents=True, exist_ok=True)

    print(f"gerando sinteticas em {dir_saida}/...")
    start_time = time.time()
    n_geradas = 0
    n_existentes = 0
    n_erros = 0

    for i, img_path in enumerate(imagens, 1):
        dst_path = dir_saida / img_path.name

        if dst_path.exists():
            n_existentes += 1
            continue

        image = cv2.imread(str(img_path))
        if image is None:
            print(f"  erro: nao conseguiu ler {img_path.name}")
            n_erros += 1
            continue

        try:
            degradada = degradar(image)
            cv2.imwrite(str(dst_path), degradada)
            n_geradas += 1
        except Exception as e:
            print(f"  erro em {img_path.name}: {e}")
            n_erros += 1

        if i % 500 == 0 or i == len(imagens):
            print(f"  {i}/{len(imagens)}...", flush=True)

    elapsed = time.time() - start_time

    stats = {
        "n_encontradas": len(imagens),
        "n_geradas": n_geradas,
        "n_existentes": n_existentes,
        "n_erros": n_erros,
        "tempo": elapsed,
    }

    save_report(args, stats, dir_saida)

    print(f"concluido. {n_geradas} geradas | {n_existentes} ja existiam | {n_erros} erros | {elapsed:.1f}s")


if __name__ == "__main__":
    main()
