"""Tests for the HTML annotation validator."""
from pathlib import Path

import pytest

from simbi_mcp.mockup.validator import ValidationError, validate_mockup
from simbi_mcp.types import (
    ModelMeasure,
    ModelSchema,
    ModelTable,
)


@pytest.fixture
def schema() -> ModelSchema:
    return ModelSchema(
        tables=[
            ModelTable(name="sales", columns=["Region", "OrderDate", "Revenue"]),
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
        ],
        relationships=[],
    )


@pytest.fixture
def fixtures_html() -> Path:
    return Path(__file__).parent.parent / "fixtures" / "html"


def test_valid_dashboard_passes(schema: ModelSchema, fixtures_html: Path) -> None:
    html = (fixtures_html / "valid_dashboard.html").read_text()
    validate_mockup(html, schema)  # must not raise


def test_invalid_measures_raises(schema: ModelSchema, fixtures_html: Path) -> None:
    html = (fixtures_html / "invalid_measures.html").read_text()
    with pytest.raises(ValidationError, match="Hallucinated KPI"):
        validate_mockup(html, schema)


def test_unknown_visual_type_raises(schema: ModelSchema) -> None:
    html = '<div data-pbi="pieChart" data-pbi-measure="Total Revenue"></div>'
    with pytest.raises(ValidationError, match="Unknown visual type"):
        validate_mockup(html, schema)


def test_missing_required_attribute_raises(schema: ModelSchema) -> None:
    # card missing data-pbi-measure
    html = '<div data-pbi="card"></div>'
    with pytest.raises(ValidationError, match="data-pbi-measure"):
        validate_mockup(html, schema)


def test_unknown_column_in_axis_raises(schema: ModelSchema) -> None:
    html = (
        '<div data-pbi="columnChart" '
        'data-pbi-axis="sales[FakeColumn]" '
        'data-pbi-values="Total Revenue"></div>'
    )
    with pytest.raises(ValidationError, match="FakeColumn"):
        validate_mockup(html, schema)


def test_unknown_table_in_axis_raises(schema: ModelSchema) -> None:
    html = (
        '<div data-pbi="columnChart" '
        'data-pbi-axis="FakeTable[Region]" '
        'data-pbi-values="Total Revenue"></div>'
    )
    with pytest.raises(ValidationError, match="FakeTable"):
        validate_mockup(html, schema)


def test_column_ref_wrong_format_raises(schema: ModelSchema) -> None:
    # Must be Table[Column], not just Column
    html = (
        '<div data-pbi="slicer" '
        'data-pbi-field="Region"></div>'
    )
    with pytest.raises(ValidationError, match="Table\\[Column\\]"):
        validate_mockup(html, schema)


def test_empty_html_raises(schema: ModelSchema) -> None:
    with pytest.raises(ValidationError, match="no data-pbi"):
        validate_mockup("<html><body></body></html>", schema)


def test_table_visual_validates_each_column(schema: ModelSchema) -> None:
    html = (
        '<div data-pbi="table" '
        'data-pbi-columns="Total Revenue,HallucinatedMeasure"></div>'
    )
    with pytest.raises(ValidationError, match="HallucinatedMeasure"):
        validate_mockup(html, schema)
