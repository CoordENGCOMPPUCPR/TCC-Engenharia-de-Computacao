from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import pytest

from src.m1_pipeline import MIN_EVENTS_BEFORE_TRIGGER, Event, build_session_profile
from src.trigger import T_WINDOW  # definição oficial — os testes não redefinem T
from src.trigger import REASON_USER_LEFT, _is_time, ineligibility_reason


def make_event(
    offset_seconds: int,
    event_type: str,
    product_id: int = 1,
    category_id: str = "electronics",
    category_code: Optional[str] = "electronics.smartphone",
    brand: str = "apple",
    price: float = 999.0,
) -> Event:
    return Event(
        event_time=datetime(2019, 10, 1, 10, 0, 0) + timedelta(seconds=offset_seconds),
        event_type=event_type,
        product_id=product_id,
        category_id=category_id,
        category_code=category_code,
        brand=brand,
        price=price,
        user_id=1,
        user_session="s1",
    )


def make_session(
    event_types: list[str], brands: list[str] = None, post_view: bool = True
) -> list[Event]:
    """Sessão simples com eventos espaçados de 30 segundos.

    post_view=True acrescenta um view 30s após o último cart, tornando a sessão elegível
    sob a regra oficial (≥1 evento pós-cart em T). Use post_view=False para saída silenciosa.
    """
    brands = brands or ["apple"] * len(event_types)
    events = [
        make_event(i * 30, et, product_id=i + 1, brand=b)
        for i, (et, b) in enumerate(zip(event_types, brands))
    ]
    if post_view and "cart" in event_types:
        events.append(make_event(len(event_types) * 30, "view", product_id=99, brand=brands[-1]))
    return events


# --- Trigger conditions ---

class TestTriggerConditions:
    def test_returns_none_without_cart(self):
        events = make_session(["view", "view", "view", "view", "view"])
        assert build_session_profile(events) is None

    def test_returns_none_below_min_events(self):
        events = make_session(["view", "view", "view", "cart"])
        assert build_session_profile(events) is None

    def test_returns_none_cart_as_first_event(self):
        events = make_session(["cart", "view", "view", "view", "view"])
        assert build_session_profile(events) is None

    def test_triggers_with_exactly_min_events(self):
        events = make_session(["view", "view", "view", "view", "cart"])
        assert build_session_profile(events) is not None

    def test_triggers_above_min_events(self):
        events = make_session(["view", "view", "view", "view", "view", "cart"])
        assert build_session_profile(events) is not None


# --- Features pré-cart: sem data leakage ---

class TestIncrementalFeatures:
    def test_session_duration_only_up_to_cart(self):
        events = make_session(["view", "view", "view", "view", "cart", "view", "view"])
        profile = build_session_profile(events)
        assert profile.session_duration == pytest.approx(120.0)

    def test_nav_depth_excludes_post_cart_views(self):
        events = make_session(["view", "view", "view", "view", "cart", "view", "view"])
        profile = build_session_profile(events)
        assert profile.nav_depth == 4

    def test_n_categories_only_pre_trigger(self):
        events = [
            make_event(0,   "view", category_id="electronics"),
            make_event(30,  "view", category_id="computers"),
            make_event(60,  "view", category_id="phones"),
            make_event(90,  "view", category_id="tablets"),
            make_event(120, "cart", category_id="electronics"),
            make_event(150, "view", category_id="furniture"),
        ]
        profile = build_session_profile(events)
        assert profile.n_categories == 4

    def test_inter_event_time_mean_pre_trigger(self):
        events = make_session(["view", "view", "view", "view", "cart"])
        profile = build_session_profile(events)
        assert profile.inter_event_time_mean == pytest.approx(30.0)


# --- Features pré-cart: valores ---

class TestPreCartFeatureValues:
    @pytest.fixture
    def profile(self):
        return build_session_profile(make_session(["view", "view", "view", "view", "cart"]))

    def test_cart_items_contains_cart_category(self, profile):
        assert "electronics" in profile.cart_items
        assert isinstance(profile.cart_items, frozenset)

    def test_cart_view_ratio(self, profile):
        assert profile.cart_view_ratio == pytest.approx(0.25)

    def test_session_id(self, profile):
        assert profile.user_session == "s1"

    def test_cart_item_price(self):
        events = [
            make_event(0, "view", product_id=1, price=200.0),
            make_event(30, "view", product_id=2, price=300.0),
            make_event(60, "view", product_id=3, price=400.0),
            make_event(90, "view", product_id=4, price=100.0),
            make_event(120, "cart", product_id=5, price=799.0),
            make_event(150, "view", product_id=9),
        ]
        profile = build_session_profile(events)
        assert profile.cart_item_price == pytest.approx(799.0)

    def test_views_of_cart_item(self):
        events = [
            make_event(0,   "view", product_id=1),
            make_event(30,  "view", product_id=2),
            make_event(60,  "view", product_id=2),
            make_event(90,  "view", product_id=3),
            make_event(120, "cart", product_id=2),
            make_event(150, "view", product_id=9),
        ]
        profile = build_session_profile(events)
        assert profile.views_of_cart_item == 2

    def test_price_ratio_above_one_when_expensive(self):
        events = [
            make_event(0,   "view", product_id=1, price=200.0),
            make_event(30,  "view", product_id=2, price=200.0),
            make_event(60,  "view", product_id=3, price=200.0),
            make_event(90,  "view", product_id=4, price=200.0),
            make_event(120, "cart", product_id=5, price=1000.0),
            make_event(150, "view", product_id=9),
        ]
        profile = build_session_profile(events)
        assert profile.price_ratio == pytest.approx(5.0)

    def test_cart_item_category_top_extracted(self):
        events = [
            make_event(0,  "view", product_id=1, category_code="electronics.audio"),
            make_event(30, "view", product_id=2, category_code="electronics.audio"),
            make_event(60, "view", product_id=3, category_code="electronics.audio"),
            make_event(90, "view", product_id=4, category_code="electronics.audio"),
            make_event(120, "cart", product_id=5, category_code="electronics.smartphone"),
            make_event(150, "view", product_id=9),
        ]
        profile = build_session_profile(events)
        assert profile.cart_item_category_top == "electronics"

    def test_cart_item_brand_from_cart_event(self):
        brands = ["samsung", "samsung", "samsung", "samsung", "apple"]
        events = make_session(["view", "view", "view", "view", "cart"], brands=brands)
        profile = build_session_profile(events)
        assert profile.cart_item_brand == "apple"


