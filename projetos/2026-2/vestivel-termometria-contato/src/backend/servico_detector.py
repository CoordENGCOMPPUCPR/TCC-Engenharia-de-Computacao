"""Liga o detector (pasta detector/) ao PostgreSQL.

Chamado pelo app.py depois de responder o POST /leituras e pelas rotas /estado,
/alertas e /deteccao.

- Parâmetros: tabela detector_config (dá para mudar sem deploy); o que faltar
  usa o padrão de detector/config.py.
- Estado de cada animal: tabela estado_detector (o JSON do `step`, com os dois membros).
- Vários workers do gunicorn: uma trava consultiva por animal (pg_advisory_xact_lock),
  mantida até o commit.
- Linha de base: recalculada na primeira ingestão de cada hora, só para a hora
  local corrente, a partir de deteccao_ciclos (igual ao sim/rodar.py).
"""

import json
import logging
import math
from datetime import datetime, timezone

from psycopg2.extras import execute_values

from detector import (Config, calcular_baseline, consultar, estado_atual, estado_inicial, fechar_vencidos,
                      hora_local, step, validar)
from detector.adaptador import linhas_para_pacotes
from detector.nucleo import VERSAO_ESTADO

logger = logging.getLogger(__name__)

TRAVA_DETECTOR = 7341       # identificador das travas consultivas por animal
MARGEM_FECHAMENTO_S = 30    # só fecha bins que terminaram há mais que isso
OPCIONAIS = {"congela_frac", "congela_max_h"}   # parâmetros que aceitam null
PRIORIDADE_ANIMAL = ("ALERTA", "FALHA_SENSOR", "SEM_DADOS", "ARMANDO", "OK")


def _somar(total, parcial):
    for k, v in parcial.items():
        total[k] = total.get(k, 0) + v


def _linhas_como_dicts(cur):
    nomes = [d[0] for d in cur.description]
    return [dict(zip(nomes, r)) for r in cur.fetchall()]


def _iso(ts):
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.isoformat()
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _membro_db(m):
    """No banco, o membro único "U" é gravado como NULL na tabela leituras."""
    return None if m == "U" else m


# ---------------------------------------------------------------------------
# Parâmetros
# ---------------------------------------------------------------------------

def _valor_valido(chave, valor, padrao):
    if valor is None:
        return chave in OPCIONAIS
    if isinstance(padrao, bool):
        return isinstance(valor, bool)
    if isinstance(padrao, int):
        return isinstance(valor, int) and not isinstance(valor, bool)
    if isinstance(padrao, float) or chave in OPCIONAIS:
        return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)
    if isinstance(padrao, str):
        return isinstance(valor, str)
    return False


def _combinacao_valida(cfg):
    return (cfg.ciclo_s > 0 and 3600 % cfg.ciclo_s == 0 and cfg.n_sensores >= 1 and cfg.n_persist >= 1
            and cfg.g_ausentes >= 0 and cfg.n_min_validos >= 1 and cfg.baseline_dias >= 1
            and cfg.congela_max_modo in ("liberar", "reset") and 0 < cfg.histerese <= 1
            and min(cfg.lambda_s, cfg.lambda_b, cfg.lambda_c) > 0)


def carregar_config(cur):
    """Lê detector_config. Chave desconhecida ou valor inválido é ignorado (fica o
    padrão do código) e gera aviso no log."""
    padrao = Config().para_dict()
    valores = dict(padrao)
    cur.execute("SELECT chave, valor FROM detector_config")
    for chave, valor in cur.fetchall():
        if chave not in padrao:
            logger.warning("detector_config: chave desconhecida ignorada: %s", chave)
        elif not _valor_valido(chave, valor, padrao[chave]):
            logger.warning("detector_config: valor inválido para %s (%r); usando %r", chave, valor, padrao[chave])
        elif isinstance(padrao[chave], float) and valor is not None:
            valores[chave] = float(valor)
        else:
            valores[chave] = valor
    cfg = Config.de_dict(valores)
    if not _combinacao_valida(cfg):
        logger.error("detector_config: combinação inválida; usando o padrão do código")
        return Config()
    return cfg


