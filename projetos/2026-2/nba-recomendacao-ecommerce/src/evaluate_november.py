# evaluate_november.py — Avaliação out-of-time do modelo (treinado em outubro) sobre novembro.
#
# População avaliada = população oficial de disparo (src/trigger.py), a mesma que o
# StreamSimulator pontua: 1º cart com N≥5, sem purchase em ≤T, ≥1 evento pós-cart em T.
# O M1 já aplica a regra ao construir os perfis; este script AUDITA isso cruzando cada
# perfil com os instantes reais da sessão (assert_official_trigger_population) — se
# treino/avaliação e simulador divergirem, o script falha em vez de reportar.
#
# Métricas: AUC-ROC (global e por tamanho de sessão), taxa de ação e precision/recall
# em θ₁/θ₂ (definidos por percentil no treino — dataset/thresholds.json) e calibração
# das probabilidades (Brier, ECE e curva de confiabilidade).
#
# Uso:   python3 -m src.evaluate_november
# Saída: dataset/evaluate_november_results.json

import json
import pickle
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.build_dataset import (
    assert_official_trigger_population, load_labeled_profiles, session_trigger_times,
)
from src.m3_classifier import profiles_to_features
from src.m4_nba import THETA_1, THETA_2, THRESHOLDS_PATH
from src.trigger import REQUIRE_ACTIVITY, T_WINDOW, ineligibility_reason

DATASET_DIR = Path(__file__).parent.parent / "dataset"
NOV_CSV = DATASET_DIR / "2019-Nov.csv"
MODEL_PATH = DATASET_DIR / "model.lgb"
VOCAB_PATH = DATASET_DIR / "brand_vocab.pkl"

SEGMENTS = [
    ("= 5",   lambda n: n == 5),
    ("6–10",  lambda n: 6 <= n <= 10),
    ("11–20", lambda n: 11 <= n <= 20),
    ("> 20",  lambda n: n > 20),
]


def _at_threshold(y: np.ndarray, p: np.ndarray, theta: float) -> dict:
    flagged = p >= theta
    tp = int((flagged & (y == 1)).sum())
    return {
        "theta": round(float(theta), 4),
        "action_rate": round(float(flagged.mean() * 100), 1),
        "precision": round(tp / flagged.sum() * 100, 1) if flagged.sum() else None,
        "recall": round(tp / (y == 1).sum() * 100, 1) if (y == 1).sum() else None,
    }


