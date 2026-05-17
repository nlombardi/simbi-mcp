"""Integration tests for the emit_report tool.

Requires system Chrome at C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe.
Uses tests/fixtures/html/valid_dashboard.html (4 data-pbi elements matching _SALES_SCHEMA).

Run with: uv run pytest -m integration -v
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from simbi_mcp.server import mcp
from simbi_mcp.types import ModelMeasure, ModelSchema, ModelTable

pytestmark = pytest.mark.integration

_CHROME_EXE = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
_FIXTURES_HTML = Path(__file__).parent.parent / "fixtures" / "html"

_SALES_SCHEMA = ModelSchema(
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


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_emit_report_returns_pbip_path(tmp_path: Path) -> None:
    html = (_FIXTURES_HTML / "valid_dashboard.html").read_text()
    schema_json = _SALES_SCHEMA.model_dump_json()
    _, result = await mcp.call_tool(
        "emit_report",
        {
            "html": html,
            "schema_json": schema_json,
            "report_name": "TestDashboard",
            "output_dir": str(tmp_path),
        },
    )
    pbip = Path(result["result"])
    assert pbip == tmp_path / "TestDashboard.pbip"
    assert pbip.exists()
    project = json.loads(pbip.read_text())
    assert project["artifacts"][0]["report"]["path"] == "TestDashboard.Report"


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_emit_report_creates_report_and_semantic_model(tmp_path: Path) -> None:
    html = (_FIXTURES_HTML / "valid_dashboard.html").read_text()
    schema_json = _SALES_SCHEMA.model_dump_json()
    _, result = await mcp.call_tool(
        "emit_report",
        {
            "html": html,
            "schema_json": schema_json,
            "report_name": "TestDashboard",
            "output_dir": str(tmp_path),
        },
    )
    report_dir = tmp_path / "TestDashboard.Report"
    model_dir = tmp_path / "TestDashboard.SemanticModel"
    assert report_dir.is_dir()
    assert (report_dir / "definition.pbir").exists()
    assert model_dir.is_dir()
    assert (model_dir / "definition.pbism").exists()
    assert (model_dir / "model.bim").exists()
    bim = json.loads((model_dir / "model.bim").read_text())
    table_names = [t["name"] for t in bim["model"]["tables"]]
    assert "sales" in table_names


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_emit_report_correct_visual_count(tmp_path: Path) -> None:
    # valid_dashboard.html has 4 data-pbi elements
    html = (_FIXTURES_HTML / "valid_dashboard.html").read_text()
    schema_json = _SALES_SCHEMA.model_dump_json()
    _, result = await mcp.call_tool(
        "emit_report",
        {
            "html": html,
            "schema_json": schema_json,
            "report_name": "TestDashboard",
            "output_dir": str(tmp_path),
        },
    )
    report_dir = tmp_path / "TestDashboard.Report"
    pages_dir = report_dir / "definition" / "pages"
    pages_content = json.loads((pages_dir / "pages.json").read_text())
    page_guid = pages_content["pageOrder"][0]
    visual_files = list((pages_dir / page_guid / "visuals").glob("*/visual.json"))
    assert len(visual_files) == 4
