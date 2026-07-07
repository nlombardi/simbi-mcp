"""Unit tests for the PBIR folder writer."""
import json
from pathlib import Path
from typing import Any

import pytest

from simbi_mcp.pbir.writer import PageSpec, write_report

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
    result = write_report(
        pages=[PageSpec(visuals=sample_visuals)], report_name="TestReport", output_dir=tmp_path
    )
    assert result == tmp_path / "TestReport.Report"
    assert result.is_dir()


def test_definition_pbir_default_path(tmp_path: Path, sample_visuals: list[dict[str, Any]]) -> None:
    write_report(pages=[PageSpec(visuals=sample_visuals)], report_name="TestReport", output_dir=tmp_path)
    content = json.loads((tmp_path / "TestReport.Report" / "definition.pbir").read_text())
    assert content["version"] == "4.0"
    assert content["datasetReference"]["byPath"]["path"] == "../TestReport.SemanticModel"


def test_definition_pbir_custom_path(tmp_path: Path, sample_visuals: list[dict[str, Any]]) -> None:
    write_report(
        pages=[PageSpec(visuals=sample_visuals)],
        report_name="TestReport",
        output_dir=tmp_path,
        semantic_model_rel_path="../CustomModel.SemanticModel",
    )
    content = json.loads((tmp_path / "TestReport.Report" / "definition.pbir").read_text())
    assert content["datasetReference"]["byPath"]["path"] == "../CustomModel.SemanticModel"


def test_version_json(tmp_path: Path, sample_visuals: list[dict[str, Any]]) -> None:
    write_report(pages=[PageSpec(visuals=sample_visuals)], report_name="TestReport", output_dir=tmp_path)
    content = json.loads(
        (tmp_path / "TestReport.Report" / "definition" / "version.json").read_text()
    )
    assert content["version"] == "2.0.0"


def test_pages_json_single_page(tmp_path: Path, sample_visuals: list[dict[str, Any]]) -> None:
    write_report(pages=[PageSpec(visuals=sample_visuals)], report_name="TestReport", output_dir=tmp_path)
    pages_path = tmp_path / "TestReport.Report" / "definition" / "pages" / "pages.json"
    content = json.loads(pages_path.read_text())
    assert len(content["pageOrder"]) == 1
    assert content["pageOrder"][0] == content["activePageName"]


def test_page_json_dimensions(tmp_path: Path, sample_visuals: list[dict[str, Any]]) -> None:
    write_report(pages=[PageSpec(visuals=sample_visuals)], report_name="TestReport", output_dir=tmp_path)
    pages_dir = tmp_path / "TestReport.Report" / "definition" / "pages"
    pages_content = json.loads((pages_dir / "pages.json").read_text())
    page_guid = pages_content["pageOrder"][0]
    content = json.loads((pages_dir / page_guid / "page.json").read_text())
    assert content["height"] == 720
    assert content["width"] == 1280
    assert content["displayOption"] == "FitToPage"


def test_visual_json_files_created(tmp_path: Path, sample_visuals: list[dict[str, Any]]) -> None:
    write_report(pages=[PageSpec(visuals=sample_visuals)], report_name="TestReport", output_dir=tmp_path)
    pages_dir = tmp_path / "TestReport.Report" / "definition" / "pages"
    pages_content = json.loads((pages_dir / "pages.json").read_text())
    page_guid = pages_content["pageOrder"][0]
    visual_files = list((pages_dir / page_guid / "visuals").glob("*/visual.json"))
    assert len(visual_files) == 2


def test_visual_json_guid_used_as_folder_name(
    tmp_path: Path, sample_visuals: list[dict[str, Any]]
) -> None:
    write_report(pages=[PageSpec(visuals=sample_visuals)], report_name="TestReport", output_dir=tmp_path)
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
    write_report(pages=[PageSpec(visuals=sample_visuals)], report_name="TestReport", output_dir=tmp_path)
    theme_path = (
        tmp_path
        / "TestReport.Report"
        / "StaticResources"
        / "SharedResources"
        / "BaseThemes"
        / "SimBIDefault.json"
    )
    assert theme_path.exists()
    assert theme_path.stat().st_size > 1000
    theme_content = json.loads(theme_path.read_text())
    assert theme_content["dataColors"][0].upper() == "#118DFF"
    assert theme_content["visualStyles"]


