# trigger.py — Definição oficial e única do critério de disparo da predição.

#   1. 1º evento cart com N ≥ MIN_EVENTS_BEFORE_TRIGGER eventos até ele (inclusive)
#   2. nenhum purchase em (-inf, t_cart + T_WINDOW]   -> senão a sessão converteu; trigger cancelado
#   3. ≥ 1 evento (view/cart) em (t_cart, t_cart + T_WINDOW]  -> senão o usuário saiu; sem canal in-session

from datetime import datetime
from typing import Optional

T_WINDOW: float = 120.0            # segundos após o 1º cart
MIN_EVENTS_BEFORE_TRIGGER: int = 5
REQUIRE_ACTIVITY: bool = True      # exige >=1 evento pós-cart dentro da janela

# Motivos de não-elegibilidade — usados por StreamSimulator.metrics e pela avaliação
REASON_PURCHASED = "purchased_within_window"
REASON_USER_LEFT = "user_left"
REASON_TOO_SHORT = "too_few_pre_cart_events"


# exemplo: 
# cart_time = 14:30:00 purchase_time = 14:31:00 -> ineligibility_reason(cart_time, purchase_time, None) = REASON_PURCHASED
# cart_time = 14:30:00 first_post_event_time= 14:33:00 -> ineligibility_reason(cart_time, None, first_post_event_time) = REASON_USER_LEFT
# cart_time = 14:30:00 first_post_event_time= None -> ineligibility_reason(cart_time, None, first_post_event_time) = REASON_USER_LEFT

def is_eligible(
    cart_time: datetime,
    purchase_time: Optional[datetime],
    first_post_event_time: Optional[datetime],
    t_window: float = T_WINDOW,
    require_activity: bool = REQUIRE_ACTIVITY,
) -> bool:
    # bool conveniente para quem só quer sim/não; o motivo detalhado é quem importa
    # pras métricas (StreamSimulator.metrics agrupa por REASON_*)
    return ineligibility_reason(cart_time, purchase_time, first_post_event_time, t_window, require_activity) is None

def ineligibility_reason(
    cart_time: datetime,
    purchase_time: Optional[datetime],
    first_post_event_time: Optional[datetime],
    t_window: float = T_WINDOW,
    require_activity: bool = REQUIRE_ACTIVITY,
) -> Optional[str]:
    # Retorna None se elegível; caso contrário, retorna o motivo de não-elegibilidade.
    if purchase_time is not None and _is_time(purchase_time):
        if (purchase_time - cart_time).total_seconds() <= t_window: # converteu dentro da janela de 120s
            return REASON_PURCHASED
    # checado depois da compra de propósito: se comprou rápido, o motivo certo é
    # REASON_PURCHASED, não REASON_USER_LEFT — mesmo sem nenhum evento pós-cart
    if require_activity:
        if first_post_event_time is None or not _is_time(first_post_event_time): # sem evento pós-cart
            return REASON_USER_LEFT 
        delta = (first_post_event_time - cart_time).total_seconds()
        if not (0 < delta <= t_window):   #  após o cart e dentro da janela de 120s
            return REASON_USER_LEFT
    return None

def _is_time(value) -> bool:
    # True para datetime/Timestamp válidos; False para None/NaT.
    try:
        return value == value  # NaT != NaT
    except Exception:
        return False
