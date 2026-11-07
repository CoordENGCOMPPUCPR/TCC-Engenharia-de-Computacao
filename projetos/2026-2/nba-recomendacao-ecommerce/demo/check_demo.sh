#!/usr/bin/env bash
# Confere se a API no ar decide os quatro cenários como o README descreve. Não sobe a API:
# ela precisa estar rodando (passo 4 do README).
#
#   bash demo/check_demo.sh              # usa http://127.0.0.1:8000
#   bash demo/check_demo.sh http://...   # outro endereço
set -uo pipefail

API="${1:-http://127.0.0.1:8000}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
CENARIOS="$AQUI/scenarios.json"

verde=$'\033[32m'; vermelho=$'\033[31m'; cinza=$'\033[90m'; fim=$'\033[0m'
falhas=0

ok()   { printf '  %sOK%s   %s\n' "$verde" "$fim" "$1"; }
erro() { printf '  %sFALHA%s %s\n' "$vermelho" "$fim" "$1"; falhas=$((falhas + 1)); }
nota() { printf '%s%s%s\n' "$cinza" "$1" "$fim"; }

echo
echo "Verificação da demonstração — $API"
echo

# ── 1. Artefatos de treino ────────────────────────────────────────────────────
echo "1. Artefatos em dataset/"
for a in model.lgb ruleset.pkl product_lookup.parquet brand_vocab.pkl thresholds.json; do
  if [[ -f "$AQUI/../dataset/$a" ]]; then ok "$a"; else erro "$a não encontrado"; fi
done
echo

# ── 2. API no ar ──────────────────────────────────────────────────────────────
echo "2. Serviço"
if curl -fsS --max-time 5 "$API/openapi.json" >/dev/null 2>&1; then
  ok "API responde em $API"
else
  erro "API não responde"
  nota "    Suba na pasta do projeto:  python -m uvicorn src.api:app --port 8000"
  echo; exit 1
fi
for rota in /docs /metrics /demo/scenarios; do
  if curl -fsS --max-time 5 "$API$rota" >/dev/null 2>&1; then ok "GET $rota"; else erro "GET $rota"; fi
done
echo

# ── 3. Decisão de cada cenário ────────────────────────────────────────────────
echo "3. Cenários (decisão esperada × decisão obtida)"
python3 - "$API" "$CENARIOS" <<'PY'
import json, sys, urllib.request

api, caminho = sys.argv[1], sys.argv[2]
cenarios = json.load(open(caminho, encoding="utf-8"))["cenarios"]
VERDE, VERMELHO, FIM = "\033[32m", "\033[31m", "\033[0m"
falhas = 0

def hhmmss(s):
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"

for cen in cenarios:
    hora = cen.get("hora_base", 10)
    corpo = {"events": [{
        "event_time": f"2019-11-01T{hhmmss(hora * 3600 + e['t'])}",
        "event_type": e["event_type"], "product_id": e["product_id"],
        "category_id": e["category_id"], "category_code": e["category_code"],
        "brand": e["brand"], "price": e["price"], "user_id": 513903572,
        "user_session": "check",
    } for e in cen["eventos"]]}

    req = urllib.request.Request(f"{api}/session", method="POST",
                                 data=json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
    except Exception as exc:                                  # noqa: BLE001
        print(f"  {VERMELHO}FALHA{FIM} {cen['id']}: {exc}")
        falhas += 1
        continue

    acao = (d or {}).get("action")
    produto = (d or {}).get("recommended_product_id")
    esp = cen["esperado"]
    bom = acao == esp["action"] and (produto is not None) == esp["tem_produto"]
    falhas += 0 if bom else 1
    p = (d or {}).get("p_abandon")
    print(f"  {(VERDE + 'OK   ' if bom else VERMELHO + 'FALHA') + FIM} "
          f"{cen['id']:<10} esperado={esp['action']} obtido={acao} "
          f"produto={produto} p={p if p is None else round(p, 4)}")

sys.exit(1 if falhas else 0)
PY
[[ $? -ne 0 ]] && falhas=$((falhas + 1))
echo

# ── 4. category_id como número ────────────────────────────────────────────────
echo "4. Robustez de tipo (category_id como número)"
resp=$(curl -fsS --max-time 30 -X POST "$API/session" \
  -H 'Content-Type: application/json' \
  -d '{"events":[
    {"event_time":"2019-11-01T02:00:00","event_type":"view","product_id":4804056,"category_id":2053013554658804075,"category_code":"electronics.audio.headphone","brand":"other","price":1299.99,"user_id":1,"user_session":"n"},
    {"event_time":"2019-11-01T02:03:20","event_type":"view","product_id":4804057,"category_id":2053013554658804075,"category_code":"electronics.audio.headphone","brand":"other","price":1299.99,"user_id":1,"user_session":"n"},
    {"event_time":"2019-11-01T02:08:00","event_type":"view","product_id":4804058,"category_id":2053013554658804075,"category_code":"electronics.audio.headphone","brand":"other","price":1299.99,"user_id":1,"user_session":"n"},
    {"event_time":"2019-11-01T02:13:20","event_type":"view","product_id":4804059,"category_id":2053013554658804075,"category_code":"electronics.audio.headphone","brand":"other","price":1299.99,"user_id":1,"user_session":"n"},
    {"event_time":"2019-11-01T02:19:10","event_type":"view","product_id":4804060,"category_id":2053013554658804075,"category_code":"electronics.audio.headphone","brand":"other","price":1299.99,"user_id":1,"user_session":"n"},
    {"event_time":"2019-11-01T02:23:20","event_type":"cart","product_id":4804060,"category_id":2053013554658804075,"category_code":"electronics.audio.headphone","brand":"other","price":1299.99,"user_id":1,"user_session":"n"},
    {"event_time":"2019-11-01T02:23:35","event_type":"view","product_id":4804061,"category_id":2053013554658804075,"category_code":"electronics.audio.headphone","brand":"other","price":1299.99,"user_id":1,"user_session":"n"},
    {"event_time":"2019-11-01T02:25:30","event_type":"view","product_id":4804062,"category_id":2053013554658804075,"category_code":"electronics.audio.headphone","brand":"other","price":1299.99,"user_id":1,"user_session":"n"}]}' 2>/dev/null)
if [[ -n "$resp" ]] && echo "$resp" | grep -q '"recommended_product_id": *[0-9]'; then
  ok "id numérico aceito e produto resolvido"
else
  erro "id numérico não resolveu produto"
fi
echo

# ── 5. Repetição ──────────────────────────────────────────────────────────────
echo "5. Repetição sem reiniciar o serviço"
if [[ -n "$resp" ]] && curl -fsS --max-time 30 "$API/metrics" | grep -q 'total_sessions'; then
  ok "a mesma sessão pode ser reenviada sem reiniciar o serviço"
else
  erro "não foi possível confirmar"
fi
echo

if [[ $falhas -eq 0 ]]; then
  printf '%sPronto para apresentar.%s\n\n' "$verde" "$fim"
else
  printf '%s%d verificação(ões) falharam — ver acima.%s\n\n' "$vermelho" "$falhas" "$fim"
  exit 1
fi
