# tune_m3.py — Tuning de hiperparâmetros do M3: busca em amostra, validação no dataset completo.
#
# A busca (Optuna) roda numa amostra de outubro. Os melhores parâmetros são comparados com os
# parâmetros base do M3 (_BASE_PARAMS) em validação cruzada out-of-fold sobre outubro inteiro.
#
# Uso:   python3 -m src.analysis.tune_m3
# Saída: dataset/tune_m3_results.json

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json

import numpy as np
import optuna
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score

from src.build_dataset import load_labeled_profiles
from src.m3_classifier import CATEGORICAL_FEATURES, _BASE_PARAMS, build_brand_vocab, profiles_to_features

DATASET_DIR = Path(__file__).parent.parent.parent / "dataset"

optuna.logging.set_verbosity(optuna.logging.WARNING)

CSV = Path(__file__).parent.parent.parent / "dataset" / "2019-Oct.csv"

# Busca de hiperparâmetros em amostra — mais rápido localmente
SAMPLE_ROWS = 5_000_000   # 7.058 sessões da população de disparo
N_TRIALS = 15
N_SPLITS = 3


def objective(trial, X, y):
    params = {
        "objective": "binary",
        "metric": "auc",
        "verbose": -1,
        "random_state": 42,
        "n_jobs": 1,
        "n_estimators": trial.suggest_int("n_estimators", 100, 500),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 16, 128),
        "min_child_samples": trial.suggest_int("min_child_samples", 10, 100),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
    }
    model = LGBMClassifier(**params)
    cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=42)
    return cross_val_score(model, X, y, cv=cv, scoring="roc_auc", n_jobs=1).mean()


def main():
    # --- busca em amostra ---
    print(f"Carregando amostra ({SAMPLE_ROWS:,} eventos) para busca...")
    t0 = time.time()
    profiles_s, labels_s = load_labeled_profiles(str(CSV), nrows=SAMPLE_ROWS)
    print(f"  {time.time()-t0:.1f}s | sessoes: {len(profiles_s):,}")

    brand_vocab = build_brand_vocab(profiles_s)
    X_s = profiles_to_features(profiles_s, brand_vocab)
    y_s = np.array(labels_s)

    print(f"\nOptuna: {N_TRIALS} trials x {N_SPLITS}-fold na amostra...")
    t1 = time.time()
    study = optuna.create_study(direction="maximize",
                                sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(lambda t: objective(t, X_s, y_s), n_trials=N_TRIALS, show_progress_bar=False)
    print(f"  Tuning: {time.time()-t1:.1f}s")
    print(f"  Melhor AUC (amostra): {study.best_value:.4f}")

    best = {
        **study.best_params,
        "objective": "binary", "metric": "auc",
        "verbose": -1, "random_state": 42, "n_jobs": 1,
    }
    print(f"  Params: {best}")

    # --- validação no dataset completo ---
    # Out-of-fold: brand_vocab recalculado só com o treino de cada fold
    print("\nCarregando outubro completo para validacao final...")
    t2 = time.time()
    profiles_f, labels_f = load_labeled_profiles(str(CSV), nrows=None)
    y_f = np.array(labels_f)
    print(f"  {time.time()-t2:.1f}s | sessoes: {len(profiles_f):,}")

    cv5 = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    base_oof = np.full(len(profiles_f), np.nan)
    tuned_oof = np.full(len(profiles_f), np.nan)

    for train_idx, test_idx in cv5.split(np.zeros(len(y_f)), y_f):
        train_p = [profiles_f[i] for i in train_idx]
        test_p = [profiles_f[i] for i in test_idx]
        vocab = build_brand_vocab(train_p)
        X_tr = profiles_to_features(train_p, vocab)
        X_te = profiles_to_features(test_p, vocab)

        base_model = LGBMClassifier(**{**_BASE_PARAMS, "n_jobs": 1})
        base_model.fit(X_tr, y_f[train_idx], categorical_feature=CATEGORICAL_FEATURES)
        base_oof[test_idx] = base_model.predict_proba(X_te)[:, 1]

        tuned_model = LGBMClassifier(**{**best, "n_jobs": 1})
        tuned_model.fit(X_tr, y_f[train_idx], categorical_feature=CATEGORICAL_FEATURES)
        tuned_oof[test_idx] = tuned_model.predict_proba(X_te)[:, 1]

    assert not np.isnan(base_oof).any() and not np.isnan(tuned_oof).any()
    auc_base = roc_auc_score(y_f, base_oof)
    auc_tuned = roc_auc_score(y_f, tuned_oof)

    print(f"\n--- Resultado (out-of-fold, vocab por fold) ---")
    print(f"  AUC baseline: {auc_base:.4f}")
    print(f"  AUC tuned:    {auc_tuned:.4f}")
    print(f"  Delta:        {auc_tuned - auc_base:+.4f}")

    print(f"\n  Params da amostra (Optuna):\n  {best}")

    out = {
        "population": "disparo (T=120s + atividade)",
        "n_sessions": len(profiles_f),
        "sample_n_sessions": len(profiles_s),
        "method": "5-fold StratifiedKFold out-of-fold (brand_vocab recalculado por fold)",
        "auc_roc_base": round(float(auc_base), 4),
        "auc_roc_tuned": round(float(auc_tuned), 4),
        "delta": round(float(auc_tuned - auc_base), 4),
        "tuned_params": best,
    }
    (DATASET_DIR / "tune_m3_results.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Salvo em tune_m3_results.json")


if __name__ == "__main__":
    main()