def parametros_publicos(cfg):
    return {"lambda_s": cfg.lambda_s, "lambda_b": cfg.lambda_b, "lambda_c": cfg.lambda_c,
            "n_persist": cfg.n_persist, "ciclo_s": cfg.ciclo_s, "histerese": cfg.histerese,
            "sem_dados_min": cfg.sem_dados_min, "congela_max_h": cfg.congela_max_h}


# ---------------------------------------------------------------------------
# Estado e linha de base
# ---------------------------------------------------------------------------

def _travar(cur, vaca_id, esperar=True):
    if esperar:
        cur.execute("SELECT pg_advisory_xact_lock(%s, hashtext(%s))", (TRAVA_DETECTOR, vaca_id))
        return True
    cur.execute("SELECT pg_try_advisory_xact_lock(%s, hashtext(%s))", (TRAVA_DETECTOR, vaca_id))
    return cur.fetchone()[0]


def _carregar_estado(cur, vaca_id):
    cur.execute("SELECT versao, estado FROM estado_detector WHERE vaca_id = %s", (vaca_id,))
    r = cur.fetchone()
    if r is None:
        return estado_inicial()
    return {"versao": r[0], "vacas": {vaca_id: r[1]}}


def _salvar_estado(cur, vaca_id, estado):
    sub = estado["vacas"].get(vaca_id)
    if sub is None:
        return
    cur.execute(
        """INSERT INTO estado_detector (vaca_id, versao, estado, atualizado_em) VALUES (%s, %s, %s, now())
           ON CONFLICT (vaca_id) DO UPDATE SET versao = EXCLUDED.versao, estado = EXCLUDED.estado,
                                               atualizado_em = now()""",
        (vaca_id, estado.get("versao", VERSAO_ESTADO), json.dumps(sub)))


def _carregar_baseline(cur, vaca_id):
    cur.execute("SELECT membro, sensor, hora, b, n, dias FROM baseline WHERE vaca_id = %s", (vaca_id,))
    out = {}
    for membro, sensor, hora, b, n, dias in cur.fetchall():
        celulas = out.setdefault(f"{vaca_id}|{membro}", {}).setdefault(str(sensor), {})
        celulas[str(hora)] = {"b": b, "n": n, "dias": dias}
    return out


def _recalcular_baseline(cur, vaca_id, ts, cfg):
    """Recalcula a linha de base da hora local de `ts`, se ainda não foi feito nesta hora.
    Supõe fuso com deslocamento de horas inteiras (America/Sao_Paulo: UTC-3)."""
    h = hora_local(ts, cfg.fuso)
    inicio_hora = ts - ts % 3600
    cur.execute("SELECT extract(epoch FROM recalculado_em) FROM baseline_recalculo WHERE vaca_id = %s AND hora = %s",
                (vaca_id, h))
    r = cur.fetchone()
    if r is not None and float(r[0]) >= inicio_hora:
        return False

    cur.execute(
        """SELECT d.membro, extract(epoch FROM d.ciclo_ts), d.t
             FROM deteccao_ciclos d
             LEFT JOIN baseline_reset r ON r.vaca_id = d.vaca_id AND r.membro = d.membro
            WHERE d.vaca_id = %s AND d.hora_local = %s AND NOT d.congelado
              AND d.ciclo_ts >= to_timestamp(%s) AND d.ciclo_ts < to_timestamp(%s)
              AND (r.desde IS NULL OR d.ciclo_ts >= r.desde)""",
        (vaca_id, h, ts - cfg.baseline_dias * 86400, ts))
    ciclos = [{"vaca_id": vaca_id, "membro": m, "ts": float(t0), "T": list(t or []), "congelado": False}
              for m, t0, t in cur.fetchall()]
    novo = calcular_baseline(ciclos, cfg, ts, horas={h})

    cur.execute("DELETE FROM baseline WHERE vaca_id = %s AND hora = %s", (vaca_id, h))
    linhas = [(vaca_id, k.split("|", 1)[1], int(s), int(hh), c["b"], c["n"], c["dias"])
              for k, sensores in novo.items() for s, horas in sensores.items() for hh, c in horas.items()]
    if linhas:
        execute_values(cur, "INSERT INTO baseline (vaca_id, membro, sensor, hora, b, n, dias) VALUES %s", linhas)
    cur.execute(
        """INSERT INTO baseline_recalculo (vaca_id, hora, recalculado_em) VALUES (%s, %s, to_timestamp(%s))
           ON CONFLICT (vaca_id, hora) DO UPDATE SET recalculado_em = EXCLUDED.recalculado_em""",
        (vaca_id, h, ts))
    return True


