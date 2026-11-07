# benchmark_latency.py — Latência do caminho de inferência com os artefatos reais.
#
# Mede, em processo único e sem I/O de rede, 2.000 sessões sintéticas de 7 eventos com o
# formato real. Resultado em latency_results.json.
#
# Uso: python3 -m src.analysis.benchmark_latency

import json
import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.m1_pipeline import Event
from src.stream_simulator import StreamSimulator
from src.trigger import T_WINDOW

DATASET_DIR = Path(__file__).parent.parent.parent / "dataset"
N_SESSIONS = 2000
T0 = datetime(2019, 11, 1, 10, 0, 0)


def _session(i: int) -> list[Event]:
    # 4 views, cart em 80 s, 1 view dentro da janela (atividade) e 1 view depois do prazo,
    # que dispara a sessão; cada sessão começa 1.000 s depois da anterior
    sid = f"bench-{i}"
    mk = lambda off, et, pid: Event(  # noqa: E731
        event_time=T0 + timedelta(seconds=i * 1000 + off), event_type=et, product_id=pid,
        category_id="2053013555631882655", category_code="electronics.smartphone",
        brand="samsung", price=249.99, user_id=i, user_session=sid,
    )
    return [mk(0, "view", 1), mk(20, "view", 2), mk(40, "view", 3), mk(60, "view", 4),
            mk(80, "cart", 5), mk(110, "view", 6), mk(80 + int(T_WINDOW) + 5, "view", 7)]


def _run(batch_shap: bool) -> tuple[list[float], list[float]]:
    sim = StreamSimulator(batch_shap=batch_shap)
    ingest_ms, trigger_ms = [], []
    for i in range(N_SESSIONS):
        ev = _session(i)
        for e in ev[:-1]:
            # eventos que só atualizam o estado da sessão, sem disparo
            t = time.perf_counter(); sim.ingest(e); ingest_ms.append((time.perf_counter() - t) * 1000)
        # último evento: disparo completo (M1 + LightGBM + SHAP, se ligado, + M4)
        t = time.perf_counter(); action = sim.ingest(ev[-1]); trigger_ms.append((time.perf_counter() - t) * 1000)
        assert action is not None
    return ingest_ms, trigger_ms


def _stats(xs: list[float]) -> dict:
    xs = sorted(xs)
    return {"mean_ms": round(statistics.mean(xs), 3), "p50_ms": round(xs[len(xs) // 2], 3),
            "p95_ms": round(xs[int(len(xs) * 0.95)], 3), "p99_ms": round(xs[int(len(xs) * 0.99)], 3)}


def main():
    ing, trg = _run(batch_shap=False)       # como na API: SHAP local por sessão
    _, trg_noshap = _run(batch_shap=True)   # como no replay: sem SHAP por sessão
    out = {"n_sessions": N_SESSIONS, "ingest_no_trigger": _stats(ing),
           "trigger_full_with_local_shap": _stats(trg), "trigger_without_shap": _stats(trg_noshap)}
    for k, v in out.items():
        if isinstance(v, dict):
            print(f"{k:<30} média {v['mean_ms']:>7.3f} ms | p50 {v['p50_ms']:>7.3f} | p95 {v['p95_ms']:>7.3f} | p99 {v['p99_ms']:>7.3f}")
    (DATASET_DIR / "latency_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("Salvo em latency_results.json")


if __name__ == "__main__":
    main()
