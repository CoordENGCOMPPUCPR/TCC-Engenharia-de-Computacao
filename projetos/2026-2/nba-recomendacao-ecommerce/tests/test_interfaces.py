import numpy as np
import pandas as pd
import pytest

from src.interfaces import AbandonScore, NBAAction, RuleSet, SessionProfile


@pytest.fixture
def session_profile():
    return SessionProfile(
        user_session="s1",
        cart_items=frozenset(["electronics", "computers"]),
        cart_view_ratio=0.4,
        n_categories=3,
        session_duration=120.0,
        inter_event_time_mean=60.0,
        nav_depth=5,
        dominant_brand="apple",
        cart_item_price=999.0,
        views_of_cart_item=2,
        price_ratio=1.1,
        hour_of_day=14,
        cart_item_category_top="electronics",
        cart_item_brand="apple",
        n_events_after_cart=3,
        n_views_after_cart=2,
        n_categories_after_cart=1,
        idle_time_after_cart=30.0,
        n_pre_cart_events=5,
    )


@pytest.fixture
def rule_set():
    df = pd.DataFrame({
        "antecedent": [frozenset(["electronics"])],
        "consequent": [frozenset(["computers"])],
        "support": [0.02],
        "confidence": [0.6],
        "lift": [2.0],
    })
    return RuleSet(rules=df)


@pytest.fixture
def abandon_score():
    return AbandonScore(p_abandon=0.8, shap_values=np.zeros(16))


@pytest.fixture
def nba_action():
    return NBAAction(
        action="strong_intervention",
        p_abandon=0.8,
        consequent=frozenset(["computers"]),
        recommended_product_id=42,
        nba_score=1.5,
        shap_values=np.zeros(16),
        dominant_feature="n_views_after_cart",
        intervention_message="Você ainda está decidindo? Aqui está um cupom.",
    )


class TestSessionProfile:
    def test_instantiation(self, session_profile):
        assert session_profile.user_session == "s1"
        assert "electronics" in session_profile.cart_items
        assert session_profile.cart_view_ratio == 0.4

    def test_cart_items_is_frozenset(self, session_profile):
        assert isinstance(session_profile.cart_items, frozenset)

    def test_pre_cart_price_fields(self, session_profile):
        assert session_profile.cart_item_price == 999.0
        assert session_profile.views_of_cart_item == 2
        assert session_profile.price_ratio == pytest.approx(1.1)

    def test_pre_cart_temporal_fields(self, session_profile):
        assert 0 <= session_profile.hour_of_day <= 23

    def test_pre_cart_category_brand_fields(self, session_profile):
        assert session_profile.cart_item_category_top == "electronics"
        assert session_profile.cart_item_brand == "apple"

    def test_post_cart_fields(self, session_profile):
        assert session_profile.n_events_after_cart == 3
        assert session_profile.n_views_after_cart == 2
        assert session_profile.n_categories_after_cart == 1
        assert session_profile.idle_time_after_cart == pytest.approx(30.0)

    def test_post_cart_zero_when_user_exits(self):
        profile = SessionProfile(
            user_session="s2",
            cart_items=frozenset(["electronics"]),
            cart_view_ratio=0.5,
            n_categories=1,
            session_duration=30.0,
            inter_event_time_mean=30.0,
            nav_depth=2,
            dominant_brand="unknown",
            cart_item_price=50.0,
            views_of_cart_item=0,
            price_ratio=1.0,
            hour_of_day=10,
            cart_item_category_top="unknown",
            cart_item_brand="unknown",
            n_events_after_cart=0,
            n_views_after_cart=0,
            n_categories_after_cart=0,
            idle_time_after_cart=120.0,
            n_pre_cart_events=4,
        )
        assert profile.n_events_after_cart == 0
        assert profile.idle_time_after_cart == pytest.approx(120.0)


class TestRuleSet:
    def test_instantiation(self, rule_set):
        assert isinstance(rule_set.rules, pd.DataFrame)
        assert len(rule_set.rules) == 1

    def test_required_columns(self, rule_set):
        for col in ("antecedent", "consequent", "support", "confidence", "lift"):
            assert col in rule_set.rules.columns

    def test_empty_ruleset(self):
        empty = RuleSet(rules=pd.DataFrame(
            columns=["antecedent", "consequent", "support", "confidence", "lift"]
        ))
        assert len(empty.rules) == 0


class TestAbandonScore:
    def test_instantiation(self, abandon_score):
        assert abandon_score.p_abandon == 0.8
        assert isinstance(abandon_score.shap_values, np.ndarray)

    def test_p_abandon_range(self, abandon_score):
        assert 0.0 <= abandon_score.p_abandon <= 1.0


class TestNBAAction:
    def test_strong_intervention(self, nba_action):
        assert nba_action.action == "strong_intervention"
        assert nba_action.recommended_product_id == 42
        assert nba_action.consequent is not None

    def test_no_intervention(self):
        action = NBAAction(
            action="no_intervention",
            p_abandon=0.3,
            consequent=None,
            recommended_product_id=None,
            nba_score=None,
            shap_values=None,
            dominant_feature=None,
            intervention_message=None,
        )
        assert action.action == "no_intervention"
        assert action.consequent is None

    def test_valid_action_values(self, nba_action):
        valid = {"strong_intervention", "moderate_intervention", "no_intervention"}
        assert nba_action.action in valid