# --- Dominant brand ---

class TestDominantBrand:
    def test_most_frequent_brand(self):
        brands = ["apple", "apple", "samsung", "apple", None]
        events = make_session(["view", "view", "view", "view", "cart"], brands=brands)
        assert build_session_profile(events).dominant_brand == "apple"

    def test_all_null_brands_returns_unknown(self):
        events = [make_event(i * 30, et, brand=None)
                  for i, et in enumerate(["view", "view", "view", "view", "cart", "view"])]
        assert build_session_profile(events).dominant_brand == "unknown"

    def test_null_cart_brand_becomes_unknown(self):
        events = [
            make_event(0,   "view", product_id=1, brand="apple"),
            make_event(30,  "view", product_id=2, brand="apple"),
            make_event(60,  "view", product_id=3, brand="apple"),
            make_event(90,  "view", product_id=4, brand="apple"),
            make_event(120, "cart", product_id=5, brand=None),
            make_event(150, "view", product_id=9),
        ]
        assert build_session_profile(events).cart_item_brand == "unknown"


# --- Features pós-cart ---

class TestPostCartFeatures:
    def _session(self, post_types: list[str], t_window: float = T_WINDOW) -> list[Event]:
        """4 views + cart no t=120 + eventos pós-cart espaçados de 30s."""
        base = [make_event(i * 30, "view", product_id=i + 1) for i in range(4)]
        cart = make_event(120, "cart", product_id=5)
        post = [
            make_event(120 + (i + 1) * 30, et, product_id=10 + i)
            for i, et in enumerate(post_types)
        ]
        return base + [cart] + post

    def test_n_events_after_cart(self):
        profile = build_session_profile(self._session(["view", "view"]))
        assert profile.n_events_after_cart == 2

    def test_user_exit_is_ineligible(self):
        # saída silenciosa: nenhum evento pós-cart em T → sem canal in-session → None
        events = make_session(["view", "view", "view", "view", "cart"], post_view=False)
        assert build_session_profile(events) is None

    def test_user_exit_profile_without_activity_requirement(self):
        events = make_session(["view", "view", "view", "view", "cart"], post_view=False)
        profile = build_session_profile(events, require_activity=False)
        assert profile.n_events_after_cart == 0

    def test_n_views_after_cart(self):
        # 2 views + 1 cart pós-trigger
        profile = build_session_profile(self._session(["view", "cart", "view"]))
        assert profile.n_views_after_cart == 2

    def test_n_categories_after_cart(self):
        events = [
            make_event(0,   "view", product_id=1, category_id="electronics"),
            make_event(30,  "view", product_id=2, category_id="electronics"),
            make_event(60,  "view", product_id=3, category_id="electronics"),
            make_event(90,  "view", product_id=4, category_id="electronics"),
            make_event(120, "cart", product_id=5, category_id="electronics"),
            make_event(150, "view", product_id=6, category_id="computers"),
            make_event(180, "view", product_id=7, category_id="phones"),
        ]
        profile = build_session_profile(events)
        assert profile.n_categories_after_cart == 2

    def test_idle_time_equals_t_window_when_no_events(self):
        profile = build_session_profile(
            make_session(["view", "view", "view", "view", "cart"], post_view=False),
            t_window=T_WINDOW, require_activity=False,
        )
        assert profile.idle_time_after_cart == pytest.approx(T_WINDOW)

    def test_idle_time_measured_from_cart(self):
        # cart em t=120, 1º pós-cart em t=150 → idle = 30s
        events = [
            make_event(0,   "view", product_id=1),
            make_event(30,  "view", product_id=2),
            make_event(60,  "view", product_id=3),
            make_event(90,  "view", product_id=4),
            make_event(120, "cart", product_id=5),
            make_event(150, "view", product_id=6),
        ]
        profile = build_session_profile(events, t_window=T_WINDOW)
        assert profile.idle_time_after_cart == pytest.approx(30.0)

    def test_purchase_within_window_cancels_trigger(self):
        # compra em T → sessão converteu sozinha; nunca é pontuada
        events = [
            make_event(0,   "view", product_id=1),
            make_event(30,  "view", product_id=2),
            make_event(60,  "view", product_id=3),
            make_event(90,  "view", product_id=4),
            make_event(120, "cart", product_id=5),
            make_event(150, "view", product_id=6),
            make_event(200, "purchase", product_id=5),
        ]
        assert build_session_profile(events) is None

    def test_purchase_after_window_keeps_session_and_is_excluded_from_features(self):
        events = [
            make_event(0,   "view", product_id=1),
            make_event(30,  "view", product_id=2),
            make_event(60,  "view", product_id=3),
            make_event(90,  "view", product_id=4),
            make_event(120, "cart", product_id=5),
            make_event(150, "view", product_id=6),
            make_event(120 + int(T_WINDOW) + 60, "purchase", product_id=5),
        ]
        profile = build_session_profile(events)
        assert profile is not None
        assert profile.n_events_after_cart == 1  # só o view; purchase nunca entra

    def test_events_outside_window_excluded(self):
        # 1º evento pós-cart só depois de T → usuário ausente durante a janela → inelegível
        events = [
            make_event(0,   "view", product_id=1),
            make_event(30,  "view", product_id=2),
            make_event(60,  "view", product_id=3),
            make_event(90,  "view", product_id=4),
            make_event(120, "cart", product_id=5),
            make_event(120 + int(T_WINDOW) + 100, "view", product_id=6),
        ]
        assert build_session_profile(events, t_window=T_WINDOW) is None
        profile = build_session_profile(events, t_window=T_WINDOW, require_activity=False)
        assert profile.n_events_after_cart == 0

    def test_cart_items_includes_post_cart_categories(self):
        # cart em "electronics" no trigger + um 2º cart em "furniture" na janela pós-cart
        events = [
            make_event(0,   "view", product_id=1, category_id="electronics"),
            make_event(30,  "view", product_id=2, category_id="electronics"),
            make_event(60,  "view", product_id=3, category_id="electronics"),
            make_event(90,  "view", product_id=4, category_id="electronics"),
            make_event(120, "cart", product_id=5, category_id="electronics"),
            make_event(150, "cart", product_id=6, category_id="furniture"),
        ]
        profile = build_session_profile(events)
        assert profile.cart_items == frozenset({"electronics", "furniture"})

    def test_pre_cart_features_unaffected_by_post_cart_cart_items(self):
        # mesma sessão pré-cart, com e sem um 2º cart na janela pós — features
        # pré-cart (que usam só 'pre') não podem mudar
        base = [
            make_event(0,   "view", product_id=1, category_id="electronics"),
            make_event(30,  "view", product_id=2, category_id="electronics"),
            make_event(60,  "view", product_id=3, category_id="electronics"),
            make_event(90,  "view", product_id=4, category_id="electronics"),
            make_event(120, "cart", product_id=5, category_id="electronics"),
        ]
        profile_sem = build_session_profile(base + [make_event(150, "view", product_id=6)])
        profile_com = build_session_profile(base + [make_event(150, "cart", product_id=6, category_id="furniture")])
        assert profile_sem is not None and profile_com is not None
        assert profile_sem.cart_view_ratio == profile_com.cart_view_ratio
        assert profile_sem.n_categories == profile_com.n_categories
        assert profile_sem.nav_depth == profile_com.nav_depth
        assert profile_sem.cart_items != profile_com.cart_items  # só cart_items diverge


