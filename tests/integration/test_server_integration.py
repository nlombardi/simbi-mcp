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
async def test_emit_report_creates_pbip_folder(tmp_path: Path) -> None:
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
    report_dir = Path(result["result"])
    assert report_dir == tmp_path / "TestDashboard.Report"
    assert report_dir.is_dir()
    assert (report_dir / "definition.pbir").exists()
    definition = json.loads((report_dir / "definition.pbir").read_text())
    assert definition["datasetReference"]["byPath"]["path"] == "../TestDashboard.SemanticModel"


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
    report_dir = Path(result["result"])
    pages_dir = report_dir / "definition" / "pages"
    pages_content = json.loads((pages_dir / "pages.json").read_text())
    page_guid = pages_content["pageOrder"][0]
    visual_files = list((pages_dir / page_guid / "visuals").glob("*/visual.json"))
    assert len(visual_files) == 4
