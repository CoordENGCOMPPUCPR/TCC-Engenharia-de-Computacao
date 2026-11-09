# modulo 2 — degradacao sintetica generativa (cyclegan-turbo)
# recebe crops limpos retificados (saida do modulo 1) e gera versoes
# degradadas via cyclegan-turbo na direcao a2b. saida alimenta modulo 3.
#
# uso:
#   python3 modulo2_cyclegan.py \
#       --dir_limpas ../dataset_limpas/train \
#       --checkpoint /caminho/img2img-turbo/output/treino/checkpoints/model.pkl \
#       --repo_cyclegan /caminho/img2img-turbo \
#       --saida ../dir_sinteticas
#
# importante: somente imagens do split de treino devem ser degradadas.

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

_IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


# LISTAGEM DE IMAGENS ---------------------------------------------------------

def list_images(directory: Path) -> list[Path]:
    return sorted(
        f for f in directory.iterdir()
        if f.is_file() and f.suffix.lower() in _IMG_EXTS
    )


# RELATORIO -------------------------------------------------------------------

def save_report(output_path: Path, args, stats: dict) -> None:
    with open(output_path, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("  Modulo II — Relatorio de Degradacao Sintetica\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write(f"dir_limpas:      {args.dir_limpas}\n")
        f.write(f"checkpoint:      {args.checkpoint}\n")
        f.write(f"repo_cyclegan:   {args.repo_cyclegan}\n")
        f.write(f"prompt:          {args.prompt}\n")
        f.write(f"gpu:             {args.gpu}\n")
        f.write(f"saida:           {args.saida}\n\n")

        f.write("-" * 40 + "\n")
        f.write("  Contagens\n")
        f.write("-" * 40 + "\n")
        f.write(f"Imagens encontradas:  {stats['n_encontradas']}\n")
        f.write(f"Imagens geradas:      {stats['n_geradas']}\n")
        f.write(f"Ja existiam (pulo):   {stats['n_existentes']}\n")
        f.write(f"Erros:                {stats['n_erros']}\n")
        f.write(f"Tempo total:          {stats['tempo']:.1f}s\n")


# MAIN ------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="modulo II — degradacao sintetica com cyclegan-turbo")

    parser.add_argument("--dir_limpas", type=str, required=True,
                        help="Diretorio com imagens limpas 128x64 (somente treino).")
    parser.add_argument("--checkpoint", type=str, required=True,
                        help="Caminho do checkpoint .pkl do CycleGAN-Turbo.")
    parser.add_argument("--repo_cyclegan", type=str, required=True,
                        help="Caminho do repositorio img2img-turbo (contém src/).")
    parser.add_argument("--saida", type=str, default="dir_sinteticas",
                        help="Diretorio de saida (default: dir_sinteticas).")
    parser.add_argument("--prompt", type=str,
                        default="blurry low resolution license plate",
                        help="Prompt do dominio-alvo (default: 'blurry low resolution license plate').")
    parser.add_argument("--gpu", type=str, default="0",
                        help="ID da GPU (default: 0).")

    args = parser.parse_args()

    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu

    dir_limpas = Path(args.dir_limpas)
    dir_saida = Path(args.saida)
    checkpoint = Path(args.checkpoint)
    repo = Path(args.repo_cyclegan)

    if not dir_limpas.exists():
        print(f"ERRO: dir_limpas nao existe: {dir_limpas}")
        return

    if not checkpoint.exists():
        print(f"ERRO: checkpoint nao existe: {checkpoint}")
        return

    repo_src = repo / "src"
    if not repo_src.exists():
        print(f"ERRO: pasta src/ nao encontrada em {repo}")
        return

    sys.path.insert(0, str(repo_src))
    try:
        from cyclegan_turbo import CycleGAN_Turbo
    except ImportError as e:
        print(f"ERRO: nao conseguiu importar CycleGAN_Turbo de {repo_src}: {e}")
        return

    import torch
    from torchvision import transforms
    from PIL import Image

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    imagens = list_images(dir_limpas)
    print(f"Imagens encontradas: {len(imagens)}")

    if not imagens:
        print("Nenhuma imagem encontrada. Encerrando.")
        return

    dir_saida.mkdir(parents=True, exist_ok=True)

    print(f"Carregando modelo de {checkpoint}...")
    model = CycleGAN_Turbo(pretrained_name=None, pretrained_path=str(checkpoint))
    model.eval()

    normaliza = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize([0.5], [0.5]),
    ])

    print(f"\nGerando sinteticas em {dir_saida}/...")
    start_time = time.time()
    n_geradas = 0
    n_existentes = 0
    n_erros = 0

    with torch.no_grad():
        for i, img_path in enumerate(imagens, 1):
            dst_path = dir_saida / img_path.name

            if dst_path.exists():
                n_existentes += 1
                continue

            try:
                img_pil = Image.open(img_path).convert("RGB")
                x = normaliza(img_pil).unsqueeze(0)
                if device == "cuda":
                    x = x.cuda()

                out = model(x, direction="a2b", caption=args.prompt)
                out = (out[0].cpu() * 0.5 + 0.5).clamp(0, 1)
                transforms.ToPILImage()(out).save(dst_path)
                n_geradas += 1

            except Exception as e:
                print(f"  ERRO em {img_path.name}: {e}")
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

    report_path = dir_saida / "modulo2_report.txt"
    save_report(report_path, args, stats)

    print(f"\n{'='*40}")
    print(f"  Degradacao sintetica concluida")
    print(f"  Geradas:     {n_geradas}")
    print(f"  Ja existiam: {n_existentes}")
    print(f"  Erros:       {n_erros}")
    print(f"  Tempo:       {elapsed:.1f}s")
    print(f"  Saida:       {dir_saida}")
    print(f"  Relatorio:   {report_path}")
    print(f"{'='*40}")


if __name__ == "__main__":
    main()
