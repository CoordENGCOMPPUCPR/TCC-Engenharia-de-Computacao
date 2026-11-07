"""Teste de contrato sobre os artefatos reais em dev/dataset/ (skip se ausentes)."""

import pickle
from pathlib import Path

import pytest

from src.m2_association import filter_rules_for_session, validate_ruleset_types
from src.product_lookup import load_lookup, resolve_product

DATASET_DIR = Path(__file__).parent.parent / "dataset"
RULESET = DATASET_DIR / "ruleset.pkl"
LOOKUP = DATASET_DIR / "product_lookup.parquet"

pytestmark = pytest.mark.skipif(
    not (RULESET.exists() and LOOKUP.exists()),
    reason="artefatos reais ausentes em dev/dataset/",
)


@pytest.fixture(scope="module")
def ruleset():
    with open(RULESET, "rb") as f:
        return pickle.load(f)


@pytest.fixture(scope="module")
def lookup():
    return load_lookup(str(LOOKUP))


def test_ruleset_category_ids_are_str(ruleset):
    validate_ruleset_types(ruleset)


def test_lookup_index_is_str(lookup):
    assert all(isinstance(i, str) for i in lookup.index)


def test_every_antecedent_matches_itself(ruleset):
    """Simula um carrinho contendo exatamente o antecedente — a regra deve casar."""
    for ant in ruleset.rules["antecedents"]:
        assert not filter_rules_for_session(ruleset, frozenset(ant)).empty


def test_at_least_one_consequent_resolves_to_product(ruleset, lookup):
    resolved = [
        resolve_product(c, lookup)
        for cons in ruleset.rules["consequents"] for c in cons
    ]
    assert any(pid is not None for pid in resolved)
