# replay_november.py — Alimenta o StreamSimulator com Nov CSV em ordem cronológica.
#
# Dois passos: (1) identifica sessões com cart (vetorizado), (2) processa só essas (~15%).
# Faz flush das sessões pendentes ao final. Salva métricas em replay_november_results.json.

import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.m1_pipeline import Event  # noqa: E402
from src.stream_simulator import StreamSimulator  # noqa: E402

DATASET_DIR = Path(__file__).parent.parent / "dataset"
COLS = [
    "event_time", "event_type", "product_id", "category_id",
    "category_code", "brand", "price", "user_id", "user_session",
]
CHUNK_SIZE = 500_000


def _find_cart_sessions(csv_path: Path) -> set[str]:
    # Passo 1: identifica sessões com pelo menos um evento cart (vetorizado, sem loop).
    print("Passo 1/2 — identificando sessões com cart...")
    cart_sessions: set[str] = set()
    for chunk in pd.read_csv(csv_path, usecols=["event_type", "user_session"], chunksize=CHUNK_SIZE):
        mask = chunk["event_type"] == "cart"
        cart_sessions.update(chunk.loc[mask, "user_session"].astype(str).tolist())
    print(f"  {len(cart_sessions):,} sessões com cart encontradas\n")
    return cart_sessions



def _to_event(record) -> Event:
    brand = str(record.brand) if pd.notna(record.brand) else None
    category_code = str(record.category_code) if pd.notna(record.category_code) else None
    return Event(
        event_time=record.event_time.to_pydatetime(),
        event_type=str(record.event_type),
        product_id=int(record.product_id),
        category_id=str(record.category_id),
        category_code=category_code,
        brand=brand,
        price=float(record.price),
        user_id=int(record.user_id),
        user_session=str(record.user_session),
    )


def _batch_shap(sim: "StreamSimulator") -> None:
    # Calcula SHAP em batch (explicabilidade/auditoria) para todas as sessões pontuadas.
    from src.m3_classifier import FEATURE_NAMES, profiles_to_features

    items = [
        (sid, state)
        for sid, state in sim._sessions.items()
        if state.triggered and state.profile is not None and state.action is not None
    ]
    if not items:
        return

    print(f"\nCalculando SHAP em batch para {len(items):,} sessões...")
    t0 = time.time()
    profiles = [state.profile for _, state in items]
    X = profiles_to_features(profiles, sim.brand_vocab)
    # UMA chamada matricial pra todas as sessões de uma vez (em vez de 1 por sessão)
    shap_vals = sim.explainer.shap_values(X)
    import numpy as np
    # mesmos 3 formatos possíveis de shap.TreeExplainer — ver m3_classifier.predict_abandon_score
    if isinstance(shap_vals, list):
        values = shap_vals[1]
    elif getattr(shap_vals, "ndim", 0) == 3:
        values = shap_vals[:, :, 1]
    else:
        values = shap_vals

    for i, (_, state) in enumerate(items):
        sv = np.array(values[i])
        state.action.shap_values = sv
        state.action.dominant_feature = FEATURE_NAMES[int(np.argmax(np.abs(sv)))]

    print(f"  SHAP batch concluído em {time.time()-t0:.1f}s")


