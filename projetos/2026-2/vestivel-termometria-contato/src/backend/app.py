"""API de telemetria do TCC (monitoramento vestível bovino).

Recebe as leituras do gateway ESP32 por HTTP e grava no PostgreSQL (Aiven).

Rotas:
  POST /leituras   grava uma leitura ou uma lista (um pacote LoRa = uma leitura por
                   sensor, todas gravadas na mesma transação)
  GET  /leituras   últimas leituras (?limite=&vaca_id=&de=&ate=&extra=1&agregar_s=)
  GET  /health     verificação simples de que o serviço está no ar
  GET  /estado     estado do detector por animal e membro
  GET  /alertas    alertas (?vaca_id=&abertos=true|false)
  GET  /deteccao   ciclos do detector (?vaca_id=&membro=&de=&ate=)

No POST, `membro` ("E"/"D") e `seq` são opcionais. Se vier `seq`, uma retentativa com
o mesmo (vaca_id, membro, seq) nos últimos DEDUPE_JANELA_S segundos é ignorada.
O detector roda depois que a resposta já foi enviada; se ele falhar, o erro só vai
para o log e a gravação não é afetada.
"""

import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from flask import Flask, jsonify, make_response, request
from flask_cors import CORS
from psycopg2 import OperationalError, errors, pool
from psycopg2.extras import execute_values

import servico_detector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL")
API_KEY = os.environ.get("API_KEY")  # enviada pelo gateway no header X-API-Key

if not DATABASE_URL:
    raise RuntimeError("Variável de ambiente DATABASE_URL não definida.")
if not API_KEY:
    raise RuntimeError("Variável de ambiente API_KEY não definida.")

DEDUPE_JANELA_S = 300   # janela em que uma retentativa é considerada duplicada
TRAVA_DEDUPE = 7342     # identificador das travas consultivas do dedupe

COLUNAS_LEITURA = ("vaca_id", "quarto", "temp_raw", "temp_ambiente", "delta_t", "rssi", "snr")
COLUNAS_GET = "id, vaca_id, quarto, temp_raw, temp_ambiente, delta_t, rssi, snr, timestamp"

app = Flask(__name__)

# Front-end hospedado em outro domínio. Liberado para qualquer origem; para restringir,
# troque "*" pela URL do front publicado.
CORS(app, resources={r"/*": {"origins": "*"}})

# O plano gratuito do Aiven aceita 20 conexões no total; 5 por worker é suficiente.
connection_pool = pool.SimpleConnectionPool(
    minconn=1,
    maxconn=5,
    dsn=DATABASE_URL,
    sslmode=os.environ.get("DB_SSLMODE", "require"),  # "disable" só no banco local de teste
)


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def _rollback(conn):
    try:
        conn.rollback()
    except Exception:
        pass


@contextmanager
def conexao():
    """Pega uma conexão do pool e devolve ao final. Em caso de erro, desfaz a transação."""
    conn = connection_pool.getconn()
    try:
        yield conn
    except Exception:
        _rollback(conn)
        raise
    finally:
        connection_pool.putconn(conn)


def erro(mensagem, status):
    return jsonify({"erro": mensagem}), status


def autenticado(req):
    return req.headers.get("X-API-Key") == API_KEY


def _data_param(nome):
    """Lê um parâmetro de data ISO 8601 (sem fuso = UTC). Retorna (valor, erro)."""
    txt = request.args.get(nome)
    if not txt:
        return None, None
    try:
        dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
    except ValueError:
        return None, f"parâmetro {nome} inválido (use ISO 8601)"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt, None


def _periodo():
    """Lê `de` e `ate`. Retorna (de, ate, erro)."""
    de, erro_de = _data_param("de")
    ate, erro_ate = _data_param("ate")
    return de, ate, erro_de or erro_ate


# ---------------------------------------------------------------------------
# POST /leituras
# ---------------------------------------------------------------------------

