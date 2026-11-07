from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class SessionProfile:
    # Perfil comportamental de uma sessão.
    # Features pré-cart: calculadas sobre eventos até o 1º cart (inclusive).
    # Features pós-cart: calculadas sobre eventos em (cart_time, cart_time + T]
    user_session: str
    cart_items: frozenset[str]
    # --- features pré-cart: comportamentais ---
    cart_view_ratio: float
    n_categories: int
    session_duration: float
    inter_event_time_mean: float
    nav_depth: int
    dominant_brand: str
    # --- features pré-cart: item no carrinho ---
    cart_item_price: float
    views_of_cart_item: int
    price_ratio: float
    hour_of_day: int
    cart_item_category_top: str
    cart_item_brand: str
    # --- features pós-cart (janela T=120s) ---
    n_events_after_cart: int
    n_views_after_cart: int
    n_categories_after_cart: int
    idle_time_after_cart: float
    # --- metadado para avaliação segmentada ---
    n_pre_cart_events: int


@dataclass
class RuleSet:
    # Regras de associação produzidas pelo FP-Growth, ordenadas por lift decrescente.
    rules: pd.DataFrame  

@dataclass
class AbandonScore:
    # Probabilidade de abandono e vetor SHAP produzidos pelo LightGBM.
    p_abandon: float
    shap_values: np.ndarray

@dataclass
class NBAAction:
    # Ação recomendada pelo motor NBA para uma sessão.
    action: str
    p_abandon: float
    consequent: Optional[frozenset]
    recommended_product_id: Optional[int]
    nba_score: Optional[float]
    shap_values: Optional[np.ndarray]
    dominant_feature: Optional[str]
    intervention_message: Optional[str]
