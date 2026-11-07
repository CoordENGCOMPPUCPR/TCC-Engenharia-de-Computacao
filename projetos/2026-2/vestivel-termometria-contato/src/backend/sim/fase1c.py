"""Experimentos da Fase 1C e seus critérios de aprovação.

Usado por scripts/fase1c.py. Os critérios foram definidos antes de rodar os
experimentos (docs/regra-de-alerta.md, seção 12.1) e não devem ser mudados.
Todos os dados são sintéticos.
"""

import math
import random

from detector import Config
from sim.gerador import INGREDIENTES, T_INICIO, Injecao, Premissas, gerar
from sim.rodar import executar

DESCARTE_D = 4
DIAS_CP05 = 100
SEMENTES_CP05 = range(1, 9)
SEMENTES_RAMPA = range(1, 9)
PREM_LIMPA_RAMPA = ("ambiente", "ambiente_dia", "deriva", "decubito", "idio")

# Critérios de aprovação
CP05_MEDIA_MAX = 0.05          # aberturas por animal-dia, média das sementes
CP05_SEMENTE_MAX = 0.10        # aberturas por animal-dia, cada semente
CP05_TEMPO_ALERTA_MAX = 0.05   # fração do tempo em alerta, média das sementes
CP05_ARMANDO_MAX = 0.05        # ARMANDO / bins com dados, cada membro de cada semente
CP05_FECHA_MAX_H = 48.0        # fechamento em até 48 h após o fim da elevação
CP01_AMP = 2.0
CP01_TAXA_MIN = 0.90
RAMPA_AMP = 1.5
RAMPA_FECHA_MAX_H = 48.0


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(max(0.0, c - h), 3), round(min(1.0, c + h), 3))


# ---------------------------------------------------------------------------
# CP-05
# ---------------------------------------------------------------------------

def _acima_fecho(c, cfg):
    """O bin ainda conta como elevado para o fechamento (algum componente >= histerese * lambda)?"""
    h = cfg.histerese
    if c["dt_i_max"] is not None and c["dt_i_max"] >= h * cfg.lambda_s:
        return True
    if c["dt_b"] is not None and c["dt_b"] >= h * cfg.lambda_b:
        return True
    if c["dt_c"] is not None:
        exc = c["dt_c"] if c["membro"] == "E" else -c["dt_c"]
        if exc >= h * cfg.lambda_c:
            return True
    return False


def atrasos_de_fechamento(res, cfg, fim_sim):
    """Horas entre o fim da elevação e o fechamento de cada alerta.

    Fim da elevação = fim do último bin do alerta ainda elevado. Alerta que continua
    aberto no fim da simulação conta até fim_sim."""
    por_membro = {}
    for c in res.ciclos:
        por_membro.setdefault(c["membro"], []).append(c)
    alertas = [(f["membro"], f["inicio_elevacao"], f["fim"], False) for f in res.fechamentos]
    for vaca in res.estado["vacas"].values():
        for m, st in vaca["membros"].items():
            if st["alerta"] is not None:
                alertas.append((m, st["alerta"]["inicio_elevacao"], fim_sim, True))
    out = []
    for m, ini, fim, aberto in alertas:
        acima = [c["ts"] for c in por_membro.get(m, []) if ini <= c["ts"] < fim and _acima_fecho(c, cfg)]
        fim_elev = (acima[-1] + cfg.ciclo_s) if acima else ini
        out.append({"membro": m, "aberto_no_fim": aberto, "atraso_h": (fim - fim_elev) / 3600})
    return out