def _validar_item(item):
    """Retorna a mensagem de erro do item, ou None se ele estiver ok.
    temp_raw pode ser null (sensor aberto/em curto), mas a chave precisa existir."""
    if not isinstance(item, dict):
        return "cada leitura deve ser um objeto JSON"
    if item.get("vaca_id") in (None, ""):
        return "campo obrigatório ausente: vaca_id"
    if item.get("quarto") is None:
        return "campo obrigatório ausente: quarto"
    if "temp_raw" not in item:
        return "campo obrigatório ausente: temp_raw (pode ser null, mas a chave deve existir)"
    if item.get("membro") not in (None, "E", "D"):
        return 'membro deve ser "E", "D" ou ausente'
    seq = item.get("seq")
    if seq is not None and (not isinstance(seq, int) or isinstance(seq, bool)):
        return "seq deve ser inteiro ou ausente"
    return None


_colunas_novas = {"ok": False, "verificado_em": 0.0}


def _tem_colunas_novas(cur):
    """Verifica se a migração 001 (membro, pacote_id, seq) já foi aplicada.

    Sem ela, grava no formato antigo e não roda o detector. Enquanto não existir,
    verifica de novo a cada 60 s."""
    if _colunas_novas["ok"] or time.monotonic() - _colunas_novas["verificado_em"] < 60:
        return _colunas_novas["ok"]
    cur.execute(
        """SELECT count(*) FROM information_schema.columns
            WHERE table_name = 'leituras' AND column_name IN ('membro', 'pacote_id', 'seq')""")
    _colunas_novas["ok"] = cur.fetchone()[0] == 3
    _colunas_novas["verificado_em"] = time.monotonic()
    if not _colunas_novas["ok"]:
        logger.warning("Migração 001 não aplicada: gravando no formato antigo, sem detector")
    return _colunas_novas["ok"]


def _chave_dedupe(item):
    return (item["vaca_id"], item.get("membro"), item["seq"])


def _duplicadas(cur, itens):
    """Índices dos itens cujo (vaca_id, membro, seq) já foi gravado dentro da janela.

    Usa uma trava consultiva por chave (até o commit) para que dois workers não
    gravem a mesma retentativa ao mesmo tempo."""
    chaves = sorted({_chave_dedupe(i) for i in itens if i.get("seq") is not None}, key=str)
    repetidas = set()
    for vaca_id, membro, seq in chaves:
        cur.execute("SELECT pg_advisory_xact_lock(%s, hashtext(%s))",
                    (TRAVA_DEDUPE, f"{vaca_id}|{membro or ''}|{seq}"))
        cur.execute(
            """SELECT 1 FROM leituras
                WHERE vaca_id = %s AND membro IS NOT DISTINCT FROM %s AND seq = %s
                  AND timestamp > now() - make_interval(secs => %s)
                LIMIT 1""",
            (vaca_id, membro, seq, DEDUPE_JANELA_S))
        if cur.fetchone():
            repetidas.add((vaca_id, membro, seq))
    return {k for k, i in enumerate(itens)
            if i.get("seq") is not None and _chave_dedupe(i) in repetidas}


def _inserir(cur, itens, com_colunas_novas):
    """Grava os itens e retorna [(id, timestamp), ...] na mesma ordem."""
    colunas = list(COLUNAS_LEITURA)
    linhas = [[it.get(c) for c in COLUNAS_LEITURA] for it in itens]
    if com_colunas_novas:
        cur.execute("SELECT nextval('leituras_pacote_id_seq')")
        pacote_id = cur.fetchone()[0]
        colunas += ["membro", "pacote_id", "seq"]
        for linha, it in zip(linhas, itens):
            linha += [it.get("membro"), pacote_id, it.get("seq")]
    return execute_values(
        cur,
        f"INSERT INTO leituras ({', '.join(colunas)}) VALUES %s RETURNING id, timestamp;",
        [tuple(l) for l in linhas],
        fetch=True,
    )


