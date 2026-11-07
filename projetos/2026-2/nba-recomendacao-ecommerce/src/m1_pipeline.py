# Módulo M1: Pipeline de Extração Incremental de Features de Sessão.

# Processa a sequência temporal de eventos de uma sessão de navegação,
# valida a elegibilidade oficial de disparo e constrói o SessionProfile

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean
from typing import Optional

from src.interfaces import SessionProfile
from src.trigger import MIN_EVENTS_BEFORE_TRIGGER, REQUIRE_ACTIVITY, T_WINDOW, is_eligible


@dataclass
class Event:
    event_time: datetime
    event_type: str           # 'view', 'cart' ou 'purchase'
    product_id: int
    category_id: str          # Identificador categórico (consumido pelo M2)
    category_code: Optional[str]  # Taxonomia textual hierárquica (ex.: 'electronics.smartphone')
    brand: Optional[str]
    price: float
    user_id: int
    user_session: str


def build_session_profile(
    events: list[Event],
    t_window: float = T_WINDOW,
    require_activity: bool = REQUIRE_ACTIVITY,
) -> Optional[SessionProfile]:
    # Entradas:
        # events: Sequência de eventos da sessão.
        # t_window: Duração da janela de observação pós-cart em segundos (padrão: 120s).
        # require_activity: Exige atividade posterior ao cart para garantir usuário ativo in-session.

    # Saídas:
        # SessionProfile populado se a sessão for elegível; caso contrário, None.

    # Reordena defensivamente por timestamp: eventos fora de ordem (rede, replay de
    # CSV não ordenado) descolocariam o índice do 1º cart e todo o corte pré/pós.
    events = sorted(events, key=lambda e: e.event_time)

    # Identifica o 1º evento 'cart' (ponto de disparo do pipeline)
    trigger_idx = next(
        (i for i, e in enumerate(events) if e.event_type == "cart"), None
    )

    # Rejeição: sem cart não há abandono de carrinho
    if trigger_idx is None:
        return None
    # Histórico mínimo pré-disparo: evita avaliar sessões excessivamente curtas
    if trigger_idx < MIN_EVENTS_BEFORE_TRIGGER - 1:
        return None

    pre = events[: trigger_idx + 1]
    cart_event = pre[-1]
    cart_time = cart_event.event_time
    window_cutoff = cart_time + timedelta(seconds=t_window)  # limite dos T=120s

    # Janela pós-cart (cart_time, cart_time + T]: estritamente posterior ao cart.
    # Eventos com timestamp idêntico ao cart (duplicatas) não contam como atividade pós-cart.
    # 'purchase' é excluído propositalmente para evitar data leakage da variável-alvo (y).
    post = [
        e for e in events[trigger_idx + 1 :]
        if cart_time < e.event_time <= window_cutoff and e.event_type != "purchase"
    ]

    purchase_times = [e.event_time for e in events if e.event_type == "purchase"]
    if not is_eligible(
        cart_time,
        min(purchase_times) if purchase_times else None,
        post[0].event_time if post else None,
        t_window,
        require_activity,
    ):
        return None

    # Separa 'pre' por tipo — as features abaixo usam só um dos dois subconjuntos
    views = [e for e in pre if e.event_type == "view"]
    carts = [e for e in pre if e.event_type == "cart"]  # o evento que define o trigger
    # (features pré-cart usam só este subconjunto — cart_items, abaixo, agrega também
    # os carts da janela pós-cart)

    #  Features pré-cart: comportamento de navegação 
    cart_view_ratio = len(carts) / max(len(views), 1)  # Intensidade de conversão prévia
    n_categories = len({e.category_id for e in pre})   # Dispersão de categorias exploradas
    nav_depth = len({e.product_id for e in views})      # Variedade de produtos visualizados

    # Dinâmica temporal da navegação prévia
    duration = (pre[-1].event_time - pre[0].event_time).total_seconds()
    gaps = [
        (pre[i + 1].event_time - pre[i].event_time).total_seconds()
        for i in range(len(pre) - 1)
    ]
    inter_event_time_mean = mean(gaps) if gaps else 0.0

    # Cesta de compras para filtrar regras no M4: categorias de todos os eventos cart até o gatilho (pre) mais os da janela pós-carrinho (post).
    
    post_carts = [e for e in post if e.event_type == "cart"]
    cart_items = frozenset(e.category_id for e in carts) | frozenset(e.category_id for e in post_carts)
    brands = [e.brand for e in pre if e.brand]
    dominant_brand = Counter(brands).most_common(1)[0][0] if brands else "unknown"

    #  Features pré-cart: contexto do item adicionado 
    cart_item_price = cart_event.price
    views_of_cart_item = sum(1 for e in views if e.product_id == cart_event.product_id)

    # Disparidade de preço: compara o item adicionado com os itens navegados previamente
    prices_viewed = [e.price for e in views if e.price > 0]
    mean_price_viewed = mean(prices_viewed) if prices_viewed else cart_item_price
    price_ratio = cart_item_price / mean_price_viewed if mean_price_viewed > 0 else 1.0

    hour_of_day = cart_event.event_time.hour

    # Extrai o nível superior da categoria (ex.: 'electronics' de 'electronics.smartphone')
    raw_category = cart_event.category_code or ""
    cart_item_category_top = raw_category.split(".")[0] if raw_category else "unknown"
    cart_item_brand = cart_event.brand or "unknown"

    #  Features pós-cart: dinâmica de hesitação e busca contínua 
    post_views = [e for e in post if e.event_type == "view"]

    n_events_after_cart = len(post)
    n_views_after_cart = len(post_views)
    n_categories_after_cart = len({e.category_id for e in post_views})
    # Latência até a 1ª ação pós-cart (se sem eventos, penaliza com o teto da janela)
    idle_time_after_cart = (
        (post[0].event_time - cart_time).total_seconds() if post else t_window
    )

    return SessionProfile(
        user_session=events[0].user_session,
        cart_items=cart_items,
        cart_view_ratio=cart_view_ratio,
        n_categories=n_categories,
        session_duration=duration,
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
        n_pre_cart_events=len(pre),
    )
