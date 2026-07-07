"""Tests for the HTML annotation validator."""
from pathlib import Path

import pytest

from simbi_mcp.mockup.validator import ValidationError, validate_mockup
from simbi_mcp.types import (
    ModelColumn,
    ModelMeasure,
    ModelRelationship,
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


# ---------- Cross-table axis/series relationship guardrail ----------


def _xtable_schema(relationships: list[ModelRelationship]) -> ModelSchema:
    return ModelSchema(
        tables=[
            ModelTable(name="Fact", columns=[ModelColumn(name="Year"), ModelColumn(name="Country")]),
            ModelTable(name="DimYear", columns=[ModelColumn(name="Year")]),
        ],
        measures=[ModelMeasure(name="Rev", table="Fact", expression="SUM(Fact[V])", return_type="number")],
        relationships=relationships,
    )


def test_cross_table_axis_series_no_relationship_is_fatal() -> None:
    schema = _xtable_schema([])  # no relationships
    html = ('<div data-pbi="clusteredColumnChart" data-pbi-axis="DimYear[Year]" '
            'data-pbi-values="Rev" data-pbi-series="Fact[Country]"></div>')
    with pytest.raises(ValidationError, match="no.*relationship|relationship connects"):
        validate_mockup(html, schema)


def test_cross_table_axis_series_with_relationship_warns() -> None:
    schema = _xtable_schema([ModelRelationship(from_table="Fact", from_column="Year", to_table="DimYear", to_column="Year")])
    html = ('<div data-pbi="clusteredColumnChart" data-pbi-axis="DimYear[Year]" '
            'data-pbi-values="Rev" data-pbi-series="Fact[Country]"></div>')
    warnings = validate_mockup(html, schema)
    assert any("different tables" in w for w in warnings)


def test_same_table_axis_series_no_warning() -> None:
    schema = _xtable_schema([])
    html = ('<div data-pbi="clusteredColumnChart" data-pbi-axis="Fact[Year]" '
            'data-pbi-values="Rev" data-pbi-series="Fact[Country]"></div>')
    warnings = validate_mockup(html, schema)
    assert warnings == []


def test_clean_mockup_returns_empty_warnings() -> None:
    schema = _xtable_schema([])
    html = '<div data-pbi="card" data-pbi-measure="Rev"></div>'
    assert validate_mockup(html, schema) == []


def test_unknown_attr_is_hard_error_with_suggestion(schema) -> None:
    html = '<div data-pbi="shape" data-pbi-fil="#ff0000" style="width:10px;height:10px"></div>'
    with pytest.raises(ValidationError, match="data-pbi-fill"):
        validate_mockup(html, schema)


def test_unknown_attr_error_lists_valid_attrs(schema) -> None:
    html = '<div data-pbi="card" data-pbi-measure="Total Revenue" data-pbi-nonsense="x"></div>'
    with pytest.raises(ValidationError, match="data-pbi-measure"):
        validate_mockup(html, schema)


def test_universal_attrs_accepted_on_every_type(schema) -> None:
    html = (
        '<div data-pbi="card" data-pbi-measure="Total Revenue" '
        'data-pbi-id="kpi1" data-pbi-hidden="true"></div>'
    )
    assert validate_mockup(html, schema) == []


def test_non_data_pbi_attrs_ignored(schema) -> None:
    html = (
        '<div class="db-card" id="x" style="color:red" '
        'data-pbi="card" data-pbi-measure="Total Revenue"></div>'
    )
    validate_mockup(html, schema)  # must not raise


# ---------- Cross-reference checks (bookmarks and buttons) ----------


def test_bookmark_unknown_visual_id_is_error(schema) -> None:
    html = (
        '<div data-pbi="lineChart" data-pbi-id="chartLine" '
        'data-pbi-axis="sales[OrderDate]" data-pbi-values="Total Revenue"></div>'
        '<div data-pbi="bookmark" data-pbi-name="View: Bar" '
        'data-pbi-visible="chartBar" data-pbi-hidden="chartLine"></div>'
    )
    with pytest.raises(ValidationError, match="chartBar"):
        validate_mockup(html, schema)


def test_bookmark_known_ids_pass(schema) -> None:
    html = (
        '<div data-pbi="lineChart" data-pbi-id="chartLine" '
        'data-pbi-axis="sales[OrderDate]" data-pbi-values="Total Revenue"></div>'
        '<div data-pbi="barChart" data-pbi-id="chartBar" data-pbi-hidden="true" '
        'data-pbi-axis="sales[Region]" data-pbi-values="Total Revenue"></div>'
        '<div data-pbi="bookmark" data-pbi-name="View: Bar" data-pbi-captures="visibility" '
        'data-pbi-visible="chartBar" data-pbi-hidden="chartLine"></div>'
    )
    validate_mockup(html, schema)  # must not raise


def test_bookmark_target_all_is_skipped(schema) -> None:
    html = (
        '<div data-pbi="card" data-pbi-measure="Total Revenue"></div>'
        '<div data-pbi="bookmark" data-pbi-name="B" data-pbi-target="all"></div>'
    )
    validate_mockup(html, schema)  # must not raise


def test_duplicate_visual_id_is_error(schema) -> None:
    html = (
        '<div data-pbi="card" data-pbi-id="dup" data-pbi-measure="Total Revenue"></div>'
        '<div data-pbi="card" data-pbi-id="dup" data-pbi-measure="Order Count"></div>'
    )
    with pytest.raises(ValidationError, match="dup"):
        validate_mockup(html, schema)


def test_button_unknown_bookmark_is_error(schema) -> None:
    html = (
        '<div data-pbi="bookmark" data-pbi-name="View: Bar"></div>'
        '<div data-pbi="button" data-pbi-action="bookmark" data-pbi-bookmark="View: Line"></div>'
    )
    with pytest.raises(ValidationError, match="View: Bar"):
        validate_mockup(html, schema)


def test_button_bookmark_action_requires_bookmark_attr(schema) -> None:
    html = '<div data-pbi="button" data-pbi-action="bookmark"></div>'
    with pytest.raises(ValidationError, match="data-pbi-bookmark"):
        validate_mockup(html, schema)


# ---------- Bar chart time-axis heuristic warning ----------


def _schema_with_year() -> ModelSchema:
    return ModelSchema(
        tables=[ModelTable(name="gdp", columns=[
            ModelColumn(name="Year", data_type="int64"),
            ModelColumn(name="Country"),
            ModelColumn(name="AsOf", data_type="dateTime"),
        ])],
        measures=[ModelMeasure(name="GDP", table="gdp", expression="SUM(gdp[Value])", return_type="number")],
        relationships=[],
    )


def test_barchart_year_axis_warns() -> None:
    html = '<div data-pbi="barChart" data-pbi-axis="gdp[Year]" data-pbi-values="GDP"></div>'
    warnings = validate_mockup(html, _schema_with_year())
    assert any("HORIZONTAL" in w and "columnChart" in w for w in warnings)


def test_barchart_datetime_axis_warns() -> None:
    html = '<div data-pbi="barChart" data-pbi-axis="gdp[AsOf]" data-pbi-values="GDP"></div>'
    warnings = validate_mockup(html, _schema_with_year())
    assert any("columnChart" in w for w in warnings)


def test_barchart_category_axis_does_not_warn() -> None:
    html = '<div data-pbi="barChart" data-pbi-axis="gdp[Country]" data-pbi-values="GDP"></div>'
    assert validate_mockup(html, _schema_with_year()) == []


def test_columnchart_year_axis_does_not_warn() -> None:
    html = '<div data-pbi="columnChart" data-pbi-axis="gdp[Year]" data-pbi-values="GDP"></div>'
    assert validate_mockup(html, _schema_with_year()) == []


# ---------- Inline style warnings ----------


def test_inline_color_warns(schema) -> None:
    html = (
        '<div data-pbi="card" data-pbi-measure="Total Revenue" '
        'style="color: red; background-color: #fff"></div>'
    )
    warnings = validate_mockup(html, schema)
    assert any("'color'" in w and "does not transfer" in w for w in warnings)
    assert not any("background-color" in w for w in warnings)  # honored, no warning


def test_inline_gradient_warns(schema) -> None:
    html = (
        '<div data-pbi="card" data-pbi-measure="Total Revenue" '
        'style="background: linear-gradient(#fff, #000)"></div>'
    )
    warnings = validate_mockup(html, schema)
    assert any("gradient" in w for w in warnings)


def test_inline_layout_props_do_not_warn(schema) -> None:
    html = (
        '<div data-pbi="card" data-pbi-measure="Total Revenue" '
        'style="position:absolute; left:10px; top:10px; width:200px; height:100px"></div>'
    )
    assert validate_mockup(html, schema) == []
