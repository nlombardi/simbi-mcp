"""End-to-end walkthrough tests for the SimBI usage path.

The Power BI MCP (or Power BI Desktop) creates the .pbip + .SemanticModel
first (simulated here by pre-creating those artifacts). SimBI's job is to
fill in the missing .Report/ folder beside the existing project file.

  parse_schema (ExportTMDL output) → emit_report → .Report/

Run with: uv run pytest -m integration -v -k walkthrough
Requires: system Chrome at C:/Program Files/Google/Chrome/Application/chrome.exe
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from simbi_mcp.server import mcp

pytestmark = pytest.mark.integration

_CHROME_EXE = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
_FIXTURES = Path(__file__).parent.parent / "fixtures"
_TMDL = (_FIXTURES / "tmdl" / "sales_pbi_mcp.tmdl").read_text(encoding="utf-8")
_HTML = (_FIXTURES / "html" / "sales_walkthrough.html").read_text(encoding="utf-8")

# 3 cards + 1 slicer + 1 columnChart + 1 lineChart
_EXPECTED_VISUAL_COUNT = 6


def _visual_files(report_dir: Path) -> list[Path]:
    pages_dir = report_dir / "definition" / "pages"
    pages = json.loads((pages_dir / "pages.json").read_text())
    page_guid = pages["pageOrder"][0]
    return list((pages_dir / page_guid / "visuals").glob("*/visual.json"))


def _seed_pbi_project(output_dir: Path, report_name: str) -> Path:
    """Simulate the .pbip + .SemanticModel that Power BI MCP / Desktop creates first."""
    pbip = output_dir / f"{report_name}.pbip"
    pbip.write_text(
        json.dumps(
            {
                "version": "1.0",
                "artifacts": [{"report": {"path": f"{report_name}.Report"}}],
                "settings": {"enableAutoRecovery": True},
            }
        ),
        encoding="utf-8",
    )
    model_dir = output_dir / f"{report_name}.SemanticModel"
    model_dir.mkdir(parents=True)
    (model_dir / "definition.pbism").write_text(
        json.dumps({"version": "4.2", "settings": {}}), encoding="utf-8"
    )
    (model_dir / "_ms_mcp_sentinel").write_text("created by MS MCP", encoding="utf-8")
    return pbip


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_walkthrough_returns_report_dir(tmp_path: Path) -> None:
    """emit_report returns the path to the .Report folder it wrote."""
    pbip = _seed_pbi_project(tmp_path, "SalesDashboard")

    _, schema_result = await mcp.call_tool("parse_schema", {"tmdl": _TMDL})
    schema_json = schema_result["result"]

    _, emit_result = await mcp.call_tool(
        "emit_report",
        {"html": _HTML, "schema_json": schema_json, "pbip_path": str(pbip)},
    )

    report_dir = Path(emit_result["result"])
    assert report_dir == tmp_path / "SalesDashboard.Report"
    assert report_dir.is_dir()


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_walkthrough_preserves_existing_pbip(tmp_path: Path) -> None:
    """SimBI must leave the .pbip created by Power BI MCP exactly as it was."""
    pbip = _seed_pbi_project(tmp_path, "SalesDashboard")
    original_pbip = pbip.read_text()

    _, schema_result = await mcp.call_tool("parse_schema", {"tmdl": _TMDL})
    schema_json = schema_result["result"]
    await mcp.call_tool(
        "emit_report",
        {"html": _HTML, "schema_json": schema_json, "pbip_path": str(pbip)},
    )

    assert pbip.read_text() == original_pbip


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_walkthrough_preserves_existing_semantic_model(tmp_path: Path) -> None:
    """SimBI must leave the .SemanticModel created by Power BI MCP untouched."""
    pbip = _seed_pbi_project(tmp_path, "SalesDashboard")

    _, schema_result = await mcp.call_tool("parse_schema", {"tmdl": _TMDL})
    schema_json = schema_result["result"]
    await mcp.call_tool(
        "emit_report",
        {"html": _HTML, "schema_json": schema_json, "pbip_path": str(pbip)},
    )

    sentinel = tmp_path / "SalesDashboard.SemanticModel" / "_ms_mcp_sentinel"
    assert sentinel.exists(), "SemanticModel folder was modified"
    assert sentinel.read_text() == "created by MS MCP"


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_walkthrough_report_references_existing_model(tmp_path: Path) -> None:
    """Report's definition.pbir points at the sibling SemanticModel folder."""
    pbip = _seed_pbi_project(tmp_path, "SalesDashboard")

    _, schema_result = await mcp.call_tool("parse_schema", {"tmdl": _TMDL})
    schema_json = schema_result["result"]
    await mcp.call_tool(
        "emit_report",
        {"html": _HTML, "schema_json": schema_json, "pbip_path": str(pbip)},
    )

    report_dir = tmp_path / "SalesDashboard.Report"
    pbir = json.loads((report_dir / "definition.pbir").read_text())
    assert pbir["datasetReference"]["byPath"]["path"] == "../SalesDashboard.SemanticModel"


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_walkthrough_correct_visual_count(tmp_path: Path) -> None:
    """All 6 annotated visuals from the HTML are written."""
    pbip = _seed_pbi_project(tmp_path, "SalesDashboard")

    _, schema_result = await mcp.call_tool("parse_schema", {"tmdl": _TMDL})
    schema_json = schema_result["result"]
    await mcp.call_tool(
        "emit_report",
        {"html": _HTML, "schema_json": schema_json, "pbip_path": str(pbip)},
    )

    report_dir = tmp_path / "SalesDashboard.Report"
    assert len(_visual_files(report_dir)) == _EXPECTED_VISUAL_COUNT


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_walkthrough_visual_types_correct(tmp_path: Path) -> None:
    """Visual JSON files carry the right Power BI visualType strings."""
    pbip = _seed_pbi_project(tmp_path, "SalesDashboard")

    _, schema_result = await mcp.call_tool("parse_schema", {"tmdl": _TMDL})
    schema_json = schema_result["result"]
    await mcp.call_tool(
        "emit_report",
        {"html": _HTML, "schema_json": schema_json, "pbip_path": str(pbip)},
    )

    report_dir = tmp_path / "SalesDashboard.Report"
    vtypes = sorted(
        json.loads(vf.read_text())["visual"]["visualType"]
        for vf in _visual_files(report_dir)
    )
    assert vtypes == sorted(["card", "card", "card", "slicer", "columnChart", "lineChart"])
