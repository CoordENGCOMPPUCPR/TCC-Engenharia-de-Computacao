"""Testes do M4 com dados sintéticos."""

import numpy as np
import pandas as pd
import pytest

from src.interfaces import AbandonScore, NBAAction, RuleSet, SessionProfile
from src.m4_nba import THETA_1, THETA_2, calibrate_thresholds, decide, load_thresholds, thresholds


def make_profile(cart_items: set[str] = None) -> SessionProfile:
    return SessionProfile(
        user_session="s1",
        cart_items=frozenset(cart_items or {"electronics"}),
        cart_view_ratio=0.3,
        n_categories=2,
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
        n_events_after_cart=0,
        n_views_after_cart=0,
        n_categories_after_cart=0,
        idle_time_after_cart=120.0,
        n_pre_cart_events=5,
    )


def make_abandon_score(p: float) -> AbandonScore:
    shap = np.zeros(16)
    shap[0] = 0.5  # cart_view_ratio dominante
    return AbandonScore(p_abandon=p, shap_values=shap)


def make_ruleset(antecedent: str = "electronics", consequent: str = "computers") -> RuleSet:
    df = pd.DataFrame([{
        "antecedents": frozenset({antecedent}),
        "consequents": frozenset({consequent}),
        "support": 0.05,
        "confidence": 0.7,
        "lift": 2.5,
    }])
    return RuleSet(rules=df)


def make_lookup(category: str = "computers", product_id: int = 42) -> pd.DataFrame:
    return pd.DataFrame(
        {"product_id": [product_id], "purchase_count": [100]},
        index=pd.Index([category], name="category_id"),
    )


class TestDecideNoIntervention:
    def test_below_theta2_returns_no_intervention(self):
        result = decide(
            make_profile(), make_abandon_score(THETA_2 - 0.01),
            make_ruleset(), make_lookup()
        )
        assert result.action == "no_intervention"
        assert result.consequent is None
        assert result.nba_score is None

    def test_no_intervention_has_empty_message(self):
        result = decide(
            make_profile(), make_abandon_score(0.1),
            make_ruleset(), make_lookup()
        )
        assert result.intervention_message == ""


class TestDecideModerateIntervention:
    def test_between_thresholds_returns_moderate(self):
        p = (THETA_1 + THETA_2) / 2
        result = decide(
            make_profile({"electronics"}),
            make_abandon_score(p),
            make_ruleset(),
            make_lookup(),
        )
        assert result.action == "moderate_intervention"

    def test_moderate_has_message(self):
        result = decide(
            make_profile({"electronics"}),
            make_abandon_score(THETA_2),
            make_ruleset(),
            make_lookup(),
        )
        assert result.intervention_message != ""


class TestDecideStrongIntervention:
    def test_above_theta1_returns_strong(self):
        result = decide(
            make_profile({"electronics"}),
            make_abandon_score(THETA_1),
            make_ruleset(),
            make_lookup(),
        )
        assert result.action == "strong_intervention"

    def test_resolves_product_id(self):
        result = decide(
            make_profile({"electronics"}),
            make_abandon_score(THETA_1),
            make_ruleset(antecedent="electronics", consequent="computers"),
            make_lookup(category="computers", product_id=42),
        )
        assert result.recommended_product_id == 42

    def test_consequent_is_frozenset(self):
        result = decide(
            make_profile({"electronics"}),
            make_abandon_score(THETA_1),
            make_ruleset(),
            make_lookup(),
        )
        assert isinstance(result.consequent, frozenset)

    def test_nba_score_positive(self):
        result = decide(
            make_profile({"electronics"}),
            make_abandon_score(THETA_1),
            make_ruleset(),
            make_lookup(),
        )
        assert result.nba_score is not None
        assert result.nba_score > 0

    def test_nba_score_formula(self):
        p = THETA_1
        result = decide(
            make_profile({"electronics"}),
            make_abandon_score(p),
            make_ruleset(antecedent="electronics", consequent="computers"),
            make_lookup(),
        )
        # lift=2.5, confidence=0.7 — nba_score não depende de p_abandon
        expected = 2.5 * 0.7
        assert result.nba_score == pytest.approx(expected)


