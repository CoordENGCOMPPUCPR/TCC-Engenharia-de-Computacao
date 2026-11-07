# stream_simulator.py — Processa eventos em ordem cronológica e dispara NBA no trigger.

import heapq
import pickle
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import lightgbm as lgb
import numpy as np
import shap

from src.interfaces import AbandonScore, NBAAction, SessionProfile
from src.m1_pipeline import Event, build_session_profile
from src.m2_association import validate_ruleset_types
from src.m3_classifier import FEATURE_NAMES, predict_abandon_score, profiles_to_features
from src.m4_nba import decide
from src.product_lookup import load_lookup
from src.trigger import (
    REASON_PURCHASED, REASON_TOO_SHORT, REASON_USER_LEFT, REQUIRE_ACTIVITY, T_WINDOW,
    ineligibility_reason,
)

DATASET_DIR = Path(__file__).parent.parent / "dataset"


@dataclass
class SessionState:
    events: list[Event] = field(default_factory=list)
    cart_time: Optional[datetime] = None
    triggered: bool = False
    purchased: bool = False
    reason: Optional[str] = None      # motivo de não-elegibilidade (src/trigger.REASON_*), se houver
    action: Optional[NBAAction] = None
    p_abandon: Optional[float] = None
    profile: Optional[SessionProfile] = None


