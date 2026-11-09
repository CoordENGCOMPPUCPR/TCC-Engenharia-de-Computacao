# organizar_rodosol.py — copia todas as imagens da RodoSol-ALPR
# para uma pasta train/ compativel com o modulo 1
# toda a RodoSol entra como dado adicional de treino no pipeline
#
# uso:
#   python3 organizar_rodosol.py --rodosol ../Datasets/tbFcZE-RodoSol-ALPR --saida ../rodosol_organizado

import argparse
import shutil
from pathlib import Path

_IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def main():
    parser = argparse.ArgumentParser(description="organiza RodoSol para o modulo 1")
    parser.add_argument("--rodosol", required=True, help="diretorio raiz da RodoSol-ALPR")
    parser.add_argument("--saida", default="rodosol_organizado", help="diretorio de saida (default: rodosol_organizado)")
    args = parser.parse_args()

    rodosol = Path(args.rodosol)
    images_dir = rodosol / "images"

    if not images_dir.exists():
        print(f"ERRO: pasta images/ nao encontrada em {rodosol}")
        return

    out_train = Path(args.saida) / "train"
    out_train.mkdir(parents=True, exist_ok=True)

    n = 0
    for category_dir in sorted(images_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        for img in sorted(category_dir.iterdir()):
            if not img.is_file() or img.suffix.lower() not in _IMG_EXTS:
                continue
            txt = img.with_suffix(".txt")
            shutil.copy2(img, out_train / img.name)
            n += 1
            if txt.exists():
                shutil.copy2(txt, out_train / (img.stem + ".txt"))

    print(f"concluido. {n} imagens copiadas para {out_train}")


if __name__ == "__main__":
    main()