def main():
    csv_path = DATASET_DIR / "2019-Nov.csv"
    if not csv_path.exists():
        print(f"Arquivo não encontrado: {csv_path}")
        sys.exit(1)

    print("Carregando artefatos de treino (outubro)...")
    sim = StreamSimulator(batch_shap=True)
    print("  model.lgb, ruleset.pkl, product_lookup.parquet — OK\n")

    # Passo 1: sessões com cart e ground truth de compras (vetorizado, rápido)
    t0 = time.time()
    cart_sessions = _find_cart_sessions(csv_path)
    # Passo 2: replay só das sessões relevantes
    print(f"Passo 2/2 — replay de {csv_path.name} (chunks de {CHUNK_SIZE:,} linhas)...")
    total_events = 0
    chunk_n = 0

    for chunk in pd.read_csv(csv_path, usecols=COLS, chunksize=CHUNK_SIZE):
        # filtra só sessões com cart antes de qualquer processamento
        chunk = chunk[chunk["user_session"].astype(str).isin(cart_sessions)]
        if chunk.empty:
            chunk_n += 1
            continue

        chunk["event_time"] = pd.to_datetime(chunk["event_time"], utc=True).dt.tz_localize(None)
        chunk = chunk.sort_values("event_time")
        chunk_n += 1

        for record in chunk.itertuples(index=False):
            sim.ingest(_to_event(record))
            total_events += 1

        elapsed = time.time() - t0
        m = sim.metrics()
        print(
            f"  chunk {chunk_n:3d} | {total_events/1_000_000:.2f}M eventos | "
            f"elegíveis: {m['eligible']:,} | {elapsed:.0f}s"
        )

    # flush: sessões cujo prazo vence depois do último evento do arquivo
    # (o relógio virtual só avança quando chega um evento)
    print("\nAvaliando sessões com prazo pendente no fim do arquivo...")
    # list() congela as chaves antes do loop — flush() pode disparar o trigger,
    # mas não insere sessão nova nenhuma, então é só defensivo contra mutação
    flushed = sum(
        1 for sid in list(sim._sessions.keys()) if sim.flush(sid) is not None
    )
    print(f"  {flushed:,} sessões adicionais pontuadas via flush")

    # SHAP em batch — uma chamada para todas as sessões triggeradas
    _batch_shap(sim)

    m = sim.metrics()
    elapsed = time.time() - t0

    # --- resultado ---
    print(f"\n{'='*52}")
    print(f"RESULTADO — Replay de novembro ({elapsed:.0f}s)")
    print(f"{'='*52}")
    print(f"Eventos processados:          {total_events:,}")
    print(f"Sessões com cart:             {m['cart_sessions']:,}")
    print(f"Elegíveis (pontuadas):        {m['eligible']:,}  ({m['coverage']:.1%} das sessões com cart)")
    print(f"Não elegíveis por motivo:     {m['reasons']}")
    print(f"Com purchase (qualquer hora): {m['purchased']:,}")

    n_eligible = m["eligible"]
    if n_eligible:
        print("\nDistribuição de ações (sobre elegíveis):")
        for action, count in sorted(m["actions"].items()):
            print(f"  {action:28s}: {count:,} ({count / n_eligible * 100:.1f}%)")

    # --- alcance da recomendação (M2 + lookup) ---
    n_intervention = sum(
        1 for s in sim._sessions.values()
        if s.action and s.action.action in ("strong_intervention", "moderate_intervention")
    )
    n_with_rule = sum(1 for s in sim._sessions.values() if s.action and s.action.consequent)
    n_with_product = sum(1 for s in sim._sessions.values()
                         if s.action and s.action.recommended_product_id is not None)
    action_rate = n_intervention / n_eligible if n_eligible else 0.0
    print(f"\nTaxa de ação (forte+moderada / elegíveis): {action_rate:.1%}")
    print(f"Regra M2 aplicável:                        {n_with_rule:,} ({n_with_rule / n_eligible:.2%} das elegíveis)")
    print(f"Produto concreto recomendado:              {n_with_product:,} ({n_with_product / n_eligible:.2%} das elegíveis)")

    # --- salva JSON ---
    result = {
        "source": "2019-Nov.csv",
        "total_events_processed": total_events,
        "cart_sessions": m["cart_sessions"],
        "n_eligible": n_eligible,
        "coverage_eligible_over_cart": round(m["coverage"], 4),
        "exclusion_reasons": m["reasons"],
        "purchased": m["purchased"],
        "action_rate": round(action_rate, 4),
        "n_with_rule": n_with_rule,
        "n_with_product": n_with_product,
        "actions": m["actions"],
        "elapsed_s": round(elapsed, 1),
    }
    out_path = DATASET_DIR / "replay_november_results.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nResultados salvos em {out_path.name}")


if __name__ == "__main__":
    main()