# ---------------------------------------------------------------------------
# Gravação dos eventos
# ---------------------------------------------------------------------------

def _gravar_ciclo(cur, e, cfg):
    cur.execute(
        """INSERT INTO deteccao_ciclos (vaca_id, membro, ciclo_ts, hora_local, t_media, dt_b, dt_c, dt_i_max,
                                        n_validos, n_pacotes, estado, congelado, t, dt_i)
           VALUES (%s, %s, to_timestamp(%s), %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   %s::double precision[], %s::double precision[])
           ON CONFLICT (vaca_id, membro, ciclo_ts) DO NOTHING""",
        (e["vaca_id"], e["membro"], e["ts"], e["hora_local"], e["t_media"], e["dt_b"], e["dt_c"],
         e["dt_i_max"], e["n_validos"], e["n_pacotes"], e["estado"], e["congelado"], e["T"], e["dt_i"]))

    # Preenche delta_t das leituras do bin com o dT_i do sensor. Só onde ainda está
    # NULL, para não sobrescrever um valor mandado pelo gateway.
    if any(v is not None for v in e["dt_i"]):
        cur.execute(
            """UPDATE leituras SET delta_t = (%s::double precision[])[quarto]
                WHERE vaca_id = %s AND membro IS NOT DISTINCT FROM %s
                  AND timestamp >= to_timestamp(%s) AND timestamp < to_timestamp(%s)
                  AND delta_t IS NULL AND quarto BETWEEN 1 AND %s""",
            (e["dt_i"], e["vaca_id"], _membro_db(e["membro"]), e["ts"], e["ts"] + cfg.ciclo_s,
             len(e["dt_i"])))


def _gravar_abertura(cur, e, cfg):
    cur.execute(
        """INSERT INTO alertas (vaca_id, membro, componentes, primeiro, inicio, inicio_elevacao, parametros_json)
           VALUES (%s, %s, %s, %s, to_timestamp(%s), to_timestamp(%s), %s)
           ON CONFLICT (vaca_id, membro, inicio) DO NOTHING""",
        (e["vaca_id"], e["membro"], e["componentes"], e["primeiro"], e["ts"], e["inicio_elevacao"],
         json.dumps(cfg.para_dict())))


def _gravar_fechamento(cur, e, cfg):
    cur.execute(
        """UPDATE alertas SET fim = to_timestamp(%s), componentes = %s, picos = %s
            WHERE vaca_id = %s AND membro = %s AND inicio = to_timestamp(%s)""",
        (e["fim"], e["componentes"], json.dumps(e["picos"]), e["vaca_id"], e["membro"], e["inicio"]))
    if cur.rowcount == 0:  # alerta aberto antes de a tabela existir
        cur.execute(
            """INSERT INTO alertas (vaca_id, membro, componentes, primeiro, inicio, inicio_elevacao, fim,
                                    picos, parametros_json)
               VALUES (%s, %s, %s, %s, to_timestamp(%s), to_timestamp(%s), to_timestamp(%s), %s, %s)""",
            (e["vaca_id"], e["membro"], e["componentes"], e["primeiro"], e["inicio"], e["inicio_elevacao"],
             e["fim"], json.dumps(e["picos"]), json.dumps(cfg.para_dict())))


