from datetime import datetime, timezone

import pytest

from detector import Config, calcular_baseline, componentes, consultar, estado_inicial, linhas_para_pacotes, step, validar


def test_sensor_nulo_ou_fora_da_faixa_e_invalido():
    validos, _ = validar([None, 50.0, 2.0, 32.0, 32.1], Config())
    assert validos == [False, False, False, True, True]


def test_sensor_muito_frio_indica_perda_de_contato():
    validos, frios = validar([32.0, 32.1, 32.2, 32.1, 25.0], Config())
    assert validos == [True, True, True, True, False]
    assert frios == [4]


def test_sensor_quente_nao_e_descartado():
    validos, frios = validar([32.0, 32.1, 32.2, 32.1, 40.0], Config())
    assert all(validos)
    assert frios == []


def test_calculo_dos_componentes():
    dt_i, dt_b = componentes([33.0, 32.0, 32.0, 32.0, 32.0], [32.0] * 5, [True] * 5)
    assert dt_i[0] == pytest.approx(1.0)
    assert dt_i[1] == pytest.approx(-0.25)
    assert dt_b == pytest.approx(0.2)


def test_leituras_do_mesmo_instante_formam_um_pacote():
    ts = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    linhas = [{"vaca_id": "v1", "membro": "E", "quarto": q, "temp_raw": 30.0 + q, "timestamp": ts}
              for q in range(1, 6)]
    pacotes, avisos = linhas_para_pacotes(linhas)
    assert len(pacotes) == 1
    assert pacotes[0]["T"] == [31.0, 32.0, 33.0, 34.0, 35.0]
    assert avisos == []


def test_pacote_incompleto_gera_aviso():
    ts = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    linhas = [{"vaca_id": "v1", "membro": "E", "quarto": q, "temp_raw": 32.0, "timestamp": ts} for q in (1, 2, 3)]
    pacotes, avisos = linhas_para_pacotes(linhas)
    assert pacotes[0]["T"] == [32.0, 32.0, 32.0, None, None]
    assert avisos[0]["tipo"] == "pacote_incompleto"
    assert avisos[0]["faltam"] == [4, 5]


def test_celula_da_linha_de_base_so_arma_com_dados_suficientes():
    cfg = Config()
    baseline = {"v1|E": {"1": {"10": {"b": 32.0, "n": 12, "dias": 3},
                               "11": {"b": 32.0, "n": 12, "dias": 2}}}}
    assert consultar(baseline, "v1", "E", 1, 10, cfg) == (32.0, True)
    assert consultar(baseline, "v1", "E", 1, 11, cfg) == (32.0, False)
    assert consultar(baseline, "v1", "E", 1, 12, cfg) == (None, False)


def test_ciclo_congelado_nao_entra_na_linha_de_base():
    agora = 1772366400.0
    ciclo = {"vaca_id": "v1", "membro": "E", "T": [32.0], "ts": agora - 3600}
    assert calcular_baseline([{**ciclo, "congelado": True}], Config(), agora) == {}
    assert "v1|E" in calcular_baseline([{**ciclo, "congelado": False}], Config(), agora)


def test_pacote_de_bin_ja_fechado_e_ignorado():
    cfg = Config()
    t0 = 1772366400.0
    pacote = {"vaca_id": "v1", "membro": "E", "T": [32.0] * 5}
    estado, _ = step(estado_inicial(), {**pacote, "ts": t0}, cfg, {})
    estado, _ = step(estado, {**pacote, "ts": t0 + cfg.ciclo_s}, cfg, {})
    _, eventos = step(estado, {**pacote, "ts": t0}, cfg, {})
    assert [e["tipo"] for e in eventos] == ["atrasado"]


def test_step_nao_altera_o_estado_recebido():
    estado = estado_inicial()
    step(estado, {"vaca_id": "v1", "membro": "E", "ts": 1772366400.0, "T": [32.0] * 5}, Config(), {})
    assert estado == estado_inicial()