def tarefa_cp05(modelo, semente, cfg=None):
    cfg = cfg or Config()
    prem = Premissas() if modelo == "completo" else Premissas().sem(*INGREDIENTES)
    dias = DESCARTE_D + DIAS_CP05
    corte, fim = T_INICIO + DESCARTE_D * 86400, T_INICIO + dias * 86400
    res = executar(gerar(prem, semente, dias), cfg, fim=fim)
    linha = {"modelo": modelo, "semente": semente, "dias": DIAS_CP05,
             "aberturas": sum(1 for a in res.aberturas if a["ts"] >= corte)}
    for comp in ("S", "B", "C"):
        linha[f"com_{comp}"] = sum(1 for a in res.aberturas if a["ts"] >= corte and comp in a["componentes"])
    linha["aberturas_por_animal_dia"] = linha["aberturas"] / DIAS_CP05
    linha["aberturas_por_membro_dia"] = linha["aberturas"] / (2 * DIAS_CP05)
    tempos = []
    for m in ("E", "D"):
        cs = [c for c in res.ciclos if c["ts"] >= corte and c["membro"] == m]
        armando = sum(1 for c in cs if c["dt_b"] is None and c["n_validos"] >= cfg.n_min_validos)
        falha = sum(1 for c in cs if c["n_validos"] < cfg.n_min_validos)
        alerta = sum(1 for c in cs if c["estado"] == "ALERTA")
        bins_periodo = int((fim - corte) // cfg.ciclo_s)
        linha[f"{m}_bins_com_dados"] = len(cs)
        linha[f"{m}_frac_armando_dados"] = armando / len(cs)
        linha[f"{m}_frac_armando_periodo"] = armando / bins_periodo
        linha[f"{m}_frac_falha_dados"] = falha / len(cs)
        linha[f"{m}_frac_tempo_alerta"] = alerta / len(cs)
        tempos.append(alerta / len(cs))
    linha["frac_tempo_alerta"] = sum(tempos) / 2
    atr = atrasos_de_fechamento(res, cfg, fim)
    linha["alertas_total"] = len(atr)
    linha["atraso_fechamento_max_h"] = round(max((a["atraso_h"] for a in atr), default=0.0), 2)
    linha["alertas_atraso_acima_48h"] = sum(1 for a in atr if a["atraso_h"] > CP05_FECHA_MAX_H)
    linha["abertos_no_fim"] = sum(1 for a in atr if a["aberto_no_fim"])
    return linha


def avaliar_cp05(linhas):
    ls = [l for l in linhas if l["modelo"] == "completo"]
    media = sum(l["aberturas_por_animal_dia"] for l in ls) / len(ls)
    c1 = media <= CP05_MEDIA_MAX and all(l["aberturas_por_animal_dia"] <= CP05_SEMENTE_MAX for l in ls)
    tempo = sum(l["frac_tempo_alerta"] for l in ls) / len(ls)
    c2 = tempo <= CP05_TEMPO_ALERTA_MAX
    arm = [l[f"{m}_frac_armando_dados"] for l in ls for m in ("E", "D")]
    c3 = all(x <= CP05_ARMANDO_MAX for x in arm)
    c4 = all(l["alertas_atraso_acima_48h"] == 0 for l in ls)
    return {"c1_aberturas": c1, "media_aberturas_animal_dia": media,
            "max_semente_aberturas_animal_dia": max(l["aberturas_por_animal_dia"] for l in ls),
            "c2_tempo_alerta": c2, "media_tempo_alerta": tempo,
            "c3_armando": c3, "armando_max": max(arm), "armando_media": sum(arm) / len(arm),
            "c4_sem_travamento": c4, "atraso_max_h": max(l["atraso_fechamento_max_h"] for l in ls),
            "aprovado": c1 and c2 and c3 and c4}


# ---------------------------------------------------------------------------
# CP-01
# ---------------------------------------------------------------------------

def tarefa_cp01(amp, semente, cfg=None):
    """Degrau de `amp` °C num sensor sorteado do membro E, em hora aleatória do 11º dia,
    por 12 h (como na Fase 1B). Conta os ciclos válidos a partir do bin onde a elevação começa."""
    cfg = cfg or Config()
    rng = random.Random(20_000 + semente)
    t0 = T_INICIO + (10 + rng.random()) * 86400
    sensor = rng.randrange(5)
    inj = Injecao("E", (sensor,), amp, t0, rampa_h=0, dur_h=12)
    fim = t0 + 86400
    res = executar(gerar(Premissas(), semente, (fim - T_INICIO) / 86400 + 0.01, injecoes=[inj]), cfg, fim=fim)
    bin0 = t0 // cfg.ciclo_s * cfg.ciclo_s
    e = [c for c in res.ciclos if c["membro"] == "E"]
    antes = [c for c in e if c["ts"] < bin0]
    ja = bool(antes) and antes[-1]["estado"] == "ALERTA"
    validos = [c for c in e if c["ts"] >= bin0 and c["dt_b"] is not None and c["ts"] < inj.fim]
    disparo = next((k + 1 for k, c in enumerate(validos) if c["acima"]["S"] >= cfg.n_persist), None)
    return {"amp": amp, "semente": semente, "sensor": sensor + 1,
            "hora_local_t0": round(((t0 - T_INICIO) % 86400) / 3600, 2), "ja_em_alerta": ja,
            "ciclos_validos_ate_disparo_S": disparo,
            "aprovado": disparo is not None and disparo <= cfg.n_persist + 1}


def resumir_cp01(linhas, alvo):
    """Pega as `alvo` primeiras repetições avaliáveis (em ordem de semente) e conta as descartadas."""
    aval, desc = [], 0
    for l in sorted(linhas, key=lambda x: x["semente"]):
        if len(aval) == alvo:
            break
        if l["ja_em_alerta"]:
            desc += 1
        else:
            aval.append(l)
    k = sum(l["aprovado"] for l in aval)
    return {"avaliaveis": len(aval), "descartadas": desc, "sementes_usadas": len(aval) + desc,
            "aprovadas": k, "taxa": k / len(aval) if aval else None, "ic95": wilson(k, len(aval)),
            "ciclos": [l["ciclos_validos_ate_disparo_S"] for l in aval]}


def avaliar_cp01(linhas):
    r10, r50 = resumir_cp01(linhas, 10), resumir_cp01(linhas, 50)
    ok = (r10["avaliaveis"] == 10 and r10["aprovadas"] == 10
          and r50["avaliaveis"] == 50 and r50["taxa"] >= CP01_TAXA_MIN)
    return {"10": r10, "50": r50, "aprovado": ok}


# ---------------------------------------------------------------------------
# Rampa 0 -> amp em 48 h + patamar de 14 dias
# ---------------------------------------------------------------------------

def tarefa_rampa(modelo, amp, semente, cfg=None):
    cfg = cfg or Config()
    prem = Premissas() if modelo == "completo" else Premissas().sem(*PREM_LIMPA_RAMPA)
    rng = random.Random(semente)
    t0 = T_INICIO + (10 + rng.random()) * 86400
    inj = Injecao("E", (0, 1, 2, 3, 4), amp, t0, rampa_h=48, dur_h=14 * 24)
    fim = inj.fim + 10 * 86400
    res = executar(gerar(prem, semente, (fim - T_INICIO) / 86400, membros=("E",), injecoes=[inj]), cfg, fim=fim)
    d = lambda t: round((t - t0) / 86400, 2)  # noqa: E731
    lim = inj.fim + RAMPA_FECHA_MAX_H * 3600
    ab = [a for a in res.aberturas if t0 <= a["ts"] < inj.fim]
    fp = [f for f in res.fechamentos if t0 + 48 * 3600 <= f["fim"] < inj.fim]
    fd = [f for f in res.fechamentos if inj.fim <= f["fim"] <= lim]
    # ainda havia alerta aberto no instante lim?
    aberto_lim = any(a["ts"] < lim and not any(f["inicio_elevacao"] == a["inicio_elevacao"] and f["fim"] <= lim
                                               for f in res.fechamentos)
                     for a in res.aberturas)
    pat = [c for c in res.ciclos if t0 + 48 * 3600 <= c["ts"] < inj.fim]
    apos = [c for c in res.ciclos if c["ts"] >= inj.fim + 86400]
    m = res.estado["vacas"]["sim01"]["membros"]["E"]
    detectou = bool(ab)
    fechou = bool(fd) and not aberto_lim
    return {"modelo": modelo, "amp": amp, "semente": semente, "fim_elevacao_d": d(inj.fim),
            "c1_detectou": detectou, "latencia_h": round((ab[0]["ts"] - t0) / 3600, 2) if ab else None,
            "fechou_no_patamar": bool(fp), "dias_ate_fechar_no_patamar": d(fp[0]["fim"]) if fp else None,
            "c2_fechou_ate_48h_apos_o_fim": fechou,
            "horas_apos_o_fim_ate_fechar": round((fd[0]["fim"] - inj.fim) / 3600, 2) if fd else None,
            "aberto_48h_apos_o_fim": aberto_lim,
            "frac_alerta_no_patamar": round(sum(c["estado"] == "ALERTA" for c in pat) / len(pat), 3),
            "travou": m["alerta"] is not None and bool(apos) and all(c["dt_b"] is None for c in apos),
            "aprovado": detectou and fechou}
