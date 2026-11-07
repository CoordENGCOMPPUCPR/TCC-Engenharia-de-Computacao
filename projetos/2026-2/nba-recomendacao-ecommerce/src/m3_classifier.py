# m3_classifier.py — Classificador LightGBM + SHAP para predição de abandono de carrinho.

from typing import Optional

import numpy as np
import pandas as pd
import shap
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

from src.interfaces import AbandonScore, SessionProfile

FEATURE_NAMES = [
    # pré-cart: comportamentais
    "cart_view_ratio",
    "n_categories",
    "session_duration",
    "inter_event_time_mean",
    "nav_depth",
    "dominant_brand",
    # pré-cart: item no carrinho
    "cart_item_price",
    "views_of_cart_item",
    "price_ratio",
    "hour_of_day",
    "cart_item_category_top",
    "cart_item_brand",
    # pós-cart (janela T=120s)
    "n_events_after_cart",
    "n_views_after_cart",
    "n_categories_after_cart",
    "idle_time_after_cart",
]

CATEGORICAL_FEATURES = ["dominant_brand", "cart_item_category_top", "cart_item_brand"]

TOP_N_BRANDS = 50

_BASE_PARAMS = {
    "objective": "binary",
    "metric": "auc",
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 20,
    "verbose": -1,
    "random_state": 42,
}


def build_brand_vocab(profiles: list[SessionProfile], top_n: int = TOP_N_BRANDS) -> set[str]:
    # Top-N marcas por frequência em cart_item_brand — chamar apenas sobre dados de treino.
    # O mesmo vocabulário é aplicado a cart_item_brand e dominant_brand
    from collections import Counter
    counts = Counter(p.cart_item_brand for p in profiles)
    return {brand for brand, _ in counts.most_common(top_n)}


def profiles_to_features(
    profiles: list[SessionProfile],
    brand_vocab: Optional[set[str]] = None,
) -> pd.DataFrame:
    # Converte lista de SessionProfile em DataFrame de features.
    # brand_vocab: conjunto de brands mantidas em cart_item_brand e dominant_brand;
    rows = [
        {
            "cart_view_ratio": p.cart_view_ratio,
            "n_categories": p.n_categories,
            "session_duration": p.session_duration,
            "inter_event_time_mean": p.inter_event_time_mean,
            "nav_depth": p.nav_depth,
            "dominant_brand": p.dominant_brand,
            "cart_item_price": p.cart_item_price,
            "views_of_cart_item": p.views_of_cart_item,
            "price_ratio": p.price_ratio,
            "hour_of_day": p.hour_of_day,
            "cart_item_category_top": p.cart_item_category_top,
            "cart_item_brand": p.cart_item_brand,
            "n_events_after_cart": p.n_events_after_cart,
            "n_views_after_cart": p.n_views_after_cart,
            "n_categories_after_cart": p.n_categories_after_cart,
            "idle_time_after_cart": p.idle_time_after_cart,
        }
        for p in profiles
    ]
    df = pd.DataFrame(rows, columns=FEATURE_NAMES)

    if brand_vocab is not None:
        # marca fora do top-50 do treino -> "other": evita cardinalidade alta
        # (964 valores sem isso) e memorização de marcas raras
        for col in ("cart_item_brand", "dominant_brand"):
            df[col] = df[col].where(df[col].isin(brand_vocab), other="other")

    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].astype("category")  # LightGBM trata nativamente, sem one-hot

    return df


def train(
    profiles: list[SessionProfile],
    labels: list[int],
) -> tuple[LGBMClassifier, shap.TreeExplainer, set[str]]:
    #Treina LightGBM e retorna (modelo, TreeExplainer, brand_vocab).
    brand_vocab = build_brand_vocab(profiles)
    X = profiles_to_features(profiles, brand_vocab)
    y = np.array(labels)

    model = LGBMClassifier(**_BASE_PARAMS)
    model.fit(X, y, categorical_feature=CATEGORICAL_FEATURES)

    explainer = shap.TreeExplainer(model)

    return model, explainer, brand_vocab


