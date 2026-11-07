# pipeline_demo.py — Demo end-to-end: carrega artefatos e roda o pipeline em até 5 sessões de novembro.
#
# Fluxo: CSV novembro → amostra sessões → M1 → M3 (AbandonScore) → M2 filter → M4 (NBAAction)
#
# Uso: python3 -m src.analysis.pipeline_demo

import pickle
import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.m1_pipeline import Event, build_session_profile
from src.m3_classifier import predict_abandon_score
from src.m4_nba import decide
from src.m2_association import validate_ruleset_types
from src.product_lookup import load_lookup

DATASET_DIR = Path(__file__).parent.parent.parent / "dataset"
NOV_CSV = DATASET_DIR / "2019-Nov.csv"
LOOKUP_PATH = DATASET_DIR / "product_lookup.parquet"
RULESET_PATH = DATASET_DIR / "ruleset.pkl"
MODEL_PATH = DATASET_DIR / "model.lgb"
VOCAB_PATH = DATASET_DIR / "brand_vocab.pkl"

SAMPLE_ROWS = 500_000
RANDOM_SEED = 42


def _load_november_sessions(n_rows: int) -> dict[str, list[Event]]:
    cols = ["event_time", "event_type", "product_id", "category_id",
            "category_code", "brand", "price", "user_id", "user_session"]
    df = pd.read_csv(str(NOV_CSV), usecols=cols, nrows=n_rows)
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True).dt.tz_localize(None)

    sessions: dict[str, list[Event]] = {}
    for r in df.to_dict("records"):
        raw_brand = r["brand"]
        brand = str(raw_brand) if pd.notna(raw_brand) else None
        raw_cat = r.get("category_code")
        category_code = str(raw_cat) if pd.notna(raw_cat) else None

        e = Event(
            event_time=r["event_time"].to_pydatetime() if hasattr(r["event_time"], "to_pydatetime") else r["event_time"],
            event_type=str(r["event_type"]),
            product_id=int(r["product_id"]),
            category_id=str(r["category_id"]),
            category_code=category_code,
            brand=brand,
            price=float(r["price"]),
            user_id=int(r["user_id"]),
            user_session=str(r["user_session"]),
        )
        sessions.setdefault(str(r["user_session"]), []).append(e)
    return sessions


def main():
    print("=== Pipeline NBA — demo novembro 2019 ===\n")

    # --- carrega artefatos ---
    print("Carregando artefatos...")
    lookup = load_lookup(str(LOOKUP_PATH))
    with open(RULESET_PATH, "rb") as f:
        ruleset = pickle.load(f)
    validate_ruleset_types(ruleset)
    import lightgbm as lgb
    import shap
    model = lgb.Booster(model_str=Path(MODEL_PATH).read_text(encoding="utf-8"))
    explainer = shap.TreeExplainer(model)
    with open(VOCAB_PATH, "rb") as f:
        brand_vocab = pickle.load(f)
    print(f"  RuleSet: {len(ruleset.rules)} regras")
    print(f"  Lookup:  {len(lookup):,} categorias")

    # --- carrega sessões de novembro ---
    print(f"\nCarregando {SAMPLE_ROWS:,} eventos de novembro...")
    sessions = _load_november_sessions(SAMPLE_ROWS)
    print(f"  {len(sessions):,} sessões carregadas")

    # --- filtra sessões com cart e perfil válido ---
    valid = []
    purchases = set()
    for sid, events in sessions.items():
        if any(e.event_type == "purchase" for e in events):
            purchases.add(sid)
        profile = build_session_profile(events)
        if profile is not None:
            valid.append((sid, events, profile))

    print(f"  {len(valid):,} sessões na população de disparo")

    if not valid:
        print("Nenhuma sessão válida encontrada — aumente SAMPLE_ROWS.")
        return

    # --- roda pipeline em amostra aleatória de até 5 sessões ---
    random.seed(RANDOM_SEED)
    sample = random.sample(valid, min(5, len(valid)))

    print(f"\n{'='*60}")
    for sid, events, profile in sample:
        label = "CONVERSÃO" if sid in purchases else "ABANDONO"

        abandon_score = predict_abandon_score(profile, model, explainer, brand_vocab)
        action = decide(profile, abandon_score, ruleset, lookup)

        print(f"\nSessão: {sid}  [{label}]")
        print(f"  cart_items:            {set(profile.cart_items)}")
        print(f"  idle_time_after_cart:  {profile.idle_time_after_cart:.0f}s")
        print(f"  n_views_after_cart:    {profile.n_views_after_cart}")
        print(f"  p_abandon:             {abandon_score.p_abandon:.3f}")
        print(f"  dominant_feature:      {action.dominant_feature}")
        print(f"  action:                {action.action}")
        if action.consequent:
            print(f"  consequent:            {set(action.consequent)}")
            print(f"  recommended_product:   {action.recommended_product_id}")
            print(f"  nba_score:             {action.nba_score:.3f}")
        print(f"  message:               {action.intervention_message[:60]!r}")

    print(f"\n{'='*60}")
    print("Demo concluída.")


if __name__ == "__main__":
    main()
