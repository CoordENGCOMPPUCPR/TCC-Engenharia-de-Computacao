"""Testes do product_lookup com dados sintéticos."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.product_lookup import build_lookup, load_lookup, resolve_product


@pytest.fixture
def csv_path(tmp_path):
    """CSV sintético com eventos de purchase em categorias conhecidas."""
    rows = [
        # electronics: produto 10 comprado 3x, produto 11 comprado 1x
        {"event_type": "purchase", "product_id": 10, "category_id": "electronics"},
        {"event_type": "purchase", "product_id": 10, "category_id": "electronics"},
        {"event_type": "purchase", "product_id": 10, "category_id": "electronics"},
        {"event_type": "purchase", "product_id": 11, "category_id": "electronics"},
        # computers: produto 20 comprado 2x
        {"event_type": "purchase", "product_id": 20, "category_id": "computers"},
        {"event_type": "purchase", "product_id": 20, "category_id": "computers"},
        # views não contam
        {"event_type": "view", "product_id": 99, "category_id": "electronics"},
    ]
    path = tmp_path / "test.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


@pytest.fixture
def lookup(csv_path, tmp_path):
    out = str(tmp_path / "lookup.parquet")
    return build_lookup(csv_path, output_path=out)


class TestBuildLookup:
    def test_returns_dataframe(self, lookup):
        assert isinstance(lookup, pd.DataFrame)

    def test_indexed_by_category_id(self, lookup):
        assert lookup.index.name == "category_id"

    def test_top_product_selected(self, lookup):
        # produto 10 tem mais purchases em electronics
        assert lookup.loc["electronics", "product_id"] == 10

    def test_one_row_per_category(self, lookup):
        assert len(lookup) == 2  # electronics e computers

    def test_purchase_count_correct(self, lookup):
        assert lookup.loc["electronics", "purchase_count"] == 3
        assert lookup.loc["computers", "purchase_count"] == 2

    def test_views_not_counted(self, lookup):
        # produto 99 aparece só em view — não deve entrar no lookup
        assert 99 not in lookup["product_id"].values


class TestLoadLookup:
    def test_roundtrip(self, csv_path, tmp_path):
        out = str(tmp_path / "lookup.parquet")
        original = build_lookup(csv_path, output_path=out)
        loaded = load_lookup(out)
        pd.testing.assert_frame_equal(original, loaded)


class TestNumericCategoryIds:
    """IDs reais são inteiros de 19 dígitos — pandas os infere como int64 sem dtype."""

    @pytest.fixture
    def numeric_csv(self, tmp_path):
        rows = [
            {"event_type": "purchase", "product_id": 10, "category_id": 2053013555631882655},
            {"event_type": "purchase", "product_id": 10, "category_id": 2053013555631882655},
            {"event_type": "purchase", "product_id": 20, "category_id": 2053013554658804075},
        ]
        path = tmp_path / "numeric.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        return str(path)

    def test_build_lookup_index_is_str(self, numeric_csv, tmp_path):
        lookup = build_lookup(numeric_csv, output_path=str(tmp_path / "l.parquet"))
        assert all(isinstance(i, str) for i in lookup.index)

    def test_resolve_with_str_key_matches(self, numeric_csv, tmp_path):
        lookup = build_lookup(numeric_csv, output_path=str(tmp_path / "l.parquet"))
        assert resolve_product("2053013555631882655", lookup) == 10

    def test_load_lookup_rejects_int_index(self, tmp_path):
        bad = pd.DataFrame(
            {"product_id": [10], "purchase_count": [1]},
            index=pd.Index([2053013555631882655], name="category_id"),
        )
        out = str(tmp_path / "bad.parquet")
        bad.to_parquet(out)
        with pytest.raises(TypeError, match="esperado str"):
            load_lookup(out)


class TestResolveProduct:
    def test_known_category_returns_product(self, lookup):
        result = resolve_product("electronics", lookup)
        assert result == 10

    def test_unknown_category_returns_none(self, lookup):
        result = resolve_product("furniture", lookup)
        assert result is None

    def test_returns_int(self, lookup):
        result = resolve_product("computers", lookup)
        assert isinstance(result, int)