class StreamSimulator:
    # Simula o pipeline de produção processando eventos em ordem cronológica.

    def __init__(
        self,
        model_path: Optional[str] = None,
        ruleset_path: Optional[str] = None,
        lookup_path: Optional[str] = None,
        batch_shap: bool = False,
    ):
        mp = model_path or str(DATASET_DIR / "model.lgb")
        vp = (
            str(Path(model_path).parent / "brand_vocab.pkl")
            if model_path
            else str(DATASET_DIR / "brand_vocab.pkl")
        )
        rp = ruleset_path or str(DATASET_DIR / "ruleset.pkl")
        lp = lookup_path or str(DATASET_DIR / "product_lookup.parquet")

        # Carrega o modelo no formato nativo do LightGBM (model.lgb), sem depender de pickle.
        # O arquivo é lido pelo Python: no Windows, o LightGBM não abre caminhos com acento
        # (ex.: "Área de Trabalho")
        self.model = lgb.Booster(model_str=Path(mp).read_text(encoding="utf-8"))
        self.explainer = shap.TreeExplainer(self.model)

        with open(vp, "rb") as f:
            self.brand_vocab = pickle.load(f)

        with open(rp, "rb") as f:
            self.ruleset = pickle.load(f)
        validate_ruleset_types(self.ruleset)

        self.lookup = load_lookup(lp)
        self.batch_shap = batch_shap

        self._sessions: dict[str, SessionState] = {}
        self._deadlines: list[tuple[datetime, str]] = []   # heap (cart_time + T, session_id)

    def ingest(self, event: Event) -> Optional[NBAAction]:
        # Recebe um evento e retorna NBAAction se o trigger for ativado, None caso contrário.
        # Sessões de terceiros com prazo vencido são avaliadas antes deste evento
        # (relógio virtual); suas ações ficam acessíveis via get_action().
        
        fired = self._expire(event.event_time)
        sid = event.user_session
        state = self._sessions.setdefault(sid, SessionState())
        if sid in fired:
            # o prazo desta sessão venceu neste instante: devolve a ação; o evento atual é pós-trigger
            if event.event_type == "purchase":
                state.purchased = True
            return state.action

        if state.triggered:
            # já predisse — só atualiza purchase para métricas
            if event.event_type == "purchase":
                state.purchased = True
            return None

        if event.event_type == "purchase":
            state.purchased = True
            state.triggered = True  # cancela qualquer trigger futuro
            state.reason = REASON_PURCHASED
            return None

        state.events.append(event)

        # registra 1º cart e agenda o vencimento da janela
        if event.event_type == "cart" and state.cart_time is None:
            state.cart_time = event.event_time
            heapq.heappush(self._deadlines, (state.cart_time + timedelta(seconds=T_WINDOW), sid))

        # verifica trigger: tem cart + T segundos passados desde o cart
        if state.cart_time is not None:
            elapsed = (event.event_time - state.cart_time).total_seconds()
            if elapsed >= T_WINDOW:
                return self._trigger(sid, state)

        return None

    def _expire(self, now: datetime) -> set[str]:
        # Dispara as sessões cujo prazo cart_time + T é < now e ainda não foram avaliadas.
        # Estritamente menor (não <=): um evento que chegue exatamente no instante do
        # prazo (cart_time + T) deve primeiro ser anexado a state.events pelo fluxo normal
        # de ingest().
        # Quando o evento é da própria sessão, ingest() já dispara via elapsed >= T_WINDOW logo
        # abaixo, com o evento devidamente anexado; quando é de outra sessão, o próximo
        # evento com timestamp estritamente posterior expira esta normalmente.
        # Retorna os ids disparados nesta chamada.

        fired: set[str] = set()
        while self._deadlines and self._deadlines[0][0] < now:
            _, sid = heapq.heappop(self._deadlines)
            state = self._sessions.get(sid)
            if state is not None and not state.triggered:
                self._trigger(sid, state)
                fired.add(sid)
        return fired

    def flush(self, session_id: str) -> Optional[NBAAction]:
        # Força o disparo de uma sessão com cart ainda pendente. No replay, é chamado ao final
        # para as sessões cujo prazo vence depois do último evento. Na API, avalia sem esperar T.
        state = self._sessions.get(session_id)
        if state is None or state.triggered or state.cart_time is None:
            return None
        return self._trigger(session_id, state)

    def reset(self, session_id: str) -> None:
        # Descarta o estado de uma sessão, para que ela seja avaliada do zero. Usado pela API
        # quando a mesma sessão é reenviada inteira (POST /session).
        self._sessions.pop(session_id, None)
        self._deadlines = [d for d in self._deadlines if d[1] != session_id]
        heapq.heapify(self._deadlines)

    def has_session(self, session_id: str) -> bool:
        # Se a sessão já foi vista, independentemente de ter sido pontuada.
        return session_id in self._sessions

    def get_action(self, session_id: str) -> Optional[NBAAction]:
        # Retorna a NBAAction já computada para a sessão, ou None.
        state = self._sessions.get(session_id)
        return state.action if state else None

    def metrics(self) -> dict:
        # Retorna métricas agregadas de todas as sessões processadas.
    
        # eligible  = sessões que receberam predição (perfil válido)
        # coverage  = eligible / sessões com cart
        # reasons   = contagem de sessões não elegíveis por motivo (src/trigger.REASON_*)
        
        states = list(self._sessions.values())
        total = len(states)
        with_cart = sum(1 for s in states if s.cart_time is not None)
        eligible = sum(1 for s in states if s.profile is not None)
        purchased = sum(1 for s in states if s.purchased)
        reasons: dict[str, int] = {}
        actions: dict[str, int] = {}
        for s in states:
            if s.reason:
                reasons[s.reason] = reasons.get(s.reason, 0) + 1
            if s.action:
                actions[s.action.action] = actions.get(s.action.action, 0) + 1

        return {
            "total_sessions": total,
            "cart_sessions": with_cart,
            "eligible": eligible,
            "triggered": sum(1 for s in states if s.triggered),
            "purchased": purchased,
            "coverage": eligible / with_cart if with_cart else 0.0,
            "reasons": reasons,
            "actions": actions,
        }

    def _trigger(self, session_id: str, state: SessionState) -> Optional[NBAAction]:
        state.triggered = True
        # eventos pós-cart dentro da janela, nunca purchase (já teria cancelado o
        # trigger em ingest, antes de chegar aqui) — só pra achar o 1º pra REASON_USER_LEFT
        post = [e for e in state.events
                if e.event_type != "purchase" and state.cart_time is not None
                and e.event_time > state.cart_time
                and (e.event_time - state.cart_time).total_seconds() <= T_WINDOW]
        state.reason = ineligibility_reason(
            state.cart_time, None, post[0].event_time if post else None, T_WINDOW, REQUIRE_ACTIVITY
        )
        profile = None
        if state.reason is None:
            profile = build_session_profile(state.events, t_window=T_WINDOW)
            if profile is None:
                state.reason = REASON_TOO_SHORT
        state.events = []  # libera memória — eventos não são mais necessários
        if profile is None:
            return None
        state.profile = profile

        if self.batch_shap:
            # Replay: pula SHAP por sessão — será calculado em batch ao final
            X = profiles_to_features([profile], self.brand_vocab)
            p_abandon = float(self.model.predict(X)[0])
            abandon_score = AbandonScore(
                p_abandon=p_abandon,
                shap_values=np.zeros(len(FEATURE_NAMES)),
            )
        else:
            # API: SHAP por sessão 
            abandon_score = predict_abandon_score(
                profile, self.model, self.explainer, self.brand_vocab
            )
            p_abandon = abandon_score.p_abandon
        state.p_abandon = p_abandon
        action = decide(profile, abandon_score, self.ruleset, self.lookup)
        state.action = action
        return action
