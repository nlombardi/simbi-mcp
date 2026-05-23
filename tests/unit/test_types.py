"""Smoke tests for shared Pydantic types."""
import pytest
from pydantic import ValidationError

from simbi_mcp.types import (
    ColumnProfile,
    ColumnRole,
    DatasetProfile,
    MeasurePlan,
    ModelColumn,
    ModelMeasure,
    ModelSchema,
    ModelTable,
)


class TestColumnProfile:
    def test_minimal_valid(self) -> None:
        cp = ColumnProfile(
            name="Revenue",
            dtype="float64",
            role=ColumnRole.MEASURE,
            null_count=0,
            distinct_count=42,
            sample_values=[1.0, 2.5, 3.14],
        )
        assert cp.name == "Revenue"
        assert cp.role is ColumnRole.MEASURE

    def test_rejects_unknown_role(self) -> None:
        with pytest.raises(ValidationError):
            ColumnProfile(
                name="X", dtype="int64", role="bogus",  # type: ignore[arg-type]
                null_count=0, distinct_count=1, sample_values=[],
            )


class TestDatasetProfile:
    def test_round_trip(self) -> None:
        dp = DatasetProfile(
            source_path="/tmp/x.csv",
            table_name="sales",
            row_count=50,
            columns=[
                ColumnProfile(
                    name="Revenue", dtype="float64", role=ColumnRole.MEASURE,
                    null_count=0, distinct_count=50, sample_values=[1.0],
                ),
            ],
        )
        roundtrip = DatasetProfile.model_validate_json(dp.model_dump_json())
        assert roundtrip == dp


class TestMeasurePlan:
    def test_minimal_valid(self) -> None:
        mp = MeasurePlan(
            name="Total Revenue",
            expression="SUM('sales'[Revenue])",
            return_type="currency",
            rationale="User asked for revenue totals",
        )
        assert mp.name == "Total Revenue"


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
