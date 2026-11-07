#!/usr/bin/env bash
# Mostra que a decisão é incremental: evento a evento, a API responde `null` até a janela
# de 120 s fechar. Último argumento opcional: endereço da API.
#
#   bash demo/incremental.sh
set -euo pipefail
API="${1:-http://127.0.0.1:8000}"
SID="inc-$(date +%s)"
AQUI="$(cd "$(dirname "$0")" && pwd)"

python3 - "$API" "$SID" "$AQUI/scenarios.json" <<'PY'
import json, sys, urllib.request

api, sid, caminho = sys.argv[1], sys.argv[2], sys.argv[3]
cen = next(c for c in json.load(open(caminho, encoding="utf-8"))["cenarios"] if c["id"] == "cupom")
hora = cen["hora_base"]

print(f"\nsessão {sid} — janela de 120 s a partir do carrinho\n")
for e in cen["eventos"]:
    t = hora * 3600 + e["t"]
    corpo = {
        "event_time": f"2019-11-01T{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}",
        "event_type": e["event_type"], "product_id": e["product_id"],
        "category_id": int(e["category_id"]), "category_code": e["category_code"],
        "brand": e["brand"], "price": e["price"], "user_id": 513903572,
        "user_session": sid,
    }
    req = urllib.request.Request(f"{api}/event", method="POST",
                                 data=json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    marca = "  ← carrinho: janela começa" if e["event_type"] == "cart" else ""
    if d is None:
        print(f"  t+{e['t']:<5d} {e['event_type']:<8} → null{marca}")
    else:
        print(f"  t+{e['t']:<5d} {e['event_type']:<8} → {d['action']}  "
              f"p={d['p_abandon']:.4f}  produto={d['recommended_product_id']}")
print(f"\n  GET /session/{sid} devolve a mesma decisão a qualquer momento.")
print(f"  POST /flush/{sid} forçaria a avaliação sem esperar o próximo evento.\n")
PY
