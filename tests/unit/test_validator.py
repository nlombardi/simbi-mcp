"""Tests for the HTML annotation validator."""
from pathlib import Path

import pytest

from simbi_mcp.mockup.validator import ValidationError, validate_mockup
from simbi_mcp.types import (
    ModelColumn,
    ModelMeasure,
    ModelSchema,
    ModelTable,
)


@pytest.fixture
def schema() -> ModelSchema:
    return ModelSchema(
        tables=[
            ModelTable(name="sales", columns=[ModelColumn(name="Region"), ModelColumn(name="OrderDate"), ModelColumn(name="Revenue")]),
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
    with pytest.raises(ValidationError, match="does not exist in the schema"):
        validate_mockup(html, schema)


def test_unknown_visual_type_raises(schema: ModelSchema) -> None:
    # decompositionTree is permanently out-of-scope (AI service-only per roadmap),
    # so it stays a safe "definitely unknown" placeholder.
    html = '<div data-pbi="decompositionTree" data-pbi-measure="Total Revenue"></div>'
    with pytest.raises(ValidationError, match="Unknown data-pbi value"):
        validate_mockup(html, schema)


def test_clustered_and_stacked_column_charts_pass(schema: ModelSchema) -> None:
    html_clustered = (
        '<div data-pbi="clusteredColumnChart" '
        'data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue" '
        'data-pbi-series="sales[OrderDate]"></div>'
    )
    validate_mockup(html_clustered, schema)  # must not raise

    html_stacked = (
        '<div data-pbi="columnChart" '
        'data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue" '
        'data-pbi-series="sales[OrderDate]"></div>'
    )
    validate_mockup(html_stacked, schema)  # must not raise

    html_clustered_bar = (
        '<div data-pbi="clusteredBarChart" '
        'data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue" '
        'data-pbi-series="sales[OrderDate]"></div>'
    )
    validate_mockup(html_clustered_bar, schema)  # must not raise

    html_stacked_bar = (
        '<div data-pbi="barChart" '
        'data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue" '
        'data-pbi-series="sales[OrderDate]"></div>'
    )
    validate_mockup(html_stacked_bar, schema)  # must not raise

    html_hundred_percent_stacked_column = (
        '<div data-pbi="hundredPercentStackedColumnChart" '
        'data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue" '
        'data-pbi-series="sales[OrderDate]"></div>'
    )
    validate_mockup(html_hundred_percent_stacked_column, schema)  # must not raise

    html_hundred_percent_stacked_bar = (
        '<div data-pbi="hundredPercentStackedBarChart" '
        'data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue" '
        'data-pbi-series="sales[OrderDate]"></div>'
    )
    validate_mockup(html_hundred_percent_stacked_bar, schema)  # must not raise

    html_area = (
        '<div data-pbi="areaChart" '
        'data-pbi-axis="sales[OrderDate]" '
        'data-pbi-values="Total Revenue"></div>'
    )
    validate_mockup(html_area, schema)  # must not raise

    html_pie = (
        '<div data-pbi="pieChart" '
        'data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue"></div>'
    )
    validate_mockup(html_pie, schema)  # must not raise

    html_donut = (
        '<div data-pbi="donutChart" '
        'data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue"></div>'
    )
    validate_mockup(html_donut, schema)  # must not raise


def test_clustered_column_chart_missing_series_raises(schema: ModelSchema) -> None:
    html = (
        '<div data-pbi="clusteredColumnChart" '
        'data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue"></div>'
    )
    with pytest.raises(ValidationError, match="data-pbi-series"):
        validate_mockup(html, schema)


def test_missing_required_attribute_raises(schema: ModelSchema) -> None:
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
        'data-pbi-columns="HallucinatedMeasure,Total Revenue"></div>'
    )
    with pytest.raises(ValidationError, match="HallucinatedMeasure"):
        validate_mockup(html, schema)


def test_table_visual_accepts_mixed_columns_and_measures(schema: ModelSchema) -> None:
    """A table token may be EITHER a measure name OR a Table[Column] ref."""
    html = (
        '<div data-pbi="table" '
        'data-pbi-columns="sales[Region],Total Revenue,sales[OrderDate],Order Count"></div>'
    )
    validate_mockup(html, schema)  # must not raise


def test_table_visual_rejects_unknown_column_in_mixed_list(schema: ModelSchema) -> None:
    html = (
        '<div data-pbi="table" '
        'data-pbi-columns="sales[FakeColumn],Total Revenue"></div>'
    )
    with pytest.raises(ValidationError, match="FakeColumn"):
        validate_mockup(html, schema)


def test_table_visual_rejects_unknown_table_in_mixed_list(schema: ModelSchema) -> None:
    html = (
        '<div data-pbi="table" '
        'data-pbi-columns="FakeTable[Region],Total Revenue"></div>'
    )
    with pytest.raises(ValidationError, match="FakeTable"):
        validate_mockup(html, schema)


# ---------- Pass-2 visual validation ----------


def test_multi_row_card_accepts_known_measures(schema: ModelSchema) -> None:
    html = '<div data-pbi="multiRowCard" data-pbi-measures="Total Revenue, Order Count"></div>'
    validate_mockup(html, schema)


def test_multi_row_card_rejects_unknown_measure(schema: ModelSchema) -> None:
    html = '<div data-pbi="multiRowCard" data-pbi-measures="Total Revenue,GhostMeasure"></div>'
    with pytest.raises(ValidationError, match="GhostMeasure"):
        validate_mockup(html, schema)


def test_kpi_validates_target_measure_and_trend_column(schema: ModelSchema) -> None:
    html = (
        '<div data-pbi="kpi" data-pbi-measure="Total Revenue" '
        'data-pbi-target="GhostTarget" data-pbi-trend="sales[OrderDate]"></div>'
    )
    with pytest.raises(ValidationError, match="GhostTarget"):
        validate_mockup(html, schema)


def test_scatter_chart_rejects_unknown_x_measure(schema: ModelSchema) -> None:
    html = (
        '<div data-pbi="scatterChart" data-pbi-x="GhostMeasure" '
        'data-pbi-y="Total Revenue"></div>'
    )
    with pytest.raises(ValidationError, match="GhostMeasure"):
        validate_mockup(html, schema)


def test_treemap_with_optional_details_accepts(schema: ModelSchema) -> None:
    html = (
        '<div data-pbi="treemap" data-pbi-group="sales[Region]" '
        'data-pbi-values="Total Revenue" data-pbi-details="sales[OrderDate]"></div>'
    )
    validate_mockup(html, schema)


def test_filled_map_validates_color_saturation_measure(schema: ModelSchema) -> None:
    html = (
        '<div data-pbi="filledMap" data-pbi-location="sales[Region]" '
        'data-pbi-color-saturation="GhostMeasure"></div>'
    )
    with pytest.raises(ValidationError, match="GhostMeasure"):
        validate_mockup(html, schema)
