# modulo 3 — construcao do dataset hibrido
# implementa o algoritmo 4 do projeto fisico:
#   1. le imagens reais (limpas) do modulo I, ja divididas em train/val/test
#   2. le imagens sinteticas do modulo II (diretorio unico, sem splits)
#   3. amostra sinteticas na proporcao desejada em relacao as reais
#   4. copia tudo para dataset_hibrido/, renomeando sinteticas com _sint
#   5. gera indices train.txt, val.txt, test.txt (formato: imagem.png,PLACA)
#
# uso:
#   python3 modulo3.py \
#     --dir_limpas ../dataset_limpas \
#     --dir_sinteticas ../dir_sinteticas \
#     --proporcao 0.5 \
#     --saida ../dataset_hibrido
#
# proporcao em relacao as reais:
#   0.5 = 50% (1000 reais + 500 sint)
#   1.0 = 100% (1000 reais + 1000 sint)
#   2.0 = 200% (1000 reais + 2000 sint, se disponiveis)
#   0.0 = sem sinteticas (dataset 100% real)

import argparse
import random
import shutil
from datetime import datetime
from pathlib import Path

_IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


# UTILITARIOS ------------------------------------------------------------

# extrai placa do nome do arquivo: {PLACA}_{resto}.png -> PLACA
def extract_plate(filename: str) -> str:
    stem = Path(filename).stem
    if stem.endswith("_sint"):
        stem = stem[: -len("_sint")]
    return stem.split("_", 1)[0]


# lista imagens em um diretorio, ordenadas por nome
def list_images(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        f for f in directory.iterdir()
        if f.is_file() and f.suffix.lower() in _IMG_EXTS
    )


# adiciona _sint antes da extensao
def add_sint_suffix(filename: str) -> str:
    p = Path(filename)
    return f"{p.stem}_sint{p.suffix}"


# COPIA DE ARQUIVOS ------------------------------------------------------

