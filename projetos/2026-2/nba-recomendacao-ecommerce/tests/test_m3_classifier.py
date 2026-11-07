"""Testes do M3 com dados sintéticos — não lê os CSVs reais."""

import numpy as np
import pytest

from src.interfaces import AbandonScore, SessionProfile
from src.m3_classifier import (
    FEATURE_NAMES,
    build_brand_vocab,
    cross_validate,
    evaluate,
    predict_abandon_score,
    profiles_to_features,
    train,
)


def make_profile(
    cart_view_ratio: float = 0.3,
    n_categories: int = 3,
    session_duration: float = 120.0,
    inter_event_time_mean: float = 30.0,
    nav_depth: int = 4,
    dominant_brand: str = "apple",
    cart_item_price: float = 299.0,
    views_of_cart_item: int = 2,
    price_ratio: float = 1.2,
    hour_of_day: int = 14,
    cart_item_category_top: str = "electronics",
    cart_item_brand: str = "apple",
    n_events_after_cart: int = 2,
    n_views_after_cart: int = 2,
    n_categories_after_cart: int = 1,
    idle_time_after_cart: float = 30.0,
    n_pre_cart_events: int = 5,
) -> SessionProfile:
    return SessionProfile(
        user_session="s1",
        cart_items=frozenset(["electronics"]),
        cart_view_ratio=cart_view_ratio,
        n_categories=n_categories,
        session_duration=session_duration,
        inter_event_time_mean=inter_event_time_mean,
        nav_depth=nav_depth,
        dominant_brand=dominant_brand,
        cart_item_price=cart_item_price,
        views_of_cart_item=views_of_cart_item,
        price_ratio=price_ratio,
        hour_of_day=hour_of_day,
        cart_item_category_top=cart_item_category_top,
        cart_item_brand=cart_item_brand,
        n_events_after_cart=n_events_after_cart,
        n_views_after_cart=n_views_after_cart,
        n_categories_after_cart=n_categories_after_cart,
        idle_time_after_cart=idle_time_after_cart,
        n_pre_cart_events=n_pre_cart_events,
    )


def make_synthetic_dataset(n: int = 100) -> tuple[list[SessionProfile], list[int]]:
    """Dataset sintético balanceado para smoke tests de treino."""
    rng = np.random.default_rng(42)
    brands = ["apple", "samsung", "xiaomi", "huawei", "sony", "unknown"]
    categories = ["electronics", "appliances", "computers", "phones"]
    profiles, labels = [], []
    for i in range(n):
        label = i % 2
        profiles.append(make_profile(
            cart_view_ratio=float(rng.uniform(0.1, 0.9)),
            n_categories=int(rng.integers(1, 8)),
            session_duration=float(rng.uniform(10.0, 600.0)),
            inter_event_time_mean=float(rng.uniform(5.0, 120.0)),
            nav_depth=int(rng.integers(0, 10)),
            dominant_brand=str(rng.choice(brands)),
            cart_item_price=float(rng.uniform(10.0, 2000.0)),
            views_of_cart_item=int(rng.integers(0, 10)),
            price_ratio=float(rng.uniform(0.5, 5.0)),
            hour_of_day=int(rng.integers(0, 24)),
            cart_item_category_top=str(rng.choice(categories)),
            cart_item_brand=str(rng.choice(brands)),
            n_events_after_cart=int(rng.integers(0, 10)),
            n_views_after_cart=int(rng.integers(0, 8)),
            n_categories_after_cart=int(rng.integers(0, 4)),
            idle_time_after_cart=float(rng.uniform(0.0, 120.0)),
        ))
        labels.append(label)
    return profiles, labels


@pytest.fixture(scope="module")
def trained_model():
    profiles, labels = make_synthetic_dataset(200)
    return train(profiles, labels)


class TestProfilesToFeatures:
    def test_columns_match_feature_names(self):
        df = profiles_to_features([make_profile()])
        assert list(df.columns) == FEATURE_NAMES

    def test_feature_count(self):
        assert len(FEATURE_NAMES) == 16

    def test_categorical_dtypes(self):
        df = profiles_to_features([make_profile()])
        for col in ["dominant_brand", "cart_item_category_top", "cart_item_brand"]:
            assert df[col].dtype.name == "category"

    def test_shape(self):
        df = profiles_to_features([make_profile() for _ in range(5)])
        assert df.shape == (5, 16)

    def test_brand_vocab_groups_rare_brands(self):
        vocab = {"apple", "samsung"}
        profiles = [make_profile(cart_item_brand="nokia"), make_profile(cart_item_brand="apple")]
        df = profiles_to_features(profiles, brand_vocab=vocab)
        assert df["cart_item_brand"].iloc[0] == "other"
        assert df["cart_item_brand"].iloc[1] == "apple"

    def test_brand_vocab_also_applies_to_dominant_brand(self):
        # o mesmo vocabulário limita a cardinalidade de dominant_brand
        vocab = {"apple", "samsung"}
        profiles = [make_profile(dominant_brand="xiaomi"), make_profile(dominant_brand="samsung")]
        df = profiles_to_features(profiles, brand_vocab=vocab)
        assert df["dominant_brand"].iloc[0] == "other"
        assert df["dominant_brand"].iloc[1] == "samsung"

    def test_post_cart_columns_present(self):
        df = profiles_to_features([make_profile()])
        for col in ["n_events_after_cart", "n_views_after_cart",
                    "n_categories_after_cart", "idle_time_after_cart"]:
            assert col in df.columns