def _rodar_detector(linhas):
    """Roda depois que a resposta foi enviada. Nunca deixa o erro escapar."""
    try:
        with conexao() as conn:
            servico_detector.processar_linhas(conn, linhas)
            vacas = {l["vaca_id"] for l in linhas}
            servico_detector.fechar_vencidos_todos(conn, time.time(), exceto=vacas)
    except Exception:
        logger.exception("Detector falhou (a ingestão não foi afetada)")


@app.route("/leituras", methods=["POST"])
def criar_leitura():
    if not autenticado(request):
        return erro("não autorizado", 401)

    dados = request.get_json(silent=True)
    if not dados:
        return erro("corpo JSON ausente ou inválido", 400)

    # Aceita um objeto só ou uma lista. A resposta segue o mesmo formato da entrada.
    em_lista = isinstance(dados, list)
    entrada = dados if em_lista else [dados]
    if not entrada:
        return erro("lista de leituras vazia", 400)
    for i, item in enumerate(entrada):
        msg = _validar_item(item)
        if msg:
            return erro(f"item {i}: {msg}", 400)

    try:
        with conexao() as conn:
            with conn.cursor() as cur:
                novas = _tem_colunas_novas(cur)
                if novas:
                    repetidas = _duplicadas(cur, entrada)
                    itens = [it for k, it in enumerate(entrada) if k not in repetidas]
                else:
                    itens = list(entrada)

                if not itens:
                    conn.commit()
                    logger.info("Retentativa descartada pelo dedupe: vaca=%s seq=%s",
                                entrada[0].get("vaca_id"), entrada[0].get("seq"))
                    if em_lista:
                        return jsonify({"status": "duplicado", "quantidade": 0, "leituras": []}), 200
                    return jsonify({"status": "duplicado"}), 200

                resultado = _inserir(cur, itens, novas)
                conn.commit()
    except OperationalError as e:
        logger.error("Erro de conexão com o banco: %s", e)
        return erro("falha ao conectar ao banco", 503)
    except Exception:
        logger.exception("Erro inesperado ao gravar leitura(s)")
        return erro("erro interno", 500)

    gravados = [{"id": row[0], "timestamp": row[1].isoformat()} for row in resultado]
    logger.info("Lote gravado: %d leitura(s), vaca=%s", len(gravados), itens[0].get("vaca_id"))

    if em_lista:
        corpo = {"status": "gravado", "quantidade": len(gravados), "leituras": gravados}
    else:
        corpo = {"status": "gravado", **gravados[0]}
    resposta = make_response(jsonify(corpo), 201)

    if novas:
        linhas_detector = [
            {"vaca_id": it.get("vaca_id"), "membro": it.get("membro"), "quarto": it.get("quarto"),
             "temp_raw": it.get("temp_raw"), "timestamp": row[1]}
            for it, row in zip(itens, resultado)
        ]
        resposta.call_on_close(lambda: _rodar_detector(linhas_detector))
    return resposta


# ---------------------------------------------------------------------------
# GET /leituras e /health
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


