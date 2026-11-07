"""Experimentos da Fase 1C com os parâmetros padrão atuais (dados sintéticos).

Padrão: N = 24, λ_s = 1,5 °C, λ_b = λ_c = 2,0 °C, congela_max_h = 168 ("liberar").
Usa o mesmo gerador e as mesmas premissas da Fase 1B. As tarefas e os critérios
estão em sim/fase1c.py.

Subcomandos (os CSV vão para docs/resultados/fase1c/):
  cp05   100 dias após o armamento, 8 sementes, 2 membros (modelo completo e limpo)
  cp01   +1,5 / +2,0 / +2,5 °C num sensor (critério só em +2,0), 10 e 50 repetições
  e      detecção pareada: 4 formas x amplitudes 1,5 / 2,0 / 3,0 °C, 50 sementes
  rampa  rampa de 48 h + patamar de 14 dias: 1,5 °C (critério) e 2,0 / 2,5 / 3,0 °C
  todos  roda todos
"""

import argparse
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fase1b import FORMAS, _detectar, gravar, resumir_det  # noqa: E402
from detector import Config  # noqa: E402
from sim import fase1c as f1c  # noqa: E402

SAIDA = "docs/resultados/fase1c"


def _cp05(args):
    return f1c.tarefa_cp05(*args)


def _cp01(args):
    return f1c.tarefa_cp01(*args)


def _rampa(args):
    return f1c.tarefa_rampa(*args)


def _json(nome, obj, saida):
    os.makedirs(saida, exist_ok=True)
    with open(os.path.join(saida, nome), "w") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
    print("gravado", os.path.join(saida, nome))


def exp_cp05(saida, pool):
    linhas = pool.map(_cp05, [(m, s) for m in ("completo", "limpo") for s in f1c.SEMENTES_CP05])
    gravar("cp05.csv", linhas, saida)
    _json("cp05_criterio.json", f1c.avaliar_cp05(linhas), saida)


def coletar_cp01(pool, amp, alvo=50):
    ls, s = [], 0
    while sum(1 for l in ls if not l["ja_em_alerta"]) < alvo:
        ls += pool.map(_cp01, [(amp, x) for x in range(s + 1, s + 17)])
        s += 16
    return ls


def exp_cp01(saida, pool):
    linhas, resumo = [], {}
    for amp in (1.5, 2.0, 2.5):
        ls = coletar_cp01(pool, amp)
        linhas += ls
        resumo[str(amp)] = f1c.avaliar_cp01(ls)
        if amp != f1c.CP01_AMP:
            resumo[str(amp)]["aprovado"] = "sem critério (só reporte)"
    gravar("cp01.csv", linhas, saida)
    _json("cp01_criterio.json", resumo, saida)


def exp_e(saida, pool, sementes=50):
    configs = [("padrao_1c", Config())]
    condicoes = [(f, a) for f in FORMAS for a in (1.5, 2.0, 3.0)]
    linhas = [l for ls in pool.map(_detectar, [(s, 2, configs, condicoes) for s in range(1, sementes + 1)])
              for l in ls]
    gravar("e_deteccao_pareada.csv", linhas, saida)
    gravar("e_deteccao_resumo.csv", resumir_det(linhas, ("config", "membros", "forma", "amp")), saida)


def exp_rampa(saida, pool):
    tarefas = [(m, a, s) for m in ("limpo", "completo") for a in (1.5, 2.0, 2.5, 3.0) for s in f1c.SEMENTES_RAMPA]
    linhas = pool.map(_rampa, tarefas)
    gravar("rampa_patamar14d.csv", linhas, saida)
    crit = {m: {"aprovado": all(l["aprovado"] for l in linhas if l["modelo"] == m and l["amp"] == f1c.RAMPA_AMP),
                "c1_detectou": sum(l["c1_detectou"] for l in linhas if l["modelo"] == m and l["amp"] == f1c.RAMPA_AMP),
                "c2_fechou": sum(l["c2_fechou_ate_48h_apos_o_fim"] for l in linhas
                                 if l["modelo"] == m and l["amp"] == f1c.RAMPA_AMP),
                "n": len(f1c.SEMENTES_RAMPA)} for m in ("limpo", "completo")}
    _json("rampa_criterio.json", crit, saida)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("experimento", choices=("cp05", "cp01", "e", "rampa", "todos"))
    ap.add_argument("--saida", default=SAIDA)
    a = ap.parse_args()
    with Pool(os.cpu_count()) as pool:
        t = a.experimento == "todos"
        for nome, fn in (("cp05", exp_cp05), ("cp01", exp_cp01), ("e", exp_e), ("rampa", exp_rampa)):
            if t or a.experimento == nome:
                fn(a.saida, pool)


if __name__ == "__main__":
    main()