class TestBuildBrandVocab:
    def test_returns_set(self):
        profiles, _ = make_synthetic_dataset(50)
        assert isinstance(build_brand_vocab(profiles, top_n=5), set)

    def test_top_n_respected(self):
        profiles, _ = make_synthetic_dataset(100)
        assert len(build_brand_vocab(profiles, top_n=3)) <= 3


class TestTrain:
    def test_returns_three_tuple(self, trained_model):
        assert len(trained_model) == 3

    def test_model_and_explainer_not_none(self, trained_model):
        model, explainer, brand_vocab = trained_model
        assert model is not None
        assert explainer is not None

    def test_brand_vocab_is_set(self, trained_model):
        _, _, brand_vocab = trained_model
        assert isinstance(brand_vocab, set)

    def test_model_has_predict_proba(self, trained_model):
        model, _, _ = trained_model
        assert hasattr(model, "predict_proba")


class TestPredictAbandonScore:
    def test_returns_abandon_score(self, trained_model):
        model, explainer, brand_vocab = trained_model
        result = predict_abandon_score(make_profile(), model, explainer, brand_vocab)
        assert isinstance(result, AbandonScore)

    def test_p_abandon_in_range(self, trained_model):
        model, explainer, brand_vocab = trained_model
        result = predict_abandon_score(make_profile(), model, explainer, brand_vocab)
        assert 0.0 <= result.p_abandon <= 1.0

    def test_shap_values_length_matches_features(self, trained_model):
        model, explainer, brand_vocab = trained_model
        result = predict_abandon_score(make_profile(), model, explainer, brand_vocab)
        assert len(result.shap_values) == len(FEATURE_NAMES)

    def test_shap_values_are_finite(self, trained_model):
        model, explainer, brand_vocab = trained_model
        result = predict_abandon_score(make_profile(), model, explainer, brand_vocab)
        assert np.all(np.isfinite(result.shap_values))

    def test_user_exit_profile_handled(self, trained_model):
        # n_events_after_cart=0, idle_time=300 → usuário saiu do app
        model, explainer, brand_vocab = trained_model
        profile = make_profile(n_events_after_cart=0, n_views_after_cart=0,
                               n_categories_after_cart=0, idle_time_after_cart=120.0)
        result = predict_abandon_score(profile, model, explainer, brand_vocab)
        assert 0.0 <= result.p_abandon <= 1.0

    def test_unknown_brand_handled(self, trained_model):
        model, explainer, brand_vocab = trained_model
        result = predict_abandon_score(
            make_profile(cart_item_brand="brand_nunca_vista_xyz"),
            model, explainer, brand_vocab
        )
        assert 0.0 <= result.p_abandon <= 1.0


class TestEvaluate:
    def test_returns_auc_roc(self, trained_model):
        model, _, brand_vocab = trained_model
        profiles, labels = make_synthetic_dataset(50)
        metrics = evaluate(model, profiles, labels, brand_vocab)
        assert "auc_roc" in metrics
        assert 0.0 <= metrics["auc_roc"] <= 1.0


class TestCrossValidate:
    def test_returns_mean_std_folds(self):
        profiles, labels = make_synthetic_dataset(100)
        result = cross_validate(profiles, labels, n_splits=3)
        assert "auc_roc_mean" in result
        assert "auc_roc_std" in result
        assert len(result["folds"]) == 3


# --- caixa branca: formatos de saída do SHAP em predict_abandon_score ---

class _ExplainerFalso:
    """Devolve valores SHAP num formato fixo, para exercitar cada ramo de predict_abandon_score."""

    def __init__(self, valores):
        self.valores = valores

    def shap_values(self, X):
        return self.valores


@pytest.mark.caixa_branca
class TestFormatosShapRamos:
    def test_predict_abandon_score_shap_em_lista_usa_classe_positiva(self, trained_model):
        # ramo `isinstance(shap_values, list)`: [classe 0, classe 1], cada uma (amostras, features)
        model, _, brand_vocab = trained_model
        n = len(FEATURE_NAMES)
        classe_0 = np.zeros((1, n))
        classe_1 = np.arange(n, dtype=float).reshape(1, -1)
        result = predict_abandon_score(
            make_profile(), model, _ExplainerFalso([classe_0, classe_1]), brand_vocab
        )
        np.testing.assert_array_equal(result.shap_values, classe_1[0])

    def test_predict_abandon_score_shap_3d_usa_classe_positiva(self, trained_model):
        # ramo `ndim == 3`: (amostras, features, classes)
        model, _, brand_vocab = trained_model
        n = len(FEATURE_NAMES)
        valores = np.zeros((1, n, 2))
        valores[0, :, 1] = np.arange(n, dtype=float)
        result = predict_abandon_score(make_profile(), model, _ExplainerFalso(valores), brand_vocab)
        np.testing.assert_array_equal(result.shap_values, np.arange(n, dtype=float))
