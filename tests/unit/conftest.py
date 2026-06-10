"""Shared pytest fixtures for unit tests."""
import pytest

from simbi_mcp.types import ModelColumn, ModelMeasure, ModelSchema, ModelTable


@pytest.fixture
def schema() -> ModelSchema:
    return ModelSchema(
        tables=[ModelTable(name="sales", columns=[ModelColumn(name="Region"), ModelColumn(name="OrderDate")])],
        measures=[
            ModelMeasure(
                name="Total Revenue",
                table="sales",
                expression="SUM(sales[Revenue])",
                return_type="currency",
            ),
            ModelMeasure(
                name="Order Count",
                table="sales",
                expression="COUNTROWS(sales)",
                return_type="integer",
            ),
        ],
        relationships=[],
    )
