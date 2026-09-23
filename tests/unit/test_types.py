"""Tests for shared Pydantic types, including data-profile models."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from simbi_mcp.types import (
    ColumnProfile,
    DataSourceProfile,
    ModelColumn,
    ModelMeasure,
    ModelSchema,
    ModelTable,
    TableProfile,
)


class TestModelSchema:
    def test_lookup_by_measure_name(self) -> None:
        schema = ModelSchema(
            tables=[
                ModelTable(
                    name="sales",
                    columns=[ModelColumn(name="Revenue"), ModelColumn(name="Region")],
                ),
            ],
            measures=[
                ModelMeasure(
                    name="Total Revenue",
                    table="sales",
                    expression="SUM('sales'[Revenue])",
                    return_type="currency",
                ),
            ],
            relationships=[],
        )
        assert schema.has_measure("Total Revenue")
        assert not schema.has_measure("Nonexistent")
        assert schema.find_measure("Total Revenue").table == "sales"


def test_column_profile_defaults() -> None:
    col = ColumnProfile(
        name="Region",
        polars_dtype="String",
        tmdl_type="string",
        null_count=0,
        null_pct=0.0,
        distinct_count=4,
        sample_values=["North", "South"],
    )
    assert col.min is None
    assert col.max is None
    assert col.hints == []


def test_data_source_profile_round_trips_through_json() -> None:
    profile = DataSourceProfile(
        source_path="Sales.csv",
        tables=[
            TableProfile(
                table_name="Sales",
                row_count=50,
                columns=[
                    ColumnProfile(
                        name="OrderID",
                        polars_dtype="Int64",
                        tmdl_type="int64",
                        null_count=0,
                        null_pct=0.0,
                        distinct_count=50,
                        sample_values=["1001", "1002"],
                        min="1001",
                        max="1050",
                        hints=["likely primary key"],
                    ),
                ],
                hints=[],
            ),
        ],
    )
    payload = json.loads(profile.model_dump_json())
    assert payload["source_path"] == "Sales.csv"
    assert payload["tables"][0]["table_name"] == "Sales"
    assert payload["tables"][0]["columns"][0]["hints"] == ["likely primary key"]


def test_models_are_frozen() -> None:
    col = ColumnProfile(
        name="Region", polars_dtype="String", tmdl_type="string",
        null_count=0, null_pct=0.0, distinct_count=4, sample_values=[],
    )
    with pytest.raises(ValidationError):
        col.name = "Other"  # type: ignore[misc]
