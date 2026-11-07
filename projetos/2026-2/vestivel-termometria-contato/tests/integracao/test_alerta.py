import json

from detector import Config
from sim.gerador import INGREDIENTES, T_INICIO, Injecao, Premissas, gerar
from sim.rodar import baseline_constante, executar

DIAS = 3
FIM = T_INICIO + DIAS * 86400
INICIO_ELEVACAO = T_INICIO + 86400
TODOS = (0, 1, 2, 3, 4)
PREMISSAS = Premissas().sem(*INGREDIENTES)
BASELINE = baseline_constante("sim01", ("E", "D"), {"E": [32.0] * 5, "D": [32.0] * 5})


def rodar(injecoes=(), extras=None):
    pacotes = gerar(PREMISSAS, 1, DIAS, injecoes=injecoes, extras=extras)
    return executar(pacotes, Config(), baseline_fixo=BASELINE, fim=FIM)


def test_sem_elevacao_nao_abre_alerta():
    res = rodar()
    assert res.aberturas == []
    assert {c["estado"] for c in res.ciclos} == {"OK"}


def test_elevacao_em_um_sensor_abre_alerta_espacial_depois_de_n_ciclos():
    cfg = Config()
    res = rodar([Injecao("E", (2,), 2.0, INICIO_ELEVACAO, dur_h=12)])
    assert len(res.aberturas) == 1
    abertura = res.aberturas[0]
    assert abertura["membro"] == "E"
    assert abertura["primeiro"] == "S"
    latencia_s = abertura["ts"] - INICIO_ELEVACAO
    assert cfg.n_persist * cfg.ciclo_s <= latencia_s <= (cfg.n_persist + 1) * cfg.ciclo_s


def test_elevacao_no_membro_todo_abre_alerta_temporal_e_contralateral():
    res = rodar([Injecao("E", TODOS, 3.0, INICIO_ELEVACAO, dur_h=12)])
    assert len(res.aberturas) == 1
    assert res.aberturas[0]["membro"] == "E"
    assert set(res.aberturas[0]["componentes"]) == {"B", "C"}


def test_alerta_fecha_depois_que_a_elevacao_termina():
    injecao = Injecao("E", TODOS, 3.0, INICIO_ELEVACAO, dur_h=12)
    res = rodar([injecao])
    assert len(res.fechamentos) == 1
    assert res.fechamentos[0]["fim"] >= injecao.fim
    assert res.estado["vacas"]["sim01"]["membros"]["E"]["alerta"] is None


def test_sensores_sem_leitura_geram_falha_e_nao_alerta():
    def sem_tres_sensores(membro, t, T):
        return [None, None, None, T[3], T[4]] if membro == "E" else T

    res = rodar(extras=sem_tres_sensores)
    assert res.aberturas == []
    assert {c["estado"] for c in res.ciclos if c["membro"] == "E"} == {"FALHA_SENSOR"}


def test_estado_salvo_em_json_continua_igual_depois_de_reiniciar():
    injecao = Injecao("E", TODOS, 3.0, INICIO_ELEVACAO, dur_h=12)
    pacotes = gerar(PREMISSAS, 1, DIAS, injecoes=[injecao])
    normal = executar(pacotes, Config(), baseline_fixo=BASELINE, fim=FIM)
    reiniciado = executar(pacotes, Config(), baseline_fixo=BASELINE, fim=FIM,
                          interromper_em=len(pacotes) // 2,
                          ao_interromper=lambda estado: json.loads(json.dumps(estado)))
    assert reiniciado.aberturas == normal.aberturas
    assert reiniciado.fechamentos == normal.fechamentos
    assert reiniciado.ciclos == normal.ciclos