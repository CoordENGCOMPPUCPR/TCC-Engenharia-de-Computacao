# train.py — Treino offline: constrói todos os artefatos a partir de outubro.

# Uso: python3 -m src.train

import gc
import json
import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lightgbm.basic import LightGBMError
from sklearn.metrics import roc_auc_score

from src.build_dataset import load_labeled_profiles
from src.m2_association import build_transactions_from_csv, mine_rules
from src.m3_classifier import cross_val_oof_predict, train as train_m3
from src.m4_nba import calibrate_thresholds
from src.product_lookup import build_lookup
from src.trigger import REQUIRE_ACTIVITY, T_WINDOW

DATASET_DIR = Path(__file__).parent.parent / "dataset"


def main():
    print("=== Treino offline — outubro 2019 ===")
    print(f"    trigger: T={T_WINDOW:.0f}s, atividade pós-cart={'sim' if REQUIRE_ACTIVITY else 'não'} (src/trigger.py)\n")

    oct_csv           = DATASET_DIR / "2019-Oct.csv"
    lookup_path       = DATASET_DIR / "product_lookup.parquet"
    profiles_ckpt     = DATASET_DIR / "_profiles_checkpoint.pkl"   # temporário
    ruleset_path      = DATASET_DIR / "ruleset.pkl"
    model_path        = DATASET_DIR / "model.lgb"
    vocab_path        = DATASET_DIR / "brand_vocab.pkl"
    thresholds_path   = DATASET_DIR / "thresholds.json"

    if not oct_csv.exists():
        print(f"ERRO: CSV não encontrado em {oct_csv}")
        print("Ajuste DATASET_DIR em src/train.py.")
        sys.exit(1)

    t0 = time.time()

    # --- 1/5  product_lookup ---
    # cada passo checa se seu artefato já existe antes de recomputar — checkpoint
    # manual simples, pra sobreviver a uma interrupção sem recomeçar do zero
    if lookup_path.exists():
        print(f"1/5  product_lookup já existe — pulando.")
    else:
        print("1/5  Construindo product_lookup...")
        t1 = time.time()
        lookup = build_lookup(str(oct_csv), output_path=str(lookup_path))
        print(f"     {time.time()-t1:.1f}s | {len(lookup):,} categorias → {lookup_path.name}")
        gc.collect()
    print()

    # --- 2/5  SessionProfiles + labels (M1) ---
    if profiles_ckpt.exists():
        print("2/5  Checkpoint de perfis encontrado — carregando...")
        t1 = time.time()
        with open(profiles_ckpt, "rb") as f:
            profiles, labels = pickle.load(f)
        print(f"     {time.time()-t1:.1f}s | {len(profiles):,} sessões carregadas do checkpoint")
    else:
        print("2/5  Carregando perfis (M1) — dois passes no CSV...")
        t1 = time.time()
        profiles, labels = load_labeled_profiles(str(oct_csv), nrows=None)
        n_abandon = sum(labels)
        print(f"     {time.time()-t1:.1f}s | {len(profiles):,} sessões | abandono {n_abandon/len(labels)*100:.1f}%")
        print("     Salvando checkpoint de perfis...")
        with open(profiles_ckpt, "wb") as f:
            pickle.dump((profiles, labels), f)
        print(f"     → {profiles_ckpt.name} ({profiles_ckpt.stat().st_size/1024/1024:.0f} MB)")
    print()

    # --- 3/5  FP-Growth (M2) ---
    if ruleset_path.exists():
        print(f"3/5  ruleset.pkl já existe — pulando.")
    else:
        print("3/5  Minerando regras de associação (M2)...")
        t2 = time.time()
        transactions = build_transactions_from_csv(str(oct_csv))
        print(f"     {len(transactions):,} sessões com 2+ categorias no carrinho")
        ruleset = mine_rules(profiles, transactions=transactions)
        with open(ruleset_path, "wb") as f:
            pickle.dump(ruleset, f)
        print(f"     {time.time()-t2:.1f}s | {len(ruleset.rules)} regras → {ruleset_path.name}")
        del transactions
        gc.collect()
    print()

    # --- 4/5  LightGBM + SHAP (M3) ---
    if model_path.exists() and vocab_path.exists():
        print(f"4/5  model.lgb e brand_vocab.pkl já existem — pulando.")
    else:
        print("4/5  Treinando LightGBM (M3)...")
        t3 = time.time()
        model, _explainer, brand_vocab = train_m3(profiles, labels)
        try:
            model.booster_.save_model(str(model_path))
        except LightGBMError:
            # no Windows, o LightGBM não grava em caminhos com acento: grava pelo Python
            model_path.write_text(model.booster_.model_to_string(), encoding="utf-8")
        with open(vocab_path, "wb") as f:
            pickle.dump(brand_vocab, f)
        print(f"     {time.time()-t3:.1f}s | modelo salvo → {model_path.name}, {vocab_path.name}")
    print()

    # --- 5/5  Calibração de θ₁/θ₂ por percentil da distribuição OOF (M4) ---
    if thresholds_path.exists():
        print(f"5/5  thresholds.json já existe — pulando.")
    else:
        print("5/5  Calibrando θ₁/θ₂ (predições out-of-fold, 5-fold)...")
        t4 = time.time()
        p_oof = cross_val_oof_predict(profiles, labels)
        th = calibrate_thresholds(p_oof)
        th["auc_roc_oof"] = round(float(roc_auc_score(labels, p_oof)), 4)
        th["t_window_s"] = T_WINDOW
        th["require_activity"] = REQUIRE_ACTIVITY
        thresholds_path.write_text(json.dumps(th, indent=2))
        print(f"     {time.time()-t4:.1f}s | θ₁={th['theta_1']:.4f} (P{100*(1-th['strong_top_frac']):.0f}) "
              f"θ₂={th['theta_2']:.4f} (P{100*(1-th['action_top_frac']):.0f}) | AUC OOF={th['auc_roc_oof']} → {thresholds_path.name}")
        del profiles, labels
        gc.collect()

        # Remove checkpoint temporário — não é mais necessário
        if profiles_ckpt.exists():
            profiles_ckpt.unlink()
            print(f"     Checkpoint temporário removido.")
    print()

    # --- Resumo ---
    total = time.time() - t0
    print(f"=== Artefatos prontos ({total/60:.1f} min) ===")
    for path in [lookup_path, ruleset_path, model_path, vocab_path, thresholds_path]:
        if path.exists():
            size_mb = path.stat().st_size / 1024 / 1024
            print(f"  {path.name:<35} {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
