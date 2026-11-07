"""Testes de integração da API com os artefatos reais de treino.

Cobrem a demonstração de ponta a ponta: os quatro cenários de `demo/scenarios.json`
precisam produzir exatamente a decisão que o roteiro anuncia, e o `category_id` precisa
funcionar tanto como número quanto como texto — foi essa divergência de tipo que, antes,
fazia o motor nunca encontrar regra aplicável.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.api import _exemplos_sessao  # noqa: PLC2701 — exemplos vêm do mesmo scenarios.json

DATASET = Path(__file__).parent.parent / "dataset"
SCENARIOS = Path(__file__).parent.parent / "demo" / "scenarios.json"

ARTEFATOS = ["model.lgb", "ruleset.pkl", "product_lookup.parquet",
             "brand_vocab.pkl", "thresholds.json"]

pytestmark = pytest.mark.skipif(
    not all((DATASET / a).exists() for a in ARTEFATOS),
    reason="requer os artefatos reais de treino em dev/dataset/",
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def cenarios() -> list[dict]:
    return json.loads(SCENARIOS.read_text(encoding="utf-8"))["cenarios"]


@pytest.fixture(scope="module")
def payloads() -> dict[str, dict]:
    """Payloads do Swagger indexados pelo título do cenário."""
    return {e["summary"]: e["value"] for e in _exemplos_sessao().values()}


def _cenario(cenarios, cid: str) -> dict:
    return next(c for c in cenarios if c["id"] == cid)


def test_cenarios_produzem_a_decisao_esperada(client, cenarios, payloads):
    """Cada cenário do roteiro precisa cair no nível de ação esperado em scenarios.json."""
    for cen in cenarios:
        corpo = client.post("/session", json=payloads[cen["titulo"]]).json()
        esperado = cen["esperado"]
        acao = corpo["action"] if corpo else None
        produto = corpo["recommended_product_id"] if corpo else None
        assert acao == esperado["action"], f"{cen['id']}: ação {acao}"
        assert (produto is not None) == esperado["tem_produto"], f"{cen['id']}: produto {produto}"


def test_category_id_numerico_e_texto_dao_o_mesmo_resultado(client, cenarios, payloads):
    """Regressão do bug de tipo: id serializado como número precisa casar com o ruleset.

    Sem a coerção em `EventIn`, o carrinho guarda `'2053013554658804075'` vindo do artefato
    e o evento traz o inteiro — nenhuma regra casa e o produto volta nulo.
    """
    texto = payloads[_cenario(cenarios, "cupom")["titulo"]]
    numerico = copy.deepcopy(texto)
    for e in numerico["events"]:
        e["category_id"] = int(e["category_id"])

    r_texto = client.post("/session", json=texto)
    r_num = client.post("/session", json=numerico)

    assert r_num.status_code == 200, r_num.text
    assert r_texto.json()["recommended_product_id"] == r_num.json()["recommended_product_id"]
    assert r_num.json()["recommended_product_id"] is not None


def test_carrinho_em_categoria_antecedente_resolve_produto(client, cenarios, payloads):
    """Categoria que é antecedente de regra do M2 precisa render produto concreto."""
    corpo = client.post("/session", json=payloads[_cenario(cenarios, "cupom")["titulo"]]).json()
    assert corpo["consequent"], "nenhuma regra aplicada ao carrinho"
    assert corpo["recommended_product_id"] is not None
    assert corpo["nba_score"] is not None and corpo["nba_score"] > 0


def test_compra_dentro_da_janela_nao_e_pontuada(client, cenarios, payloads):
    """Quem converte em ≤120 s sai da população de disparo e não recebe intervenção."""
    r = client.post("/session", json=payloads[_cenario(cenarios, "converteu")["titulo"]])
    assert r.status_code == 200
    assert r.json() is None


def test_mesma_sessao_repetida_decide_de_novo(client, cenarios, payloads):
    """A demonstração precisa poder ser repetida sem reiniciar o serviço.

    Reenviar a mesma sessão a reavalia do zero — a segunda execução não depende do
    estado da primeira.
    """
    payload = payloads[_cenario(cenarios, "cupom")["titulo"]]
    primeira = client.post("/session", json=payload).json()
    segunda = client.post("/session", json=payload).json()
    assert primeira["action"] == segunda["action"] == "strong_intervention"
    assert primeira["p_abandon"] == pytest.approx(segunda["p_abandon"])


def test_shap_tem_uma_contribuicao_por_feature(client, cenarios, payloads):
    """O vetor SHAP precisa alinhar com FEATURE_NAMES, senão a feature dominante mente."""
    from src.m3_classifier import FEATURE_NAMES

    corpo = client.post("/session", json=payloads[_cenario(cenarios, "cupom")["titulo"]]).json()
    assert len(corpo["shap_values"]) == len(FEATURE_NAMES)
    dominante = max(range(len(FEATURE_NAMES)), key=lambda i: abs(corpo["shap_values"][i]))
    assert corpo["dominant_feature"] == FEATURE_NAMES[dominante]


def test_swagger_expoe_os_quatro_exemplos(client, cenarios):
    """O Swagger precisa listar um exemplo por cenário, para a defesa não digitar JSON."""
    schema = client.get("/openapi.json").json()
    corpo = schema["paths"]["/session"]["post"]["requestBody"]["content"]["application/json"]
    exemplos = corpo["examples"]
    assert set(exemplos) == {c["id"] for c in cenarios}
    for cen in cenarios:
        assert exemplos[cen["id"]]["summary"] == cen["titulo"]
