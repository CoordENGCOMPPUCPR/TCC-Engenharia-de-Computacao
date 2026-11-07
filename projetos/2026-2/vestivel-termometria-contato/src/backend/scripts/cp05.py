"""CP-05: 100 dias simulados depois do armamento, sem nenhuma anomalia.

Para cada variante do modelo de ruído (completo, limpo, sem cada ingrediente e só
com cada ingrediente) conta os alertas abertos depois do descarte inicial, por
semente e por componente.

Uso: python scripts/cp05.py [--sementes 8] [--membros 2] [--saida docs/resultados]
"""

import argparse
import csv
import os
import sys
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detector import Config  # noqa: E402
from sim.gerador import INGREDIENTES, T_INICIO, Premissas, gerar  # noqa: E402
from sim.rodar import executar  # noqa: E402

DESCARTE_DIAS = 4   # 3 dias para armar a linha de base + 1 de folga
DIAS = 100


def variantes():
    p = Premissas()
    v = [("completo", p), ("limpo", p.sem(*INGREDIENTES))]
    v += [(f"sem_{i}", p.sem(i)) for i in INGREDIENTES]
    v += [(f"so_{i}", p.sem(*[j for j in INGREDIENTES if j != i])) for i in INGREDIENTES]
    v += [("completo_kappa_0.1", replace(p, kappa=0.1)), ("completo_kappa_0.5", replace(p, kappa=0.5))]
    return v


def rodar(args):
    nome, prem, semente, membros = args
    total = DESCARTE_DIAS + DIAS
    pac = gerar(prem, semente, total, membros=membros)
    res = executar(pac, Config(), fim=T_INICIO + total * 86400)
    corte = T_INICIO + DESCARTE_DIAS * 86400
    ab = [a for a in res.aberturas if a["ts"] >= corte]
    armando = sum(1 for c in res.ciclos if c["ts"] >= corte and c["estado"] == "ARMANDO")
    return {
        "variante": nome, "semente": semente, "membros": len(membros), "dias": DIAS,
        "alertas": len(ab),
        "com_S": sum("S" in a["componentes"] for a in ab),
        "com_B": sum("B" in a["componentes"] for a in ab),
        "com_C": sum("C" in a["componentes"] for a in ab),
        "ciclos_armando_apos_descarte": armando,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sementes", type=int, default=8)
    ap.add_argument("--membros", type=int, default=2, choices=(1, 2))
    ap.add_argument("--saida", default="docs/resultados")
    a = ap.parse_args()
    membros = ("E", "D") if a.membros == 2 else ("E",)
    tarefas = [(n, p, s, membros) for n, p in variantes() for s in range(1, a.sementes + 1)]
    with Pool(os.cpu_count()) as pool:
        linhas = pool.map(rodar, tarefas)
    os.makedirs(a.saida, exist_ok=True)
    caminho = os.path.join(a.saida, f"cp05_{a.membros}membro{'s' if a.membros == 2 else ''}.csv")
    with open(caminho, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    print(f"gravado {caminho}")
    print(f"{'variante':22} alertas por semente (total S/B/C)")
    for nome, _ in variantes():
        ls = [l for l in linhas if l["variante"] == nome]
        por = " ".join(f"{l['alertas']:3d}" for l in ls)
        print(f"{nome:22} {por}   S={sum(l['com_S'] for l in ls)} B={sum(l['com_B'] for l in ls)} "
              f"C={sum(l['com_C'] for l in ls)}")


if __name__ == "__main__":
    main()
