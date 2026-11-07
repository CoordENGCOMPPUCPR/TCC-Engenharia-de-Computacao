"""Experimentos da Fase 1B (dados sintéticos).

Subcomandos (os CSV vão para docs/resultados/fase1b/):
  a      componente espacial com a variação própria de cada sensor: lambda x variantes
  cp05   variantes do gerador x regras de congelamento: alertas, disponibilidade
         (ARMANDO, FALHA_SENSOR) e tempo em alerta, por semente e membro
  rampa  rampa de 0 a 1,5 °C em 48 h + patamar de 14 dias, por regra de congelamento
  b      superfície N x duração do decúbito x lambda (2 membros): falsos alarmes,
         tempo em alerta e detecção num subconjunto, com controle pareado
  bdet   só a parte de detecção de b
  e      detecção: 160 condições x 50 sementes, com controle pareado
  h      CP-01: +1,5 °C em um sensor deve disparar o espacial em até N+1 ciclos válidos
  todos  roda todos

Uso: python scripts/fase1b.py <subcomando> [--sementes K] [--saida DIR]
"""

import argparse
import csv
import math
import os
import random
import sys
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detector import Config  # noqa: E402
from sim.gerador import INGREDIENTES, T_INICIO, Injecao, Premissas, gerar  # noqa: E402
from sim.rodar import Simulador, executar  # noqa: E402

DESCARTE_D = 4
SAIDA = "docs/resultados/fase1b"
LAMBDAS = (0.5, 1.0, 1.5, 2.0)
AMPS = (0.5, 1.0, 1.5, 2.0, 3.0)
FORMAS = {"degrau_5": ((0, 1, 2, 3, 4), 0.0), "degrau_1": ((0,), 0.0),
          "rampa_12h": ((0, 1, 2, 3, 4), 12.0), "rampa_48h": ((0, 1, 2, 3, 4), 48.0)}
PATAMAR_H = 24.0


# ---------------------------------------------------------------------------
# Estatística
# ---------------------------------------------------------------------------

def wilson(k, n, z=1.96):
    """IC de 95% de Wilson para k sucessos em n."""
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(max(0.0, c - h), 3), round(min(1.0, c + h), 3))


def bootstrap_diferenca(pares, b=4000, semente=0):
    """Diferença média pareada (detecção - controle) e IC de 95% por bootstrap."""
    if not pares:
        return (None, None, None)
    rng = random.Random(semente)
    d = [x - y for x, y in pares]
    n = len(d)
    medias = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(b))
    return (round(sum(d) / n, 3), round(medias[int(0.025 * b)], 3), round(medias[int(0.975 * b) - 1], 3))


def gravar(nome, linhas, saida):
    os.makedirs(saida, exist_ok=True)
    campos = []
    for l in linhas:
        for k in l:
            if k not in campos:
                campos.append(k)
    caminho = os.path.join(saida, nome)
    with open(caminho, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)
    print("gravado", caminho)


def membros_de(n):
    return ("E", "D") if n == 2 else ("E",)


