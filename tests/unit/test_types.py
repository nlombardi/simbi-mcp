"""Smoke tests for shared Pydantic types."""
from simbi_mcp.types import (
    ModelColumn,
    ModelMeasure,
    ModelSchema,
    ModelTable,
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
