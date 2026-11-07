"""Monta as tabelas em markdown da Fase 1B a partir dos CSV gerados por scripts/fase1b.py.

Uso: python scripts/fase1b_tabelas.py [PASTA] > docs/resultados/fase1b/tabelas.md
"""

import ast
import csv
import sys
from statistics import mean, median

PASTA = sys.argv[1] if len(sys.argv) > 1 else "docs/resultados/fase1b"
LAMBDAS = ("0.5", "1.0", "1.5", "2.0")


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def ler(nome):
    with open(f"{PASTA}/{nome}", newline="") as f:
        return list(csv.DictReader(f))


def br(x, casas=2):
    """Número com vírgula decimal."""
    return f"{x:.{casas}f}".replace(".", ",")


def num(x):
    """Converte o texto do CSV em float; vazio vira 0."""
    return float(x) if x not in ("", None) else 0.0


def agrupar(linhas, *chaves):
    grupos = {}
    for l in linhas:
        grupos.setdefault(tuple(l[k] for k in chaves), []).append(l)
    return grupos


def ic(texto):
    """Formata um intervalo de confiança gravado como tupla no CSV."""
    a, b = ast.literal_eval(texto)
    return f"[{br(a)}; {br(b)}]" if a is not None else "–"


def taxa(x):
    return br(float(x)) if x else "–"


def cabecalho(titulo, colunas):
    return f"\n### {titulo}\n| " + " | ".join(colunas) + " |\n|" + "---|" * len(colunas)


# ---------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------

def tabela_a():
    linhas = ler("a_espacial_idio_resumo.csv")
    out = [cabecalho("a", ["Variante", "λ = 0,5", "λ = 1,0", "λ = 1,5", "λ = 2,0"]).lstrip("\n")]
    for variante in dict.fromkeys(l["variante"] for l in linhas):
        celulas = []
        for lam in LAMBDAS:
            l = next(x for x in linhas if x["variante"] == variante and x["lambda"] == lam)
            celulas.append(f"{br(float(l['disparos_S_md_media']), 3)} "
                           f"[{br(float(l['min']), 3)} – {br(float(l['max']), 3)}]")
        out.append(f"| {variante} | " + " | ".join(celulas) + " |")
    return out


def tabelas_cp05():
    grupos = agrupar(ler("cp05_disponibilidade_congelamento.csv"), "variante", "regra_congelamento")

    out = [cabecalho("cp05", ["Variante", "Congelamento", "Aberturas por semente (1 a 8)", "Média", "com S",
                              "com B", "com C", "ARMANDO / bins com dados", "ARMANDO / bins do período",
                              "FALHA_SENSOR", "Tempo em alerta"])]
    for (variante, regra), ls in grupos.items():
        def media_membros(campo):
            return mean((num(l["E_" + campo]) + num(l["D_" + campo])) / 2 for l in ls)

        def media_int(campo):
            return br(mean(int(l[campo]) for l in ls), 1)

        out.append(f"| {variante} | {regra} | {' · '.join(l['aberturas'] for l in ls)} | {media_int('aberturas')} | "
                   f"{media_int('com_S')} | {media_int('com_B')} | {media_int('com_C')} | "
                   f"{br(100 * media_membros('frac_armando_dados'))}% | "
                   f"{br(100 * media_membros('frac_armando_periodo'))}% | "
                   f"{br(100 * media_membros('frac_falha_dados'))}% | "
                   f"{br(100 * media_membros('frac_tempo_alerta'), 1)}% |")

    out.append(cabecalho("cp05 por membro (completo)", ["Congelamento", "Membro", "ARMANDO / dados, por semente (%)",
                                                       "ARMANDO / período, por semente (%)"]))
    for (variante, regra), ls in grupos.items():
        if variante != "completo" or regra not in ("padrao_0.5", "desligado", "so_alerta", "frac_1.0"):
            continue
        for membro in "ED":
            dados = " · ".join(br(100 * num(l[membro + "_frac_armando_dados"]), 1) for l in ls)
            periodo = " · ".join(br(100 * num(l[membro + "_frac_armando_periodo"]), 1) for l in ls)
            out.append(f"| {regra} | {membro} | {dados} | {periodo} |")
    return out