def _gravar_reset(cur, e, cfg):
    cur.execute("DELETE FROM baseline WHERE vaca_id = %s AND membro = %s", (e["vaca_id"], e["membro"]))
    cur.execute(
        """INSERT INTO baseline_reset (vaca_id, membro, desde) VALUES (%s, %s, to_timestamp(%s))
           ON CONFLICT (vaca_id, membro) DO UPDATE SET desde = EXCLUDED.desde""",
        (e["vaca_id"], e["membro"], e["ts"]))


def _avisar_atrasado(cur, e, cfg):
    logger.warning("detector: pacote atrasado ignorado (vaca=%s membro=%s ts=%s)",
                   e["vaca_id"], e["membro"], e["ts"])


GRAVAR_EVENTO = {
    "ciclo": _gravar_ciclo,
    "abertura": _gravar_abertura,
    "fechamento": _gravar_fechamento,
    "reset_baseline": _gravar_reset,
    "atrasado": _avisar_atrasado,
}


def _persistir(cur, eventos, cfg):
    """Grava os eventos e retorna quantos houve de cada tipo."""
    contagem = {}
    for e in eventos:
        tipo = e["tipo"]
        contagem[tipo] = contagem.get(tipo, 0) + 1
        gravar = GRAVAR_EVENTO.get(tipo)
        if gravar:
            gravar(cur, e, cfg)
    return contagem


# ---------------------------------------------------------------------------
# Processamento
# ---------------------------------------------------------------------------

def processar_linhas(conn, linhas):
    """Processa as leituras recém-gravadas (vaca_id, membro, quarto, temp_raw e
    timestamp com fuso). Uma transação por animal. Retorna a contagem de eventos."""
    with conn.cursor() as cur:
        cfg = carregar_config(cur)
    conn.commit()

    pacotes, avisos = linhas_para_pacotes(linhas, n_sensores=cfg.n_sensores)
    for a in avisos:
        logger.warning("detector: %s", a)
    por_vaca = {}
    for p in pacotes:
        por_vaca.setdefault(p["vaca_id"], []).append(p)

    total = {}
    for vaca_id, pacotes_vaca in por_vaca.items():
        try:
            with conn.cursor() as cur:
                _travar(cur, vaca_id)
                estado = _carregar_estado(cur, vaca_id)
                for p in pacotes_vaca:
                    _recalcular_baseline(cur, vaca_id, p["ts"], cfg)
                    baseline = _carregar_baseline(cur, vaca_id)
                    estado, eventos = step(estado, p, cfg, baseline, copiar=False)
                    _somar(total, _persistir(cur, eventos, cfg))
                _salvar_estado(cur, vaca_id, estado)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return total


