"""Núcleo do detector: uma função de transição de estado.

    novo_estado, eventos = step(estado, entrada, config, baseline)

O estado é um dict serializável em JSON, para o backend gravar no banco depois de
cada ingestão e continuar de onde parou se o processo reiniciar.

Entrada (um pacote LoRa de um membro):
    {"vaca_id": str, "membro": "E" | "D" | "U", "ts": float (s, UTC), "T": [T1..Tn]}
T = None indica sensor com erro. "U" é membro único (sem identificação), que
nunca tem contralateral.

Eventos emitidos (campo "tipo"):
    ciclo           bin fechado de um membro (vai para deteccao_ciclos)
    abertura        alerta aberto
    fechamento      alerta fechado
    atrasado        pacote de um bin que já foi fechado (ignorado)
    reset_baseline  só com congela_max_modo = "reset": descartar a linha de base do membro
"""

import copy
from statistics import median

from .baseline import consultar, hora_local

COMPONENTES = ("S", "B", "C")  # espacial, temporal, contralateral
VERSAO_ESTADO = 2  # a versão 2 acrescentou congelado_desde e congela_liberado


def estado_inicial():
    return {"versao": VERSAO_ESTADO, "vacas": {}}


def _novo_membro():
    return {
        "ultimo_ts": None,
        "estado": "ARMANDO",
        "cont": {c: {"acima": 0, "aus": 0, "desde": None} for c in COMPONENTES},
        "fecha": {"abaixo": 0, "aus": 0},
        "alerta": None,
        "congelado_desde": None,
        "congela_liberado": False,
    }


def _nova_vaca():
    return {"ciclo_aberto": None, "contabilizado_ate": None, "bins": {}, "membros": {}}


