"""Contrato: M1 (treino/avaliação) e StreamSimulator (produção) decidem elegibilidade
pela MESMA definição (src/trigger.py). Qualquer divergência falha aqui."""

from datetime import datetime, timedelta

import pytest

import src.m1_pipeline as m1
import src.stream_simulator as sim_mod
import src.trigger as trigger
from src.m1_pipeline import Event, build_session_profile
from src.trigger import (
    REASON_PURCHASED, REASON_USER_LEFT, T_WINDOW, ineligibility_reason, is_eligible,
)

T0 = datetime(2019, 11, 1, 10, 0, 0)


def _ev(offset: float, event_type: str, pid: int = 1) -> Event:
    return Event(event_time=T0 + timedelta(seconds=offset), event_type=event_type, product_id=pid,
                 category_id="c", category_code="e.x", brand="b", price=10.0, user_id=1, user_session="s")


def _session(post_offsets: list[tuple[float, str]]) -> list[Event]:
    """4 views + cart em t=0 (relativo) + eventos pós-cart informados como (offset_desde_cart, tipo)."""
    pre = [_ev(-120 + 30 * i, "view", pid=i + 1) for i in range(4)] + [_ev(0, "cart", pid=5)]
    return pre + [_ev(off, et, pid=10) for off, et in post_offsets]


class TestSingleSourceOfTruth:
    def test_no_module_redefines_t_window(self):
        assert m1.T_WINDOW is trigger.T_WINDOW
        assert sim_mod.T_WINDOW is trigger.T_WINDOW
        assert m1.MIN_EVENTS_BEFORE_TRIGGER is trigger.MIN_EVENTS_BEFORE_TRIGGER

    def test_official_constants(self):
        # mudar aqui exige retreino; o teste existe para tornar a mudança deliberada
        assert T_WINDOW == 120.0
        assert trigger.REQUIRE_ACTIVITY is True
        assert trigger.MIN_EVENTS_BEFORE_TRIGGER == 5


class TestIneligibilityReason:
    def test_purchase_in_window(self):
        assert ineligibility_reason(T0, T0 + timedelta(seconds=10), T0 + timedelta(seconds=5)) == REASON_PURCHASED

    def test_user_left(self):
        assert ineligibility_reason(T0, None, None) == REASON_USER_LEFT
        assert ineligibility_reason(T0, None, T0 + timedelta(seconds=T_WINDOW + 1)) == REASON_USER_LEFT
        assert ineligibility_reason(T0, None, T0) == REASON_USER_LEFT  # simultâneo ao cart

    def test_purchase_takes_precedence_over_user_left(self):
        assert ineligibility_reason(T0, T0 + timedelta(seconds=10), None) == REASON_PURCHASED

    def test_eligible(self):
        assert ineligibility_reason(T0, None, T0 + timedelta(seconds=30)) is None
        assert is_eligible(T0, T0 + timedelta(seconds=T_WINDOW + 60), T0 + timedelta(seconds=30))


@pytest.mark.parametrize("post, expected_eligible", [
    ([(30, "view")], True),                                   # ativo, sem compra
    ([(30, "view"), (T_WINDOW + 60, "purchase")], True),      # compra tardia
    ([(30, "view"), (60, "purchase")], False),                # compra na janela
    ([], False),                                              # saída silenciosa
    ([(T_WINDOW + 30, "view")], False),                       # voltou só depois da janela
    ([(T_WINDOW, "cart")], True),                             # atividade no limite da janela
    ([(0, "view")], False),                                   # mesmo timestamp do cart: não é atividade
    ([(0, "view"), (30, "view")], True),                      # duplicata + atividade real
])
def test_m1_agrees_with_trigger_definition(post, expected_eligible):
    """M1 retorna perfil sse a definição oficial diz elegível, para os mesmos instantes."""
    events = _session(post)
    cart_t = T0
    purch = [e.event_time for e in events if e.event_type == "purchase"]
    post_ev = [e.event_time for e in events
               if e.event_type != "purchase"
               and 0 < (e.event_time - cart_t).total_seconds() <= T_WINDOW]
    official = is_eligible(cart_t, min(purch) if purch else None, min(post_ev) if post_ev else None)
    assert official is expected_eligible
    assert (build_session_profile(events) is not None) is official
