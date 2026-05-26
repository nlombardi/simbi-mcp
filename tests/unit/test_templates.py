"""Unit tests for PBIR visual JSON template builders."""
from __future__ import annotations

import pytest

from simbi_mcp.pbir.extractor import VisualNode
from simbi_mcp.pbir.templates import build_visual_json
from simbi_mcp.types import ModelColumn, ModelMeasure, ModelSchema, ModelTable

_VISUAL_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report"
    "/definition/visualContainer/2.3.0/schema.json"
)


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


def _card_node(**extra: str) -> VisualNode:
    attrs = {"data-pbi": "card", "data-pbi-measure": "Total Revenue", **extra}
    return VisualNode(x=24.0, y=24.0, width=400.0, height=104.0, attrs=attrs)


def test_card_visual_type(schema: ModelSchema) -> None:
    result = build_visual_json(_card_node(), z_order=0, schema=schema)
    assert result["visual"]["visualType"] == "card"


def test_card_has_measure_projection(schema: ModelSchema) -> None:
    result = build_visual_json(_card_node(), z_order=0, schema=schema)
    proj = result["visual"]["query"]["queryState"]["Values"]["projections"][0]
    assert proj["field"]["Measure"]["Property"] == "Total Revenue"
    assert proj["field"]["Measure"]["Expression"]["SourceRef"]["Entity"] == "sales"
    assert proj["queryRef"] == "sales.Total Revenue"
    assert proj["nativeQueryRef"] == "Total Revenue"


def test_card_position(schema: ModelSchema) -> None:
    result = build_visual_json(_card_node(), z_order=1000, schema=schema)
    pos = result["position"]
    assert pos["x"] == 24.0
    assert pos["y"] == 24.0
    assert pos["z"] == 1000
    assert pos["tabOrder"] == 1000
    assert pos["width"] == 400.0
    assert pos["height"] == 104.0


def test_card_schema_url(schema: ModelSchema) -> None:
    result = build_visual_json(_card_node(), z_order=0, schema=schema)
    assert result["$schema"] == _VISUAL_SCHEMA


def test_card_guid_is_20_chars(schema: ModelSchema) -> None:
    result = build_visual_json(_card_node(), z_order=0, schema=schema)
    assert len(result["name"]) == 20
    assert result["name"].isalnum()


