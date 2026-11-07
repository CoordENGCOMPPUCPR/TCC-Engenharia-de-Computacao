"""A avaliação deve pontuar exatamente as sessões que o StreamSimulator pontua (src/trigger.py)."""

import numpy as np
import pandas as pd
import pytest

from src.build_dataset import (
    assert_official_trigger_population, is_scored_in_production, production_population_mask,
)
from src.interfaces import SessionProfile
from src.trigger import T_WINDOW

T0 = pd.Timestamp("2019-11-01 10:00:00")
S = lambda s: T0 + pd.Timedelta(seconds=s)  # noqa: E731


def _profile(sid: str) -> SessionProfile:
    return SessionProfile(
        user_session=sid, cart_items=frozenset(["c"]), cart_view_ratio=0.2, n_categories=1,
        session_duration=60.0, inter_event_time_mean=10.0, nav_depth=3, dominant_brand="b",
        cart_item_price=10.0, views_of_cart_item=1, price_ratio=1.0, hour_of_day=10,
        cart_item_category_top="e", cart_item_brand="b", n_events_after_cart=1,
        n_views_after_cart=1, n_categories_after_cart=1, idle_time_after_cart=30.0,
        n_pre_cart_events=5,
    )


class TestIsScoredInProduction:
    def test_abandon_with_activity_is_scored(self):
        assert is_scored_in_production(T0, None, S(30)) is True
        assert is_scored_in_production(T0, pd.NaT, S(30)) is True

    def test_purchase_within_window_cancels(self):
        assert is_scored_in_production(T0, S(T_WINDOW - 1), S(30)) is False
        assert is_scored_in_production(T0, S(T_WINDOW), S(30)) is False  # limite inclusivo

    def test_late_purchase_is_scored(self):
        assert is_scored_in_production(T0, S(T_WINDOW + 1), S(30)) is True

    def test_purchase_before_first_cart_cancels(self):
        # StreamSimulator.ingest marca triggered=True ao ver purchase antes do cart
        assert is_scored_in_production(T0, S(-10), S(30)) is False

    def test_no_activity_in_window_is_user_left(self):
        assert is_scored_in_production(T0, None, None) is False
        assert is_scored_in_production(T0, None, pd.NaT) is False
        assert is_scored_in_production(T0, None, S(T_WINDOW + 5)) is False

    def test_activity_at_window_edge_is_scored(self):
        assert is_scored_in_production(T0, None, S(T_WINDOW)) is True


class TestProductionPopulationMask:
    @pytest.fixture
    def trigger_times(self):
        return pd.DataFrame(
            {
                "cart_time": [T0] * 5,
                "purchase_time": [pd.NaT, S(60), S(T_WINDOW + 500), S(-5), pd.NaT],
                "first_post_event_time": [S(30), S(30), S(30), S(30), pd.NaT],
            },
            index=pd.Index(["abandon", "fast", "late", "before", "silent"], name="user_session"),
        )

    def test_mask_matches_simulator_rules(self, trigger_times):
        sids = ["abandon", "fast", "late", "before", "silent"]
        mask = production_population_mask([_profile(s) for s in sids], trigger_times)
        np.testing.assert_array_equal(mask, [True, False, True, False, False])

    def test_assert_passes_on_official_population(self, trigger_times):
        assert_official_trigger_population([_profile("abandon"), _profile("late")], trigger_times)

    def test_assert_fails_on_divergent_population(self, trigger_times):
        with pytest.raises(AssertionError, match="fora da população oficial"):
            assert_official_trigger_population([_profile("abandon"), _profile("fast")], trigger_times)
        with pytest.raises(AssertionError, match="fora da população oficial"):
            assert_official_trigger_population([_profile("silent")], trigger_times)