# copia arquivos para dest_dir, renomeia com _sint se solicitado
def copy_files(files: list[Path], dest_dir: Path, rename_sint: bool = False) -> list[str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    names = []

    for src in files:
        if rename_sint:
            dst_name = add_sint_suffix(src.name)
        else:
            dst_name = src.name
        shutil.copy2(src, dest_dir / dst_name)
        names.append(dst_name)

    return names


# GERACAO DE INDICES -----------------------------------------------------

# gera arquivo de indice no formato imagem.png,PLACA
def generate_index(filenames: list[str], output_path: Path) -> None:
    with open(output_path, "w") as f:
        for name in sorted(filenames):
            plate = extract_plate(name)
            f.write(f"{name},{plate}\n")


# RELATORIO --------------------------------------------------------------

def save_report(output_path: Path, args, stats: dict) -> None:
    with open(output_path, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("  modulo 3 - relatorio do dataset hibrido\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write(f"dir_limpas:      {args.dir_limpas}\n")
        f.write(f"dir_sinteticas:  {args.dir_sinteticas}\n")
        f.write(f"proporcao:       {args.proporcao}\n")
        f.write(f"seed:            {args.seed}\n")
        f.write(f"saida:           {args.saida}\n\n")

        f.write("-" * 40 + "\n")
        f.write("  contagens\n")
        f.write("-" * 40 + "\n")
        f.write(f"train (reais):      {stats['n_train_reais']}\n")
        f.write(f"train (sinteticas): {stats['n_train_sint']}\n")
        f.write(f"train (total):      {stats['n_train_total']}\n")
        f.write(f"val:                {stats['n_val']}\n")
        f.write(f"test:               {stats['n_test']}\n\n")

        f.write(f"sinteticas disponiveis: {stats['n_sint_disponiveis']}\n")
        f.write(f"sinteticas solicitadas: {stats['n_sint_solicitadas']}\n")
        f.write(f"sinteticas usadas:      {stats['n_train_sint']}\n")
        f.write(f"proporcao efetiva:      {stats['proporcao_efetiva']:.4f}\n")

        if stats['aviso']:
            f.write(f"\nAVISO: {stats['aviso']}\n")


# MAIN -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="modulo 3 - construcao do dataset hibrido",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
exemplos:
  # 50%% de sinteticas em relacao as reais
  python3 modulo3.py --dir_limpas ../dataset_limpas --dir_sinteticas ../sinteticas --proporcao 0.5

  # sem sinteticas (baseline real)
  python3 modulo3.py --dir_limpas ../dataset_limpas --dir_sinteticas ../sinteticas --proporcao 0.0

  # proporcao 2:1 (2x mais sinteticas que reais)
  python3 modulo3.py --dir_limpas ../dataset_limpas --dir_sinteticas ../sinteticas --proporcao 2.0
        """,
    )

    parser.add_argument("--dir_limpas", type=str, required=True,
                        help="diretorio com train/, val/, test/ (saida do modulo I)")
    parser.add_argument("--dir_sinteticas", type=str, required=True,
                        help="diretorio com imagens sinteticas (saida do modulo II)")
    parser.add_argument("--proporcao", type=float, required=True,
                        help="fracao de sinteticas em relacao as reais (0.5 = 50%%, 1.0 = 100%%)")
    parser.add_argument("--saida", type=str, default="dataset_hibrido",
                        help="diretorio de saida (default: dataset_hibrido)")
    parser.add_argument("--seed", type=int, default=42,
                        help="seed para reprodutibilidade (default: 42)")

    args = parser.parse_args()

    dir_limpas = Path(args.dir_limpas)
    dir_sinteticas = Path(args.dir_sinteticas)
    dir_saida = Path(args.saida)

    if not dir_limpas.exists():
        print(f"ERRO: dir_limpas nao existe: {dir_limpas}")
        return

    splits_faltando = [s for s in ["train", "val", "test"] if not (dir_limpas / s).exists()]
    if splits_faltando:
        print(f"ERRO: splits faltando em dir_limpas: {splits_faltando}")
        return

    if not dir_sinteticas.exists():
        print(f"ERRO: dir_sinteticas nao existe: {dir_sinteticas}")
        return

    if args.proporcao < 0:
        print("ERRO: proporcao deve ser >= 0.")
        return

    print("listando arquivos...")
    train_reais = list_images(dir_limpas / "train")
    val_reais = list_images(dir_limpas / "val")
    test_reais = list_images(dir_limpas / "test")
    sinteticas = list_images(dir_sinteticas)

    print(f"  train (reais):      {len(train_reais)}")
    print(f"  val:                {len(val_reais)}")
    print(f"  test:               {len(test_reais)}")
    print(f"  sinteticas:         {len(sinteticas)}")

    n_solicitadas = int(len(train_reais) * args.proporcao)
    aviso = ""

    if n_solicitadas > len(sinteticas):
        aviso = (f"solicitadas {n_solicitadas} sinteticas, mas so ha {len(sinteticas)} "
                 f"disponiveis. usando todas.")
        print(f"  AVISO: {aviso}")
        selected_sint = sinteticas
    else:
        random.seed(args.seed)
        selected_sint = random.sample(sinteticas, n_solicitadas)

    print(f"  sinteticas selecionadas: {len(selected_sint)}")

    print("\ncopiando arquivos...")

    print("  train/ (reais)...")
    train_names_reais = copy_files(train_reais, dir_saida / "train")

    print("  train/ (sinteticas)...")
    train_names_sint = copy_files(selected_sint, dir_saida / "train", rename_sint=True)

    print("  val/...")
    val_names = copy_files(val_reais, dir_saida / "val")

    print("  test/...")
    test_names = copy_files(test_reais, dir_saida / "test")

    print("\ngerando indices...")
    train_all_names = train_names_reais + train_names_sint
    generate_index(train_all_names, dir_saida / "train.txt")
    generate_index(val_names, dir_saida / "val.txt")
    generate_index(test_names, dir_saida / "test.txt")

    n_train_sint = len(train_names_sint)
    n_train_reais = len(train_names_reais)
    proporcao_efetiva = n_train_sint / n_train_reais if n_train_reais > 0 else 0.0

    stats = {
        "n_train_reais": n_train_reais,
        "n_train_sint": n_train_sint,
        "n_train_total": n_train_reais + n_train_sint,
        "n_val": len(val_names),
        "n_test": len(test_names),
        "n_sint_disponiveis": len(sinteticas),
        "n_sint_solicitadas": n_solicitadas,
        "proporcao_efetiva": proporcao_efetiva,
        "aviso": aviso,
    }

    report_path = dir_saida / "modulo3_report.txt"
    save_report(report_path, args, stats)

    print(f"\n{'='*40}")
    print(f"  dataset hibrido construido em: {dir_saida}")
    print(f"  train: {stats['n_train_reais']} reais + {stats['n_train_sint']} sint = {stats['n_train_total']}")
    print(f"  val:   {stats['n_val']}")
    print(f"  test:  {stats['n_test']}")
    print(f"  proporcao efetiva: {proporcao_efetiva:.2f}")
    print(f"  relatorio: {report_path}")
    print(f"{'='*40}")


if __name__ == "__main__":
    main()
