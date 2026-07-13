"""Profiles raw CSV/Excel data into structured JSON for TMDL authoring.

This is the mirror image of schema_reader.py: that module reads TMDL text
into a ModelSchema (an *existing* model); this one reads raw data files into
a DataSourceProfile (a *prospective* one). Neither module authors TMDL —
Claude stays the author, this only supplies the facts (column names, types,
null/uniqueness stats, sample values) it would otherwise have to guess.
"""
from __future__ import annotations

import polars as pl

from simbi_mcp.types import ColumnProfile, TableProfile

_DTYPE_TO_TMDL: dict[type, str] = {
    pl.Int8: "int64",
    pl.Int16: "int64",
    pl.Int32: "int64",
    pl.Int64: "int64",
    pl.UInt8: "int64",
    pl.UInt16: "int64",
    pl.UInt32: "int64",
    pl.UInt64: "int64",
    pl.Float32: "double",
    pl.Float64: "double",
    pl.Utf8: "string",  # pl.String is an alias of pl.Utf8
    pl.Boolean: "boolean",
    pl.Date: "dateTime",
    pl.Datetime: "dateTime",
}

# Base types where min/max is meaningful — everything mapped except text/bool.
_NUMERIC_OR_TEMPORAL: frozenset[type] = frozenset(_DTYPE_TO_TMDL) - {pl.Boolean, pl.Utf8}


def _map_dtype_to_tmdl(dtype: pl.DataType) -> str:
    return _DTYPE_TO_TMDL.get(dtype.base_type(), "string")


def _profile_column(series: pl.Series, row_count: int) -> ColumnProfile:
    dtype = series.dtype
    tmdl_type = _map_dtype_to_tmdl(dtype)
    null_count = series.null_count()
    null_pct = round(null_count / row_count * 100, 2) if row_count else 0.0

    non_null = series.drop_nulls()
    distinct_count = non_null.n_unique()
    sample_values = [str(v) for v in non_null.unique().head(5).to_list()]

    min_val: str | None = None
    max_val: str | None = None
    if dtype.base_type() in _NUMERIC_OR_TEMPORAL and null_count < row_count:
        min_val = str(series.min())
        max_val = str(series.max())

    return ColumnProfile(
        name=series.name,
        polars_dtype=str(dtype),
        tmdl_type=tmdl_type,
        null_count=null_count,
        null_pct=null_pct,
        distinct_count=distinct_count,
        sample_values=sample_values,
        min=min_val,
        max=max_val,
        hints=[],
    )


def profile_dataframe(df: pl.DataFrame, table_name: str) -> TableProfile:
    row_count = df.height
    columns = [_profile_column(df[col], row_count) for col in df.columns]
    return TableProfile(table_name=table_name, row_count=row_count, columns=columns, hints=[])
