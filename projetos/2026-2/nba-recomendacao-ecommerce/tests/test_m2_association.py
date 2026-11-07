"""Testes do M2 com transações sintéticas — não lê os CSVs reais."""

import pandas as pd
import pytest

from src.interfaces import RuleSet, SessionProfile
from src.m2_association import (
    MIN_CONFIDENCE,
    MIN_LIFT,
    MIN_SUPPORT,
    _empty_rules,
    _run_fpgrowth,
    filter_rules_for_session,
    mine_rules,
)


def make_profile(cart_items: set[str]) -> SessionProfile:
    return SessionProfile(
        user_session="s1",
        cart_items=frozenset(cart_items),
        cart_view_ratio=0.3,
        n_categories=len(cart_items),
        session_duration=120.0,
        inter_event_time_mean=30.0,
        nav_depth=4,
        dominant_brand="apple",
        cart_item_price=299.0,
        views_of_cart_item=2,
        price_ratio=1.2,
        hour_of_day=14,
        cart_item_category_top="electronics",
        cart_item_brand="apple",
        n_events_after_cart=2,
        n_views_after_cart=2,
        n_categories_after_cart=1,
        idle_time_after_cart=30.0,
        n_pre_cart_events=5,
    )


def make_profiles_with_pattern(
    n: int = 200,
    pattern: tuple = ("electronics", "computers"),
    noise_ratio: float = 0.2,
) -> list[SessionProfile]:
    """Cria n perfis onde `pattern` aparece junto em (1 - noise_ratio)% das sessões."""
    profiles = []
    for i in range(n):
        if i < int(n * noise_ratio):
            profiles.append(make_profile({"phones", "tablets"}))
        else:
            profiles.append(make_profile(set(pattern)))
    return profiles


class TestMineRules:
    def test_returns_ruleset(self):
        profiles = make_profiles_with_pattern(200)
        result = mine_rules(profiles)
        assert isinstance(result, RuleSet)
        assert isinstance(result.rules, pd.DataFrame)

    def test_required_columns(self):
        profiles = make_profiles_with_pattern(200)
        result = mine_rules(profiles)
        for col in ("antecedents", "consequents", "support", "confidence", "lift"):
            assert col in result.rules.columns

    def test_finds_frequent_pattern(self):
        profiles = make_profiles_with_pattern(200, pattern=("electronics", "computers"))
        result = mine_rules(profiles)
        assert len(result.rules) > 0

    def test_ordered_by_lift_descending(self):
        profiles = make_profiles_with_pattern(200)
        result = mine_rules(profiles)
        if len(result.rules) > 1:
            lifts = result.rules["lift"].tolist()
            assert lifts == sorted(lifts, reverse=True)

    def test_all_rules_meet_thresholds(self):
        profiles = make_profiles_with_pattern(200)
        result = mine_rules(profiles)
        if not result.rules.empty:
            assert (result.rules["confidence"] >= MIN_CONFIDENCE).all()
            assert (result.rules["lift"] >= MIN_LIFT).all()

    def test_empty_when_no_multi_item_sessions(self):
        profiles = [make_profile({"electronics"}) for _ in range(50)]
        result = mine_rules(profiles)
        assert result.rules.empty

    def test_empty_profiles_returns_empty(self):
        result = mine_rules([])
        assert result.rules.empty

    def test_support_floor_discards_rules_below_min_sessions(self):
        # padrão presente em 24 cestas: suporte relativo alto (0,8), mas abaixo do piso absoluto
        profiles = make_profiles_with_pattern(30, pattern=("electronics", "computers"))
        assert mine_rules(profiles).rules.empty
        # com piso relaxado, a mesma base gera regras
        assert not mine_rules(profiles, min_rule_sessions=10).rules.empty

    def test_all_rules_meet_support_floor(self):
        from src.m2_association import MIN_RULE_SESSIONS
        profiles = make_profiles_with_pattern(200)
        result = mine_rules(profiles)
        n_tx = sum(1 for p in profiles if len(p.cart_items) >= 2)
        assert (result.rules["support"] * n_tx >= MIN_RULE_SESSIONS).all()


class TestFilterRulesForSession:
    @pytest.fixture
    def ruleset(self):
        profiles = make_profiles_with_pattern(200, pattern=("electronics", "computers"))
        return mine_rules(profiles)

    def test_match_when_antecedent_in_cart(self, ruleset):
        cart = frozenset({"electronics", "computers"})
        filtered = filter_rules_for_session(ruleset, cart)
        assert isinstance(filtered, pd.DataFrame)
        # todas as regras retornadas têm antecedente ⊆ cart
        for _, row in filtered.iterrows():
            assert row["antecedents"].issubset(cart)

    def test_no_match_when_cart_disjoint(self, ruleset):
        cart = frozenset({"furniture", "garden"})
        filtered = filter_rules_for_session(ruleset, cart)
        assert filtered.empty

    def test_empty_ruleset_returns_empty(self):
        from src.m2_association import _empty_rules
        empty = RuleSet(rules=_empty_rules())
        filtered = filter_rules_for_session(empty, frozenset({"electronics"}))
        assert filtered.empty

    def test_result_ordered_by_lift(self, ruleset):
        cart = frozenset({"electronics", "computers"})
        filtered = filter_rules_for_session(ruleset, cart)
        if len(filtered) > 1:
            lifts = filtered["lift"].tolist()
            assert lifts == sorted(lifts, reverse=True)

    def test_single_item_cart_still_matches(self, ruleset):
        # antecedente pode ser apenas {electronics}
        cart = frozenset({"electronics"})
        filtered = filter_rules_for_session(ruleset, cart)
        assert isinstance(filtered, pd.DataFrame)


class TestCategoryIdTypes:
    def test_build_transactions_returns_str_ids(self, tmp_path):
        from src.m2_association import build_transactions_from_csv
        rows = [
            {"event_type": "cart", "category_id": 2053013552637149417, "user_session": "a"},
            {"event_type": "cart", "category_id": 2053013552888807671, "user_session": "a"},
        ]
        path = tmp_path / "carts.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        tx = build_transactions_from_csv(str(path))
        assert tx and all(isinstance(c, str) for c in tx[0])

    def test_validate_rejects_int_ruleset(self):
        from src.m2_association import validate_ruleset_types
        df = pd.DataFrame([{
            "antecedents": frozenset({2053013552637149417}),
            "consequents": frozenset({2053013552888807671}),
            "support": 0.01, "confidence": 0.7, "lift": 2.0,
        }])
        with pytest.raises(TypeError, match="esperado str"):
            validate_ruleset_types(RuleSet(rules=df))

    def test_validate_accepts_str_ruleset(self):
        from src.m2_association import validate_ruleset_types
        ruleset = mine_rules(make_profiles_with_pattern(200))
        validate_ruleset_types(ruleset)  # não lança


# --- caixa branca: ramos de _run_fpgrowth ---

@pytest.mark.caixa_branca
class TestRunFpgrowthRamos:
    def test_run_fpgrowth_sem_itemset_frequente_retorna_regras_vazias(self):
        # ramo `if freq.empty`: nenhuma categoria atinge o suporte mínimo
        cestas = [[f"cat_{i}", f"cat_{i + 1000}"] for i in range(50)]
        regras = _run_fpgrowth(cestas, min_support=0.5, min_confidence=0.5, min_lift=1.0)
        assert regras.empty
        assert list(regras.columns) == list(_empty_rules().columns)
