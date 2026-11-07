"""Testes do cálculo de significância estatística do M2 (qui-quadrado, bootstrap)."""

import numpy as np
import pytest

from src.analysis.m2_significance import bootstrap_lift_ci, chi_square_yates, contingency_table


def test_contingency_table_soma_n():
    table = contingency_table(antecedent_support=0.1, consequent_support=0.5,
                              joint_support=0.05, n=1000)
    assert table.sum() == 1000


def test_contingency_table_celulas_conhecidas():
    """10% têm A, 50% têm B, 5% têm ambos — reproduz a tabela à mão."""
    table = contingency_table(0.10, 0.50, 0.05, n=1000)
    assert table[0, 0] == 50    # ambos
    assert table[0, 1] == 50    # só A
    assert table[1, 0] == 450   # só B
    assert table[1, 1] == 450   # nenhum


def test_chi2_independencia_perfeita_e_proximo_de_zero():
    """Se observado == esperado sob independência, chi2 deve ser ~0."""
    # P(A)=0.5, P(B)=0.5, independentes: P(ambos)=0.25 de 1000 = 250
    table = np.array([[250, 250], [250, 250]])
    stat, p = chi_square_yates(table)
    assert stat < 1.0
    assert p > 0.5


def test_chi2_associacao_forte_tem_p_pequeno():
    """Associação quase perfeita (A e B sempre juntos ou nunca) deve rejeitar
    independência com folga, mesmo com a correção conservadora de Yates."""
    table = np.array([[480, 20], [20, 480]])
    stat, p = chi_square_yates(table)
    assert stat > 50
    assert p < 1e-10


def test_chi2_regra_real_do_m2_bate_com_resultado():
    """Tabela reconstruída da regra telephone→smartphone (m2_significance_results.json):
    185 cestas com ambos, 9.744 cestas totais multi-categoria."""
    table = contingency_table(antecedent_support=0.026273, consequent_support=0.487787,
                              joint_support=0.018986, n=9744)
    stat, p = chi_square_yates(table)
    assert stat == pytest.approx(57.08, abs=0.05)
    assert p == pytest.approx(4.18e-14, rel=0.05)


def test_bootstrap_ic_contem_o_lift_pontual():
    """O IC bootstrap deve conter (ou ficar muito próximo de) o lift medido na
    amostra original — ele é o centro da distribuição reamostrada."""
    table = contingency_table(0.170772, 0.487787, 0.090620, n=9744)  # audio.headphone
    lift_pontual = (0.090620 / 0.170772) / 0.487787
    lo, hi = bootstrap_lift_ci(table, n_boot=500, seed=1)
    assert lo < lift_pontual < hi


def test_bootstrap_ic_mais_estreito_com_mais_cestas():
    """Amostras maiores (mesma proporção) devem produzir IC mais estreito —
    a incerteza cai com o tamanho da amostra."""
    table_small = contingency_table(0.10, 0.50, 0.08, n=200)
    table_large = contingency_table(0.10, 0.50, 0.08, n=20000)
    lo_s, hi_s = bootstrap_lift_ci(table_small, n_boot=500, seed=1)
    lo_l, hi_l = bootstrap_lift_ci(table_large, n_boot=500, seed=1)
    assert (hi_l - lo_l) < (hi_s - lo_s)


def test_bootstrap_e_deterministico_com_mesma_seed():
    table = contingency_table(0.10, 0.50, 0.08, n=1000)
    r1 = bootstrap_lift_ci(table, n_boot=300, seed=7)
    r2 = bootstrap_lift_ci(table, n_boot=300, seed=7)
    assert r1 == r2
