# api.py — FastAPI + Swagger para o sistema NBA de detecção de abandono de carrinho.
#
# Uso: uvicorn src.api:app --reload
# Docs: http://localhost:8000/docs

import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.m1_pipeline import Event
from src.stream_simulator import StreamSimulator

DATASET_DIR = Path(__file__).parent.parent / "dataset"
SCENARIOS_PATH = Path(__file__).parent.parent / "demo" / "scenarios.json"

sim: Optional[StreamSimulator] = None


def _carregar_cenarios() -> dict:
    import json as _json
    if SCENARIOS_PATH.exists():
        return _json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    return {"cenarios": []}


CENARIOS = _carregar_cenarios()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # roda uma vez, na inicialização — carrega os 5 artefatos uma única vez,
    # não a cada requisição; o estado das sessões vive em `sim` entre chamadas
    global sim
    sim = StreamSimulator()
    yield


app = FastAPI(
    title="NBA — Next Best Action",
    description=(
        "Detecção de abandono de carrinho e recomendação de ação em tempo de sessão.\n\n"
        "**Como o disparo funciona:** a predição ocorre 120 s após o primeiro evento `cart`, "
        "desde que a sessão tenha ao menos 5 eventos até o carrinho, não registre `purchase` "
        "na janela e mantenha o usuário ativo nela. Enquanto essas condições não se completam, "
        "`POST /event` responde `null` — é o comportamento esperado, não um erro.\n\n"
        "**Para ver o pipeline completo de uma vez, use `POST /session`.**"
    ),
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Demonstração",
         "description": "Envia uma sessão inteira e devolve a decisão. É o caminho mais curto "
                        "para ver o pipeline completo em funcionamento."},
        {"name": "Ingestão",
         "description": "Fluxo real de produção: um evento por requisição, como chegaria de um "
                        "front-end de loja."},
        {"name": "Consulta",
         "description": "Estado de uma sessão e métricas agregadas."},
        {"name": "Bastidores",
         "description": "Dados de apoio da demonstração. Não faz parte do contrato de "
                        "produção."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Modelos de entrada e saída

def _exemplos_sessao() -> dict[str, dict]:
    # Exemplos do Swagger, montados a partir de demo/scenarios.json.
    exemplos = {}
    for c in CENARIOS.get("cenarios", []):
        hora = c.get("hora_base", 10)
        eventos = []
        for e in c["eventos"]:
            t = e["t"]
            eventos.append({
                "event_time": f"2019-11-01T{hora + t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}",
                "event_type": e["event_type"], "product_id": e["product_id"],
                "category_id": e["category_id"], "category_code": e["category_code"],
                "brand": e["brand"], "price": e["price"], "user_id": 513903572,
                "user_session": c.get("sessao_original", "sessao-exemplo"),
            })
        exemplos[c["id"]] = {"summary": c["titulo"], "description": c["resumo"],
                             "value": {"events": eventos}}
    return exemplos

class EventIn(BaseModel):
    event_time: datetime = Field(..., description="Instante do evento (ISO 8601, sem fuso).")
    event_type: str = Field(..., description="`view`, `cart` ou `purchase`.")
    product_id: int = Field(..., description="Identificador do produto.")
    category_id: str = Field(..., description=(
        "Identificador da categoria. Aceito como número ou texto — o JSON costuma "
        "entregá-lo como número, e a conversão para texto é feita aqui."))
    category_code: Optional[str] = Field(None, description="Hierarquia textual, ex.: `electronics.audio.headphone`.")
    brand: Optional[str] = Field(None, description="Marca; nulo é imputado como `unknown`.")
    price: float = Field(..., description="Preço do produto em dólares.")
    user_id: int = Field(..., description="Identificador do usuário.")
    user_session: str = Field(..., description=(
        "Identificador da sessão: use o mesmo valor em todos os eventos dela. É ele que vale em "
        "`GET /session/{id}` e `POST /flush/{id}`."))

    @field_validator("category_id", mode="before")
    @classmethod
    def _id_para_texto(cls, v):        
        return str(v) if isinstance(v, (int, float)) else v
    model_config = {"json_schema_extra": {"example": {
        "event_time": "2019-11-01T10:00:00",
        "event_type": "view",
        "product_id": 4804056,
        "category_id": "2053013554658804075",
        "category_code": "electronics.audio.headphone",
        "brand": "apple",
        "price": 160.55,
        "user_id": 513903572,
        "user_session": "demo-session-001",
    }}}


class NBAActionOut(BaseModel):
    action: str = Field(..., description=(
        "`strong_intervention` (cupom), `moderate_intervention` (produto complementar) "
        "ou `no_intervention`."))
    p_abandon: float = Field(..., description="Probabilidade estimada de abandono, entre 0 e 1.")
    consequent: Optional[list[str]] = Field(None, description=(
        "Categorias recomendadas pela regra de associação. Nulo quando nenhuma regra se "
        "aplica ao carrinho."))
    recommended_product_id: Optional[int] = Field(None, description=(
        "Produto concreto resolvido a partir da categoria recomendada. Nulo quando não há "
        "regra aplicável."))
    nba_score: Optional[float] = Field(None, description=(
        "lift × confiança da regra escolhida."))
    dominant_feature: Optional[str] = Field(None, description=(
        "Variável de maior contribuição absoluta no SHAP. Serve à auditoria; não participa "
        "da decisão."))
    shap_values: Optional[list[float]] = Field(None, description=(
        "Dezesseis contribuições, na ordem de `FEATURE_NAMES` do M3."))
    intervention_message: Optional[str] = Field(None, description="Mensagem associada ao nível de ação.")

# Endpoints

def _sim() -> StreamSimulator:
    assert sim is not None, "Simulador não inicializado"
    return sim


@app.post("/event", response_model=Optional[NBAActionOut], tags=["Ingestão"],
          summary="Ingere um evento isolado",
          description=("O `user_session` do evento identifica a sessão: use o mesmo valor em todos "
                       "os eventos dela e, depois, em `GET /session/{id}` ou `POST /flush/{id}`."))
def ingest_event(payload: EventIn):
    # Processa um evento e devolve a decisão, se a sessão atingir as condições de disparo.
    # Responde `null` enquanto a sessão não completa as condições — faltam eventos, o prazo
    # de 120 s ainda não venceu, ou a sessão foi excluída por ter comprado dentro da janela.
    event = Event(
        event_time=payload.event_time.replace(tzinfo=None),
        event_type=payload.event_type,
        product_id=payload.product_id,
        category_id=payload.category_id,
        category_code=payload.category_code,
        brand=payload.brand,
        price=payload.price,
        user_id=payload.user_id,
        user_session=payload.user_session,
    )
    action = _sim().ingest(event)
    return _serialize(action)


@app.post("/flush/{session_id}", response_model=Optional[NBAActionOut], tags=["Ingestão"],
          summary="Força a avaliação de uma sessão pendente",
          description=("`session_id` é o `user_session` dos eventos. A sessão precisa ter um `cart` e "
                       "ao menos um evento depois dele. Eventos novos para uma sessão já avaliada são "
                       "ignorados. Para reavaliá-la, reenvie a sessão inteira por `POST /session`."))
def flush_session(session_id: str):
    # Força o trigger de uma sessão com cart que ainda não atingiu T=120s
    action = _sim().flush(session_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada, sem cart ou já avaliada.")
    return _serialize(action)


class SessionIn(BaseModel):
    # Sessão completa: a lista de eventos em ordem cronológica, todos com o mesmo user_session
    events: list[EventIn] = Field(..., description="Eventos da sessão, em ordem cronológica.")


@app.post("/session", response_model=Optional[NBAActionOut], tags=["Demonstração"],
          summary="Processa uma sessão inteira e devolve a decisão",
          description=("Processa todos os eventos de uma sessão, que devem ter o mesmo `user_session`, "
                       "e devolve a decisão. Reenviar a mesma sessão a reavalia do zero. A decisão pode "
                       "ser consultada depois em `GET /session/{user_session}`."))
def ingest_session(payload: SessionIn = Body(..., openapi_examples=_exemplos_sessao())):
    # Ingere todos os eventos de uma sessão e devolve a decisão do motor NBA.
    # Equivale a chamar `POST /event` para cada evento, na ordem.
    ids = {e.user_session for e in payload.events}
    if len(ids) != 1:
        raise HTTPException(status_code=422, detail=(
            "A sessão precisa ter eventos, todos com o mesmo user_session."))
    sid = ids.pop()
    simulador = _sim()
    # reenviar a mesma sessão a reavalia do zero — permite repetir a demonstração sem reiniciar
    simulador.reset(sid)
    resultado = None
    for e in payload.events:
        evento = Event(
            event_time=e.event_time.replace(tzinfo=None), event_type=e.event_type,
            product_id=e.product_id, category_id=e.category_id,
            category_code=e.category_code, brand=e.brand, price=e.price,
            user_id=e.user_id, user_session=sid,
        )
        # reusa o MESMO ingest() do fluxo de produção — nenhuma lógica duplicada
        acao = simulador.ingest(evento)
        if acao is not None:
            resultado = acao
    # fallback defensivo: get_action deveria sempre coincidir com 'resultado'
    return _serialize(resultado or simulador.get_action(sid))


@app.get("/session/{session_id}", response_model=Optional[NBAActionOut],
         tags=["Demonstração", "Consulta"],
         summary="Consulta a decisão de UMA sessão, pelo identificador",
         description="Use o `user_session` dos eventos da sessão.")
def get_session(session_id: str):
    # Devolve a decisão já tomada para essa sessão, ou `null` se ela não foi pontuada.
    # Identificador nunca visto devolve 404; sessão conhecida mas não pontuada devolve `null`. 
    simulador = _sim()
    if not simulador.has_session(session_id):
        raise HTTPException(status_code=404, detail=f"Sessão '{session_id}' não existe.")
    return _serialize(simulador.get_action(session_id))

@app.get("/demo/scenarios", tags=["Bastidores"],
         summary="Cenários prontos que alimentam o demo.html")
def demo_scenarios():
    #Devolve os cenários de `demo/scenarios.json`, com eventos em deslocamento de segundos.
    return CENARIOS


@app.get("/metrics", tags=["Consulta"], summary="Métricas agregadas das sessões processadas")
def get_metrics():
    # Retorna métricas agregadas de todas as sessões processadas.
    return _sim().metrics()


def _serialize(action) -> Optional[NBAActionOut]:
    if action is None:
        return None
    return NBAActionOut(
        action=action.action,
        p_abandon=action.p_abandon,
        consequent=list(action.consequent) if action.consequent else None,
        recommended_product_id=action.recommended_product_id,
        nba_score=action.nba_score,
        dominant_feature=action.dominant_feature,
        # np.ndarray não serializa em JSON — .tolist() converte pra lista nativa
        shap_values=action.shap_values.tolist() if action.shap_values is not None else None,
        intervention_message=action.intervention_message,
    )
