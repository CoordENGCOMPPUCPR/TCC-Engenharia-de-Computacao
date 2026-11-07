"""Testes do StreamSimulator com artefatos e eventos sintéticos."""

import pickle
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.interfaces import AbandonScore, NBAAction, RuleSet
from src.m1_pipeline import Event
from src.stream_simulator import SessionState, StreamSimulator
from src.trigger import REASON_PURCHASED, REASON_TOO_SHORT, REASON_USER_LEFT, T_WINDOW


# --- fixtures de artefatos sintéticos ---

def _make_event(
    offset_s: int,
    event_type: str,
    session: str = "s1",
    product_id: int = 1,
    category_id: str = "electronics",
    price: float = 299.0,
) -> Event:
    return Event(
        event_time=datetime(2019, 11, 1, 10, 0, 0) + timedelta(seconds=offset_s),
        event_type=event_type,
        product_id=product_id,
        category_id=category_id,
        category_code="electronics.smartphone",
        brand="apple",
        price=price,
        user_id=1,
        user_session=session,
    )


def _make_session(event_types: list[str], session: str = "s1") -> list[Event]:
    """Cria sessão com eventos espaçados de 30s."""
    return [_make_event(i * 30, et, session=session) for i, et in enumerate(event_types)]


ELIGIBLE = ["view", "view", "view", "view", "cart", "view"]   # cart em t=120, atividade em t=150
LATE = 120 + int(T_WINDOW) + 10                                # 1º evento após a janela


@pytest.fixture
def artifact_paths(tmp_path):
    """Cria artefatos mínimos em disco para instanciar o StreamSimulator."""
    from src.m2_association import _empty_rules
    from src.m3_classifier import train
    from src.interfaces import SessionProfile

    # SessionProfile sintético para treinar modelo mínimo
    def _profile(i):
        return SessionProfile(
            user_session=f"s{i}", cart_items=frozenset(["electronics"]),
            cart_view_ratio=0.3, n_categories=2, session_duration=120.0,
            inter_event_time_mean=30.0, nav_depth=4, dominant_brand="apple",
            cart_item_price=299.0, views_of_cart_item=2, price_ratio=1.2,
            hour_of_day=14, cart_item_category_top="electronics",
            cart_item_brand="apple", n_events_after_cart=i % 5,
            n_views_after_cart=i % 3, n_categories_after_cart=1,
            idle_time_after_cart=float(i * 10 % 300), n_pre_cart_events=5,
        )

    profiles = [_profile(i) for i in range(100)]
    labels = [i % 2 for i in range(100)]
    model, explainer, brand_vocab = train(profiles, labels)

    model_path = str(tmp_path / "model.lgb")
    Path(model_path).write_text(model.booster_.model_to_string(), encoding="utf-8")

    vocab_path = str(tmp_path / "brand_vocab.pkl")
    with open(vocab_path, "wb") as f:
        pickle.dump(brand_vocab, f)

    ruleset_path = str(tmp_path / "ruleset.pkl")
    with open(ruleset_path, "wb") as f:
        pickle.dump(RuleSet(rules=_empty_rules()), f)

    lookup_path = str(tmp_path / "lookup.parquet")
    pd.DataFrame(
        {"product_id": [10], "purchase_count": [100]},
        index=pd.Index(["electronics"], name="category_id"),
    ).to_parquet(lookup_path)

    return {"model": model_path, "ruleset": ruleset_path, "lookup": lookup_path}


@pytest.fixture
def sim(artifact_paths):
    return StreamSimulator(
        model_path=artifact_paths["model"],
        ruleset_path=artifact_paths["ruleset"],
        lookup_path=artifact_paths["lookup"],
    )


# --- testes de trigger ---