@app.route("/leituras", methods=["GET"])
def listar_leituras():
    """Últimas leituras, da mais recente para a mais antiga. Sem autenticação.

    extra=1 inclui membro, pacote_id e seq.
    agregar_s=S devolve, em vez das leituras, uma linha por (vaca, membro, sensor,
    janela de S segundos) com a mediana de temp_raw e n = leituras com valor. Serve
    para o gráfico de períodos longos sem baixar todas as leituras."""
    limite = request.args.get("limite", default=50, type=int)
    vaca_id = request.args.get("vaca_id", default=None, type=str)
    de, ate, msg = _periodo()
    if msg:
        return erro(msg, 400)
    extra = request.args.get("extra") in ("1", "true")
    agregar_s = None
    if request.args.get("agregar_s"):
        agregar_s = request.args.get("agregar_s", type=int)
        if agregar_s is None or not 1 <= agregar_s <= 86400:
            return erro("parâmetro agregar_s inválido (inteiro de 1 a 86400)", 400)

    cond, args = [], []
    if vaca_id:
        cond.append("vaca_id = %s")
        args.append(vaca_id)
    if de is not None:
        cond.append("timestamp >= %s")
        args.append(de)
    if ate is not None:
        cond.append("timestamp < %s")
        args.append(ate)
    where = ("WHERE " + " AND ".join(cond)) if cond else ""

    if agregar_s is not None:
        sql = f"""
            SELECT vaca_id, membro, quarto,
                   to_timestamp(floor(extract(epoch FROM timestamp) / %s) * %s) AS timestamp,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY temp_raw::numeric) AS temp_raw,
                   count(temp_raw) AS n
              FROM leituras
              {where}
             GROUP BY 1, 2, 3, 4
             ORDER BY 4 DESC, 1, 2, 3
             LIMIT %s;"""
        args = [agregar_s, agregar_s] + args
    else:
        colunas = COLUNAS_GET + (", membro, pacote_id, seq" if extra else "")
        sql = f"SELECT {colunas} FROM leituras {where} ORDER BY timestamp DESC LIMIT %s;"

    try:
        with conexao() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args + [limite])
                nomes = [d[0] for d in cur.description]
                linhas = [dict(zip(nomes, row)) for row in cur.fetchall()]
    except errors.UndefinedColumn:
        logger.exception("extra=1 sem a migração 001")
        return erro("migrações da Fase 2 não aplicadas", 503)
    except Exception:
        logger.exception("Erro ao listar leituras")
        return erro("erro interno", 500)

    for linha in linhas:
        linha["timestamp"] = linha["timestamp"].isoformat()
    return jsonify(linhas), 200


# ---------------------------------------------------------------------------
# Consultas do detector (só leitura)
# ---------------------------------------------------------------------------

def _consulta(fn):
    try:
        with conexao() as conn:
            return jsonify(fn(conn)), 200
    except (errors.UndefinedTable, errors.UndefinedColumn):
        logger.exception("Consulta do detector sem as migrações")
        return erro("migrações da Fase 2 não aplicadas", 503)
    except Exception:
        logger.exception("Erro na consulta do detector")
        return erro("erro interno", 500)


@app.route("/estado", methods=["GET"])
def estado():
    """Estado por animal e membro. Antes de responder, fecha os bins já vencidos."""
    return _consulta(lambda conn: servico_detector.consultar_estado(conn, time.time()))


@app.route("/alertas", methods=["GET"])
def alertas():
    vaca_id = request.args.get("vaca_id") or None
    abertos_txt = request.args.get("abertos")
    if not abertos_txt:
        abertos = None
    elif abertos_txt in ("true", "1"):
        abertos = True
    elif abertos_txt in ("false", "0"):
        abertos = False
    else:
        return erro("abertos deve ser true ou false", 400)
    limite = min(request.args.get("limite", default=200, type=int), 1000)
    return _consulta(lambda conn: servico_detector.consultar_alertas(conn, vaca_id, abertos, limite))


@app.route("/deteccao", methods=["GET"])
def deteccao():
    vaca_id = request.args.get("vaca_id")
    if not vaca_id:
        return erro("vaca_id é obrigatório", 400)
    membro = request.args.get("membro") or None
    if membro not in (None, "E", "D", "U"):
        return erro('membro deve ser "E", "D" ou "U"', 400)
    de, ate, msg = _periodo()
    if msg:
        return erro(msg, 400)
    limite = min(request.args.get("limite", default=2000, type=int), 10000)
    return _consulta(lambda conn: servico_detector.consultar_deteccao(conn, vaca_id, membro, de, ate, limite))


if __name__ == "__main__":
    # Só para rodar localmente; no Render quem sobe a aplicação é o gunicorn.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