def fechar_vencidos_todos(conn, agora, esperar=False, exceto=()):
    """Fecha os bins vencidos de todos os animais. Com esperar=False, pula o animal
    cuja trava está ocupada (o worker que está com ela fecha os bins)."""
    with conn.cursor() as cur:
        cfg = carregar_config(cur)
        cur.execute("SELECT vaca_id FROM estado_detector")
        vacas = [r[0] for r in cur.fetchall() if r[0] not in exceto]
    conn.commit()

    for vaca_id in vacas:
        try:
            with conn.cursor() as cur:
                if not _travar(cur, vaca_id, esperar):
                    conn.rollback()
                    continue
                estado = _carregar_estado(cur, vaca_id)
                baseline = _carregar_baseline(cur, vaca_id)
                estado, eventos = fechar_vencidos(estado, agora - MARGEM_FECHAMENTO_S, cfg, baseline, copiar=False)
                if eventos:
                    _persistir(cur, eventos, cfg)
                    _salvar_estado(cur, vaca_id, estado)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return cfg


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def _sensores_invalidos(cur, vaca_id, membro, ciclo_ts, cfg):
    """Sensores inválidos no último ciclo fechado do membro e o motivo de cada um.

    Refaz a mediana por sensor das leituras do bin e aplica a mesma validação do
    detector. Motivos: "ausente" (sem leitura válida no bin), "fora_da_faixa" ou
    "frio" (perda de contato). Retorna None se o membro ainda não tem ciclo."""
    if ciclo_ts is None:
        return None
    cur.execute(
        """SELECT quarto, percentile_cont(0.5) WITHIN GROUP (ORDER BY temp_raw)
             FROM leituras
            WHERE vaca_id = %s AND membro IS NOT DISTINCT FROM %s AND temp_raw IS NOT NULL
              AND timestamp >= %s AND timestamp < %s + make_interval(secs => %s)
            GROUP BY quarto""",
        (vaca_id, _membro_db(membro), ciclo_ts, ciclo_ts, cfg.ciclo_s))
    medianas = dict(cur.fetchall())
    T = [medianas.get(i + 1) for i in range(cfg.n_sensores)]
    validos, frios = validar(T, cfg)

    saida = []
    for i, ok in enumerate(validos):
        if ok:
            continue
        if T[i] is None:
            motivo = "ausente"
        elif i in frios:
            motivo = "frio"
        else:
            motivo = "fora_da_faixa"
        saida.append({"sensor": i + 1, "motivo": motivo})
    return saida


def _progresso_armamento(baseline, vaca_id, membro, cfg):
    """Quanto falta para a linha de base do membro ficar pronta.

    dias: maior número de dias distintos de uma célula sensor-hora;
    celulas_armadas: horas do dia (de 24) em que pelo menos n_min_validos sensores
    estão armados, ou seja, em que o membro já consegue calcular os componentes."""
    sensores = baseline.get(f"{vaca_id}|{membro}", {})
    dias = max((c["dias"] for horas in sensores.values() for c in horas.values()), default=0)
    armadas = 0
    for h in range(24):
        n_armados = sum(consultar(baseline, vaca_id, membro, i + 1, h, cfg)[1] for i in range(cfg.n_sensores))
        if n_armados >= cfg.n_min_validos:
            armadas += 1
    return {"dias": dias, "dias_necessarios": cfg.arm_dias, "celulas_armadas": armadas, "celulas_total": 24}


def _estado_do_animal(membros):
    if not membros:
        return "SEM_DADOS"
    if any(m["alerta_aberto"] for m in membros):
        return "ALERTA"
    return min((m["estado"] for m in membros), key=PRIORIDADE_ANIMAL.index)


