# product_lookup.py — Lookup de produto concreto: category_id → product_id mais comprado.

import sys
from pathlib import Path
from typing import Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

LOOKUP_PATH = Path(__file__).parent.parent / "dataset" / "product_lookup.parquet"


def build_lookup(csv_path: str, output_path: Optional[str] = None) -> pd.DataFrame:
    # Constrói tabela category_id → top produto por volume de purchase.
    # Deve ser chamado uma vez sobre o CSV de treino (outubro).
    # Salva em product_lookup.parquet para uso em inferência.
    cols = ["event_type", "product_id", "category_id"]
    df = pd.read_csv(csv_path, usecols=cols, dtype={"category_id": str})

    purchases = df[df["event_type"] == "purchase"].copy()

    lookup = (
        purchases.groupby(["category_id", "product_id"])
        .size()  # conta compras por par (categoria, produto)
        .reset_index(name="purchase_count")
        .sort_values("purchase_count", ascending=False)  # mais comprado primeiro
        # keep="first" após a ordenação acima = pega só o top-1 produto por
        # categoria, sem precisar de groupby().apply() (mais lento)
        .drop_duplicates(subset="category_id", keep="first")
        .set_index("category_id")[["product_id", "purchase_count"]]
    )

    out = output_path or str(LOOKUP_PATH)
    lookup.to_parquet(out)
    return lookup


def load_lookup(path: Optional[str] = None) -> pd.DataFrame:
    #Carrega product_lookup.parquet do disco e valida que o índice é str.
    p = path or str(LOOKUP_PATH)
    lookup = pd.read_parquet(p)
    if not pd.api.types.is_string_dtype(lookup.index):
        raise TypeError(
            f"product_lookup índice com dtype {lookup.index.dtype} (esperado str). "
            "Regenere product_lookup.parquet com src.train."
        )
    return lookup


def resolve_product(category_id: str, lookup: pd.DataFrame) -> Optional[int]:
    # Retorna o product_id mais comprado na categoria, ou None se não encontrado.
    if category_id in lookup.index:
        return int(lookup.loc[category_id, "product_id"])
    return None


if __name__ == "__main__":
    import time

    csv = Path(__file__).parent.parent / "dataset" / "2019-Oct.csv"
    print(f"Construindo product_lookup a partir de {csv.name}...")
    t0 = time.time()
    lookup = build_lookup(str(csv))
    print(f"  {time.time()-t0:.1f}s | {len(lookup):,} categorias mapeadas")
    print(f"  Salvo em {LOOKUP_PATH}")
    print(lookup.head(5))
