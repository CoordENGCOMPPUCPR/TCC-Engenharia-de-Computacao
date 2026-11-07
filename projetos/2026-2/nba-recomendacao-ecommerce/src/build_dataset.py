# build_dataset.py — Carrega eventos do CSV e constrói SessionProfiles rotulados para treino.
#
# O CSV é lido em três passos para caber em 16 GB de RAM.

import gc
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.interfaces import SessionProfile  # noqa: E402
from src.m1_pipeline import Event, build_session_profile  # noqa: E402
from src.trigger import REQUIRE_ACTIVITY, T_WINDOW, is_eligible  # noqa: E402

CHUNK_SIZE = 500_000
COLS = [
    "event_time", "event_type", "product_id", "category_id", "category_code",
    "brand", "price", "user_id", "user_session",
]


def load_labeled_profiles(
    csv_path: str,
    nrows: Optional[int] = None,
) -> tuple[list[SessionProfile], list[int]]: # Lê CSV, aplica M1 e rotula abandono.
    
    # 1 = sessão com cart sem purchase (abandono)
    # 0 = sessão com cart e purchase após a janela (conversão tardia)
    # Sessões inelegíveis são descartadas.
    # Retorna (profiles, labels) com mesma ordem.
    path = str(csv_path)

    # Passo 1: lê só 2 colunas para achar as sessões com cart e as com purchase (~300 MB)
    cart_sessions: set[str] = set()
    purchase_sessions: set[str] = set()
    rows_seen = 0

    for chunk in pd.read_csv(path, usecols=["event_type", "user_session"], chunksize=CHUNK_SIZE):
        cart_sessions.update(
            chunk.loc[chunk["event_type"] == "cart", "user_session"].astype(str)
        )
        purchase_sessions.update(
            chunk.loc[chunk["event_type"] == "purchase", "user_session"].astype(str)
        )
        rows_seen += len(chunk)
        if nrows and rows_seen >= nrows:
            break

    gc.collect()

    # Passo 2: carrega só os eventos das sessões com cart, com dtypes compactos (~500 MB)
    # category dtype para colunas de baixa cardinalidade: ~1-2 bytes/valor vs ~50 bytes/objeto
    chunks: list[pd.DataFrame] = []
    rows_seen = 0

    for chunk in pd.read_csv(path, usecols=COLS, chunksize=CHUNK_SIZE):
        rows_seen += len(chunk)
        chunk = chunk[chunk["user_session"].astype(str).isin(cart_sessions)]
        if not chunk.empty:
            chunk["event_type"] = chunk["event_type"].astype("category")
            chunks.append(chunk)
        if nrows and rows_seen >= nrows:
            break

    df = pd.concat(chunks, ignore_index=True)
    del chunks
    gc.collect()

    df["event_time"] = pd.to_datetime(df["event_time"], utc=True).dt.tz_localize(None)
    df["user_session"] = df["user_session"].astype(str)
    df = df.sort_values("event_time")

    # Passo 3: agrupa por sessão, converte para Event e constrói um perfil por vez
    profiles: list[SessionProfile] = []
    labels: list[int] = []

    for session_id, group in df.groupby("user_session", sort=False):
        session_id = str(session_id)
        events = _rows_to_events(group, session_id)
        profile = build_session_profile(events)
        if profile is None:
            continue
        profiles.append(profile)
        # rótulo OFFLINE: compra em QUALQUER momento da sessão completa (não só na janela de 120s) -> sempre conversão tardia aqui, nunca a que o trigger já filtrou
        labels.append(0 if session_id in purchase_sessions else 1)

    del df
    gc.collect()

    return profiles, labels


def is_scored_in_production(
    cart_time: pd.Timestamp,
    purchase_time: Optional[pd.Timestamp],
    first_post_event_time: Optional[pd.Timestamp] = None,
    t_window: float = T_WINDOW,
) -> bool:
    #Delegado à definição oficial em src/trigger.py (mesma regra do StreamSimulator).
    return is_eligible(cart_time, purchase_time, first_post_event_time, t_window, REQUIRE_ACTIVITY)