def consultar_estado(conn, agora):
    """GET /estado: todos os animais (inclusive os que só têm leituras antigas) e seus membros."""
    cfg = fechar_vencidos_todos(conn, agora)
    with conn.cursor() as cur:
        # Lista os animais e a última leitura de cada um usando o índice (sem varrer a tabela)
        cur.execute(
            """WITH RECURSIVE v AS (
                   SELECT min(vaca_id) AS vaca_id FROM leituras
                   UNION ALL
                   SELECT (SELECT min(vaca_id) FROM leituras WHERE vaca_id > v.vaca_id) FROM v
                    WHERE v.vaca_id IS NOT NULL)
               SELECT v.vaca_id,
                      (SELECT timestamp FROM leituras l WHERE l.vaca_id = v.vaca_id
                        ORDER BY timestamp DESC LIMIT 1)
                 FROM v WHERE v.vaca_id IS NOT NULL""")
        ultima = dict(cur.fetchall())

        cur.execute("SELECT vaca_id, versao, estado FROM estado_detector")
        estados = {v: {"versao": ver, "vacas": {v: e}} for v, ver, e in cur.fetchall()}

        cur.execute(
            """SELECT DISTINCT ON (vaca_id, membro) vaca_id, membro, ciclo_ts, estado, t_media, dt_b, dt_c,
                      dt_i_max, n_validos
                 FROM deteccao_ciclos
                ORDER BY vaca_id, membro, ciclo_ts DESC""")
        ultimo_ciclo, ts_ultimo_ciclo = {}, {}
        for vaca_id, membro, ciclo_ts, est, t_media, dt_b, dt_c, dt_i_max, n_validos in cur.fetchall():
            ultimo_ciclo[(vaca_id, membro)] = {"ts": _iso(ciclo_ts), "estado": est, "t_media": t_media,
                                               "dt_b": dt_b, "dt_c": dt_c, "dt_i_max": dt_i_max,
                                               "n_validos": n_validos}
            ts_ultimo_ciclo[(vaca_id, membro)] = ciclo_ts

        baselines = {v: _carregar_baseline(cur, v) for v in estados}
        invalidos = {chave: _sensores_invalidos(cur, *chave, ts, cfg) for chave, ts in ts_ultimo_ciclo.items()}
    conn.commit()

    animais = []
    for vaca_id in sorted(set(ultima) | set(estados)):
        membros = []
        if vaca_id in estados:
            for m in estado_atual(estados[vaca_id], agora, cfg):
                chave = (vaca_id, m["membro"])
                membros.append({
                    "membro": m["membro"], "estado": m["estado"], "alerta_aberto": m["alerta_aberto"],
                    "componentes": m["componentes"], "ultima_leitura": _iso(m["ultimo_ts"]),
                    "ultimo_ciclo": ultimo_ciclo.get(chave),
                    "sensores_invalidos": invalidos.get(chave),
                    "progresso_armamento": _progresso_armamento(baselines[vaca_id], vaca_id, m["membro"], cfg),
                })
        membros.sort(key=lambda x: x["membro"])
        animais.append({"vaca_id": vaca_id, "estado": _estado_do_animal(membros),
                        "ultima_leitura": _iso(ultima.get(vaca_id)), "membros": membros})
    return {"agora": _iso(agora), "parametros": parametros_publicos(cfg), "animais": animais}


def consultar_alertas(conn, vaca_id=None, abertos=None, limite=200):
    cond, args = [], []
    if vaca_id:
        cond.append("vaca_id = %s")
        args.append(vaca_id)
    if abertos is True:
        cond.append("fim IS NULL")
    elif abertos is False:
        cond.append("fim IS NOT NULL")
    where = ("WHERE " + " AND ".join(cond)) if cond else ""

    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT id, vaca_id, membro, componentes, primeiro, inicio, inicio_elevacao, fim, picos, parametros_json
                  FROM alertas {where} ORDER BY inicio DESC LIMIT %s""", args + [limite])
        linhas = _linhas_como_dicts(cur)
    conn.commit()

    for l in linhas:
        for k in ("inicio", "inicio_elevacao", "fim"):
            l[k] = _iso(l[k])
        l["aberto"] = l["fim"] is None
        l["parametros"] = l.pop("parametros_json")
    return linhas


def consultar_deteccao(conn, vaca_id, membro=None, de=None, ate=None, limite=5000):
    cond, args = ["vaca_id = %s"], [vaca_id]
    if membro:
        cond.append("membro = %s")
        args.append(membro)
    if de is not None:
        cond.append("ciclo_ts >= %s")
        args.append(de)
    if ate is not None:
        cond.append("ciclo_ts < %s")
        args.append(ate)

    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT vaca_id, membro, ciclo_ts, t_media, dt_b, dt_c, dt_i_max, n_validos, estado, congelado, dt_i
                  FROM deteccao_ciclos WHERE {' AND '.join(cond)}
                 ORDER BY ciclo_ts DESC, membro LIMIT %s""", args + [limite])
        linhas = _linhas_como_dicts(cur)
    conn.commit()

    for l in linhas:
        l["ciclo_ts"] = _iso(l["ciclo_ts"])
    return linhas


__all__ = ["carregar_config", "processar_linhas", "fechar_vencidos_todos", "consultar_estado",
           "consultar_alertas", "consultar_deteccao", "parametros_publicos"]
