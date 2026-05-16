"""Integration test for the mockup generator against the real Anthropic API.

Requires: ANTHROPIC_API_KEY in environment.

Run with: uv run pytest -m integration -v
"""
import os

import pytest
from anthropic import Anthropic

from simbi_mcp.mockup.generator import generate_mockup
from simbi_mcp.types import (
    ModelMeasure,
    ModelSchema,
    ModelTable,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def schema() -> ModelSchema:
    return ModelSchema(
        tables=[
            ModelTable(
                name="sales",
                columns=["Region", "Category", "OrderDate"],
            ),
        ],
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
            ModelMeasure(
                name="Avg Order Value",
                table="sales",
                expression="DIVIDE([Total Revenue], [Order Count])",
                return_type="currency",
            ),
        ],
        relationships=[],
    )


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
def test_generate_mockup_with_real_claude(schema: ModelSchema) -> None:
    client = Anthropic()
    html = generate_mockup(
        prompt="Show a sales performance dashboard with revenue by region and trend over time.",
        schema=schema,
        client=client,
    )

    assert "<html" in html
    assert "data-pbi=" in html
    assert "dashboard.css" in html

    assert "Total Revenue" in html or "Order Count" in html or "Avg Order Value" in html
