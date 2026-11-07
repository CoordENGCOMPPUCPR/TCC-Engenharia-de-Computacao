# m2_association.py — Mineração de regras de associação via FP-Growth.

from typing import Optional

import pandas as pd
from mlxtend.frequent_patterns import association_rules, fpgrowth
from mlxtend.preprocessing import TransactionEncoder

from src.interfaces import RuleSet, SessionProfile

# nenhuma regra com ≥ 100 cestas e confiança ≥ 0,50 atinge lift 1,5 neste catálogo; as 4 regras com
# lift ∈ [1,0; 1,5) são significativas (χ² p < 0,005; IC95% do lift > 1,0).
MIN_SUPPORT = 0.01
MIN_CONFIDENCE = 0.50
MIN_LIFT = 1.0

# Piso absoluto de suporte: regra precisa de ≥ 100 cestas para ter significância estatística mínima. 
MIN_RULE_SESSIONS = 100


def build_transactions_from_csv(csv_path: str) -> list[list[str]]:
    # Extrai transações de category_id a partir de todos os eventos cart do CSV.
    # Usa a sessão completa (não apenas até o trigger) para capturar co-ocorrências reais entre categorias — necessário para FP-Growth produzir regras.
    # Retorna apenas sessões com 2+ categorias distintas no carrinho.
    
    cols = ["event_type", "category_id", "user_session"]
    
    df = pd.read_csv(csv_path, usecols=cols, dtype={"category_id": str})
    carts = df[df["event_type"] == "cart"]
    by_session = (
        carts.groupby("user_session")["category_id"]
        .apply(lambda s: list(s.unique()))  # categorias distintas por sessão = a "cesta"
        .reset_index()
    )
    return [row for row in by_session["category_id"] if len(row) >= 2]  # cesta de 1 item

def mine_rules(
    profiles: list[SessionProfile],
    min_support: float = MIN_SUPPORT,
    min_confidence: float = MIN_CONFIDENCE,
    min_lift: float = MIN_LIFT,
    transactions: Optional[list[list[str]]] = None,
    min_rule_sessions: int = MIN_RULE_SESSIONS,
) -> RuleSet:
    # Minera regras de associação entre category_ids.
    # transactions: lista de cestas de compra (sessão completa). Se None, usa profile.cart_items 
    if transactions is None:
        transactions = [list(p.cart_items) for p in profiles if len(p.cart_items) >= 2]

    if not transactions:
        return RuleSet(rules=_empty_rules())

    rules = _run_fpgrowth(transactions, min_support, min_confidence, min_lift, min_rule_sessions)
    return RuleSet(rules=rules.reset_index(drop=True))


def filter_rules_for_session(
    ruleset: RuleSet,
    cart_items: frozenset[str],
) -> pd.DataFrame:
    # Retorna regras cujo antecedente é subconjunto dos itens no carrinho da sessão.
    # Resultado ordenado por lift decrescente — pronto para M4 consumir.
    
    if ruleset.rules.empty:
        return _empty_rules()

    mask = ruleset.rules["antecedents"].apply(lambda a: a.issubset(cart_items))
    return ruleset.rules[mask].sort_values("lift", ascending=False).reset_index(drop=True)


def _run_fpgrowth(
    transactions: list[list[str]],
    min_support: float,
    min_confidence: float,
    min_lift: float,
    min_rule_sessions: int = MIN_RULE_SESSIONS,
) -> pd.DataFrame:
    # Executa FP-Growth e retorna regras filtradas por confiança, lift e piso de suporte.
    # cestas de texto -> matriz binária (1 linha por cesta, 1 coluna por categoria)
    te = TransactionEncoder()
    te_array = te.fit_transform(transactions)
    df = pd.DataFrame(te_array, columns=te.columns_)

    # conjuntos de categorias que co-ocorrem com frequência >= min_support
    freq = fpgrowth(df, min_support=min_support, use_colnames=True)
    if freq.empty:
        return _empty_rules()

    # transforma "A e B aparecem juntos" em regras direcionais A->B e B->A
    rules = association_rules(freq, metric="confidence", min_threshold=min_confidence)
    # support * len(df) converte suporte fracionário de volta em contagem de cestas,
    # pra comparar contra o piso absoluto (min_rule_sessions é uma contagem, não fração)
    rules = rules[(rules["lift"] >= min_lift) & (rules["support"] * len(df) >= min_rule_sessions)].copy()
    rules = rules.sort_values("lift", ascending=False)
    return rules


def _empty_rules() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["antecedents", "consequents", "support", "confidence", "lift"]
    )

def validate_ruleset_types(ruleset: RuleSet) -> None:
    # Garante que antecedents/consequents contêm category_id como str.
    if ruleset.rules.empty:
        return
    for col in ("antecedents", "consequents"):
        bad = ruleset.rules[col].apply(lambda s: any(not isinstance(x, str) for x in s))
        if bad.any():
            sample = next(iter(ruleset.rules.loc[bad, col].iloc[0]))
            raise TypeError(
                f"RuleSet.{col} contém category_id do tipo {type(sample).__name__} "
                f"(esperado str). Regenere ruleset.pkl com src.train."
            )
