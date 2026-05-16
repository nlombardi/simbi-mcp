"""Dataset profiler — classifies columns by role for downstream planning."""
from __future__ import annotations

import re
from pathlib import Path

import polars as pl

from simbi_mcp.types import ColumnProfile, ColumnRole, DatasetProfile

_SAMPLE_SIZE = 5
_ID_PATTERN = re.compile(r"(^id$|_id$|^.+id$)", re.IGNORECASE)


def profile_dataset(csv_path: Path) -> DatasetProfile:
    """Read a CSV and return a typed profile.

    Column-role classification rules (applied in order, first match wins):
      1. DATE if dtype is temporal (or parseable as date).
      2. ID if column name matches *id pattern AND distinct_count == row_count.
      3. MEASURE if dtype is numeric AND distinct_count > 1 AND not an ID.
      4. DIMENSION otherwise.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    df = pl.read_csv(csv_path, try_parse_dates=True)
    row_count = df.height
    columns: list[ColumnProfile] = []

    for name in df.columns:
        series = df[name]
        dtype = str(series.dtype)
        null_count = int(series.null_count())
        distinct_count = int(series.n_unique())
        role = _classify(
            name=name,
            dtype=series.dtype,
            distinct_count=distinct_count,
            row_count=row_count,
        )
        sample_values = [_coerce(v) for v in series.head(_SAMPLE_SIZE).to_list()]
        columns.append(
            ColumnProfile(
                name=name,
                dtype=dtype,
                role=role,
                null_count=null_count,
                distinct_count=distinct_count,
                sample_values=sample_values,
            )
        )

    return DatasetProfile(
        source_path=str(csv_path),
        table_name=csv_path.stem,
        row_count=row_count,
        columns=columns,
    )


def _classify(
    *,
    name: str,
    dtype: pl.DataType,
    distinct_count: int,
    row_count: int,
) -> ColumnRole:
    if dtype.is_temporal():
        return ColumnRole.DATE
    if _ID_PATTERN.search(name) and distinct_count == row_count:
        return ColumnRole.ID
    if dtype.is_numeric() and distinct_count > 1:
        return ColumnRole.MEASURE
    return ColumnRole.DIMENSION


def _coerce(value: object) -> str | int | float | bool | None:
    """Polars may return numpy/datetime types; coerce to JSON-safe primitives."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