def test_report_json_has_theme_collection(
    tmp_path: Path, sample_visuals: list[dict[str, Any]]
) -> None:
    write_report(pages=[PageSpec(visuals=sample_visuals)], report_name="TestReport", output_dir=tmp_path)
    content = json.loads(
        (tmp_path / "TestReport.Report" / "definition" / "report.json").read_text()
    )
    assert content["themeCollection"]["baseTheme"]["name"] == "SimBIDefault"
    assert "settings" in content


def test_write_report_with_user_theme_override(
    tmp_path: Path, sample_visuals: list[dict[str, Any]]
) -> None:
    """User theme deep-merges onto SimBI default; brand colours win, visualStyles preserved."""
    from simbi_mcp.pbir.theme import resolve_theme
    user = tmp_path / "brand.json"
    user.write_text(json.dumps({
        "name": "AcmeBrand",
        "dataColors": ["#FF0000", "#00FF00", "#0000FF"],
    }))
    theme = resolve_theme(user_theme_path=user)
    write_report(
        pages=[PageSpec(visuals=sample_visuals)],
        report_name="TestReport",
        output_dir=tmp_path,
        theme=theme,
    )
    emitted = json.loads(
        (
            tmp_path / "TestReport.Report" / "StaticResources" / "SharedResources"
            / "BaseThemes" / "AcmeBrand.json"
        ).read_text()
    )
    assert emitted["dataColors"] == ["#FF0000", "#00FF00", "#0000FF"]
    assert emitted["visualStyles"]
    report_json = json.loads(
        (tmp_path / "TestReport.Report" / "definition" / "report.json").read_text()
    )
    assert report_json["themeCollection"]["baseTheme"]["name"] == "AcmeBrand"


def test_write_report_does_not_create_pbip(
    tmp_path: Path, sample_visuals: list[dict[str, Any]]
) -> None:
    """SimBI never creates the .pbip — that's PBI Desktop / Power BI MCP's job."""
    write_report(pages=[PageSpec(visuals=sample_visuals)], report_name="TestReport", output_dir=tmp_path)
    assert not (tmp_path / "TestReport.pbip").exists()


def test_write_report_does_not_create_semantic_model(
    tmp_path: Path, sample_visuals: list[dict[str, Any]]
) -> None:
    """SimBI never creates the .SemanticModel — that's PBI Desktop / PBI MCP's job."""
    write_report(pages=[PageSpec(visuals=sample_visuals)], report_name="TestReport", output_dir=tmp_path)
    assert not (tmp_path / "TestReport.SemanticModel").exists()


def test_repeat_write_clears_orphan_page_folders(
    tmp_path: Path, sample_visuals: list[dict[str, Any]]
) -> None:
    """Each emit_report uses a fresh page GUID — old page folders must be wiped."""
    write_report(pages=[PageSpec(visuals=sample_visuals)], report_name="TestReport", output_dir=tmp_path)
    pages_dir = tmp_path / "TestReport.Report" / "definition" / "pages"
    first_guid = json.loads((pages_dir / "pages.json").read_text())["pageOrder"][0]

    write_report(pages=[PageSpec(visuals=sample_visuals)], report_name="TestReport", output_dir=tmp_path)
    second_guid = json.loads((pages_dir / "pages.json").read_text())["pageOrder"][0]

    guid_dirs = {p.name for p in pages_dir.iterdir() if p.is_dir()}
    assert guid_dirs == {second_guid}
    assert first_guid != second_guid


def test_visual_internal_keys_stripped(tmp_path: Path) -> None:
    """simbiId / simbiButtonAction are internal scaffolding, not valid PBIR."""
    visual = {
        "$schema": _VISUAL_SCHEMA,
        "name": "abcd1234ef5678901234",
        "simbiId": "chartBar",
        "simbiButtonAction": {"kind": "bookmark"},
        "visual": {"visualType": "card"},
    }
    report_dir = write_report(
        pages=[PageSpec(visuals=[visual])], report_name="TestReport", output_dir=tmp_path
    )
    visuals_dir = report_dir / "definition" / "pages"
    page_guid = json.loads(
        (visuals_dir / "pages.json").read_text()
    )["pageOrder"][0]
    written = json.loads(
        (visuals_dir / page_guid / "visuals" / "abcd1234ef5678901234" / "visual.json").read_text()
    )
    assert "simbiId" not in written
    assert "simbiButtonAction" not in written
    assert written["visual"]["visualType"] == "card"


