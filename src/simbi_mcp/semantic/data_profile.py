"""Profiles raw CSV/Excel data into structured JSON for TMDL authoring.

This is the mirror image of schema_reader.py: that module reads TMDL text
into a ModelSchema (an *existing* model); this one reads raw data files into
a DataSourceProfile (a *prospective* one). Neither module authors TMDL —
Claude stays the author, this only supplies the facts (column names, types,
null/uniqueness stats, sample values) it would otherwise have to guess.
"""
from __future__ import annotations

import re
from pathlib import Path

import fastexcel
import polars as pl

from simbi_mcp.types import ColumnProfile, DataSourceProfile, TableProfile

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

_ID_LIKE_RE = re.compile(r"(id|key|code)$", re.IGNORECASE)
_YEAR_RE = re.compile(r"^(19|20)\d{2}$")
_PERIOD_NAME_RE = re.compile(
    r"^(Q[1-4]|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", re.IGNORECASE
)


def _column_hints(name: str, dtype: pl.DataType, distinct_count: int, row_count: int) -> list[str]:
    hints: list[str] = []
    base = dtype.base_type()

    if row_count > 0 and distinct_count == row_count and _ID_LIKE_RE.search(name):
        hints.append("likely primary key")

    if base is pl.Date or base is pl.Datetime:
        hints.append("time-intelligence candidate")

    if base is pl.Utf8 and row_count > 0:
        low_cardinality_threshold = max(50, row_count * 0.05)
        if distinct_count <= low_cardinality_threshold:
            hints.append("dimension/slicer candidate")
        elif distinct_count > row_count * 0.5:
            hints.append("high cardinality — avoid as a slicer")

    return hints


def _table_hints(column_names: list[str]) -> list[str]:
    period_like = [c for c in column_names if _YEAR_RE.match(c) or _PERIOD_NAME_RE.match(c)]
    if len(period_like) < 3:
        return []
    return [
        f"WIDE format detected across columns {period_like} — unpivot "
        "(Table.UnpivotOtherColumns) into a long-form Year/Period + Value "
        "table before aggregating; do not SUM() a single period column."
    ]


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

    hints = _column_hints(series.name, dtype, distinct_count, row_count)

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
        hints=hints,
    )


def profile_dataframe(df: pl.DataFrame, table_name: str) -> TableProfile:
    row_count = df.height
    columns = [_profile_column(df[col], row_count) for col in df.columns]
    hints = _table_hints(df.columns)
    return TableProfile(table_name=table_name, row_count=row_count, columns=columns, hints=hints)


def profile_csv(path: Path) -> TableProfile:
    try:
        df = pl.read_csv(path, try_parse_dates=True)
    except Exception as exc:
        raise ValueError(f"Could not read CSV file {path}: {exc}") from exc
    return profile_dataframe(df, path.stem)


def profile_excel(path: Path, sheet: str | None = None) -> list[TableProfile]:
    try:
        reader = fastexcel.read_excel(path)
    except Exception as exc:
        raise ValueError(f"Could not read Excel file {path}: {exc}") from exc

    sheet_names = list(reader.sheet_names)
    if sheet is not None:
        if sheet not in sheet_names:
            raise ValueError(
                f"Sheet {sheet!r} not found in {path}; available sheets: {sheet_names}"
            )
        names_to_read = [sheet]
    else:
        names_to_read = sheet_names

    tables = []
    for name in names_to_read:
        df = reader.load_sheet(name).to_polars()
        tables.append(profile_dataframe(df, name))
    return tables


_SUPPORTED_EXTENSIONS = (".csv", ".xlsx")


def profile_file(path: str, sheet: str | None = None) -> DataSourceProfile:
    file_path = Path(path)
    if not file_path.exists():
        raise ValueError(f"File not found: {path}")

    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        tables = [profile_csv(file_path)]
    elif suffix == ".xlsx":
        tables = profile_excel(file_path, sheet)
    elif suffix == ".xls":
        raise ValueError(
            f"Legacy .xls is not supported (got {path}) — save as .xlsx and retry."
        )
    else:
        raise ValueError(
            f"Unsupported file type {suffix!r} (got {path}) — "
            f"analyze_data_source only supports {_SUPPORTED_EXTENSIONS}."
        )

    return DataSourceProfile(source_path=str(file_path), tables=tables)
