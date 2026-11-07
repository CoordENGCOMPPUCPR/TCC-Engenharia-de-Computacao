# m2_significance.py — Significância estatística das regras do Módulo 2.
#
# Responde: a associação entre antecedente e consequente de cada regra é real, ou
# poderia surgir por acaso numa base deste tamanho?
#
# Entrada: dataset/ruleset.pkl (regras) + dataset/2019-Oct.csv (N real de cestas).
# Saída:   dataset/m2_significance_results.json + tabela no stdout.
#
# Uso:   python3 -m src.analysis.m2_significance

import json
import pickle
import sys
from pathlib import Path

import numpy as np
from scipy.stats import chi2

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.m2_association import build_transactions_from_csv

DATASET_DIR = Path(__file__).parent.parent.parent / "dataset"
RULESET_PATH = DATASET_DIR / "ruleset.pkl"
OCT_CSV = DATASET_DIR / "2019-Oct.csv"

N_BOOTSTRAP = 2000
SEED = 42


def contingency_table(antecedent_support: float, consequent_support: float,
                      joint_support: float, n: int) -> np.ndarray:
    """Tabela 2x2 [[ambos, só antecedente], [só consequente, nenhum]] a partir dos
    suportes relativos do ruleset e do número total de cestas."""
    both = round(joint_support * n)
    a = round(antecedent_support * n)
    c = round(consequent_support * n)
    a_only = a - both
    c_only = c - both
    neither = n - both - a_only - c_only
    return np.array([[both, a_only], [c_only, neither]])


def chi_square_yates(table: np.ndarray) -> tuple[float, float]:
    """Qui-quadrado de independência com correção de Yates; devolve (chi2, p-valor)."""
    row_t, col_t = table.sum(axis=1), table.sum(axis=0)
    n = table.sum()
    expected = np.outer(row_t, col_t) / n
    stat = ((np.abs(table - expected) - 0.5).clip(min=0) ** 2 / expected).sum()
    p_value = float(chi2.sf(stat, df=1))
    return float(stat), p_value


def bootstrap_lift_ci(table: np.ndarray, n_boot: int = N_BOOTSTRAP,
                      seed: int = SEED) -> tuple[float, float]:
    """IC 95% do lift por bootstrap sobre as cestas (reamostragem com reposição).

    A tabela 2x2 é expandida numa lista de rótulos de cesta (0=ambos, 1=só
    antecedente, 2=só consequente, 3=nenhum) e reamostrada n_boot vezes; em cada
    reamostragem o lift é recalculado a partir das contagens resultantes.
    """
    both, a_only = int(table[0, 0]), int(table[0, 1])
    c_only, neither = int(table[1, 0]), int(table[1, 1])
    n = both + a_only + c_only + neither

    pool = np.array([0] * both + [1] * a_only + [2] * c_only + [3] * neither)
    rng = np.random.default_rng(seed)

    lifts = np.empty(n_boot)
    for i in range(n_boot):
        sample = rng.choice(pool, size=n, replace=True)
        both_b = int((sample == 0).sum())
        a_b = both_b + int((sample == 1).sum())
        c_b = both_b + int((sample == 2).sum())
        confidence = both_b / a_b if a_b else 0.0
        consequent_support = c_b / n
        lifts[i] = confidence / consequent_support if consequent_support else 0.0

    lo, hi = np.percentile(lifts, [2.5, 97.5])
    return float(lo), float(hi)


def main() -> None:
    if not RULESET_PATH.exists():
        raise FileNotFoundError(f"{RULESET_PATH.name} não encontrado. Execute `python -m src.train` antes.")
    if not OCT_CSV.exists():
        raise FileNotFoundError(f"{OCT_CSV.name} não encontrado em {DATASET_DIR}/.")

    with open(RULESET_PATH, "rb") as f:
        ruleset = pickle.load(f)

    # número real de cestas multi-categoria de outubro, as mesmas usadas na mineração
    n_baskets = len(build_transactions_from_csv(str(OCT_CSV)))
    print(f"Cestas multi-categoria (outubro): {n_baskets:,}\n")

    print(f"{'Antecedente → Consequente':<48} {'Lift':>7} {'χ²':>8} {'p-valor':>12} {'IC 95% do lift':>20}")
    print("-" * 100)

    rows = []
    for _, rule in ruleset.rules.iterrows():
        # as quatro regras têm um único item no antecedente e no consequente
        antecedent = next(iter(rule["antecedents"]))
        consequent = next(iter(rule["consequents"]))
        # tabela 2x2 a partir dos suportes da regra, depois qui-quadrado de Yates e IC do lift
        table = contingency_table(
            rule["antecedent support"], rule["consequent support"], rule["support"], n_baskets
        )
        stat, p_value = chi_square_yates(table)
        ci_lo, ci_hi = bootstrap_lift_ci(table)

        label = f"{antecedent} → {consequent}"
        print(f"{label:<48} {rule['lift']:>7.3f} {stat:>8.2f} {p_value:>12.2e} "
              f"[{ci_lo:.3f} ; {ci_hi:.3f}]")

        rows.append({
            "antecedent": antecedent, "consequent": consequent,
            "n_baskets": int(n_baskets),
            "table": {"both": int(table[0, 0]), "antecedent_only": int(table[0, 1]),
                      "consequent_only": int(table[1, 0]), "neither": int(table[1, 1])},
            "lift": round(float(rule["lift"]), 4),
            "confidence": round(float(rule["confidence"]), 4),
            "support": round(float(rule["support"]), 6),
            "chi2_yates": round(stat, 2),
            "p_value": p_value,
            "lift_ci_95": [round(ci_lo, 3), round(ci_hi, 3)],
        })

    out = {
        "source": "dataset/ruleset.pkl + dataset/2019-Oct.csv",
        "n_baskets_multi_category": int(n_baskets),
        "method": "qui-quadrado 2x2 com correção de Yates; IC do lift por bootstrap "
                 f"({N_BOOTSTRAP} reamostragens, seed={SEED})",
        "rules": rows,
    }
    out_path = DATASET_DIR / "m2_significance_results.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResultados salvos em {out_path.name}")


if __name__ == "__main__":
    main()