def medir(res, corte, fim, membros, n_persist):
    """Métricas de uma execução, contando só depois do corte (fim do armamento)."""
    bins_periodo = int((fim - corte) // 300)
    out = {"aberturas": sum(1 for a in res.aberturas if a["ts"] >= corte)}
    for c in ("S", "B", "C"):
        out[f"com_{c}"] = sum(1 for a in res.aberturas if a["ts"] >= corte and c in a["componentes"])
        out[f"disparos_{c}"] = sum(1 for x in res.ciclos if x["ts"] >= corte and x["acima"][c] == n_persist)
    for m in membros:
        cs = [x for x in res.ciclos if x["ts"] >= corte and x["membro"] == m]
        armando = sum(1 for x in cs if x["dt_b"] is None and x["n_validos"] >= 3)  # sem componentes por falta de linha de base
        falha = sum(1 for x in cs if x["n_validos"] < 3)
        alerta = sum(1 for x in cs if x["estado"] == "ALERTA")
        out[f"{m}_bins_com_dados"] = len(cs)
        out[f"{m}_bins_periodo"] = bins_periodo
        out[f"{m}_armando"] = armando
        out[f"{m}_falha"] = falha
        out[f"{m}_frac_armando_dados"] = round(armando / len(cs), 5) if cs else None
        out[f"{m}_frac_armando_periodo"] = round(armando / bins_periodo, 5)
        out[f"{m}_frac_falha_dados"] = round(falha / len(cs), 5) if cs else None
        out[f"{m}_frac_tempo_alerta"] = round(alerta / len(cs), 5) if cs else None
    return out


# ---------------------------------------------------------------------------
# a) Espacial com a variação própria de cada sensor
# ---------------------------------------------------------------------------

VARIANTES_IDIO = [("sem_idio", dict(idio_por_dia=0.0)), ("padrao_1.5dia_amp0.3-1.0_dur1-6h", {})] + [
    (f"idio_{pd}dia_amp{a[0]}-{a[1]}_dur{d[0]:g}-{d[1]:g}h", dict(idio_por_dia=pd, idio_amp=a, idio_dur_h=d))
    for pd in (1.0, 2.0) for a in ((0.3, 0.5), (0.3, 1.0)) for d in ((1.0, 3.0), (1.0, 6.0))]


def _tarefa_a(args):
    nome, mud, semente = args
    dias = DESCARTE_D + 40
    pac = gerar(replace(Premissas(), **mud), semente, dias)
    corte, fim = T_INICIO + DESCARTE_D * 86400, T_INICIO + dias * 86400
    linhas = []
    for lam in LAMBDAS:
        cfg = Config(lambda_s=lam, lambda_b=lam, lambda_c=lam)
        r = medir(executar(pac, cfg, fim=fim), corte, fim, ("E", "D"), cfg.n_persist)
        md = 40 * 2
        linhas.append({"variante": nome, "lambda": lam, "semente": semente, "membro_dias": md,
                       "disparos_S_md": r["disparos_S"] / md, "disparos_B_md": r["disparos_B"] / md,
                       "disparos_C_md": r["disparos_C"] / md, "aberturas_md": r["aberturas"] / md,
                       "alertas_com_S": r["com_S"]})
    return linhas


def exp_a(sementes, saida, pool):
    tarefas = [(n, m, s) for n, m in VARIANTES_IDIO for s in range(1, sementes + 1)]
    linhas = [l for ls in pool.map(_tarefa_a, tarefas) for l in ls]
    gravar("a_espacial_idio.csv", linhas, saida)
    resumo = []
    for n, _ in VARIANTES_IDIO:
        for lam in LAMBDAS:
            ls = [l for l in linhas if l["variante"] == n and l["lambda"] == lam]
            v = [l["disparos_S_md"] for l in ls]
            resumo.append({"variante": n, "lambda": lam, "n_sementes": len(ls),
                           "disparos_S_md_media": round(mean(v), 4), "min": round(min(v), 4),
                           "max": round(max(v), 4), "sementes_com_S": sum(1 for x in v if x > 0)})
    gravar("a_espacial_idio_resumo.csv", resumo, saida)


# ---------------------------------------------------------------------------
# CP-05 (f, g)
# ---------------------------------------------------------------------------

def variantes_cp05():
    p = Premissas()
    v = [("completo", p), ("limpo", p.sem(*INGREDIENTES))]
    v += [(f"sem_{i}", p.sem(i)) for i in INGREDIENTES]
    v += [(f"so_{i}", p.sem(*[j for j in INGREDIENTES if j != i])) for i in INGREDIENTES]
    v += [("completo_kappa_0.1", replace(p, kappa=0.1)), ("completo_kappa_0.5", replace(p, kappa=0.5))]
    return v


REGRAS_CONGELA = {
    "padrao_0.5": Config(),
    "desligado": Config(congelamento=False),
    "frac_1.0": Config(congela_frac=1.0),
    "so_alerta": Config(congela_frac=None),
    "liberar_24h": Config(congela_max_h=24),
    "liberar_72h": Config(congela_max_h=72),
    "liberar_168h": Config(congela_max_h=168),
    "reset_24h": Config(congela_max_h=24, congela_max_modo="reset"),
    "reset_72h": Config(congela_max_h=72, congela_max_modo="reset"),
    "reset_168h": Config(congela_max_h=168, congela_max_modo="reset"),
}


def _tarefa_cp05(args):
    nome, prem, semente, regras = args
    dias = DESCARTE_D + 100
    pac = gerar(prem, semente, dias)
    corte, fim = T_INICIO + DESCARTE_D * 86400, T_INICIO + dias * 86400
    linhas = []
    for regra in regras:
        cfg = REGRAS_CONGELA[regra]
        r = medir(executar(pac, cfg, fim=fim), corte, fim, ("E", "D"), cfg.n_persist)
        linhas.append({"variante": nome, "regra_congelamento": regra, "semente": semente, "dias": 100, **r})
    return linhas


def exp_cp05(sementes, saida, pool):
    tarefas = []
    for nome, prem in variantes_cp05():
        regras = list(REGRAS_CONGELA) if nome == "completo" else ["padrao_0.5", "desligado"]
        tarefas += [(nome, prem, s, regras) for s in range(1, sementes + 1)]
    linhas = [l for ls in pool.map(_tarefa_cp05, tarefas) for l in ls]
    gravar("cp05_disponibilidade_congelamento.csv", linhas, saida)


# ---------------------------------------------------------------------------
# g) Rampa com patamar de 14 dias, por regra de congelamento
# ---------------------------------------------------------------------------

def _tarefa_rampa(args):
    regra, semente, modelo = args
    prem = Premissas() if modelo == "completo" else Premissas().sem("ambiente", "ambiente_dia", "deriva",
                                                                    "decubito", "idio")
    rng = random.Random(semente)
    t0 = T_INICIO + (10 + rng.random()) * 86400
    inj = Injecao("E", (0, 1, 2, 3, 4), 1.5, t0, rampa_h=48, dur_h=14 * 24)
    fim = inj.fim + 86400
    dias = (fim - T_INICIO) / 86400
    res = executar(gerar(prem, semente, dias, membros=("E",), injecoes=[inj]), REGRAS_CONGELA[regra], fim=fim)
    ab = [a for a in res.aberturas if a["ts"] >= t0]
    fe = [f for f in res.fechamentos if t0 <= f["fim"] < inj.fim]
    ciclos = [c for c in res.ciclos if t0 <= c["ts"] < inj.fim]
    # No modelo completo há alertas falsos antes e durante a rampa. O fechamento indevido que
    # importa é o que acontece já no patamar (elevação cheia de 1,5 °C).
    pat0 = t0 + 48 * 3600
    fp = [f for f in res.fechamentos if pat0 <= f["fim"] < inj.fim]
    cp = [c for c in ciclos if c["ts"] >= pat0]
    return {"modelo": modelo, "regra_congelamento": regra, "semente": semente,
            "latencia_h": round((ab[0]["ts"] - t0) / 3600, 2) if ab else None,
            "fechou_com_elevacao": bool(fe),
            "dias_ate_fechar": round((fe[0]["fim"] - t0) / 86400, 2) if fe else None,
            "fechou_no_patamar": bool(fp),
            "dias_ate_fechar_no_patamar": round((fp[0]["fim"] - t0) / 86400, 2) if fp else None,
            "frac_alerta_na_elevacao": round(sum(c["estado"] == "ALERTA" for c in ciclos) / len(ciclos), 3),
            "frac_alerta_no_patamar": round(sum(c["estado"] == "ALERTA" for c in cp) / len(cp), 3),
            "resets": len(res.resets)}


def exp_rampa(sementes, saida, pool):
    tarefas = [(r, s, m) for m in ("limpo", "completo") for r in REGRAS_CONGELA for s in range(1, sementes + 1)]
    gravar("g_rampa_patamar14d.csv", pool.map(_tarefa_rampa, tarefas), saida)


# ---------------------------------------------------------------------------
# Detecção com controle pareado (usado em b e e)
# ---------------------------------------------------------------------------

def _janela(forma):
    return (FORMAS[forma][1] + PATAMAR_H) * 3600


def _detectar(args):
    """Para uma semente: roda até t0 sem injeção, guarda o estado e continua a partir
    dele com a série sem injeção (controle) e com cada uma das injeções."""
    semente, nm, configs, condicoes = args
    membros = membros_de(nm)
    rng = random.Random(10_000 + semente)
    t0 = T_INICIO + (10 + rng.random()) * 86400  # hora do dia aleatória no 11º dia
    fim = t0 + 3 * 86400
    dias = (fim - T_INICIO) / 86400 + 0.01
    prem = Premissas()
    controle = gerar(prem, semente, dias, membros=membros)
    series = {c: gerar(prem, semente, dias, membros=membros,
                       injecoes=[Injecao("E", FORMAS[c[0]][0], c[1], t0, rampa_h=FORMAS[c[0]][1], dur_h=PATAMAR_H)])
              for c in condicoes}
    antes = [p for p in controle if p["ts"] < t0]
    linhas = []
    for nome_cfg, cfg in configs:
        sim0 = Simulador(cfg, guardar_ciclos=False).alimentar(antes)
        n_antes = len(sim0.res.aberturas)
        # O bin de t0 ainda está aberto no instantâneo. Se o controle abre alerta nesse bin,
        # a causa são os bins anteriores (sem injeção): conta como "já em alerta" e a
        # repetição é excluída. A janela de detecção começa no bin de t0.
        bin0 = t0 // cfg.ciclo_s * cfg.ciclo_s

        def continuar(serie, janela):
            s = sim0.copia()
            s.alimentar([p for p in serie if p["ts"] >= t0])
            r = s.fechar(fim)
            ab = [a for a in r.aberturas[n_antes:] if a["membro"] == "E" and bin0 <= a["ts"] < t0 + janela]
            return ab[0] if ab else None

        c0 = continuar(controle, 0)
        ja = (sim0.estado["vacas"]["sim01"]["membros"]["E"]["alerta"] is not None
              or (c0 is not None and c0["ts"] < t0))

        ctrl = {}
        for (forma, amp) in condicoes:
            jan = _janela(forma)
            if jan not in ctrl:
                ctrl[jan] = continuar(controle, jan)
            a = continuar(series[(forma, amp)], jan)
            c = ctrl[jan]
            linhas.append({"config": nome_cfg, "membros": nm, "semente": semente, "forma": forma, "amp": amp,
                           "ja_em_alerta": ja, "detectado": a is not None, "controle": c is not None,
                           "latencia_h": round((a["ts"] - t0) / 3600, 2) if a else None,
                           "primeiro": a["primeiro"] if a else None})
    return linhas


def resumir_det(linhas, chaves):
    grupos = {}
    for l in linhas:
        grupos.setdefault(tuple(l[k] for k in chaves), []).append(l)
    resumo = []
    for k, ls in sorted(grupos.items()):
        val = [l for l in ls if not l["ja_em_alerta"]]
        n = len(val)
        kd = sum(l["detectado"] for l in val)
        kc = sum(l["controle"] for l in val)
        dif = bootstrap_diferenca([(int(l["detectado"]), int(l["controle"])) for l in val])
        prim = {}
        for l in val:
            if l["detectado"]:
                prim[l["primeiro"]] = prim.get(l["primeiro"], 0) + 1
        lat = [l["latencia_h"] for l in val if l["detectado"]]
        resumo.append({**dict(zip(chaves, k)), "n_total": len(ls), "n_efetivo": n,
                       "excluidas_ja_em_alerta": len(ls) - n,
                       "taxa_deteccao": round(kd / n, 3) if n else None, "ic95_det": wilson(kd, n),
                       "taxa_controle": round(kc / n, 3) if n else None, "ic95_controle": wilson(kc, n),
                       "diferenca_pareada": dif[0], "ic95_diferenca": (dif[1], dif[2]),
                       "latencia_mediana_h": round(median(lat), 2) if lat else None,
                       "primeiro_componente": " ".join(f"{a}:{b}" for a, b in sorted(prim.items()))})
    return resumo


def exp_e(sementes, saida, pool):
    configs = [(f"lambda_{lam}", Config(lambda_s=lam, lambda_b=lam, lambda_c=lam)) for lam in LAMBDAS]
    condicoes = [(f, a) for f in FORMAS for a in AMPS]
    tarefas = [(s, nm, configs, condicoes) for nm in (1, 2) for s in range(1, sementes + 1)]
    linhas = [l for ls in pool.map(_detectar, tarefas) for l in ls]
    gravar("e_deteccao_pareada.csv", linhas, saida)
    gravar("e_deteccao_resumo.csv", resumir_det(linhas, ("config", "membros", "forma", "amp")), saida)


# ---------------------------------------------------------------------------
# b) Superfície N x decúbito x lambda
# ---------------------------------------------------------------------------

NS = (6, 12, 24, 36)
DECUB_H = (0.5, 1.0, 2.0, 3.0, 6.0)


def _tarefa_b(args):
    dur, semente = args
    dias = DESCARTE_D + 40
    prem = replace(Premissas(), decub_dur_h=(0.5 * dur, 1.5 * dur))
    pac = gerar(prem, semente, dias)
    corte, fim = T_INICIO + DESCARTE_D * 86400, T_INICIO + dias * 86400
    linhas = []
    for n in NS:
        for lam in LAMBDAS:
            cfg = Config(n_persist=n, lambda_s=lam, lambda_b=lam, lambda_c=lam)
            r = medir(executar(pac, cfg, fim=fim), corte, fim, ("E", "D"), n)
            md = 80
            linhas.append({"N": n, "latencia_minima_h": n * cfg.ciclo_s / 3600, "decubito_medio_h": dur,
                           "lambda": lam, "semente": semente,
                           "aberturas_md": r["aberturas"] / md, "disparos_S_md": r["disparos_S"] / md,
                           "disparos_B_md": r["disparos_B"] / md, "disparos_C_md": r["disparos_C"] / md,
                           "frac_tempo_alerta": round((r["E_frac_tempo_alerta"] + r["D_frac_tempo_alerta"]) / 2, 4)})
    return linhas


def exp_b(sementes, saida, pool, sementes_det=20):
    linhas = [l for ls in pool.map(_tarefa_b, [(d, s) for d in DECUB_H for s in range(1, sementes + 1)])
              for l in ls]
    gravar("b_superficie.csv", linhas, saida)
    resumo = []
    for n in NS:
        for d in DECUB_H:
            for lam in LAMBDAS:
                ls = [l for l in linhas if l["N"] == n and l["decubito_medio_h"] == d and l["lambda"] == lam]
                r = {"N": n, "latencia_minima_h": ls[0]["latencia_minima_h"], "decubito_medio_h": d, "lambda": lam,
                     "n_sementes": len(ls)}
                for k in ("aberturas_md", "disparos_S_md", "disparos_B_md", "disparos_C_md", "frac_tempo_alerta"):
                    v = [l[k] for l in ls]
                    r[k] = round(mean(v), 4)
                    r[k + "_min"] = round(min(v), 4)
                    r[k + "_max"] = round(max(v), 4)
                resumo.append(r)
    gravar("b_superficie_resumo.csv", resumo, saida)
    figura_b(resumo, os.path.join(saida, "b_superficie.png"))
    exp_b_det(saida, pool, sementes_det)


def exp_b_det(saida, pool, sementes_det=20):
    # Detecção só num subconjunto: decúbito de 2 h, lambda 1,0 e 2,0, elevações de 2,0 °C
    configs = [(f"N{n}_lambda{lam}", Config(n_persist=n, lambda_s=lam, lambda_b=lam, lambda_c=lam))
               for n in NS for lam in (1.0, 2.0)]
    condicoes = [("degrau_1", 2.0), ("degrau_5", 2.0), ("rampa_12h", 2.0)]
    det = [l for ls in pool.map(_detectar, [(s, 2, configs, condicoes) for s in range(1, sementes_det + 1)])
           for l in ls]
    gravar("b_deteccao_subconjunto.csv", det, saida)
    gravar("b_deteccao_subconjunto_resumo.csv", resumir_det(det, ("config", "forma", "amp")), saida)


def figura_b(resumo, caminho):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib ausente: figura não gerada")
        return
    fig, axs = plt.subplots(2, 4, figsize=(17, 7.5))
    for lin, (k, titulo) in enumerate((("aberturas_md", "aberturas de alerta por membro-dia"),
                                       ("frac_tempo_alerta", "fração do tempo em alerta"))):
        for col, lam in enumerate(LAMBDAS):
            ax = axs[lin][col]
            mat = [[next(r[k] for r in resumo if r["N"] == n and r["decubito_medio_h"] == d and r["lambda"] == lam)
                    for d in DECUB_H] for n in NS]
            im = ax.imshow(mat, cmap="viridis", aspect="auto", origin="lower")
            ax.set_xticks(range(len(DECUB_H)), [str(d) for d in DECUB_H])
            ax.set_yticks(range(len(NS)), [f"{n} ({n * 5} min)" for n in NS])
            for i in range(len(NS)):
                for j in range(len(DECUB_H)):
                    ax.text(j, i, f"{mat[i][j]:.2f}", ha="center", va="center", color="w", fontsize=8)
            ax.set_title(f"λ = {lam} °C: {titulo}", fontsize=9)
            ax.set_xlabel("duração média do decúbito (h)")
            if col == 0:
                ax.set_ylabel("N (latência mínima)")
            fig.colorbar(im, ax=ax, fraction=0.046)
    fig.suptitle("Superfície N x decúbito x λ, 2 membros, modelo SINTÉTICO completo (sem injeção)", fontsize=10)
    fig.tight_layout()
    fig.savefig(caminho, dpi=120)
    print("gravado", caminho)


# ---------------------------------------------------------------------------
# h) CP-01
# ---------------------------------------------------------------------------

def _tarefa_h(semente):
    rng = random.Random(20_000 + semente)
    t0 = T_INICIO + (10 + rng.random()) * 86400
    sensor = rng.randrange(5)
    inj = Injecao("E", (sensor,), 1.5, t0, rampa_h=0, dur_h=12)
    fim = t0 + 86400
    cfg = Config()
    res = executar(gerar(Premissas(), semente, (fim - T_INICIO) / 86400 + 0.01, injecoes=[inj]), cfg, fim=fim)
    bin0 = t0 // cfg.ciclo_s * cfg.ciclo_s
    e = [c for c in res.ciclos if c["membro"] == "E"]
    antes = [c for c in e if c["ts"] < bin0]
    ja = bool(antes) and antes[-1]["estado"] == "ALERTA"
    validos = [c for c in e if c["ts"] >= bin0 and c["dt_b"] is not None][: cfg.n_persist + 1]
    disparou = [k for k, c in enumerate(validos) if c["acima"]["S"] >= cfg.n_persist]
    return {"semente": semente, "sensor": sensor + 1, "hora_local_t0": round(((t0 - T_INICIO) % 86400) / 3600, 2),
            "ja_em_alerta": ja, "aprovado": bool(disparou),
            "ciclos_validos_ate_disparo": disparou[0] + 1 if disparou else None}


def exp_h(saida, pool, alvo_pequeno=10, alvo_grande=50):
    linhas, s = [], 0
    while sum(1 for l in linhas if not l["ja_em_alerta"]) < alvo_grande:
        lote = list(range(s + 1, s + 1 + 16))
        s += 16
        linhas += pool.map(_tarefa_h, lote)
    gravar("h_cp01.csv", linhas, saida)
    resumo = []
    for alvo in (alvo_pequeno, alvo_grande):
        aval, descartadas = [], 0
        for l in linhas:
            if len(aval) == alvo:
                break
            if l["ja_em_alerta"]:
                descartadas += 1
            else:
                aval.append(l)
        k = sum(l["aprovado"] for l in aval)
        resumo.append({"repeticoes_avaliaveis": alvo, "sementes_usadas": len(aval) + descartadas,
                       "descartadas_ja_em_alerta": descartadas, "aprovadas": k,
                       "taxa": round(k / alvo, 3), "ic95": wilson(k, alvo),
                       "ciclos_ate_disparo": " ".join(str(l["ciclos_validos_ate_disparo"]) for l in aval)})
    gravar("h_cp01_resumo.csv", resumo, saida)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("experimento", choices=("a", "cp05", "rampa", "b", "bdet", "e", "h", "todos"))
    ap.add_argument("--sementes", type=int, default=None)
    ap.add_argument("--saida", default=SAIDA)
    a = ap.parse_args()
    with Pool(os.cpu_count()) as pool:
        todos = a.experimento == "todos"
        if todos or a.experimento == "a":
            exp_a(a.sementes or 8, a.saida, pool)
        if todos or a.experimento == "cp05":
            exp_cp05(a.sementes or 8, a.saida, pool)
        if todos or a.experimento == "rampa":
            exp_rampa(a.sementes or 8, a.saida, pool)
        if todos or a.experimento == "b":
            exp_b(a.sementes or 8, a.saida, pool)
        if a.experimento == "bdet":
            exp_b_det(a.saida, pool)
        if todos or a.experimento == "e":
            exp_e(a.sementes or 50, a.saida, pool)
        if todos or a.experimento == "h":
            exp_h(a.saida, pool)


if __name__ == "__main__":
    main()