def _calibration(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> dict:
    #Brier, ECE (bins por quantil) e curva de confiabilidade — p_abandon é probabilidade?
    # qcut = decis (mesmo nº de sessões por bin), não faixas de valor igual —
    # dá estimativas de 'observed' com erro-padrão comparável entre decis
    bins = pd.qcut(p, n_bins, labels=False, duplicates="drop")
    cal = (pd.DataFrame({"p": p, "y": y, "b": bins}).groupby("b")
           .agg(p_mean=("p", "mean"), observed=("y", "mean"), n=("y", "size")))
    ece = float((np.abs(cal["p_mean"] - cal["observed"]) * cal["n"]).sum() / len(y))
    return {"brier": round(float(brier_score_loss(y, p)), 4), "ece": round(ece, 4),
            "reliability": [{"p_mean": round(float(r.p_mean), 3), "observed": round(float(r.observed), 3), "n": int(r.n)}
                            for r in cal.itertuples()]}


def main():
    print(f"Trigger oficial: T={T_WINDOW:.0f}s, atividade pós-cart={'sim' if REQUIRE_ACTIVITY else 'não'}")
    print(f"θ₁={THETA_1:.4f}  θ₂={THETA_2:.4f}  (calibrados em {THRESHOLDS_PATH.name})\n")

    booster = lgb.Booster(model_str=Path(MODEL_PATH).read_text(encoding="utf-8"))
    with open(VOCAB_PATH, "rb") as f:
        brand_vocab = pickle.load(f)

    print("Carregando novembro (perfis elegíveis via M1)...")
    t0 = time.time()
    # perfis da população de disparo (M1); rótulo 1 = abandono, 0 = compra após a janela
    profiles, labels = load_labeled_profiles(str(NOV_CSV), nrows=None)
    print(f"  {time.time()-t0:.1f}s | {len(profiles):,} sessões elegíveis")

    print("Auditando elegibilidade contra os instantes reais das sessões...")
    t1 = time.time()
    # auditoria independente do M1: falha se algum perfil não for elegível pela definição oficial
    trigger_times = session_trigger_times(str(NOV_CSV))
    assert_official_trigger_population(profiles, trigger_times, T_WINDOW)

    # motivos de exclusão das sessões com cart
    reasons: dict[str, int] = {}
    for sid, row in trigger_times.iterrows():
        r = ineligibility_reason(row["cart_time"], row["purchase_time"], row["first_post_event_time"],
                                 T_WINDOW, REQUIRE_ACTIVITY)
        # "eligible_by_times" inclui quem passa aqui mas ainda cai por N<5 (checado só no M1)
        reasons[r or "eligible_by_times"] = reasons.get(r or "eligible_by_times", 0) + 1
    n_cart = int(len(trigger_times))
    print(f"  {time.time()-t1:.1f}s | OK — todos os {len(profiles):,} perfis são elegíveis pela definição oficial")
    print(f"  sessões com cart: {n_cart:,} | elegíveis por tempo: {reasons.get('eligible_by_times', 0):,} "
          f"(inclui N<5) | excluídas: {json.dumps({k: v for k, v in reasons.items() if k != 'eligible_by_times'})}")

    y = np.array(labels)
    p = booster.predict(profiles_to_features(profiles, brand_vocab))
    sizes = np.array([pr.n_pre_cart_events for pr in profiles])

    print(f"\n=== população oficial de disparo (n={len(y):,}, {len(y)/n_cart:.1%} das sessões com cart) ===")
    print(f"{'Segmento':>8}  {'n':>7}  {'% abandon':>10}  {'AUC-ROC':>8}  {'ação(≥θ₂)':>10}  {'forte(≥θ₁)':>11}")
    print("-" * 66)
    segments = []
    for seg, cond in SEGMENTS:
        mask = np.array([cond(s) for s in sizes])
        if mask.sum() < 10:
            continue
        y_s, p_s = y[mask], p[mask]
        row = {"segment": seg, "n": int(mask.sum()), "pct_abandon": round(float(y_s.mean() * 100), 1),
               "auc_roc": round(float(roc_auc_score(y_s, p_s)), 4),
               "action_rate": round(float((p_s >= THETA_2).mean() * 100), 1),
               "strong_rate": round(float((p_s >= THETA_1).mean() * 100), 1)}
        segments.append(row)
        print(f"{seg:>8}  {row['n']:>7,}  {row['pct_abandon']:>9.1f}%  {row['auc_roc']:>8.4f}  "
              f"{row['action_rate']:>9.1f}%  {row['strong_rate']:>10.1f}%")
    print("-" * 66)
    auc = float(roc_auc_score(y, p))
    at1, at2 = _at_threshold(y, p, THETA_1), _at_threshold(y, p, THETA_2)
    print(f"{'Total':>8}  {len(y):>7,}  {y.mean()*100:>9.1f}%  {auc:>8.4f}  {at2['action_rate']:>9.1f}%  {at1['action_rate']:>10.1f}%")
    print(f"\nθ₂ (ação):   taxa {at2['action_rate']}% | precision {at2['precision']}% | recall {at2['recall']}%")
    print(f"θ₁ (forte):  taxa {at1['action_rate']}% | precision {at1['precision']}% | recall {at1['recall']}%")
    calib = _calibration(y, p)
    print(f"\nCalibração: Brier {calib['brier']:.4f} | ECE {calib['ece']:.4f}")
    print(f"{'decil':>5} {'p médio':>8} {'observado':>10} {'n':>8}")
    for i, r in enumerate(calib["reliability"]):
        print(f"{i:>5} {r['p_mean']:>8.3f} {r['observed']:>10.3f} {r['n']:>8,}")
    print(f"Tempo total: {time.time()-t0:.0f}s")

    out = {
        "source": "2019-Nov.csv",
        "trigger": {"t_window_s": T_WINDOW, "require_activity": REQUIRE_ACTIVITY},
        "thresholds": {"theta_1": THETA_1, "theta_2": THETA_2},
        "n_cart_sessions": n_cart,
        "exclusion_reasons": reasons,
        "n_sessions": int(len(y)), "n_abandon": int(y.sum()),
        "pct_abandon": round(float(y.mean() * 100), 1),
        "auc_roc_total": round(auc, 4),
        "at_theta_1": at1, "at_theta_2": at2,
        "calibration": calib,
        "segments": segments,
    }
    out_path = DATASET_DIR / "evaluate_november_results.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Resultados salvos em {out_path.name}")


if __name__ == "__main__":
    main()
