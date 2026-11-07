"""Varredura de limiares no modelo sintético.

1) Falsos alarmes: lambda em {0,5; 1,0; 1,5; 2,0} (o mesmo nos três componentes),
   com 1 e 2 membros, 8 sementes ou mais, 40 dias depois do armamento. Por membro-dia:
   disparos de cada componente (contador chegando a N), aberturas de alerta e
   fração do tempo em ALERTA.
2) Detecção: elevações no membro E de {0,5; 1,0; 1,5; 2,0; 3,0} °C, nas formas degrau
   nos 5 sensores, degrau em 1 sensor, rampa de 12 h e rampa de 48 h (24 h de patamar
   e 48 h de recuperação entre uma e outra). Conta como detectado o alerta aberto no
   membro E dentro da janela. Também calcula a chance de abrir alerta por acaso numa
   janela igual, usando a taxa de aberturas da parte 1.

Grava em docs/resultados/ os arquivos varredura_falsos.csv, varredura_deteccao.csv,
varredura_resumo.csv e varredura.png. Precisa de matplotlib (só para a figura).
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
from sim.gerador import T_INICIO, Injecao, Premissas, gerar  # noqa: E402
from sim.rodar import executar  # noqa: E402

LAMBDAS = (0.5, 1.0, 1.5, 2.0)
AMPS = (0.5, 1.0, 1.5, 2.0, 3.0)
FORMAS = {  # nome: (sensores, rampa_h)
    "degrau_5": ((0, 1, 2, 3, 4), 0.0),
    "degrau_1": ((0,), 0.0),
    "rampa_12h": ((0, 1, 2, 3, 4), 12.0),
    "rampa_48h": ((0, 1, 2, 3, 4), 48.0),
}
PATAMAR_H = 24.0
RECUPERA_H = 48.0
DESCARTE_DIAS = 4
DIAS_FA = 40


def cfg(lam):
    return Config(lambda_s=lam, lambda_b=lam, lambda_c=lam)


def _membros(n):
    return ("E", "D") if n == 2 else ("E",)


def _disparos(ciclos, corte, n_persist):
    """Número de vezes em que o contador de cada componente chegou a N."""
    d = {"S": 0, "B": 0, "C": 0}
    for c in ciclos:
        if c["ts"] >= corte:
            for k, v in c["acima"].items():
                if v == n_persist:
                    d[k] += 1
    return d


def rodar_fa(args):
    lam, nm, semente = args
    total = DESCARTE_DIAS + DIAS_FA
    membros = _membros(nm)
    c = cfg(lam)
    res = executar(gerar(Premissas(), semente, total, membros=membros), c, fim=T_INICIO + total * 86400)
    corte = T_INICIO + DESCARTE_DIAS * 86400
    md = DIAS_FA * nm
    disp = _disparos(res.ciclos, corte, c.n_persist)
    ab = [a for a in res.aberturas if a["ts"] >= corte]
    pos = [x for x in res.ciclos if x["ts"] >= corte]
    frac = sum(x["estado"] == "ALERTA" for x in pos) / max(len(pos), 1)
    return {"lambda": lam, "membros": nm, "semente": semente, "membro_dias": md,
            "disparos_S": disp["S"] / md, "disparos_B": disp["B"] / md, "disparos_C": disp["C"] / md,
            "aberturas": len(ab) / md, "frac_tempo_alerta": frac}


def rodar_det(args):
    lam, nm, semente = args
    rng = random.Random(1000 + semente)
    ordem = [(f, a) for f in FORMAS for a in AMPS]
    rng.shuffle(ordem)
    t = T_INICIO + DESCARTE_DIAS * 86400
    injs = []
    for forma, amp in ordem:
        sens, rampa = FORMAS[forma]
        injs.append((forma, amp, Injecao("E", sens, amp, t, rampa_h=rampa, dur_h=PATAMAR_H)))
        t += (rampa + PATAMAR_H + RECUPERA_H) * 3600
    total_dias = (t - T_INICIO) / 86400
    c = cfg(lam)
    res = executar(gerar(Premissas(), semente, total_dias, membros=_membros(nm), injecoes=[i for _, _, i in injs]),
                   c, fim=t)
    ab_e = [a for a in res.aberturas if a["membro"] == "E"]
    estado_e = {x["ts"]: x["estado"] for x in res.ciclos if x["membro"] == "E"}
    linhas = []
    for forma, amp, inj in injs:
        janela = [a for a in ab_e if inj.t0 <= a["ts"] < inj.fim]
        bin0 = inj.t0 // c.ciclo_s * c.ciclo_s - c.ciclo_s
        ja = estado_e.get(bin0) == "ALERTA"
        a0 = janela[0] if janela else None
        linhas.append({"lambda": lam, "membros": nm, "semente": semente, "forma": forma, "amp": amp,
                       "janela_h": (inj.fim - inj.t0) / 3600, "ja_em_alerta": ja,
                       "detectado": a0 is not None,
                       "latencia_h": (a0["ts"] - inj.t0) / 3600 if a0 else None,
                       "primeiro": a0["primeiro"] if a0 else None,
                       "componentes": "+".join(a0["componentes"]) if a0 else None})
    return linhas


def resumir(fa, det):
    resumo = []
    taxa = {}
    for lam in LAMBDAS:
        for nm in (1, 2):
            ls = [l for l in fa if l["lambda"] == lam and l["membros"] == nm]
            if not ls:
                continue
            r = {"parte": "falsos", "lambda": lam, "membros": nm, "n_sementes": len(ls)}
            for k in ("disparos_S", "disparos_B", "disparos_C", "aberturas", "frac_tempo_alerta"):
                vals = [l[k] for l in ls]
                r[k + "_media"] = round(mean(vals), 4)
                r[k + "_min"] = round(min(vals), 4)
                r[k + "_max"] = round(max(vals), 4)
            resumo.append(r)
            taxa[(lam, nm)] = mean(l["aberturas"] for l in ls)
    for lam in LAMBDAS:
        for nm in (1, 2):
            for forma in FORMAS:
                for amp in AMPS:
                    ls = [l for l in det if l["lambda"] == lam and l["membros"] == nm and l["forma"] == forma
                          and l["amp"] == amp]
                    if not ls:
                        continue
                    validas = [l for l in ls if not l["ja_em_alerta"]]
                    det_ok = [l for l in validas if l["detectado"]]
                    janela_d = ls[0]["janela_h"] / 24
                    acaso = 1 - math.exp(-taxa.get((lam, nm), 0) * janela_d)
                    prim = {}
                    for l in det_ok:
                        prim[l["primeiro"]] = prim.get(l["primeiro"], 0) + 1
                    resumo.append({
                        "parte": "deteccao", "lambda": lam, "membros": nm, "forma": forma, "amp": amp,
                        "n": len(ls), "n_ja_em_alerta": len(ls) - len(validas),
                        "taxa_deteccao": round(len(det_ok) / len(validas), 3) if validas else None,
                        "prob_alerta_por_acaso": round(acaso, 3),
                        "latencia_mediana_h": round(median(l["latencia_h"] for l in det_ok), 2) if det_ok else None,
                        "primeiro_componente": " ".join(f"{k}:{v}" for k, v in sorted(prim.items())),
                    })
    return resumo


def figura(resumo, caminho):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
    cores = {"S": "#0072B2", "B": "#E69F00", "C": "#009E73"}
    for nm, estilo in ((1, "--"), (2, "-")):
        fa = sorted([r for r in resumo if r["parte"] == "falsos" and r["membros"] == nm], key=lambda r: r["lambda"])
        for comp in ("S", "B", "C"):
            if nm == 1 and comp == "C":
                continue
            ax[0].plot([r["lambda"] for r in fa], [r[f"disparos_{comp}_media"] for r in fa], estilo, marker="o",
                       color=cores[comp], label=f"{comp}, {nm} membro{'s' if nm == 2 else ''}")
    ax[0].set_xlabel("λ (°C)")
    ax[0].set_ylabel("disparos falsos por membro-dia (média)")
    ax[0].set_yscale("symlog", linthresh=0.01)
    ax[0].set_title("Falsos alarmes por componente")
    ax[0].legend(fontsize=7)
    for k, (lam, nm) in enumerate(((1.0, 2), (2.0, 2))):
        a = ax[k + 1]
        for forma, cor in zip(FORMAS, ("#0072B2", "#D55E00", "#009E73", "#CC79A7")):
            d = sorted([r for r in resumo if r["parte"] == "deteccao" and r["lambda"] == lam and r["membros"] == nm
                        and r["forma"] == forma], key=lambda r: r["amp"])
            a.plot([r["amp"] for r in d], [r["taxa_deteccao"] for r in d], marker="o", color=cor, label=forma)
            a.plot([r["amp"] for r in d], [r["prob_alerta_por_acaso"] for r in d], ":", color=cor)
        a.axvline(lam, color="#999", lw=0.8)
        a.set_ylim(-0.05, 1.05)
        a.set_xlabel("amplitude injetada (°C)")
        a.set_ylabel("taxa de detecção")
        a.set_title(f"Detecção, λ = {lam:.1f} °C, {nm} membros\n(pontilhado: alerta por acaso na mesma janela)")
        a.legend(fontsize=7)
    fig.suptitle("Modelo SINTÉTICO, premissas não validadas em animais", fontsize=10)
    fig.tight_layout()
    fig.savefig(caminho, dpi=130)


def gravar(caminho, linhas):
    campos = []
    for l in linhas:
        for k in l:
            if k not in campos:
                campos.append(k)
    with open(caminho, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sementes", type=int, default=8)
    ap.add_argument("--saida", default="docs/resultados")
    ap.add_argument("--so-figura", action="store_true", help="regenera a figura a partir do resumo gravado")
    a = ap.parse_args()
    if a.so_figura:
        with open(os.path.join(a.saida, "varredura_resumo.csv")) as f:
            resumo = []
            for r in csv.DictReader(f):
                resumo.append({k: (None if v == "" else v if k in ("parte", "forma", "primeiro_componente")
                                   else float(v)) for k, v in r.items()})
        for r in resumo:
            r["membros"] = int(r["membros"])
        figura(resumo, os.path.join(a.saida, "varredura.png"))
        return
    tarefas = [(lam, nm, s) for lam in LAMBDAS for nm in (1, 2) for s in range(1, a.sementes + 1)]
    with Pool(os.cpu_count()) as pool:
        fa = pool.map(rodar_fa, tarefas)
        det = [l for ls in pool.map(rodar_det, tarefas) for l in ls]
    os.makedirs(a.saida, exist_ok=True)
    gravar(os.path.join(a.saida, "varredura_falsos.csv"), fa)
    gravar(os.path.join(a.saida, "varredura_deteccao.csv"), det)
    resumo = resumir(fa, det)
    gravar(os.path.join(a.saida, "varredura_resumo.csv"), resumo)
    figura(resumo, os.path.join(a.saida, "varredura.png"))
    for r in resumo:
        print({k: v for k, v in r.items() if not k.endswith(("_min", "_max"))})


if __name__ == "__main__":
    main()