def evaluate(
    model: LGBMClassifier,
    profiles: list[SessionProfile],
    labels: list[int],
    brand_vocab: Optional[set[str]] = None,
) -> dict:
    # Avalia AUC-ROC sobre um conjunto de perfis rotulados.
    X = profiles_to_features(profiles, brand_vocab)
    y = np.array(labels)
    y_pred = model.predict_proba(X)[:, 1]
    return {"auc_roc": roc_auc_score(y, y_pred)}


def cross_validate(
    profiles: list[SessionProfile],
    labels: list[int],
    n_splits: int = 5,
    seed: int = 42,
) -> dict:
    # AUC-ROC médio, desvio e por fold, a partir das predições out-of-fold.
    y = np.asarray(labels)
    oof = cross_val_oof_predict(profiles, labels, n_splits=n_splits, seed=seed)
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    folds = [float(roc_auc_score(y[te], oof[te])) for _, te in cv.split(np.zeros(len(y)), y)]
    return {"auc_roc_mean": float(np.mean(folds)), "auc_roc_std": float(np.std(folds)),
            "folds": folds}


def cross_val_oof_predict(
    profiles: list[SessionProfile],
    labels: list[int],
    n_splits: int = 5,
    seed: int = 42,
) -> np.ndarray:
    # p_abandon out-of-fold para cada perfil (StratifiedKFold; brand_vocab por fold).
    # Base para métricas de desenvolvimento e para a calibração de θ₁/θ₂ (M4).
    # Assert: nenhum índice em treino e teste do mesmo fold; todo perfil recebe 1 predição.
    
    y = np.asarray(labels)
    oof = np.full(len(profiles), np.nan)
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for train_idx, test_idx in cv.split(np.zeros(len(y)), y):
        assert not np.intersect1d(train_idx, test_idx).size, "vazamento: índice em treino e teste"
        train_p = [profiles[i] for i in train_idx]
        test_p = [profiles[i] for i in test_idx]
        # vocabulário e modelo refeitos do zero em CADA fold 
        vocab = build_brand_vocab(train_p)
        model = LGBMClassifier(**_BASE_PARAMS)
        model.fit(profiles_to_features(train_p, vocab), y[train_idx], categorical_feature=CATEGORICAL_FEATURES)
        # só o fold de teste desta rodada recebe predição — nunca viu este modelo no treino
        oof[test_idx] = model.predict_proba(profiles_to_features(test_p, vocab))[:, 1]
    assert not np.isnan(oof).any(), "perfil sem predição out-of-fold"
    return oof


def predict_abandon_score(
    profile: SessionProfile,
    model,
    explainer: shap.TreeExplainer,
    brand_vocab: Optional[set[str]] = None,
) -> AbandonScore:
    # Prediz probabilidade de abandono e valores SHAP para uma sessão.
    # model: LGBMClassifier (treino local) ou lgb.Booster (carregado de .lgb).

    import lightgbm as lgb

    X = profiles_to_features([profile], brand_vocab)
    if isinstance(model, lgb.Booster):
        p_abandon = float(model.predict(X)[0])
    else:
        p_abandon = float(model.predict_proba(X)[0][1])
    shap_values = explainer.shap_values(X)

    # shap.TreeExplainer devolve formatos diferentes dependendo da versão da lib e
    # do tipo de modelo (LGBMClassifier vs. lgb.Booster) — os 3 ramos cobrem: lista
    # de 2 arrays (1 por classe), array 3D (amostra, feature, classe), ou já 2D
    if isinstance(shap_values, list):
        vals = np.array(shap_values[1][0])        # classe 1 (abandono), única amostra
    elif getattr(shap_values, "ndim", 0) == 3:
        vals = np.array(shap_values[0, :, 1])      # amostra 0, todas features, classe 1
    else:
        vals = np.array(shap_values[0])            # já é só a classe positiva
    return AbandonScore(p_abandon=p_abandon, shap_values=vals)