def tabela_rampa():
    grupos = agrupar(ler("g_rampa_patamar14d.csv"), "modelo", "regra_congelamento")
    out = [cabecalho("rampa", ["Modelo", "Congelamento", "Latência mediana (h)", "Fechou no patamar",
                               "Dias até fechar no patamar (desde t0), por semente", "Mediana",
                               "Fração do patamar em alerta", "Resets"])]
    for (modelo, regra), ls in grupos.items():
        latencias = [float(l["latencia_h"]) for l in ls if l["latencia_h"]]
        fechou = [float(l["dias_ate_fechar_no_patamar"]) for l in ls if l["fechou_no_patamar"] == "True"]
        dias = " · ".join(br(x) for x in sorted(fechou)) or "–"
        out.append(f"| {modelo} | {regra} | {br(median(latencias), 1)} | {len(fechou)}/{len(ls)} | {dias} | "
                   f"{br(median(fechou)) if fechou else '–'} | "
                   f"{br(mean(float(l['frac_alerta_no_patamar']) for l in ls))} | "
                   f"{sum(int(l['resets']) for l in ls)} |")
    return out


def tabelas_b():
    linhas = ler("b_superficie_resumo.csv")
    out = []
    for campo, titulo in (("aberturas_md", "aberturas por membro-dia"),
                          ("frac_tempo_alerta", "fração do tempo em alerta")):
        out.append(cabecalho(f"b {titulo}", ["λ", "N (latência mínima)", "decúbito 0,5 h", "1 h", "2 h", "3 h",
                                             "6 h"]))
        for lam in LAMBDAS:
            for n in ("6", "12", "24", "36"):
                ls = [l for l in linhas if l["lambda"] == lam and l["N"] == n]
                celulas = [f"{br(float(l[campo]))} [{br(float(l[campo + '_min']))} – {br(float(l[campo + '_max']))}]"
                           for l in ls]
                out.append(f"| {br(float(lam), 1)} | {n} ({int(n) * 5} min) | " + " | ".join(celulas) + " |")
    return out


COLUNAS_DETECCAO = ["n efetivo (excluídas)", "Detecção [IC95 Wilson]", "Controle [IC95]",
                    "Diferença pareada [IC95 bootstrap]", "Latência mediana (h)", "1º componente"]


def linha_deteccao(l, chaves):
    return ("| " + " | ".join(l[c] for c in chaves)
            + f" | {l['n_efetivo']} ({l['excluidas_ja_em_alerta']})"
            + f" | {taxa(l['taxa_deteccao'])} {ic(l['ic95_det'])}"
            + f" | {taxa(l['taxa_controle'])} {ic(l['ic95_controle'])}"
            + f" | {taxa(l['diferenca_pareada'])} {ic(l['ic95_diferenca'])}"
            + f" | {taxa(l['latencia_mediana_h'])} | {l['primeiro_componente']} |")


def tabela_bdet():
    out = [cabecalho("bdet", ["Config", "Forma", "Amp"] + COLUNAS_DETECCAO)]
    for l in ler("b_deteccao_subconjunto_resumo.csv"):
        out.append(linha_deteccao(l, ("config", "forma", "amp")))
    return out


def tabela_e():
    out = [cabecalho("e", ["λ", "Membros", "Forma", "Amp (°C)"] + COLUNAS_DETECCAO)]
    for l in ler("e_deteccao_resumo.csv"):
        l = dict(l, config=l["config"].replace("lambda_", ""))
        out.append(linha_deteccao(l, ("config", "membros", "forma", "amp")))
    return out


def tabela_h():
    out = [cabecalho("h", ["Repetições avaliáveis", "Sementes usadas", "Descartadas (já em alerta)", "Aprovadas",
                           "Taxa [IC95 Wilson]", "Ciclos válidos até o disparo"])]
    for l in ler("h_cp01_resumo.csv"):
        a, b = ast.literal_eval(l["ic95"])
        out.append(f"| {l['repeticoes_avaliaveis']} | {l['sementes_usadas']} | {l['descartadas_ja_em_alerta']} | "
                   f"{l['aprovadas']} | {br(float(l['taxa']))} [{br(a)}; {br(b)}] | "
                   f"{l['ciclos_ate_disparo'].replace('None', '–')} |")
    return out


def main():
    out = ["# Fase 1B: tabelas geradas (modelo SINTÉTICO; nenhum resultado é dado de animal)\n"]
    for tabela in (tabela_a, tabelas_cp05, tabela_rampa, tabelas_b, tabela_bdet, tabela_e, tabela_h):
        out += tabela()
    print("\n".join(out))


if __name__ == "__main__":
    main()