class TestDecideNoMatchingRules:
    def test_no_rules_for_cart_returns_action_without_product(self):
        # cart tem "furniture" mas regra só existe para "electronics"
        result = decide(
            make_profile({"furniture"}),
            make_abandon_score(THETA_1),
            make_ruleset(antecedent="electronics"),
            make_lookup(),
        )
        assert result.action == "strong_intervention"
        assert result.consequent is None
        assert result.recommended_product_id is None

    def test_empty_ruleset_returns_action_without_product(self):
        from src.m2_association import _empty_rules
        empty_rs = RuleSet(rules=_empty_rules())
        result = decide(
            make_profile({"electronics"}),
            make_abandon_score(THETA_1),
            empty_rs,
            make_lookup(),
        )
        assert result.action == "strong_intervention"
        assert result.consequent is None


class TestDominantFeature:
    def test_dominant_feature_identified(self):
        shap = np.zeros(16)
        shap[13] = 1.5  # n_views_after_cart
        score = AbandonScore(p_abandon=THETA_1, shap_values=shap)
        result = decide(make_profile({"electronics"}), score, make_ruleset(), make_lookup())
        assert result.dominant_feature == "n_views_after_cart"

    def test_shap_values_propagated(self):
        score = make_abandon_score(THETA_1)
        result = decide(make_profile({"electronics"}), score, make_ruleset(), make_lookup())
        np.testing.assert_array_equal(result.shap_values, score.shap_values)


class TestThresholdsSemFallback:
    """Sem o artefato calibrado, o motor recusa-se a decidir (não há padrão)."""

    def test_load_thresholds_falha_se_artefato_ausente(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="thresholds.json não encontrado"):
            load_thresholds(tmp_path / "thresholds.json")

    def test_mensagem_indica_como_gerar(self, tmp_path):
        with pytest.raises(FileNotFoundError, match=r"src\.train"):
            load_thresholds(tmp_path / "thresholds.json")

    def test_load_thresholds_le_artefato_valido(self, tmp_path):
        import json
        p = tmp_path / "thresholds.json"
        p.write_text(json.dumps({"theta_1": 0.9, "theta_2": 0.8}), encoding="utf-8")
        assert load_thresholds(p) == (0.9, 0.8)

    def test_nenhum_limiar_herdado_de_0_50(self):
        # o corte legado (0,50) acionaria quase toda a população de disparo
        t1, t2 = thresholds()
        assert t2 > 0.5 and t1 >= t2
        assert (THETA_1, THETA_2) == (t1, t2)

    def test_modulo_importavel_sem_artefato(self):
        # train.py importa calibrate_thresholds para GERAR o artefato: o import
        # do módulo não pode depender dele existir
        import importlib
        m = importlib.import_module("src.m4_nba")
        assert callable(m.calibrate_thresholds)


# --- caixa branca: calibração dos limiares e laço de resolução do produto ---

@pytest.mark.caixa_branca
class TestM4Ramos:
    def test_calibrate_thresholds_usa_percentis_80_e_50(self):
        th = calibrate_thresholds(np.linspace(0.0, 1.0, 101))
        assert th["theta_1"] == pytest.approx(0.80)
        assert th["theta_2"] == pytest.approx(0.50)
        assert th["n_calibration"] == 101

    def test_calibrate_thresholds_rejeita_fracoes_invertidas(self):
        # ramo do assert θ₂ ≤ θ₁: fração forte maior que a de ação inverteria os limiares
        with pytest.raises(AssertionError):
            calibrate_thresholds(np.linspace(0.0, 1.0, 101), strong_top_frac=0.6, action_top_frac=0.3)

    def test_decide_consequente_fora_da_tabela_mantem_regra_sem_produto(self):
        # laço de resolve_product: nenhuma categoria do consequente está na tabela de produtos
        result = decide(
            make_profile({"electronics"}),
            make_abandon_score(THETA_1),
            make_ruleset(antecedent="electronics", consequent="computers"),
            make_lookup(category="furniture", product_id=7),
        )
        assert result.action == "strong_intervention"
        assert result.consequent == frozenset({"computers"})
        assert result.recommended_product_id is None
        assert result.nba_score == pytest.approx(2.5 * 0.7)