def _ciclo(ts, config):
    return int(ts // config.ciclo_s)


def _limiar(comp, config):
    return {"S": config.lambda_s, "B": config.lambda_b, "C": config.lambda_c}[comp]


# ---------------------------------------------------------------------------
# Validade e componentes
# ---------------------------------------------------------------------------

def validar(T, config):
    """Marca quais sensores do bin são válidos.

    Inválido: None, fora de [t_min, t_max] ou, com filtro_frio, mais frio que
    mediana - frio_delta (perda de contato). Leitura quente nunca é descartada.
    Retorna (validos, frios), com `frios` em índices começando em 0.
    """
    na_faixa = [t is not None and config.t_min <= t <= config.t_max for t in T]
    validos = list(na_faixa)
    frios = []
    if config.filtro_frio:
        vals = [t for t, ok in zip(T, na_faixa) if ok]
        if vals:
            m = median(vals)
            for i, (t, ok) in enumerate(zip(T, na_faixa)):
                if ok and t < m - config.frio_delta:
                    validos[i] = False
                    frios.append(i)
    return validos, frios


def componentes(T, B, usados):
    """Calcula dT_i e dT_b a partir dos resíduos r_i = T_i - B_i dos sensores usados.

    dT_i = r_i - média dos outros r_j
    dT_b = média de todos os r_i
    """
    idx = [i for i, u in enumerate(usados) if u]
    n = len(idx)
    r = {i: T[i] - B[i] for i in idx}
    soma = sum(r.values())
    dt_i = [None] * len(T)
    for i in idx:
        dt_i[i] = r[i] - (soma - r[i]) / (n - 1)
    return dt_i, soma / n


def _reduzir_membro(vaca_id, membro, pacotes, hora, config, baseline):
    """Junta os pacotes do bin (mediana por sensor) e calcula os componentes do membro."""
    n = config.n_sensores
    T = []
    for i in range(n):
        vals = [p[i] for p in pacotes if p[i] is not None]
        T.append(median(vals) if vals else None)

    validos, frios = validar(T, config)
    reg = {"T": T, "validos": validos, "frios": frios, "n_validos": sum(validos),
           "n_pacotes": len(pacotes), "dt_i": [None] * n, "dt_b": None, "situacao": None}
    if reg["n_validos"] < config.n_min_validos:
        reg["situacao"] = "FALHA_SENSOR"
        return reg

    B, usados = [None] * n, [False] * n
    for i in range(n):
        if validos[i]:
            b, armado = consultar(baseline, vaca_id, membro, i + 1, hora, config)
            if armado:
                B[i], usados[i] = b, True
    if sum(usados) < config.n_min_validos:
        reg["situacao"] = "ARMANDO"
        return reg

    reg["dt_i"], reg["dt_b"] = componentes(T, B, usados)
    reg["situacao"] = "CALCULADO"
    reg["usados"] = usados
    return reg


# ---------------------------------------------------------------------------
# Persistência e histerese
# ---------------------------------------------------------------------------

def _ausente(m, comps, k, config):
    """k bins sem valor para os componentes: o contador pausa; passou de G, zera."""
    for c in comps:
        ct = m["cont"][c]
        ct["aus"] += k
        if ct["aus"] > config.g_ausentes:
            ct["acima"] = 0
            ct["desde"] = None


def _ausente_fecha(m, k, config):
    f = m["fecha"]
    f["aus"] += k
    if f["aus"] > config.g_ausentes:
        f["abaixo"] = 0


def _contar(m, comp, valor, limiar, ciclo_ts):
    ct = m["cont"][comp]
    ct["aus"] = 0
    if valor > limiar:
        if ct["acima"] == 0:
            ct["desde"] = ciclo_ts
        ct["acima"] += 1
    else:
        ct["acima"] = 0
        ct["desde"] = None


def _atualizar_alerta(vaca_id, membro, m, reg, valores, ts0, config):
    """Abre, atualiza ou fecha o alerta do membro. Retorna os eventos gerados."""
    eventos = []
    fim_bin = ts0 + config.ciclo_s
    disparados = [c for c in COMPONENTES if m["cont"][c]["acima"] >= config.n_persist]

    al = m["alerta"]
    if al is None and disparados:
        al = m["alerta"] = {
            "inicio": fim_bin,  # quando a persistência se completou
            "inicio_elevacao": min(m["cont"][c]["desde"] for c in disparados),
            "componentes": list(disparados),
            "primeiro": disparados[0],
            "picos": {c: None for c in COMPONENTES},
        }
        m["fecha"] = {"abaixo": 0, "aus": 0}
        eventos.append({"tipo": "abertura", "vaca_id": vaca_id, "membro": membro,
                        "ts": al["inicio"], "inicio_elevacao": al["inicio_elevacao"],
                        "componentes": list(disparados), "primeiro": al["primeiro"]})

    if al is None:
        return eventos

    for c in disparados:
        if c not in al["componentes"]:
            al["componentes"].append(c)
    for c in COMPONENTES:
        v = valores[c]
        if v is not None and (al["picos"][c] is None or v > al["picos"][c]):
            al["picos"][c] = v

    if reg["situacao"] != "CALCULADO":
        _ausente_fecha(m, 1, config)
        return eventos

    abaixo = all(valores[c] is None or valores[c] < config.histerese * _limiar(c, config)
                 for c in COMPONENTES)
    f = m["fecha"]
    f["aus"] = 0
    f["abaixo"] = f["abaixo"] + 1 if abaixo else 0
    if f["abaixo"] >= config.n_persist:
        eventos.append({"tipo": "fechamento", "vaca_id": vaca_id, "membro": membro,
                        "inicio": al["inicio"], "inicio_elevacao": al["inicio_elevacao"],
                        "fim": fim_bin, "componentes": al["componentes"],
                        "primeiro": al["primeiro"], "picos": al["picos"]})
        m["alerta"] = None
        m["fecha"] = {"abaixo": 0, "aus": 0}
    return eventos


def _atualizar_congelamento(vaca_id, membro, m, dt_b, ts0, config):
    """Decide se o ciclo fica fora da linha de base. Retorna (congelado, eventos)."""
    congelado = config.congelamento and (
        m["alerta"] is not None
        or (config.congela_frac is not None and dt_b is not None
            and dt_b > config.congela_frac * config.lambda_b))

    if not congelado:
        m["congelado_desde"] = None
        m["congela_liberado"] = False
        return False, []

    if m.get("congelado_desde") is None:
        m["congelado_desde"] = ts0
    if m.get("congela_liberado"):
        return False, []

    passou_do_limite = (config.congela_max_h is not None
                        and ts0 + config.ciclo_s - m["congelado_desde"] > config.congela_max_h * 3600)
    if not passou_do_limite:
        return True, []

    m["congela_liberado"] = True
    eventos = []
    if config.congela_max_modo == "reset":
        eventos.append({"tipo": "reset_baseline", "vaca_id": vaca_id, "membro": membro,
                        "ts": ts0, "congelado_desde": m["congelado_desde"]})
    return False, eventos


# ---------------------------------------------------------------------------
# Fechamento de bins
# ---------------------------------------------------------------------------

def _processar_bin(vaca_id, vaca, c0, config, baseline):
    """Fecha o bin c0 de todos os membros da vaca. Retorna os eventos."""
    eventos = []
    ts0 = c0 * config.ciclo_s
    h = hora_local(ts0, config.fuso)

    calc = {membro: _reduzir_membro(vaca_id, membro, pacotes, h, config, baseline)
            for membro, pacotes in vaca["bins"].items()}

    # Contralateral: só quando E e D têm componentes no mesmo bin. Sempre E - D.
    dt_c = None
    if all(m in calc and calc[m]["dt_b"] is not None for m in ("E", "D")):
        dt_c = calc["E"]["dt_b"] - calc["D"]["dt_b"]

    for membro, m in vaca["membros"].items():
        reg = calc.get(membro)
        if reg is None:
            _ausente(m, COMPONENTES, 1, config)
            _ausente_fecha(m, 1, config)
            continue

        valores = {"S": None, "B": None, "C": None}
        if reg["situacao"] == "CALCULADO":
            valores["S"] = max(v for v in reg["dt_i"] if v is not None)
            valores["B"] = reg["dt_b"]
            if dt_c is not None:
                valores["C"] = dt_c if membro == "E" else -dt_c
        for comp in COMPONENTES:
            if valores[comp] is None:
                _ausente(m, (comp,), 1, config)
            else:
                _contar(m, comp, valores[comp], _limiar(comp, config), ts0)

        eventos += _atualizar_alerta(vaca_id, membro, m, reg, valores, ts0, config)

        if m["alerta"] is not None:
            m["estado"] = "ALERTA"
        elif reg["situacao"] == "CALCULADO":
            m["estado"] = "OK"
        else:
            m["estado"] = reg["situacao"]  # FALHA_SENSOR ou ARMANDO

        congelado, ev = _atualizar_congelamento(vaca_id, membro, m, reg["dt_b"], ts0, config)
        eventos += ev

        validos = reg["validos"]
        n_validos = reg["n_validos"]
        eventos.append({
            "tipo": "ciclo", "vaca_id": vaca_id, "membro": membro, "ts": ts0, "hora_local": h,
            "n_pacotes": reg["n_pacotes"], "n_validos": n_validos,
            # só os válidos: é isso que entra na linha de base
            "T": [t if ok else None for t, ok in zip(reg["T"], validos)],
            "T_bruta": reg["T"], "frios": [i + 1 for i in reg["frios"]],
            "t_media": (sum(t for t, ok in zip(reg["T"], validos) if ok) / n_validos
                        if n_validos else None),
            "dt_i": reg["dt_i"], "dt_i_max": valores["S"], "dt_b": reg["dt_b"],
            "dt_c": dt_c if membro in ("E", "D") else None,
            "acima": {c: m["cont"][c]["acima"] for c in COMPONENTES},
            "estado": m["estado"], "congelado": congelado,
        })
    vaca["bins"] = {}
    return eventos


def _fechar_ate(vaca_id, vaca, c_limite, config, baseline):
    """Fecha o bin aberto (se for anterior a c_limite) e conta como ausentes os
    bins vazios até c_limite - 1."""
    eventos = []
    inicio_aus = vaca["contabilizado_ate"] + 1 if vaca["contabilizado_ate"] is not None else None
    if vaca["ciclo_aberto"] is not None and vaca["ciclo_aberto"] < c_limite:
        eventos += _processar_bin(vaca_id, vaca, vaca["ciclo_aberto"], config, baseline)
        inicio_aus = vaca["ciclo_aberto"] + 1
        vaca["ciclo_aberto"] = None
    if inicio_aus is not None:
        k = c_limite - inicio_aus
        if k > 0:
            for m in vaca["membros"].values():
                _ausente(m, COMPONENTES, k, config)
                _ausente_fecha(m, k, config)
        vaca["contabilizado_ate"] = c_limite - 1
    return eventos


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def _normalizar(entrada, config):
    T = list(entrada["T"])[: config.n_sensores]
    T += [None] * (config.n_sensores - len(T))
    T = [None if t is None else float(t) for t in T]
    membro = entrada.get("membro") or "U"
    if membro not in ("E", "D", "U"):
        raise ValueError(f"membro inválido: {membro!r}")
    return str(entrada["vaca_id"]), membro, float(entrada["ts"]), T


def _migrar(estado):
    """Atualiza um estado da versão 1 com as chaves novas."""
    if estado.get("versao", 1) < VERSAO_ESTADO:
        for vaca in estado["vacas"].values():
            for m in vaca["membros"].values():
                m.setdefault("congelado_desde", None)
                m.setdefault("congela_liberado", False)
        estado["versao"] = VERSAO_ESTADO


def step(estado, entrada, config, baseline, copiar=True):
    """Processa um pacote. Retorna (novo_estado, eventos).

    Com copiar=False o estado recebido é alterado no lugar (mais rápido, usado na simulação).
    """
    estado = copy.deepcopy(estado) if copiar else estado
    _migrar(estado)
    vaca_id, membro, ts, T = _normalizar(entrada, config)
    vaca = estado["vacas"].setdefault(vaca_id, _nova_vaca())
    c = _ciclo(ts, config)
    aberto = vaca["ciclo_aberto"]

    atrasado = (c < aberto) if aberto is not None else (
        vaca["contabilizado_ate"] is not None and c <= vaca["contabilizado_ate"])
    if atrasado:
        return estado, [{"tipo": "atrasado", "vaca_id": vaca_id, "membro": membro, "ts": ts}]

    eventos = []
    if aberto is None or c > aberto:
        eventos += _fechar_ate(vaca_id, vaca, c, config, baseline)
        vaca["ciclo_aberto"] = c

    m = vaca["membros"].setdefault(membro, _novo_membro())
    m["ultimo_ts"] = ts if m["ultimo_ts"] is None else max(m["ultimo_ts"], ts)
    vaca["bins"].setdefault(membro, []).append(T)
    return estado, eventos


def fechar_vencidos(estado, agora, config, baseline, copiar=True):
    """Fecha os bins que já terminaram em `agora`, sem esperar o próximo pacote."""
    estado = copy.deepcopy(estado) if copiar else estado
    _migrar(estado)
    eventos = []
    c_agora = _ciclo(agora, config)
    for vaca_id, vaca in estado["vacas"].items():
        aberto, contado = vaca["ciclo_aberto"], vaca["contabilizado_ate"]
        if (aberto is not None and aberto < c_agora) or (
                aberto is None and contado is not None and contado < c_agora - 1):
            eventos += _fechar_ate(vaca_id, vaca, c_agora, config, baseline)
    return estado, eventos


def estado_atual(estado, agora, config):
    """Resumo por vaca e membro. Mostra SEM_DADOS quando o último pacote tem mais
    de sem_dados_min minutos (o alerta aberto continua indicado)."""
    res = []
    for vaca_id, vaca in estado["vacas"].items():
        for membro, m in vaca["membros"].items():
            idade = None if m["ultimo_ts"] is None else agora - m["ultimo_ts"]
            sem_dados = idade is None or idade > config.sem_dados_min * 60
            res.append({
                "vaca_id": vaca_id, "membro": membro,
                "estado": "SEM_DADOS" if sem_dados else m["estado"],
                "alerta_aberto": m["alerta"] is not None,
                "componentes": list(m["alerta"]["componentes"]) if m["alerta"] else [],
                "ultimo_ts": m["ultimo_ts"],
            })
    return res
