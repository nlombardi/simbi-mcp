"""Tests for CSV/Excel structure profiling (analyze_data_source's core)."""
from __future__ import annotations

import polars as pl
import pytest

from simbi_mcp.semantic.data_profile import _map_dtype_to_tmdl, profile_dataframe
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