# --- caixa branca: ramos de src/trigger.py ---

CART_TIME = datetime(2019, 10, 1, 10, 0, 0)


@pytest.mark.caixa_branca
class TestTriggerRamos:
    def test_ineligibility_reason_compra_nat_e_ignorada(self):
        # ramo `purchase_time is not None and _is_time(...)`: NaT não conta como compra
        post = CART_TIME + timedelta(seconds=30)
        assert ineligibility_reason(CART_TIME, pd.NaT, post) is None

    def test_ineligibility_reason_atividade_nat_e_user_left(self):
        # ramo `not _is_time(first_post_event_time)`: NaT equivale a nenhum evento pós-cart
        assert ineligibility_reason(CART_TIME, None, pd.NaT) == REASON_USER_LEFT

    def test_ineligibility_reason_limites_da_janela(self):
        # condição `0 < delta <= t_window`: o limite superior entra, o instante do cart não
        assert ineligibility_reason(CART_TIME, None, CART_TIME + timedelta(seconds=T_WINDOW)) is None
        assert ineligibility_reason(CART_TIME, None, CART_TIME) == REASON_USER_LEFT

    def test_is_time_comparacao_que_falha_retorna_false(self):
        # ramo `except Exception` de _is_time
        class ComparacaoQuebrada:
            def __eq__(self, other):
                raise TypeError("sem comparação")

        assert _is_time(ComparacaoQuebrada()) is False