def test_column_chart_category_and_y(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=120, width=1232, height=400,
        attrs={
            "data-pbi": "columnChart",
            "data-pbi-axis": "sales[Region]",
            "data-pbi-values": "Total Revenue",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    qs = result["visual"]["query"]["queryState"]
    assert result["visual"]["visualType"] == "columnChart"
    cat = qs["Category"]["projections"][0]
    assert cat["field"]["Column"]["Property"] == "Region"
    assert cat["field"]["Column"]["Expression"]["SourceRef"]["Entity"] == "sales"
    assert cat["active"] is True
    assert cat["queryRef"] == "sales.Region"
    y_proj = qs["Y"]["projections"][0]
    assert y_proj["field"]["Measure"]["Property"] == "Total Revenue"


def test_line_chart_without_series(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=0, width=800, height=400,
        attrs={
            "data-pbi": "lineChart",
            "data-pbi-axis": "sales[OrderDate]",
            "data-pbi-values": "Total Revenue",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    qs = result["visual"]["query"]["queryState"]
    assert "Category" in qs
    assert "Y" in qs
    assert "Series" not in qs


def test_line_chart_with_series(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=0, width=800, height=400,
        attrs={
            "data-pbi": "lineChart",
            "data-pbi-axis": "sales[OrderDate]",
            "data-pbi-values": "Total Revenue",
            "data-pbi-series": "sales[Region]",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    qs = result["visual"]["query"]["queryState"]
    assert "Series" in qs
    series_proj = qs["Series"]["projections"][0]
    assert series_proj["field"]["Column"]["Property"] == "Region"
    assert "active" not in series_proj


def test_slicer(schema: ModelSchema) -> None:
    node = VisualNode(
        x=856, y=24, width=400, height=104,
        attrs={"data-pbi": "slicer", "data-pbi-field": "sales[Region]"},
    )
    result = build_visual_json(node, z_order=2000, schema=schema)
    assert result["visual"]["visualType"] == "advancedSlicerVisual"
    values_proj = result["visual"]["query"]["queryState"]["Values"]["projections"][0]
    assert values_proj["field"]["Column"]["Property"] == "Region"
    assert values_proj["queryRef"] == "sales.Region"
    # objects.general is required by PBI Desktop to render the advanced slicer
    assert result["visual"]["objects"] == {"general": [{"properties": {}}]}
    # filterConfig wires up cross-filtering
    fc = result["filterConfig"]["filters"][0]
    assert fc["type"] == "Categorical"
    assert fc["field"]["Column"]["Property"] == "Region"


def test_table_visual_type_is_tableEx(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=0, width=1280, height=200,
        attrs={"data-pbi": "table", "data-pbi-columns": "Total Revenue,Order Count"},
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    assert result["visual"]["visualType"] == "tableEx"
    projections = result["visual"]["query"]["queryState"]["Values"]["projections"]
    assert len(projections) == 2
    assert projections[0]["nativeQueryRef"] == "Total Revenue"
    assert projections[1]["nativeQueryRef"] == "Order Count"


def test_table_visual_mixes_columns_and_measures(schema: ModelSchema) -> None:
    """Each token is independently compiled — column refs go to Column proj,
    bare names go to Measure proj. Ordering is preserved."""
    node = VisualNode(
        x=0, y=0, width=1280, height=200,
        attrs={
            "data-pbi": "table",
            "data-pbi-columns": "sales[Region],Total Revenue,sales[OrderDate],Order Count",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    projections = result["visual"]["query"]["queryState"]["Values"]["projections"]
    assert len(projections) == 4

    assert "Column" in projections[0]["field"]
    assert projections[0]["field"]["Column"]["Property"] == "Region"
    assert projections[0]["queryRef"] == "sales.Region"

    assert "Measure" in projections[1]["field"]
    assert projections[1]["field"]["Measure"]["Property"] == "Total Revenue"

    assert "Column" in projections[2]["field"]
    assert projections[2]["field"]["Column"]["Property"] == "OrderDate"

    assert "Measure" in projections[3]["field"]
    assert projections[3]["field"]["Measure"]["Property"] == "Order Count"


def test_drill_filter_always_true(schema: ModelSchema) -> None:
    result = build_visual_json(_card_node(), z_order=0, schema=schema)
    assert result["visual"]["drillFilterOtherVisuals"] is True


def test_unknown_measure_raises(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=0, width=400, height=104,
        attrs={"data-pbi": "card", "data-pbi-measure": "No Such Measure"},
    )
    with pytest.raises(KeyError, match="No Such Measure"):
        build_visual_json(node, z_order=0, schema=schema)


def test_invalid_column_ref_raises(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=120, width=1232, height=400,
        attrs={
            "data-pbi": "columnChart",
            "data-pbi-axis": "NotAValidRef",
            "data-pbi-values": "Total Revenue",
        },
    )
    with pytest.raises(ValueError, match="Invalid column reference"):
        build_visual_json(node, z_order=0, schema=schema)


def test_clustered_column_chart(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=0, width=800, height=400,
        attrs={
            "data-pbi": "clusteredColumnChart",
            "data-pbi-axis": "sales[OrderDate]",
            "data-pbi-values": "Total Revenue",
            "data-pbi-series": "sales[Region]",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    assert result["visual"]["visualType"] == "clusteredColumnChart"
    qs = result["visual"]["query"]["queryState"]
    assert "Category" in qs
    assert qs["Category"]["projections"][0]["field"]["Column"]["Property"] == "OrderDate"
    assert "Y" in qs
    assert qs["Y"]["projections"][0]["field"]["Measure"]["Property"] == "Total Revenue"
    assert "Series" in qs
    assert qs["Series"]["projections"][0]["field"]["Column"]["Property"] == "Region"


def test_column_chart_with_series(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=0, width=800, height=400,
        attrs={
            "data-pbi": "columnChart",
            "data-pbi-axis": "sales[OrderDate]",
            "data-pbi-values": "Total Revenue",
            "data-pbi-series": "sales[Region]",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    assert result["visual"]["visualType"] == "columnChart"
    qs = result["visual"]["query"]["queryState"]
    assert "Series" in qs
    assert qs["Series"]["projections"][0]["field"]["Column"]["Property"] == "Region"


def test_clustered_bar_chart(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=0, width=800, height=400,
        attrs={
            "data-pbi": "clusteredBarChart",
            "data-pbi-axis": "sales[OrderDate]",
            "data-pbi-values": "Total Revenue",
            "data-pbi-series": "sales[Region]",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    assert result["visual"]["visualType"] == "clusteredBarChart"
    qs = result["visual"]["query"]["queryState"]
    assert "Category" in qs
    assert qs["Category"]["projections"][0]["field"]["Column"]["Property"] == "OrderDate"
    assert "Y" in qs
    assert qs["Y"]["projections"][0]["field"]["Measure"]["Property"] == "Total Revenue"
    assert "Series" in qs
    assert qs["Series"]["projections"][0]["field"]["Column"]["Property"] == "Region"


def test_bar_chart_with_series(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=0, width=800, height=400,
        attrs={
            "data-pbi": "barChart",
            "data-pbi-axis": "sales[OrderDate]",
            "data-pbi-values": "Total Revenue",
            "data-pbi-series": "sales[Region]",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    assert result["visual"]["visualType"] == "barChart"
    qs = result["visual"]["query"]["queryState"]
    assert "Series" in qs
    assert qs["Series"]["projections"][0]["field"]["Column"]["Property"] == "Region"


def test_hundred_percent_stacked_bar_chart(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=0, width=800, height=400,
        attrs={
            "data-pbi": "hundredPercentStackedBarChart",
            "data-pbi-axis": "sales[OrderDate]",
            "data-pbi-values": "Total Revenue",
            "data-pbi-series": "sales[Region]",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    assert result["visual"]["visualType"] == "hundredPercentStackedBarChart"
    qs = result["visual"]["query"]["queryState"]
    assert "Category" in qs
    assert "Y" in qs
    assert "Series" in qs


def test_hundred_percent_stacked_column_chart(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=0, width=800, height=400,
        attrs={
            "data-pbi": "hundredPercentStackedColumnChart",
            "data-pbi-axis": "sales[OrderDate]",
            "data-pbi-values": "Total Revenue",
            "data-pbi-series": "sales[Region]",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    assert result["visual"]["visualType"] == "hundredPercentStackedColumnChart"
    qs = result["visual"]["query"]["queryState"]
    assert "Category" in qs
    assert "Y" in qs
    assert "Series" in qs


def test_area_chart_without_series(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=0, width=800, height=400,
        attrs={
            "data-pbi": "areaChart",
            "data-pbi-axis": "sales[OrderDate]",
            "data-pbi-values": "Total Revenue",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    assert result["visual"]["visualType"] == "areaChart"
    qs = result["visual"]["query"]["queryState"]
    assert "Category" in qs
    assert "Y" in qs
    assert "Series" not in qs


def test_area_chart_with_series(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=0, width=800, height=400,
        attrs={
            "data-pbi": "areaChart",
            "data-pbi-axis": "sales[OrderDate]",
            "data-pbi-values": "Total Revenue",
            "data-pbi-series": "sales[Region]",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    assert result["visual"]["visualType"] == "areaChart"
    qs = result["visual"]["query"]["queryState"]
    assert "Category" in qs
    assert "Y" in qs
    assert "Series" in qs


def test_pie_chart(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=0, width=400, height=400,
        attrs={
            "data-pbi": "pieChart",
            "data-pbi-axis": "sales[Region]",
            "data-pbi-values": "Total Revenue",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    assert result["visual"]["visualType"] == "pieChart"
    qs = result["visual"]["query"]["queryState"]
    assert "Category" in qs
    assert qs["Category"]["projections"][0]["field"]["Column"]["Property"] == "Region"
    assert "Y" in qs
    assert qs["Y"]["projections"][0]["field"]["Measure"]["Property"] == "Total Revenue"


def test_donut_chart(schema: ModelSchema) -> None:
    node = VisualNode(
        x=0, y=0, width=400, height=400,
        attrs={
            "data-pbi": "donutChart",
            "data-pbi-axis": "sales[Region]",
            "data-pbi-values": "Total Revenue",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    assert result["visual"]["visualType"] == "donutChart"
    qs = result["visual"]["query"]["queryState"]
    assert "Category" in qs
    assert qs["Category"]["projections"][0]["field"]["Column"]["Property"] == "Region"
    assert "Y" in qs
    assert qs["Y"]["projections"][0]["field"]["Measure"]["Property"] == "Total Revenue"


# ---------- Pass-2 visuals (KPI, Multi-row Card, Gauge, Dot Plot, Combo,
# Treemap, Funnel, Histogram, Scatter, Bubble, Waterfall, Ribbon, Map,
# Filled Map, Shape Map) ----------


@pytest.fixture
def rich_schema() -> ModelSchema:
    """Schema with the extra columns/measures needed by Pass-2 visual tests."""
    return ModelSchema(
        tables=[
            ModelTable(
                name="sales",
                columns=[
                    ModelColumn(name="Region"),
                    ModelColumn(name="OrderDate"),
                    ModelColumn(name="Stage"),
                    ModelColumn(name="Market"),
                    ModelColumn(name="Driver"),
                    ModelColumn(name="Category"),
                    ModelColumn(name="City"),
                    ModelColumn(name="Country"),
                    ModelColumn(name="Territory"),
                ],
            )
        ],
        measures=[
            ModelMeasure(name="Total Revenue", table="sales", expression="SUM(sales[Revenue])", return_type="currency"),
            ModelMeasure(name="Order Count", table="sales", expression="COUNTROWS(sales)", return_type="integer"),
            ModelMeasure(name="Revenue Target", table="sales", expression="1000000", return_type="currency"),
            ModelMeasure(name="Gross Margin", table="sales", expression="0.4", return_type="percentage"),
            ModelMeasure(name="Lead Count", table="sales", expression="COUNTROWS(sales)", return_type="integer"),
            ModelMeasure(name="Ad Spend", table="sales", expression="SUM(sales[Spend])", return_type="currency"),
            ModelMeasure(name="Variance", table="sales", expression="0", return_type="currency"),
            ModelMeasure(name="Order Value", table="sales", expression="AVERAGE(sales[Revenue])", return_type="currency"),
        ],
        relationships=[],
    )


def _node(vtype: str, **attrs: str) -> VisualNode:
    return VisualNode(
        x=0, y=0, width=400, height=300,
        attrs={"data-pbi": vtype, **attrs},
    )


def test_multi_row_card_emits_projection_per_measure(rich_schema: ModelSchema) -> None:
    node = _node("multiRowCard", **{"data-pbi-measures": "Total Revenue,Order Count"})
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    assert result["visual"]["visualType"] == "multiRowCard"
    projs = result["visual"]["query"]["queryState"]["Values"]["projections"]
    assert [p["field"]["Measure"]["Property"] for p in projs] == ["Total Revenue", "Order Count"]


def test_kpi_emits_indicator_trend_and_goal(rich_schema: ModelSchema) -> None:
    node = _node(
        "kpi",
        **{
            "data-pbi-measure": "Total Revenue",
            "data-pbi-target": "Revenue Target",
            "data-pbi-trend": "sales[OrderDate]",
        },
    )
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    assert result["visual"]["visualType"] == "kpi"
    qs = result["visual"]["query"]["queryState"]
    assert qs["Indicator"]["projections"][0]["field"]["Measure"]["Property"] == "Total Revenue"
    assert qs["TrendLine"]["projections"][0]["field"]["Column"]["Property"] == "OrderDate"
    assert qs["Goals"]["projections"][0]["field"]["Measure"]["Property"] == "Revenue Target"


def test_gauge_minimum_required_attrs(rich_schema: ModelSchema) -> None:
    node = _node("gauge", **{"data-pbi-measure": "Total Revenue"})
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    qs = result["visual"]["query"]["queryState"]
    assert "Y" in qs
    assert "MinValue" not in qs and "MaxValue" not in qs and "TargetValue" not in qs


def test_gauge_with_optional_target_and_max(rich_schema: ModelSchema) -> None:
    node = _node(
        "gauge",
        **{
            "data-pbi-measure": "Total Revenue",
            "data-pbi-max": "Revenue Target",
            "data-pbi-target": "Revenue Target",
        },
    )
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    qs = result["visual"]["query"]["queryState"]
    assert qs["MaxValue"]["projections"][0]["field"]["Measure"]["Property"] == "Revenue Target"
    assert qs["TargetValue"]["projections"][0]["field"]["Measure"]["Property"] == "Revenue Target"


def test_dot_plot(rich_schema: ModelSchema) -> None:
    node = _node("dotPlot", **{"data-pbi-axis": "sales[Region]", "data-pbi-values": "Total Revenue"})
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    assert result["visual"]["visualType"] == "dotPlot"
    qs = result["visual"]["query"]["queryState"]
    assert qs["Category"]["projections"][0]["field"]["Column"]["Property"] == "Region"
    assert qs["X"]["projections"][0]["field"]["Measure"]["Property"] == "Total Revenue"


def test_combo_chart_dual_measures(rich_schema: ModelSchema) -> None:
    node = _node(
        "comboChart",
        **{
            "data-pbi-axis": "sales[OrderDate]",
            "data-pbi-column-values": "Total Revenue",
            "data-pbi-line-values": "Gross Margin",
        },
    )
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    assert result["visual"]["visualType"] == "lineClusteredColumnComboChart"
    qs = result["visual"]["query"]["queryState"]
    assert qs["Y"]["projections"][0]["field"]["Measure"]["Property"] == "Total Revenue"
    assert qs["Y2"]["projections"][0]["field"]["Measure"]["Property"] == "Gross Margin"


def test_treemap_with_details(rich_schema: ModelSchema) -> None:
    node = _node(
        "treemap",
        **{
            "data-pbi-group": "sales[Region]",
            "data-pbi-values": "Total Revenue",
            "data-pbi-details": "sales[Category]",
        },
    )
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    assert result["visual"]["visualType"] == "treemap"
    qs = result["visual"]["query"]["queryState"]
    assert qs["Group"]["projections"][0]["field"]["Column"]["Property"] == "Region"
    assert qs["Details"]["projections"][0]["field"]["Column"]["Property"] == "Category"
    assert qs["Values"]["projections"][0]["field"]["Measure"]["Property"] == "Total Revenue"


def test_funnel_chart(rich_schema: ModelSchema) -> None:
    node = _node("funnelChart", **{"data-pbi-axis": "sales[Stage]", "data-pbi-values": "Lead Count"})
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    # Annotation token is "funnelChart" but PBIR visualType is "funnel"
    assert result["visual"]["visualType"] == "funnel"


def test_histogram_default(rich_schema: ModelSchema) -> None:
    node = _node("histogram", **{"data-pbi-values": "Order Value"})
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    assert result["visual"]["visualType"] == "barChart"
    assert "objects" not in result["visual"] or "categoryAxis" not in result["visual"].get("objects", {})


def test_histogram_with_bins(rich_schema: ModelSchema) -> None:
    node = _node("histogram", **{"data-pbi-values": "Order Value", "data-pbi-bins": "20"})
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    assert result["visual"]["visualType"] == "barChart"
    assert result["visual"]["objects"]["categoryAxis"][0]["properties"]["binCount"]


def test_histogram_invalid_bins_raises(rich_schema: ModelSchema) -> None:
    node = _node("histogram", **{"data-pbi-values": "Order Value", "data-pbi-bins": "not-an-int"})
    with pytest.raises(ValueError, match="data-pbi-bins"):
        build_visual_json(node, z_order=0, schema=rich_schema)


def test_scatter_chart(rich_schema: ModelSchema) -> None:
    node = _node(
        "scatterChart",
        **{"data-pbi-x": "Ad Spend", "data-pbi-y": "Total Revenue", "data-pbi-details": "sales[Market]"},
    )
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    assert result["visual"]["visualType"] == "scatterChart"
    qs = result["visual"]["query"]["queryState"]
    assert qs["X"]["projections"][0]["field"]["Measure"]["Property"] == "Ad Spend"
    assert qs["Y"]["projections"][0]["field"]["Measure"]["Property"] == "Total Revenue"
    assert qs["Details"]["projections"][0]["field"]["Column"]["Property"] == "Market"
    assert "Size" not in qs


def test_bubble_chart_adds_size(rich_schema: ModelSchema) -> None:
    node = _node(
        "bubbleChart",
        **{
            "data-pbi-x": "Ad Spend",
            "data-pbi-y": "Total Revenue",
            "data-pbi-size": "Order Count",
        },
    )
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    # Catalog-confirmed: bubble shares the scatterChart PBIR visualType
    assert result["visual"]["visualType"] == "scatterChart"
    qs = result["visual"]["query"]["queryState"]
    assert qs["Size"]["projections"][0]["field"]["Measure"]["Property"] == "Order Count"


def test_waterfall_with_breakdown(rich_schema: ModelSchema) -> None:
    node = _node(
        "waterfallChart",
        **{
            "data-pbi-axis": "sales[Driver]",
            "data-pbi-values": "Variance",
            "data-pbi-breakdown": "sales[Category]",
        },
    )
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    assert result["visual"]["visualType"] == "waterfallChart"
    qs = result["visual"]["query"]["queryState"]
    assert qs["Breakdown"]["projections"][0]["field"]["Column"]["Property"] == "Category"


def test_ribbon_chart(rich_schema: ModelSchema) -> None:
    node = _node(
        "ribbonChart",
        **{
            "data-pbi-axis": "sales[OrderDate]",
            "data-pbi-values": "Total Revenue",
            "data-pbi-series": "sales[Category]",
        },
    )
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    assert result["visual"]["visualType"] == "ribbonChart"
    qs = result["visual"]["query"]["queryState"]
    assert qs["Series"]["projections"][0]["field"]["Column"]["Property"] == "Category"


def test_map_with_legend(rich_schema: ModelSchema) -> None:
    node = _node(
        "map",
        **{
            "data-pbi-location": "sales[City]",
            "data-pbi-size": "Total Revenue",
            "data-pbi-legend": "sales[Category]",
        },
    )
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    assert result["visual"]["visualType"] == "map"
    qs = result["visual"]["query"]["queryState"]
    assert qs["Location"]["projections"][0]["field"]["Column"]["Property"] == "City"
    assert qs["Size"]["projections"][0]["field"]["Measure"]["Property"] == "Total Revenue"
    assert qs["Legend"]["projections"][0]["field"]["Column"]["Property"] == "Category"


def test_filled_map(rich_schema: ModelSchema) -> None:
    node = _node(
        "filledMap",
        **{"data-pbi-location": "sales[Country]", "data-pbi-color-saturation": "Total Revenue"},
    )
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    assert result["visual"]["visualType"] == "filledMap"
    qs = result["visual"]["query"]["queryState"]
    assert qs["Color saturation"]["projections"][0]["field"]["Measure"]["Property"] == "Total Revenue"


def test_shape_map_with_topojson(rich_schema: ModelSchema) -> None:
    node = _node(
        "shapeMap",
        **{
            "data-pbi-location": "sales[Territory]",
            "data-pbi-color-saturation": "Total Revenue",
            "data-pbi-topojson": "C:/maps/territories.json",
        },
    )
    result = build_visual_json(node, z_order=0, schema=rich_schema)
    assert result["visual"]["visualType"] == "shapeMap"
    assert "mapShape" in result["visual"]["objects"]
