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
from simbi_mcp.types import ModelColumn, ModelMeasure, ModelSchema, ModelTable

pytestmark = pytest.mark.integration

_CHROME_EXE = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
_FIXTURES_HTML = Path(__file__).parent.parent / "fixtures" / "html"

_SALES_SCHEMA = ModelSchema(
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


def _seed_pbip(tmp_path: Path, name: str) -> Path:
    """Simulate the .pbip + .SemanticModel that Power BI Desktop / MCP would have created."""
    pbip = tmp_path / f"{name}.pbip"
    pbip.write_text(
        json.dumps({"version": "1.0", "artifacts": [{"report": {"path": f"{name}.Report"}}]}),
        encoding="utf-8",
    )
    (tmp_path / f"{name}.SemanticModel").mkdir()
    return pbip


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_emit_report_returns_report_dir_path(tmp_path: Path) -> None:
    pbip = _seed_pbip(tmp_path, "TestDashboard")
    html = (_FIXTURES_HTML / "valid_dashboard.html").read_text()
    schema_json = _SALES_SCHEMA.model_dump_json()
    _, result = await mcp.call_tool(
        "emit_report",
        {
            "html": html,
            "schema_json": schema_json,
            "pbip_path": str(pbip),
        },
    )
    report_dir = Path(result["result"])
    assert report_dir == tmp_path / "TestDashboard.Report"
    assert report_dir.is_dir()


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_emit_report_preserves_existing_pbip_and_model(tmp_path: Path) -> None:
    pbip = _seed_pbip(tmp_path, "TestDashboard")
    original_pbip = pbip.read_text()
    html = (_FIXTURES_HTML / "valid_dashboard.html").read_text()
    schema_json = _SALES_SCHEMA.model_dump_json()
    await mcp.call_tool(
        "emit_report",
        {
            "html": html,
            "schema_json": schema_json,
            "pbip_path": str(pbip),
        },
    )
    # SimBI must not touch the .pbip or .SemanticModel
    assert pbip.read_text() == original_pbip
    assert (tmp_path / "TestDashboard.SemanticModel").is_dir()


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_emit_report_correct_visual_count(tmp_path: Path) -> None:
    pbip = _seed_pbip(tmp_path, "TestDashboard")
    html = (_FIXTURES_HTML / "valid_dashboard.html").read_text()
    schema_json = _SALES_SCHEMA.model_dump_json()
    await mcp.call_tool(
        "emit_report",
        {
            "html": html,
            "schema_json": schema_json,
            "pbip_path": str(pbip),
        },
    )
    report_dir = tmp_path / "TestDashboard.Report"
    pages_dir = report_dir / "definition" / "pages"
    pages_content = json.loads((pages_dir / "pages.json").read_text())
    page_guid = pages_content["pageOrder"][0]
    visual_files = list((pages_dir / page_guid / "visuals").glob("*/visual.json"))
    assert len(visual_files) == 4


async def test_emit_report_rejects_missing_pbip(tmp_path: Path) -> None:
    """SimBI must refuse to run when no .pbip exists at pbip_path."""
    html = (_FIXTURES_HTML / "valid_dashboard.html").read_text()
    schema_json = _SALES_SCHEMA.model_dump_json()
    with pytest.raises(Exception, match="must point to an EXISTING"):
        await mcp.call_tool(
            "emit_report",
            {
                "html": html,
                "schema_json": schema_json,
                "pbip_path": str(tmp_path / "DoesNotExist.pbip"),
            },
        )


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_emit_report_accepts_folder_and_finds_pbip(tmp_path: Path) -> None:
    """Passing a folder containing one .pbip auto-discovers it."""
    _seed_pbip(tmp_path, "TestDashboard")
    html = (_FIXTURES_HTML / "valid_dashboard.html").read_text()
    schema_json = _SALES_SCHEMA.model_dump_json()
    _, result = await mcp.call_tool(
        "emit_report",
        {
            "html": html,
            "schema_json": schema_json,
            "pbip_path": str(tmp_path),  # folder, not file
        },
    )
    assert Path(result["result"]) == tmp_path / "TestDashboard.Report"


async def test_emit_report_rejects_ambiguous_folder(tmp_path: Path) -> None:
    """Folder with multiple .pbip files must be rejected with a clear error."""
    _seed_pbip(tmp_path, "DashboardA")
    _seed_pbip(tmp_path, "DashboardB")
    html = (_FIXTURES_HTML / "valid_dashboard.html").read_text()
    schema_json = _SALES_SCHEMA.model_dump_json()
    with pytest.raises(Exception, match="multiple .pbip files"):
        await mcp.call_tool(
            "emit_report",
            {
                "html": html,
                "schema_json": schema_json,
                "pbip_path": str(tmp_path),
            },
        )


async def test_emit_report_rejects_empty_folder(tmp_path: Path) -> None:
    """Folder with no .pbip files must be rejected with a clear error."""
    html = (_FIXTURES_HTML / "valid_dashboard.html").read_text()
    schema_json = _SALES_SCHEMA.model_dump_json()
    with pytest.raises(Exception, match="No .pbip file found in folder"):
        await mcp.call_tool(
            "emit_report",
            {
                "html": html,
                "schema_json": schema_json,
                "pbip_path": str(tmp_path),
            },
        )
