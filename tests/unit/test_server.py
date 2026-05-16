"""Unit tests for SimBI MCP server tools — no API keys, no browser required."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from simbi_mcp.server import _anthropic_client, mcp
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


def _empty_schema_json() -> str:
    return ModelSchema(tables=[], measures=[], relationships=[]).model_dump_json()


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


async def test_create_dashboard_mockup_returns_html(mocker: MockerFixture) -> None:
    mocker.patch("simbi_mcp.server._generate_mockup", return_value="<html>mock</html>")
    mocker.patch("simbi_mcp.server._anthropic_client", return_value=MagicMock())
    _, result = await mcp.call_tool(
        "create_dashboard_mockup",
        {"prompt": "show sales", "schema_json": _empty_schema_json()},
    )
    assert result["result"] == "<html>mock</html>"


def test_anthropic_client_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        _anthropic_client()


def test_mcp_server_name() -> None:
    assert mcp.name == "SimBI"


def test_main_is_importable_from_package() -> None:
    from simbi_mcp import main
    from simbi_mcp.server import main as server_main
    assert main is server_main
