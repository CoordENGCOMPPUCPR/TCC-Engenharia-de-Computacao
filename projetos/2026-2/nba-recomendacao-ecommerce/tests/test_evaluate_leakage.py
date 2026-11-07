"""Trava contra reincidência de avaliação in-sample (treinar e prever no mesmo conjunto)."""

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from src.evaluate_segmented import cross_val_oof_predict
from src.interfaces import SessionProfile


def _profile(i: int, rng: np.random.Generator) -> SessionProfile:
    # session_duration único por perfil: um modelo in-sample memoriza o rótulo por ela
    return SessionProfile(
        user_session=f"s{i}", cart_items=frozenset(["c"]),
        cart_view_ratio=float(rng.random()), n_categories=1,
        session_duration=float(i), inter_event_time_mean=float(rng.random()),
        nav_depth=1, dominant_brand="b", cart_item_price=float(rng.random()),
        views_of_cart_item=1, price_ratio=1.0, hour_of_day=12,
        cart_item_category_top="e", cart_item_brand="b",
        n_events_after_cart=0, n_views_after_cart=0, n_categories_after_cart=0,
        idle_time_after_cart=float(rng.random() * 300), n_pre_cart_events=5,
    )


@pytest.fixture
def random_dataset():
    rng = np.random.default_rng(0)
    profiles = [_profile(i, rng) for i in range(400)]
    labels = rng.integers(0, 2, size=400).tolist()   # rótulos aleatórios: sem sinal real
    return profiles, labels


def test_oof_auc_is_near_chance_on_random_labels(random_dataset):
    """Sem sinal, avaliação honesta dá ≈0,5. Um AUC alto aqui só é possível com vazamento."""
    profiles, labels = random_dataset
    oof = cross_val_oof_predict(profiles, labels, n_splits=5)
    assert roc_auc_score(labels, oof) < 0.65


def test_every_profile_gets_exactly_one_prediction(random_dataset):
    profiles, labels = random_dataset
    oof = cross_val_oof_predict(profiles, labels, n_splits=5)
    assert oof.shape == (len(profiles),)
    assert not np.isnan(oof).any()
    assert ((oof >= 0) & (oof <= 1)).all()
