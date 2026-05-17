"""Unit tests for SimBI MCP server tools and resources — no API keys, no browser required."""
from __future__ import annotations

import json

from simbi_mcp.server import mcp
from simbi_mcp.types import ModelSchema

_SALES_TMDL = (
    "table sales\n"
    "\tmeasure 'Total Revenue' = SUM(sales[Revenue])\n"
    "\t\tformatString: \\$#,0.00\n"
    "\tmeasure 'Order Count' = COUNTROWS(sales)\n"
    "\t\tformatString: #,0\n"
    "\tcolumn Region\n"
    "\t\tdataType: String\n"
    "\tcolumn OrderDate\n"
    "\t\tdataType: DateTime\n"
)


async def test_parse_schema_returns_measures() -> None:
    _, result = await mcp.call_tool("parse_schema", {"tmdl": _SALES_TMDL})
    data = json.loads(result["result"])
    measure_names = [m["name"] for m in data["measures"]]
    assert "Total Revenue" in measure_names
    assert "Order Count" in measure_names


async def test_parse_schema_returns_table_columns() -> None:
    _, result = await mcp.call_tool("parse_schema", {"tmdl": _SALES_TMDL})
    data = json.loads(result["result"])
    table = next(t for t in data["tables"] if t["name"] == "sales")
    assert "Region" in table["columns"]
    assert "OrderDate" in table["columns"]


async def test_parse_schema_result_roundtrips_to_model_schema() -> None:
    _, result = await mcp.call_tool("parse_schema", {"tmdl": _SALES_TMDL})
    schema = ModelSchema.model_validate_json(result["result"])
    assert len(schema.measures) == 2
    assert schema.has_measure("Total Revenue")


async def test_annotation_vocabulary_resource_is_readable() -> None:
    results = list(await mcp.read_resource("simbi://annotation-vocabulary"))
    assert results, "resource returned no content"
    text = "".join(r.content for r in results)
    assert "data-pbi" in text
    assert "ANNOTATION VOCABULARY" in text


async def test_annotation_vocabulary_contains_all_visual_types() -> None:
    results = list(await mcp.read_resource("simbi://annotation-vocabulary"))
    text = "".join(r.content for r in results)
    for visual_type in ("card", "columnChart", "lineChart", "slicer", "table"):
        assert visual_type in text, f"Missing visual type: {visual_type}"


async def test_annotation_vocabulary_contains_css_catalog() -> None:
    results = list(await mcp.read_resource("simbi://annotation-vocabulary"))
    text = "".join(r.content for r in results)
    assert "AVAILABLE CSS CLASSES" in text
    assert "db-grid" in text


def test_mcp_server_name() -> None:
    assert mcp.name == "SimBI"


def test_main_is_importable_from_package() -> None:
    from simbi_mcp import main
    from simbi_mcp.server import main as server_main
    assert main is server_main