class TestTrigger:
    def test_no_action_before_trigger(self, sim):
        events = _make_session(["view", "view", "view", "view"])
        for e in events:
            assert sim.ingest(e) is None

    def test_no_action_on_cart_before_t_window(self, sim):
        for e in _make_session(ELIGIBLE):
            result = sim.ingest(e)
        # cart em t=120, atividade em t=150, nenhum evento atingiu T
        assert result is None

    def test_trigger_fires_after_t_window(self, sim):
        for e in _make_session(ELIGIBLE):
            sim.ingest(e)
        result = sim.ingest(_make_event(LATE, "view"))
        assert result is not None
        assert isinstance(result, NBAAction)

    @pytest.mark.caixa_branca
    def test_purchase_within_window_cancels_trigger(self, sim):
        for e in _make_session(ELIGIBLE):
            sim.ingest(e)
        sim.ingest(_make_event(200, "purchase"))          # 80 s após o cart: dentro de T
        result = sim.ingest(_make_event(LATE, "view"))
        assert result is None
        assert sim._sessions["s1"].reason == REASON_PURCHASED

    @pytest.mark.caixa_branca
    def test_purchase_after_window_is_late_conversion_not_cancellation(self, sim):
        # relógio virtual: o prazo vence antes do purchase → sessão pontuada; purchase só marca conversão
        for e in _make_session(ELIGIBLE):
            sim.ingest(e)
        sim.ingest(_make_event(120 + int(T_WINDOW) + 5, "purchase"))
        state = sim._sessions["s1"]
        assert state.action is not None
        assert state.purchased is True
        assert state.reason is None

    def test_other_session_event_expires_pending_deadlines(self, sim):
        # s1 fica em silêncio após a atividade; um evento de s2 avança o relógio e dispara s1
        for e in _make_session(ELIGIBLE, session="s1"):
            sim.ingest(e)
        assert sim.get_action("s1") is None
        sim.ingest(_make_event(LATE, "view", session="s2"))
        assert sim.get_action("s1") is not None

    @pytest.mark.caixa_branca
    def test_silent_exit_is_user_left(self, sim):
        # cart em t=120 e nenhum evento até T → sem canal in-session → sem predição
        for e in _make_session(["view", "view", "view", "view", "cart"]):
            sim.ingest(e)
        result = sim.ingest(_make_event(LATE, "view"))
        assert result is None
        assert sim._sessions["s1"].reason == REASON_USER_LEFT
        assert sim.get_action("s1") is None

    def test_trigger_fires_only_once(self, sim):
        for e in _make_session(ELIGIBLE):
            sim.ingest(e)
        r1 = sim.ingest(_make_event(LATE, "view"))
        r2 = sim.ingest(_make_event(LATE + 30, "view"))
        assert r1 is not None
        assert r2 is None  # não dispara duas vezes

    def test_flush_triggers_session(self, sim):
        for e in _make_session(ELIGIBLE):
            sim.ingest(e)
        assert sim.flush("s1") is not None

    @pytest.mark.caixa_branca
    def test_flush_on_silent_session_is_user_left(self, sim):
        for e in _make_session(["view", "view", "view", "view", "cart"]):
            sim.ingest(e)
        assert sim.flush("s1") is None
        assert sim._sessions["s1"].reason == REASON_USER_LEFT

    def test_flush_noop_without_cart(self, sim):
        events = _make_session(["view", "view", "view", "view"])
        for e in events:
            sim.ingest(e)
        assert sim.flush("s1") is None


# --- testes de estado ---

class TestSessionState:
    def test_get_action_returns_none_before_trigger(self, sim):
        sim.ingest(_make_event(0, "view"))
        assert sim.get_action("s1") is None

    def test_get_action_returns_action_after_trigger(self, sim):
        for e in _make_session(ELIGIBLE):
            sim.ingest(e)
        sim.ingest(_make_event(LATE, "view"))
        assert sim.get_action("s1") is not None

    def test_multiple_sessions_independent(self, sim):
        s1 = _make_session(["view", "view", "view", "view", "cart"], session="s1")
        s2 = _make_session(["view", "view", "view", "view"], session="s2")
        for e in s1 + s2:
            sim.ingest(e)
        assert sim.get_action("s2") is None


# --- testes de métricas ---

