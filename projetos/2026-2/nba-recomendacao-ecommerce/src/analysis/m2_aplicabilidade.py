# m2_aplicabilidade.py — Aplicabilidade e alcance das regras do Módulo 2 nas populações de
# disparo de outubro e novembro, com o pipeline completo (M3 → M4 → regras → tabela de produtos).
#
# Para cada mês: AUC-ROC, taxas de ação em θ₁ e θ₂, precisão em θ₂, fração das sessões com
# regra aplicável (antecedente contido em cart_items) e fração que sai com produto concreto.
#
# Uso:   python3 -m src.analysis.m2_aplicabilidade
# Saída: dataset/m2_aplicabilidade_results.json

import hashlib
import json
import pickle
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.build_dataset import load_labeled_profiles
from src.m2_association import filter_rules_for_session
from src.m3_classifier import profiles_to_features
from src.m4_nba import load_thresholds
from src.product_lookup import load_lookup, resolve_product

DATASET_DIR = Path(__file__).parent.parent.parent / "dataset"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def measure(csv_path: Path, booster, vocab, ruleset, lookup, theta_1: float, theta_2: float) -> dict:
    t0 = time.time()
    profiles, labels = load_labeled_profiles(str(csv_path), nrows=None)
    y = np.array(labels)
    X = profiles_to_features(profiles, vocab)
    p = booster.predict(X)

    n = len(profiles)
    auc = float(roc_auc_score(y, p))

    action_t2 = p >= theta_2
    action_t1 = p >= theta_1
    tp_t2 = int((action_t2 & (y == 1)).sum())
    precision_t2 = round(tp_t2 / action_t2.sum() * 100, 4) if action_t2.sum() else None

    n_candidates_list = []
    n_cart_items_list = []
    recommended_products = []
    nba_scores = []
    n_with_rule = 0
    n_reach = 0

    for i, prof in enumerate(profiles):
        applicable = filter_rules_for_session(ruleset, prof.cart_items)
        n_cand = len(applicable)
        n_candidates_list.append(n_cand)
        n_cart_items_list.append(len(prof.cart_items))
        if n_cand > 0:
            n_with_rule += 1

        # só decide produto se a sessão receberia alguma ação (>= theta_2) e há regra aplicável
        if action_t2[i] and n_cand > 0:
            # mesma escolha de regra de m4_nba.decide — se uma mudar, a outra precisa acompanhar
            applicable = applicable.copy()
            applicable["nba_score"] = applicable["lift"] * applicable["confidence"]
            best = applicable.sort_values("nba_score", ascending=False).iloc[0]
            consequent = frozenset(best["consequents"])
            nba_scores.append(float(best["nba_score"]))
            for cat_id in consequent:
                pid = resolve_product(cat_id, lookup)
                if pid is not None:
                    recommended_products.append(pid)
                    n_reach += 1
                    break

    cand_dist = {str(k): int((np.array(n_candidates_list) == k).sum()) for k in range(5)}
    cand_dist["4+"] = int((np.array(n_candidates_list) >= 4).sum())
    cart_items_dist = {str(k): int((np.array(n_cart_items_list) == k).sum()) for k in range(1, 5)}
    cart_items_dist["4+"] = int((np.array(n_cart_items_list) >= 4).sum())

    from collections import Counter
    prod_counts = Counter(recommended_products)

    # hash determinístico da matriz de features + p_abandon, todas as sessões (não amostra)
    feat_bytes = X.to_csv(index=False).encode("utf-8")
    p_bytes = np.asarray(p, dtype=np.float64).round(10).tobytes()
    feat_hash = hashlib.sha256(feat_bytes + p_bytes).hexdigest()

    return {
        "source": csv_path.name,
        "n_sessions": n,
        "auc_roc": round(auc, 6),
        "action_rate_theta1_pct": round(float(action_t1.mean() * 100), 4),
        "action_rate_theta2_pct": round(float(action_t2.mean() * 100), 4),
        "precision_theta2_pct": precision_t2,
        "n_sessions_with_applicable_rule": n_with_rule,
        "rule_applicability_pct": round(100 * n_with_rule / n, 4),
        "n_recommendation_reach": n_reach,
        "recommendation_reach_pct": round(100 * n_reach / n, 4),
        "candidate_rule_count_distribution": cand_dist,
        "cart_items_count_distribution": cart_items_dist,
        "distinct_recommended_product_ids": len(prod_counts),
        "recommended_product_id_counts": dict(prod_counts.most_common()),
        "nba_score_mean": round(float(np.mean(nba_scores)), 6) if nba_scores else None,
        "feature_matrix_and_pabandon_sha256": feat_hash,
        "elapsed_s": round(time.time() - t0, 1),
    }


def main():
    booster = lgb.Booster(model_str=(DATASET_DIR / "model.lgb").read_text(encoding="utf-8"))
    with open(DATASET_DIR / "brand_vocab.pkl", "rb") as f:
        vocab = pickle.load(f)
    with open(DATASET_DIR / "ruleset.pkl", "rb") as f:
        ruleset = pickle.load(f)
    lookup = load_lookup(str(DATASET_DIR / "product_lookup.parquet"))
    theta_1, theta_2 = load_thresholds()

    artifacts = ["model.lgb", "ruleset.pkl", "brand_vocab.pkl", "product_lookup.parquet", "thresholds.json"]
    artifact_hashes = {a: sha256_file(DATASET_DIR / a) for a in artifacts}

    print(f"theta_1={theta_1}, theta_2={theta_2}")
    print("Medindo outubro...")
    oct_result = measure(DATASET_DIR / "2019-Oct.csv", booster, vocab, ruleset, lookup, theta_1, theta_2)
    print(f"  {oct_result['n_sessions']:,} sessões, AUC={oct_result['auc_roc']}, "
          f"aplicabilidade={oct_result['rule_applicability_pct']}%")

    print("Medindo novembro...")
    nov_result = measure(DATASET_DIR / "2019-Nov.csv", booster, vocab, ruleset, lookup, theta_1, theta_2)
    print(f"  {nov_result['n_sessions']:,} sessões, AUC={nov_result['auc_roc']}, "
          f"aplicabilidade={nov_result['rule_applicability_pct']}%, "
          f"alcance={nov_result['recommendation_reach_pct']}%")

    out = {
        "theta_1": theta_1,
        "theta_2": theta_2,
        "artifact_sha256": artifact_hashes,
        "outubro": oct_result,
        "novembro": nov_result,
    }
    out_path = DATASET_DIR / "m2_aplicabilidade_results.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Salvo em {out_path}")


if __name__ == "__main__":
    main()
