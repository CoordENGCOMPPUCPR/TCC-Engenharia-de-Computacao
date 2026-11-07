# m4_nba.py — Motor de decisão Next Best Action.

import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.interfaces import AbandonScore, NBAAction, RuleSet, SessionProfile
from src.product_lookup import resolve_product

STRONG_TOP_FRAC = 0.20   # theta1: intervenção forte (cupom) para o quintil de maior risco
ACTION_TOP_FRAC = 0.50   # theta2: alguma ação para a metade de maior risco

THRESHOLDS_PATH = Path(__file__).parent.parent / "dataset" / "thresholds.json"
_CACHE: Optional[tuple[float, float]] = None


def calibrate_thresholds(
    p_abandon_oof: np.ndarray,
    strong_top_frac: float = STRONG_TOP_FRAC,
    action_top_frac: float = ACTION_TOP_FRAC,
) -> dict:
    # Deriva θ₁/θ₂ dos percentis da distribuição out-of-fold de p_abandon (treino).
    p = np.asarray(p_abandon_oof, dtype=float)
    theta_1 = float(np.quantile(p, 1 - strong_top_frac))
    theta_2 = float(np.quantile(p, 1 - action_top_frac))
    assert theta_2 <= theta_1, "θ₂ deve ser ≤ θ₁"
    return {
        "theta_1": theta_1, "theta_2": theta_2,
        "strong_top_frac": strong_top_frac, "action_top_frac": action_top_frac,
        "n_calibration": int(len(p)), "method": "percentil da distribuição OOF de p_abandon (outubro)",
    }


def load_thresholds(path: Path = THRESHOLDS_PATH) -> tuple[float, float]:
    # (theta1, theta2) do artefato calibrado. Falha se ausente — nunca assume padrão.
    if not path.exists():
        raise FileNotFoundError(
            f"thresholds.json não encontrado em {path.parent}/. "
            "Execute `python -m src.train` para gerar os limiares calibrados antes "
            "de usar o motor de decisão."
        )
    d = json.loads(path.read_text(encoding="utf-8"))
    return float(d["theta_1"]), float(d["theta_2"])


def thresholds(path: Path = THRESHOLDS_PATH) -> tuple[float, float]:
    # (theta1, theta2) com cache — ponto único de acesso aos limiares dentro do módulo.
    global _CACHE
    if _CACHE is None:
        _CACHE = load_thresholds(path)
    return _CACHE


def __getattr__(name: str):
    # Resolve THETA_1/THETA_2 sob demanda (PEP 562).

    # Mantém o módulo importável sem o artefato — necessário para o train.py que o gera
    if name in ("THETA_1", "THETA_2"):
        return thresholds()[0 if name == "THETA_1" else 1]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

_MESSAGES = {
    "strong_intervention": (
        "Notamos que você ainda não finalizou sua compra. "
        "Que tal um cupom especial para ajudar na decisão?"
    ),
    "moderate_intervention": (
        "Você pode gostar também de outros produtos relacionados. "
        "Confira nossas sugestões!"
    ),
    "no_intervention": "",
}


def decide(
    profile: SessionProfile,
    abandon_score: AbandonScore,
    ruleset: RuleSet,
    lookup: pd.DataFrame,
) -> NBAAction:
    # Integra M2 e M3 para produzir a NBAAction recomendada.

    # Fluxo de decisão:
    # 1. Determina o nível de intervenção pelo p_abandon (theta1, theta2)
    # 2. Filtra regras cujo antecedente está no carrinho
    # 3. Calcula nba_score = lift × confidence
    # 4. Seleciona a regra de maior score e resolve produto via lookup
   
    theta_1, theta_2 = thresholds()
    p = abandon_score.p_abandon

    if p >= theta_1:
        action = "strong_intervention"
    elif p >= theta_2:
        action = "moderate_intervention"
    else:
        return NBAAction(
            action="no_intervention",
            p_abandon=p,
            consequent=None,
            recommended_product_id=None,
            nba_score=None,
            shap_values=abandon_score.shap_values,
            dominant_feature=_dominant_feature(abandon_score),
            intervention_message=_MESSAGES["no_intervention"],
        )

    from src.m2_association import filter_rules_for_session
    applicable = filter_rules_for_session(ruleset, profile.cart_items)

    consequent: Optional[frozenset] = None
    recommended_product_id: Optional[int] = None
    nba_score: Optional[float] = None

    if not applicable.empty:
        applicable = applicable.copy()
        applicable["nba_score"] = applicable["lift"] * applicable["confidence"]
        best = applicable.sort_values("nba_score", ascending=False).iloc[0]
        consequent = frozenset(best["consequents"])
        nba_score = float(best["nba_score"])

        # resolve o consequente para produto concreto — para nas 4 regras atuais
        # (1 categoria no consequente), mas suporta consequente composto em tese
        for cat_id in consequent:
            pid = resolve_product(cat_id, lookup)
            if pid is not None:
                recommended_product_id = pid
                break

    return NBAAction(
        action=action,
        p_abandon=p,
        consequent=consequent,
        recommended_product_id=recommended_product_id,
        nba_score=nba_score,
        shap_values=abandon_score.shap_values,
        dominant_feature=_dominant_feature(abandon_score),
        intervention_message=_MESSAGES[action],
    )


def _dominant_feature(abandon_score: AbandonScore) -> str:
    # Feature de maior |SHAP| na sessão — campo de explicabilidade/auditoria.
    from src.m3_classifier import FEATURE_NAMES
    idx = int(np.argmax(np.abs(abandon_score.shap_values)))
    return FEATURE_NAMES[idx]