class TestMetrics:
    def test_metrics_structure(self, sim):
        m = sim.metrics()
        for key in ("total_sessions", "cart_sessions", "eligible", "triggered", "coverage", "reasons", "actions"):
            assert key in m

    def test_metrics_after_trigger(self, sim):
        for e in _make_session(ELIGIBLE):
            sim.ingest(e)
        sim.ingest(_make_event(LATE, "view"))
        m = sim.metrics()
        assert m["eligible"] == 1
        assert m["coverage"] == pytest.approx(1.0)

    def test_coverage_counts_only_eligible(self, sim):
        # s1 elegível, s2 saída silenciosa, s3 compra dentro da janela
        for e in _make_session(ELIGIBLE, session="s1"):
            sim.ingest(e)
        for e in _make_session(["view", "view", "view", "view", "cart"], session="s2"):
            sim.ingest(e)
        for e in _make_session(ELIGIBLE, session="s3"):
            sim.ingest(e)
        sim.ingest(_make_event(160, "purchase", session="s3"))
        for sid in ("s1", "s2", "s3"):
            sim.flush(sid)
        m = sim.metrics()
        assert m["cart_sessions"] == 3
        assert m["eligible"] == 1
        assert m["coverage"] == pytest.approx(1 / 3)
        assert m["reasons"] == {REASON_USER_LEFT: 1, REASON_PURCHASED: 1}


# --- caixa branca: ramos internos do StreamSimulator ---

@pytest.mark.caixa_branca
class TestSimuladorRamos:
    def test_ingest_evento_exatamente_no_prazo_dispara_pela_propria_sessao(self, sim):
        # _expire usa `<` estrito: o evento em cart + T não expira o prazo, segue o fluxo
        # normal e dispara por `elapsed >= T_WINDOW`, já anexado como atividade da janela
        for e in _make_session(["view", "view", "view", "view", "cart"]):   # cart em t=120
            sim.ingest(e)
        result = sim.ingest(_make_event(120 + int(T_WINDOW), "view"))
        assert isinstance(result, NBAAction)
        assert sim._sessions["s1"].reason is None

    def test_expire_prazo_de_sessao_ja_disparada_nao_redispara(self, sim):
        # ramo `not state.triggered` de _expire: o prazo de s1 continua no heap após o disparo
        for e in _make_session(["view", "view", "view", "view", "cart"]):
            sim.ingest(e)
        acao = sim.ingest(_make_event(120 + int(T_WINDOW), "view"))
        sim.ingest(_make_event(LATE, "view", session="s2"))   # avança o relógio além do prazo de s1
        assert sim.get_action("s1") is acao
        assert sim.metrics()["triggered"] == 1

    def test_ingest_compra_apos_disparo_so_marca_conversao(self, sim):
        # ramo `if state.triggered` com purchase: não cancela nem altera a ação já emitida
        for e in _make_session(ELIGIBLE):
            sim.ingest(e)
        acao = sim.ingest(_make_event(LATE, "view"))
        assert sim.ingest(_make_event(LATE + 30, "purchase")) is None
        estado = sim._sessions["s1"]
        assert estado.purchased is True
        assert estado.action is acao
        assert estado.reason is None

    def test_trigger_sessao_curta_registra_too_few_pre_cart_events(self, sim):
        # ramo `profile is None` de _trigger: passa pelo gatilho, mas tem menos de 5 eventos até o cart
        for e in _make_session(["view", "view", "cart", "view"]):   # cart em t=60, atividade em t=90
            sim.ingest(e)
        assert sim.ingest(_make_event(LATE, "view")) is None
        assert sim._sessions["s1"].reason == REASON_TOO_SHORT

    def test_trigger_batch_shap_prediz_sem_shap_por_sessao(self, artifact_paths):
        # ramo `if self.batch_shap` de _trigger: no replay o SHAP é adiado e o vetor fica zerado
        sim_lote = StreamSimulator(
            model_path=artifact_paths["model"],
            ruleset_path=artifact_paths["ruleset"],
            lookup_path=artifact_paths["lookup"],
            batch_shap=True,
        )
        for e in _make_session(ELIGIBLE):
            sim_lote.ingest(e)
        acao = sim_lote.ingest(_make_event(LATE, "view"))
        assert isinstance(acao, NBAAction)
        assert np.all(acao.shap_values == 0)
        assert 0.0 <= acao.p_abandon <= 1.0

    def test_flush_sessao_inexistente_ou_ja_disparada_retorna_none(self, sim):
        # ramos `state is None` e `state.triggered` de flush
        assert sim.flush("nao_existe") is None
        for e in _make_session(ELIGIBLE):
            sim.ingest(e)
        assert sim.flush("s1") is not None
        assert sim.flush("s1") is None