def test_bookmarks_written(
    tmp_path: Path, sample_visuals: list[dict[str, Any]]
) -> None:
    """Passing bookmarks writes the index plus one file per bookmark."""
    bm = {
        "$schema": "https://example/schema.json",
        "displayName": "View: Bar",
        "name": "Bookmarkdeadbeef",
        "options": {},
        "explorationState": {},
    }
    report_dir = write_report(
        pages=[PageSpec(visuals=sample_visuals)],
        report_name="TestReport",
        output_dir=tmp_path,
        bookmarks=[bm],
    )
    bdir = report_dir / "definition" / "bookmarks"
    index = json.loads((bdir / "bookmarks.json").read_text())
    assert index["items"] == [{"name": "Bookmarkdeadbeef"}]
    written = json.loads((bdir / "Bookmarkdeadbeef.bookmark.json").read_text())
    assert written["displayName"] == "View: Bar"


def test_repeat_write_clears_orphan_bookmarks(
    tmp_path: Path, sample_visuals: list[dict[str, Any]]
) -> None:
    """Bookmarks dir is wiped each emit so removed bookmarks don't linger."""
    bm = {"name": "BookmarkOld", "displayName": "Old"}
    write_report(
        pages=[PageSpec(visuals=sample_visuals)],
        report_name="TestReport",
        output_dir=tmp_path,
        bookmarks=[bm],
    )
    bdir = tmp_path / "TestReport.Report" / "definition" / "bookmarks"
    assert (bdir / "BookmarkOld.bookmark.json").exists()

    write_report(
        pages=[PageSpec(visuals=sample_visuals)], report_name="TestReport", output_dir=tmp_path
    )
    assert not bdir.exists()


def test_multi_page_report(tmp_path: Path, sample_visuals: list[dict[str, Any]]) -> None:
    """Multiple PageSpec entries produce multiple page folders in a single atomic write."""
    page1_visual = sample_visuals[0]
    page2_visual = sample_visuals[1]
    report_dir = write_report(
        pages=[
            PageSpec(visuals=[page1_visual], display_name="Overview"),
            PageSpec(visuals=[page2_visual], display_name="Details"),
        ],
        report_name="TestReport",
        output_dir=tmp_path,
    )
    pages_dir = report_dir / "definition" / "pages"
    pages_meta = json.loads((pages_dir / "pages.json").read_text())
    assert len(pages_meta["pageOrder"]) == 2
    assert pages_meta["activePageName"] == pages_meta["pageOrder"][0]

    for guid, expected_name in zip(pages_meta["pageOrder"], ["Overview", "Details"]):
        page_content = json.loads((pages_dir / guid / "page.json").read_text())
        assert page_content["displayName"] == expected_name


def _minimal_visual() -> dict:
    return {"name": "abc123", "position": {"x": 0, "y": 0, "z": 0, "height": 100, "width": 100, "tabOrder": 0}, "visual": {"visualType": "card"}}


def test_page_background_written(tmp_path) -> None:
    from simbi_mcp.pbir.styling import page_background_card

    spec = PageSpec(
        visuals=[_minimal_visual()],
        display_name="Overview",
        background=page_background_card("rgb(241, 245, 249)"),
    )
    report_dir = write_report(pages=[spec], report_name="R", output_dir=tmp_path)
    page_dir = next((report_dir / "definition" / "pages").glob("*/page.json"))
    page = json.loads(page_dir.read_text(encoding="utf-8"))
    color = page["objects"]["background"][0]["properties"]["color"]
    assert color == {"solid": {"color": {"expr": {"Literal": {"Value": "'#F1F5F9'"}}}}}


def test_page_without_background_has_no_objects(tmp_path) -> None:
    spec = PageSpec(visuals=[_minimal_visual()], display_name="Overview")
    report_dir = write_report(pages=[spec], report_name="R", output_dir=tmp_path)
    page_dir = next((report_dir / "definition" / "pages").glob("*/page.json"))
    page = json.loads(page_dir.read_text(encoding="utf-8"))
    assert "objects" not in page
