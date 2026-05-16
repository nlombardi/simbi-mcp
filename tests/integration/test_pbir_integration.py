"""Integration test for the full emit_pbir pipeline.

Requires system Chrome at C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe.
Uses the existing tests/fixtures/html/valid_dashboard.html fixture (4 data-pbi elements).

Run with: uv run pytest -m integration -v
"""
import json
from pathlib import Path

import pytest

from simbi_mcp.pbir.emitter import emit_pbir
from simbi_mcp.types import ModelMeasure, ModelSchema, ModelTable

pytestmark = pytest.mark.integration

_CHROME_EXE = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
_FIXTURES_HTML = Path(__file__).parent.parent / "fixtures" / "html"


@pytest.fixture
def schema() -> ModelSchema:
    return ModelSchema(
        tables=[
            ModelTable(name="sales", columns=["Region", "OrderDate", "Revenue"]),
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


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_emit_pbir_creates_report_folder(schema: ModelSchema, tmp_path: Path) -> None:
    html = (_FIXTURES_HTML / "valid_dashboard.html").read_text()
    report_dir = await emit_pbir(
        html=html,
        schema=schema,
        report_name="TestDashboard",
        output_dir=tmp_path,
    )
    assert report_dir == tmp_path / "TestDashboard.Report"
    assert (report_dir / "definition.pbir").exists()
    assert (report_dir / "definition" / "version.json").exists()
    assert (report_dir / "definition" / "report.json").exists()


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_emit_pbir_generates_correct_visual_count(
    schema: ModelSchema, tmp_path: Path
) -> None:
    # valid_dashboard.html: 2 cards + 1 slicer + 1 columnChart = 4 visuals
    html = (_FIXTURES_HTML / "valid_dashboard.html").read_text()
    report_dir = await emit_pbir(
        html=html,
        schema=schema,
        report_name="TestDashboard",
        output_dir=tmp_path,
    )
    pages_dir = report_dir / "definition" / "pages"
    page_guid = next(p for p in pages_dir.iterdir() if p.is_dir()).name
    visual_files = list((pages_dir / page_guid / "visuals").glob("*/visual.json"))
    assert len(visual_files) == 4


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_emit_pbir_visual_json_is_valid(schema: ModelSchema, tmp_path: Path) -> None:
    html = (_FIXTURES_HTML / "valid_dashboard.html").read_text()
    report_dir = await emit_pbir(
        html=html,
        schema=schema,
        report_name="TestDashboard",
        output_dir=tmp_path,
    )
    pages_dir = report_dir / "definition" / "pages"
    page_guid = next(p for p in pages_dir.iterdir() if p.is_dir()).name
    for vf in (pages_dir / page_guid / "visuals").glob("*/visual.json"):
        data = json.loads(vf.read_text())
        assert "$schema" in data
        assert "name" in data
        assert "position" in data
        assert "visual" in data
        assert "visualType" in data["visual"]
        pos = data["position"]
        assert pos["width"] > 0
        assert pos["height"] > 0


@pytest.mark.skipif(not _CHROME_EXE.exists(), reason="System Chrome not found")
async def test_emit_pbir_semantic_model_ref(schema: ModelSchema, tmp_path: Path) -> None:
    html = (_FIXTURES_HTML / "valid_dashboard.html").read_text()
    report_dir = await emit_pbir(
        html=html,
        schema=schema,
        report_name="TestDashboard",
        output_dir=tmp_path,
    )
    content = json.loads((report_dir / "definition.pbir").read_text())
    assert content["datasetReference"]["byPath"]["path"] == "../TestDashboard.SemanticModel"
