# evaluate_segmented.py — Avaliação segmentada por tamanho de sessão sobre outubro (desenvolvimento).
#
# Predições OUT-OF-FOLD (StratifiedKFold): cada sessão é pontuada por um modelo que
# não a viu no treino. brand_vocab é recalculado dentro de cada fold.
#
# Segmentos por n_pre_cart_events (eventos até o 1º cart, inclusive): [5], [6–10], [11–20], [>20].
# O menor segmento é 5 porque o M1 descarta sessões com N < 5.
#
# Métricas por segmento: n, % de abandono, AUC-ROC e "coverage", que aqui é a taxa de ação
# (% com p_abandon >= θ₂). Como θ₂ é o percentil 50 dessas mesmas predições out-of-fold
# (train.py, mesma semente), a taxa total fica em 50% por construção.
#
# Uso:   python3 -m src.evaluate_segmented
# Saída: dataset/evaluate_segmented_results.json

import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.build_dataset import load_labeled_profiles
from src.m3_classifier import cross_val_oof_predict  # também importado por tests/test_evaluate_leakage.py
from src.m4_nba import THETA_2

DATASET_DIR = Path(__file__).parent.parent / "dataset"
CSV = DATASET_DIR / "2019-Oct.csv"

# (rótulo, condição sobre n_pre_cart_events)
SEGMENTS = [
    ("= 5",   lambda n: n == 5),
    ("6–10",  lambda n: 6 <= n <= 10),
    ("11–20", lambda n: 11 <= n <= 20),
    ("> 20",  lambda n: n > 20),
]


def main():
    # Carrega outubro, gera as predições out-of-fold e calcula as métricas por segmento e no total.
    print("Carregando outubro completo...")
    t0 = time.time()
    profiles, labels = load_labeled_profiles(str(CSV), nrows=None)
    y = np.array(labels)
    print(f"  {time.time()-t0:.1f}s | {len(profiles):,} sessões\n")

    print("Predições out-of-fold (5-fold estratificado)...")
    t1 = time.time()
    y_pred = cross_val_oof_predict(profiles, labels)
    print(f"  {time.time()-t1:.1f}s\n")

    session_sizes = np.array([p.n_pre_cart_events for p in profiles])

    print(f"{'Segmento':>8}  {'n':>7}  {'% abandon':>10}  {'AUC-ROC':>8}  {'Cobertura':>10}")
    print("-" * 55)

    results = []
    for name, condition in SEGMENTS:
        mask = np.array([condition(s) for s in session_sizes])
        if mask.sum() < 10:   # segmento pequeno demais para um AUC estável (não ocorre em outubro)
            continue
        y_seg, yp_seg = y[mask], y_pred[mask]
        n = int(mask.sum())
        pct_abandon = float(y_seg.mean() * 100)
        auc = float(roc_auc_score(y_seg, yp_seg))
        coverage = float((yp_seg >= THETA_2).mean() * 100)   # taxa de ação do segmento
        print(f"{name:>8}  {n:>7,}  {pct_abandon:>9.1f}%  {auc:>8.4f}  {coverage:>9.1f}%")
        results.append({"segment": name, "n": n, "pct_abandon": round(pct_abandon, 1),
                        "auc_roc": round(auc, 4), "coverage": round(coverage, 1)})

    print("-" * 55)
    auc_total = float(roc_auc_score(y, y_pred))
    coverage_total = float((y_pred >= THETA_2).mean() * 100)
    print(f"{'Total':>8}  {len(profiles):>7,}  {y.mean()*100:>9.1f}%  {auc_total:>8.4f}  {coverage_total:>9.1f}%")
    print(f"\nθ₂ = {THETA_2}; cobertura = % sessões com p_abandon ≥ θ₂ (out-of-fold)")

    out = {
        "source": "2019-Oct.csv",
        "method": "5-fold StratifiedKFold out-of-fold predictions",
        "n_sessions": len(profiles),
        "pct_abandon": round(float(y.mean() * 100), 1),
        "auc_roc_total": round(auc_total, 4),
        "coverage_total": round(coverage_total, 1),
        "segments": results,
    }
    out_path = DATASET_DIR / "evaluate_segmented_results.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Resultados salvos em {out_path.name}")


if __name__ == "__main__":
    main()
