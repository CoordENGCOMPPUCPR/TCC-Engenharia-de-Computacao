# trigger_sweep_low_t.py — Varredura do critério de disparo, com a mesma configuração
# do classificador de m3_classifier.py. Cada execução avalia um valor de T.
#
# Uso:   python3 -m src.analysis.trigger_sweep_low_t 30
# Saída: dataset/trigger_sweep_T30.json

import gc
import json
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.m1_pipeline import Event, build_session_profile
from src.m3_classifier import (
    _BASE_PARAMS, CATEGORICAL_FEATURES, build_brand_vocab, cross_val_oof_predict,
    profiles_to_features,
)

DATASET_DIR = Path(__file__).parent.parent.parent / "dataset"
OCT_CSV = DATASET_DIR / "2019-Oct.csv"
NOV_CSV = DATASET_DIR / "2019-Nov.csv"
CHUNK_SIZE = 500_000
COLS = [
    "event_time", "event_type", "product_id", "category_id", "category_code",
    "brand", "price", "user_id", "user_session",
]
MIN_EVENTS_BEFORE_TRIGGER = 5


def _rows_to_events(group: pd.DataFrame, session_id: str) -> list[Event]:
    times = group["event_time"].dt.to_pydatetime()
    events = []
    for i, row in enumerate(group.itertuples(index=False)):
        brand = str(row.brand) if pd.notna(row.brand) else None
        category_code = str(row.category_code) if pd.notna(row.category_code) else None
        events.append(Event(
            event_time=times[i], event_type=str(row.event_type),
            product_id=int(row.product_id), category_id=str(row.category_id),
            category_code=category_code, brand=brand, price=float(row.price),
            user_id=int(row.user_id), user_session=session_id,
        ))
    return events


def _load_session_groups(csv_path: Path):
    # Carrega os eventos das sessões com ao menos um cart, ordenados por tempo.
    cart_sessions: set[str] = set()
    for chunk in pd.read_csv(csv_path, usecols=["event_type", "user_session"], chunksize=CHUNK_SIZE):
        cart_sessions.update(chunk.loc[chunk["event_type"] == "cart", "user_session"].astype(str))

    chunks = []
    for chunk in pd.read_csv(csv_path, usecols=COLS, chunksize=CHUNK_SIZE):
        chunk = chunk[chunk["user_session"].astype(str).isin(cart_sessions)]
        if not chunk.empty:
            chunk["event_type"] = chunk["event_type"].astype("category")
            chunks.append(chunk)
    df = pd.concat(chunks, ignore_index=True)
    del chunks
    gc.collect()
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True).dt.tz_localize(None)
    df["user_session"] = df["user_session"].astype(str)
    df = df.sort_values("event_time")
    return df, cart_sessions


def build_profiles_for_t(df: pd.DataFrame, purchase_sessions: set[str],
                          t_window: float, require_activity: bool):
    profiles, labels = [], []
    for session_id, group in df.groupby("user_session", sort=False):
        session_id = str(session_id)
        events = _rows_to_events(group, session_id)
        profile = build_session_profile(events, t_window=t_window, require_activity=require_activity)
        if profile is None:
            continue
        profiles.append(profile)
        labels.append(0 if session_id in purchase_sessions else 1)
    return profiles, labels


def count_n5_denominator(df: pd.DataFrame) -> int:
    # Sessões de novembro com carrinho e N >= 5 eventos até o 1º cart, inclusive
    # (independe de T e da atividade: só checa a posição do 1º cart na sessão).
    count = 0
    for session_id, group in df.groupby("user_session", sort=False):
        ev_types = group["event_type"].tolist()
        try:
            idx = ev_types.index("cart")
        except ValueError:
            continue
        if idx >= MIN_EVENTS_BEFORE_TRIGGER - 1:
            count += 1
    return count


