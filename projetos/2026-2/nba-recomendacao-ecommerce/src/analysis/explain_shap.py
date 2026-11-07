# explain_shap.py — Explicabilidade global do M3 (auditoria do modelo).
#
# Não faz parte do caminho de decisão: M4 decide por p_abandon (θ₁/θ₂) e M2 (regras).
# O SHAP local por sessão roda em produção via predict_abandon_score, não aqui.
# Este script existe para responder "o que o modelo aprendeu, agregado sobre a
# população?" — e para detectar features espúrias ou viés.
#
# Saídas (dataset/):
#   shap_global.json / shap_global_nov.json   |SHAP| médio por feature (outubro / novembro)
#   shap_summary.png / shap_summary_nov.png   beeswarm global de cada mês
#
# Uso: python3 -m src.analysis.explain_shap [oct|nov]   (padrão: oct)

import json
import pickle
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import shap

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.build_dataset import load_labeled_profiles
from src.m3_classifier import FEATURE_NAMES, profiles_to_features

DATASET_DIR = Path(__file__).parent.parent.parent / "dataset"
IMG_DIR = DATASET_DIR
# mês -> (CSV, nome na saída, sufixo dos arquivos); outubro mantém os nomes atuais
MONTHS = {
    "oct": ("2019-Oct.csv", "outubro", ""),
    "nov": ("2019-Nov.csv", "novembro", "_nov"),
}


def _shap_matrix(explainer, X) -> np.ndarray:
    vals = explainer.shap_values(X)
    if isinstance(vals, list):
        return np.asarray(vals[1])
    if getattr(vals, "ndim", 0) == 3:
        return np.asarray(vals[:, :, 1])
    return np.asarray(vals)


def main(month: str = "oct") -> None:
    csv_name, month_label, suffix = MONTHS[month]
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    booster = lgb.Booster(model_str=(DATASET_DIR / "model.lgb").read_text(encoding="utf-8"))
    with open(DATASET_DIR / "brand_vocab.pkl", "rb") as f:
        brand_vocab = pickle.load(f)

    print(f"Carregando população de disparo de {month_label}...")
    t0 = time.time()
    profiles, labels = load_labeled_profiles(str(DATASET_DIR / csv_name), nrows=None)
    X = profiles_to_features(profiles, brand_vocab)
    y = np.array(labels)
    print(f"  {time.time()-t0:.0f}s | {len(profiles):,} sessões")

    print("SHAP TreeExplainer (batch)...")
    t1 = time.time()
    explainer = shap.TreeExplainer(booster)
    S = _shap_matrix(explainer, X)
    print(f"  {time.time()-t1:.0f}s")

    # --- global ---
    mean_abs = np.abs(S).mean(axis=0)
    order = np.argsort(-mean_abs)
    glob = [{"rank": i + 1, "feature": FEATURE_NAMES[j], "mean_abs_shap": round(float(mean_abs[j]), 4)}
            for i, j in enumerate(order)]
    (DATASET_DIR / f"shap_global{suffix}.json").write_text(json.dumps(
        {"population": f"disparo (T=120s + atividade), {month_label}", "n": int(len(y)), "features": glob}, indent=2), encoding="utf-8")
    print("\nImportância global (|SHAP| médio):")
    for g in glob[:8]:
        print(f"  {g['rank']:>2}. {g['feature']:<26} {g['mean_abs_shap']:.4f}")

    from shap.plots._labels import labels as _shap_labels
    _shap_labels["FEATURE_VALUE_LOW"] = "Baixo"
    _shap_labels["FEATURE_VALUE_HIGH"] = "Alto"

    plt.figure()
    shap.summary_plot(S, X, feature_names=FEATURE_NAMES, show=False, max_display=16,
                       color_bar_label="Valor da feature")
    ax = plt.gca()
    ax.set_xlabel("Valor SHAP (impacto na saída do modelo)")
    plt.tight_layout()
    plt.savefig(IMG_DIR / f"shap_summary{suffix}.png", dpi=160, bbox_inches="tight")
    plt.close()

    print(f"\nSalvos: shap_global{suffix}.json, {IMG_DIR}/shap_summary{suffix}.png")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "oct")
