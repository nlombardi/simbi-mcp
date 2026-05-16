"""Unit tests for the PBIR folder writer."""
import json
from pathlib import Path
from typing import Any

import pytest

from simbi_mcp.pbir.writer import write_report

_VISUAL_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report"
    "/definition/visualContainer/2.3.0/schema.json"
)


@pytest.fixture
def sample_visuals() -> list[dict[str, Any]]:
    return [
        {
            "$schema": _VISUAL_SCHEMA,
            "name": "abcd1234ef5678901234",
            "position": {
                "x": 24.0,
                "y": 24.0,
                "z": 0,
                "height": 104.0,
                "width": 400.0,
                "tabOrder": 0,
            },
            "visual": {
                "visualType": "card",
                "query": {"queryState": {"Values": {"projections": []}}},
                "drillFilterOtherVisuals": True,
            },
        },
        {
            "$schema": _VISUAL_SCHEMA,
            "name": "ef5678901234abcd1234",
            "position": {
                "x": 440.0,
                "y": 24.0,
                "z": 1000,
                "height": 104.0,
                "width": 400.0,
                "tabOrder": 1000,
            },
            "visual": {
                "visualType": "slicer",
                "query": {"queryState": {"Field": {"projections": []}}},
                "drillFilterOtherVisuals": True,
            },
        },
    ]


def test_write_report_returns_report_folder(
    tmp_path: Path, sample_visuals: list[dict[str, Any]]
) -> None:
    result = write_report(visuals=sample_visuals, report_name="TestReport", output_dir=tmp_path)
    assert result == tmp_path / "TestReport.Report"
    assert result.is_dir()


def test_definition_pbir_default_path(tmp_path: Path, sample_visuals: list[dict[str, Any]]) -> None:
    write_report(visuals=sample_visuals, report_name="TestReport", output_dir=tmp_path)
    content = json.loads((tmp_path / "TestReport.Report" / "definition.pbir").read_text())
    assert content["version"] == "4.0"
    assert content["datasetReference"]["byPath"]["path"] == "../TestReport.SemanticModel"


def test_definition_pbir_custom_path(tmp_path: Path, sample_visuals: list[dict[str, Any]]) -> None:
    write_report(
        visuals=sample_visuals,
        report_name="TestReport",
        output_dir=tmp_path,
        semantic_model_rel_path="../CustomModel.SemanticModel",
    )
    content = json.loads((tmp_path / "TestReport.Report" / "definition.pbir").read_text())
    assert content["datasetReference"]["byPath"]["path"] == "../CustomModel.SemanticModel"


def test_version_json(tmp_path: Path, sample_visuals: list[dict[str, Any]]) -> None:
    write_report(visuals=sample_visuals, report_name="TestReport", output_dir=tmp_path)
    content = json.loads(
        (tmp_path / "TestReport.Report" / "definition" / "version.json").read_text()
    )
    assert content["version"] == "2.0.0"


def test_pages_json_single_page(tmp_path: Path, sample_visuals: list[dict[str, Any]]) -> None:
    write_report(visuals=sample_visuals, report_name="TestReport", output_dir=tmp_path)
    pages_path = tmp_path / "TestReport.Report" / "definition" / "pages" / "pages.json"
    content = json.loads(pages_path.read_text())
    assert len(content["pageOrder"]) == 1
    assert content["pageOrder"][0] == content["activePageName"]


def test_page_json_dimensions(tmp_path: Path, sample_visuals: list[dict[str, Any]]) -> None:
    write_report(visuals=sample_visuals, report_name="TestReport", output_dir=tmp_path)
    pages_dir = tmp_path / "TestReport.Report" / "definition" / "pages"
    pages_content = json.loads((pages_dir / "pages.json").read_text())
    page_guid = pages_content["pageOrder"][0]
    content = json.loads((pages_dir / page_guid / "page.json").read_text())
    assert content["height"] == 720
    assert content["width"] == 1280
    assert content["displayOption"] == "FitToPage"


def test_visual_json_files_created(tmp_path: Path, sample_visuals: list[dict[str, Any]]) -> None:
    write_report(visuals=sample_visuals, report_name="TestReport", output_dir=tmp_path)
    pages_dir = tmp_path / "TestReport.Report" / "definition" / "pages"
    pages_content = json.loads((pages_dir / "pages.json").read_text())
    page_guid = pages_content["pageOrder"][0]
    visual_files = list((pages_dir / page_guid / "visuals").glob("*/visual.json"))
    assert len(visual_files) == 2


def test_visual_json_guid_used_as_folder_name(
    tmp_path: Path, sample_visuals: list[dict[str, Any]]
) -> None:
    write_report(visuals=sample_visuals, report_name="TestReport", output_dir=tmp_path)
    pages_dir = tmp_path / "TestReport.Report" / "definition" / "pages"
    pages_content = json.loads((pages_dir / "pages.json").read_text())
    page_guid = pages_content["pageOrder"][0]
    visuals_dir = pages_dir / page_guid / "visuals"
    folder_names = {p.name for p in visuals_dir.iterdir() if p.is_dir()}
    assert "abcd1234ef5678901234" in folder_names
    assert "ef5678901234abcd1234" in folder_names


def test_theme_json_present_and_non_empty(
    tmp_path: Path, sample_visuals: list[dict[str, Any]]
) -> None:
    write_report(visuals=sample_visuals, report_name="TestReport", output_dir=tmp_path)
    theme_path = (
        tmp_path
        / "TestReport.Report"
        / "StaticResources"
        / "SharedResources"
        / "BaseThemes"
        / "CY25SU10.json"
    )
    assert theme_path.exists()
    assert theme_path.stat().st_size > 1000


def test_report_json_has_theme_collection(
    tmp_path: Path, sample_visuals: list[dict[str, Any]]
) -> None:
    write_report(visuals=sample_visuals, report_name="TestReport", output_dir=tmp_path)
    content = json.loads(
        (tmp_path / "TestReport.Report" / "definition" / "report.json").read_text()
    )
    assert content["themeCollection"]["baseTheme"]["name"] == "CY25SU10"
    assert "settings" in content