def main():
    t_window = float(sys.argv[1])
    t0 = time.time()

    print(f"=== Varredura T={t_window:.0f}s + atividade ===")
    print("Carregando outubro...")
    df_oct, cart_oct = _load_session_groups(OCT_CSV)
    purchase_oct: set[str] = set()
    for chunk in pd.read_csv(OCT_CSV, usecols=["event_type", "user_session"], chunksize=CHUNK_SIZE):
        purchase_oct.update(chunk.loc[chunk["event_type"] == "purchase", "user_session"].astype(str))
    print(f"  {time.time()-t0:.0f}s")

    # população de disparo de outubro com este T
    print("Construindo perfis de outubro...")
    t1 = time.time()
    profiles_oct, labels_oct = build_profiles_for_t(df_oct, purchase_oct, t_window, True)
    y_oct = np.array(labels_oct)
    del df_oct
    gc.collect()
    print(f"  {time.time()-t1:.0f}s | {len(profiles_oct):,} sessoes | abandono {y_oct.mean()*100:.1f}%")

    # AUC CV (out): validação cruzada 5-fold out-of-fold, como no M3
    print("CV 5-fold OOF...")
    t2 = time.time()
    oof = cross_val_oof_predict(profiles_oct, labels_oct, n_splits=5, seed=42)
    auc_cv = roc_auc_score(y_oct, oof)
    print(f"  {time.time()-t2:.0f}s | AUC CV (out) = {auc_cv:.4f}")

    # modelo treinado em outubro inteiro, avaliado depois em novembro com o mesmo T
    print("Treinando modelo completo em outubro...")
    t3 = time.time()
    vocab = build_brand_vocab(profiles_oct)
    X_oct = profiles_to_features(profiles_oct, vocab)
    model = lgb.LGBMClassifier(**_BASE_PARAMS)
    model.fit(X_oct, y_oct, categorical_feature=CATEGORICAL_FEATURES)
    print(f"  {time.time()-t3:.0f}s")

    print("Carregando novembro...")
    t4 = time.time()
    df_nov, cart_nov = _load_session_groups(NOV_CSV)
    purchase_nov: set[str] = set()
    for chunk in pd.read_csv(NOV_CSV, usecols=["event_type", "user_session"], chunksize=CHUNK_SIZE):
        purchase_nov.update(chunk.loc[chunk["event_type"] == "purchase", "user_session"].astype(str))
    print(f"  {time.time()-t4:.0f}s")

    # população de disparo de novembro com este T e denominador do % disparo
    print("Construindo perfis de novembro (para este T) e denominador N>=5...")
    t5 = time.time()
    profiles_nov, labels_nov = build_profiles_for_t(df_nov, purchase_nov, t_window, True)
    y_nov = np.array(labels_nov)
    denom_n5 = count_n5_denominator(df_nov)
    del df_nov
    gc.collect()
    print(f"  {time.time()-t5:.0f}s | {len(profiles_nov):,} sessoes elegiveis | denom N>=5 = {denom_n5:,}")

    print("Avaliando sobre novembro...")
    X_nov = profiles_to_features(profiles_nov, vocab)
    p_nov = model.predict_proba(X_nov)[:, 1]
    auc_nov = roc_auc_score(y_nov, p_nov)

    # % disparo: sessões que atingem o disparo / sessões com cart e N >= 5 (mesmo denominador
    # para todo T). % abandono: taxa de abandono da população de disparo de novembro.
    pct_disparo = len(profiles_nov) / denom_n5 * 100
    pct_abandono_nov = y_nov.mean() * 100

    result = {
        "t_window_s": t_window, "require_activity": True,
        "n_oct": len(profiles_oct), "auc_cv_out": round(float(auc_cv), 4),
        "n_nov": len(profiles_nov), "denom_n5_nov": denom_n5,
        "pct_disparo": round(pct_disparo, 1),
        "pct_abandono_nov": round(pct_abandono_nov, 1),
        "auc_nov": round(float(auc_nov), 4),
    }
    print("\n=== RESULTADO ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    out_path = DATASET_DIR / f"trigger_sweep_T{int(t_window)}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSalvo em {out_path}")
    print(f"Tempo total: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
