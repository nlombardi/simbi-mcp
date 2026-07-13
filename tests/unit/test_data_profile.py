"""Tests for CSV/Excel structure profiling (analyze_data_source's core)."""
from __future__ import annotations

import polars as pl
import pytest

from simbi_mcp.semantic.data_profile import _column_hints, _map_dtype_to_tmdl, _table_hints, profile_dataframe
from simbi_mcp.types import ColumnProfile


def _find(columns: list[ColumnProfile], name: str) -> ColumnProfile:
    return next(c for c in columns if c.name == name)


@pytest.mark.parametrize(
    "dtype,expected",
    [
        (pl.Int64, "int64"),
        (pl.Int32, "int64"),
        (pl.UInt8, "int64"),
        (pl.Float64, "double"),
        (pl.Float32, "double"),
        (pl.Utf8, "string"),
        (pl.Boolean, "boolean"),
        (pl.Date, "dateTime"),
        (pl.Datetime, "dateTime"),
    ],
)
def test_map_dtype_to_tmdl(dtype: pl.DataType, expected: str) -> None:
    assert _map_dtype_to_tmdl(dtype) == expected


def test_map_dtype_to_tmdl_falls_back_to_string_for_nested_types() -> None:
    assert _map_dtype_to_tmdl(pl.List(pl.Int64)) == "string"


def test_profile_dataframe_row_count() -> None:
    df = pl.DataFrame({"OrderID": [1, 2, 3, 4]})
    profile = profile_dataframe(df, "sales")
    assert profile.table_name == "sales"
    assert profile.row_count == 4


def test_profile_dataframe_column_stats() -> None:
    df = pl.DataFrame(
        {
            "OrderID": [1, 2, 3, 4],
            "Region": ["North", "South", "North", None],
            "Revenue": [10.5, 20.0, None, 5.25],
        }
    )
    profile = profile_dataframe(df, "sales")

    order_id = _find(profile.columns, "OrderID")
    assert order_id.tmdl_type == "int64"
    assert order_id.null_count == 0
    assert order_id.distinct_count == 4
    assert order_id.min == "1"
    assert order_id.max == "4"

    region = _find(profile.columns, "Region")
    assert region.tmdl_type == "string"
    assert region.null_count == 1
    assert region.null_pct == 25.0
    assert region.distinct_count == 2  # non-null distinct: North, South
    assert region.min is None  # min/max only computed for numeric/temporal
    assert region.max is None
    assert set(region.sample_values) <= {"North", "South"}

    revenue = _find(profile.columns, "Revenue")
    assert revenue.tmdl_type == "double"
    assert revenue.null_count == 1
    assert revenue.min == "5.25"
    assert revenue.max == "20.0"


def test_primary_key_hint_fires_on_unique_id_named_column() -> None:
    hints = _column_hints("OrderID", pl.Int64, distinct_count=50, row_count=50)
    assert "likely primary key" in hints


def test_primary_key_hint_does_not_fire_without_id_like_name() -> None:
    hints = _column_hints("OrderDate", pl.Date, distinct_count=50, row_count=50)
    assert "likely primary key" not in hints


def test_primary_key_hint_does_not_fire_if_not_fully_unique() -> None:
    hints = _column_hints("CustomerID", pl.Int64, distinct_count=40, row_count=50)
    assert "likely primary key" not in hints


def test_date_hint_fires_for_date_dtype() -> None:
    hints = _column_hints("OrderDate", pl.Date, distinct_count=50, row_count=50)
    assert "time-intelligence candidate" in hints


def test_date_hint_fires_for_datetime_dtype() -> None:
    hints = _column_hints("CreatedAt", pl.Datetime("us"), distinct_count=50, row_count=50)
    assert "time-intelligence candidate" in hints


def test_dimension_hint_fires_for_low_cardinality_text() -> None:
    hints = _column_hints("Region", pl.Utf8, distinct_count=4, row_count=50)
    assert "dimension/slicer candidate" in hints


def test_high_cardinality_hint_fires_for_mostly_unique_text() -> None:
    hints = _column_hints("Description", pl.Utf8, distinct_count=95, row_count=100)
    assert "high cardinality — avoid as a slicer" in hints
    assert "dimension/slicer candidate" not in hints


def test_no_hint_fires_for_plain_numeric_measure() -> None:
    hints = _column_hints("Revenue", pl.Float64, distinct_count=48, row_count=50)
    assert hints == []


def test_wide_format_hint_fires_for_year_columns() -> None:
    hints = _table_hints(["Indicator", "2023", "2024", "2025"])
    assert len(hints) == 1
    assert "WIDE format" in hints[0]
    assert "2023" in hints[0] and "2024" in hints[0] and "2025" in hints[0]


def test_wide_format_hint_fires_for_quarter_columns() -> None:
    hints = _table_hints(["Region", "Q1", "Q2", "Q3", "Q4"])
    assert len(hints) == 1
    assert "WIDE format" in hints[0]


def test_wide_format_hint_does_not_fire_for_normal_columns() -> None:
    assert _table_hints(["OrderID", "OrderDate", "Region", "Revenue"]) == []


def test_wide_format_hint_requires_at_least_three_period_columns() -> None:
    assert _table_hints(["Indicator", "2023", "2024"]) == []