def session_trigger_times(csv_path: str) -> pd.DataFrame:
    #Para cada sessão com cart: 1º cart, 1º purchase e 1º evento não-purchase após o cart.
    
    cart_sessions: set[str] = set()
    for chunk in pd.read_csv(csv_path, usecols=["event_type", "user_session"], chunksize=CHUNK_SIZE):
        cart_sessions.update(chunk.loc[chunk["event_type"] == "cart", "user_session"].astype(str))

    parts = []
    for chunk in pd.read_csv(csv_path, usecols=["event_time", "event_type", "user_session"],
                             dtype={"user_session": str}, chunksize=CHUNK_SIZE):
        parts.append(chunk[chunk["user_session"].isin(cart_sessions)])
    df = pd.concat(parts, ignore_index=True)
    del parts
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True).dt.tz_localize(None)

    cart_t = (df[df["event_type"] == "cart"].groupby("user_session")["event_time"].min()
              .rename("cart_time"))
    purch_t = (df[df["event_type"] == "purchase"].groupby("user_session")["event_time"].min()
               .rename("purchase_time"))
    non_purchase = df[df["event_type"] != "purchase"].join(cart_t, on="user_session")
    post = non_purchase[non_purchase["event_time"] > non_purchase["cart_time"]]
    first_post = post.groupby("user_session")["event_time"].min().rename("first_post_event_time")

    out = pd.concat([cart_t, purch_t, first_post], axis=1).dropna(subset=["cart_time"])
    gc.collect()
    return out


def production_population_mask(
    profiles: list[SessionProfile],
    trigger_times: pd.DataFrame,
    t_window: float = T_WINDOW,
) -> np.ndarray:
    #Máscara booleana: True para perfis elegíveis segundo src/trigger.is_eligible,
    #calculada a partir dos instantes reais da sessão (independente do M1).
    return np.array([
        is_eligible(
            trigger_times.at[p.user_session, "cart_time"],
            trigger_times.at[p.user_session, "purchase_time"],
            trigger_times.at[p.user_session, "first_post_event_time"],
            t_window, REQUIRE_ACTIVITY,
        )
        for p in profiles
    ])


def assert_official_trigger_population(
    profiles: list[SessionProfile],
    trigger_times: pd.DataFrame,
    t_window: float = T_WINDOW,
) -> None:
    #Trava: todo perfil produzido pelo M1 deve ser elegível pela definição oficial.
    mask = production_population_mask(profiles, trigger_times, t_window)
    if not mask.all():
        bad = [p.user_session for p, m in zip(profiles, mask) if not m][:5]
        raise AssertionError(
            f"{(~mask).sum():,} perfis fora da população oficial de disparo "
            f"(T={t_window:.0f}s, atividade={REQUIRE_ACTIVITY}); ex.: {bad}"
        )


def _rows_to_events(group: pd.DataFrame, session_id: str) -> list[Event]:
    #Converte linhas de um grupo (1 sessão) em lista de Event.
    times = group["event_time"].dt.to_pydatetime()  # ndarray de datetime — tipo resolvido
    events = []
    for i, row in enumerate(group.itertuples(index=False)):
        brand = str(row.brand) if pd.notna(row.brand) else None
        category_code = str(row.category_code) if pd.notna(row.category_code) else None
        events.append(Event(
            event_time=times[i],
            event_type=str(row.event_type),
            product_id=int(row.product_id),  # type: ignore
            category_id=str(row.category_id),
            category_code=category_code,
            brand=brand,
            price=float(row.price),  # type: ignore
            user_id=int(row.user_id),  # type: ignore
            user_session=session_id,
        ))
    return events


if __name__ == "__main__":
    import time

    csv_path = Path(__file__).parent.parent / "dataset" / "2019-Oct.csv"
    print(f"Carregando outubro completo de {csv_path.name}...")

    t0 = time.time()
    profiles, labels = load_labeled_profiles(str(csv_path))
    elapsed = time.time() - t0

    n_abandon = sum(labels)
    n_convert = len(labels) - n_abandon
    print(f"\nPronto em {elapsed:.1f}s")
    print(f"  Sessões com perfil válido (N≥5): {len(profiles):,}")
    print(f"  Abandono (label=1):              {n_abandon:,} ({n_abandon/len(labels)*100:.1f}%)")
    print(f"  Conversão (label=0):             {n_convert:,} ({n_convert/len(labels)*100:.1f}%)")
