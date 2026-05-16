"""Unit tests for PBIR visual JSON template builders."""
from __future__ import annotations

import pytest

from simbi_mcp.pbir.extractor import VisualNode
from simbi_mcp.pbir.templates import build_visual_json
from simbi_mcp.types import ModelMeasure, ModelSchema, ModelTable

_VISUAL_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report"
    "/definition/visualContainer/2.3.0/schema.json"
)


@pytest.fixture
def schema() -> ModelSchema:
    return ModelSchema(
        tables=[ModelTable(name="sales", columns=["Region", "OrderDate"])],
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
    assert result["visual"]["visualType"] == "slicer"
    field_proj = result["visual"]["query"]["queryState"]["Field"]["projections"][0]
    assert field_proj["field"]["Column"]["Property"] == "Region"
    assert field_proj["active"] is True
    assert field_proj["queryRef"] == "sales.Region"


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


def test_drill_filter_always_true(schema: ModelSchema) -> None:
    result = build_visual_json(_card_node(), z_order=0, schema=schema)
    assert result["visual"]["drillFilterOtherVisuals"] is True
