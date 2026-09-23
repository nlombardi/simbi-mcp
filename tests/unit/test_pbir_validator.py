"""Unit tests for PBIR report validator."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from simbi_mcp.pbir.pbir_validator import PBIRValidationError, validate_pbir_report
from simbi_mcp.pbir.writer import PageSpec, write_report


@pytest.fixture
def clean_visual() -> dict[str, Any]:
    return {
        "name": "v1",
        "position": {
            "x": 10,
            "y": 20,
            "z": 0,
            "width": 100,
            "height": 50,
            "tabOrder": 0,
        },
        "visual": {
            "visualType": "card",
            "objects": {},
        },
    }


def test_valid_report_passes_validation(tmp_path: Path, clean_visual: dict[str, Any]) -> None:
    report_dir = write_report(
        pages=[PageSpec(visuals=[clean_visual])],
        report_name="ValidReport",
        output_dir=tmp_path,
    )
    errors = validate_pbir_report(report_dir, raise_on_error=True)
    assert errors == []


def test_float_coordinate_fails_validation(
    tmp_path: Path, clean_visual: dict[str, Any]
) -> None:
    report_dir = write_report(
        pages=[PageSpec(visuals=[clean_visual])],
        report_name="FloatReport",
        output_dir=tmp_path,
    )
    # Manually inject a float into visual.json
    visual_path = next((report_dir / "definition" / "pages").glob("*/visuals/*/visual.json"))
    data = json.loads(visual_path.read_text(encoding="utf-8"))
    data["position"]["x"] = 10.5
    visual_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(PBIRValidationError, match=r"position\.x must be an integer, got float"):
        validate_pbir_report(report_dir, raise_on_error=True)


def test_unrecognized_base_theme_fails_validation(
    tmp_path: Path, clean_visual: dict[str, Any]
) -> None:
    report_dir = write_report(
        pages=[PageSpec(visuals=[clean_visual])],
        report_name="ThemeReport",
        output_dir=tmp_path,
    )
    # Manually inject invalid baseTheme name
    report_json_path = report_dir / "definition" / "report.json"
    data = json.loads(report_json_path.read_text(encoding="utf-8"))
    data["themeCollection"]["baseTheme"]["name"] = "IMF Theme"
    report_json_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(PBIRValidationError, match=r"baseTheme\.name must be 'CY25SU10'"):
        validate_pbir_report(report_dir, raise_on_error=True)


def test_legacy_objects_section_fails_validation(
    tmp_path: Path, clean_visual: dict[str, Any]
) -> None:
    report_dir = write_report(
        pages=[PageSpec(visuals=[clean_visual])],
        report_name="SectionReport",
        output_dir=tmp_path,
    )
    # Inject legacy section
    report_json_path = report_dir / "definition" / "report.json"
    data = json.loads(report_json_path.read_text(encoding="utf-8"))
    data["objects"] = {"section": [{"properties": {}}]}
    report_json_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(PBIRValidationError, match=r"legacy objects\.section"):
        validate_pbir_report(report_dir, raise_on_error=True)


def test_objects_action_fails_validation(tmp_path: Path, clean_visual: dict[str, Any]) -> None:
    report_dir = write_report(
        pages=[PageSpec(visuals=[clean_visual])],
        report_name="ActionReport",
        output_dir=tmp_path,
    )
    visual_path = next((report_dir / "definition" / "pages").glob("*/visuals/*/visual.json"))
    data = json.loads(visual_path.read_text(encoding="utf-8"))
    data["visual"]["objects"] = {"action": [{"properties": {}}]}
    visual_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(
        PBIRValidationError, match=r"invalid visual\.objects\.action"
    ):
        validate_pbir_report(report_dir, raise_on_error=True)


def test_round_edge_in_shape_fails_validation(
    tmp_path: Path, clean_visual: dict[str, Any]
) -> None:
    report_dir = write_report(
        pages=[PageSpec(visuals=[clean_visual])],
        report_name="ShapeReport",
        output_dir=tmp_path,
    )
    visual_path = next((report_dir / "definition" / "pages").glob("*/visuals/*/visual.json"))
    data = json.loads(visual_path.read_text(encoding="utf-8"))
    data["visual"]["objects"] = {"shape": [{"properties": {"roundEdge": "8L"}}]}
    visual_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(PBIRValidationError, match=r"unsupported property 'roundEdge'"):
        validate_pbir_report(report_dir, raise_on_error=True)


def test_valid_bookmark_passes_validation(tmp_path: Path, clean_visual: dict[str, Any]) -> None:
    bm = {
        "name": "bm1",
        "displayName": "Test Bookmark",
        "options": {
            "applyOnlyToTargetVisuals": True,
            "targetVisualNames": ["v1"],
        },
        "explorationState": {
            "version": "1.3",
            "activeSection": "p1",
            "sections": {
                "p1": {
                    "visualContainers": {
                        "v1": {
                            "singleVisual": {
                                "visualType": "card",
                                "objects": {},
                                "display": {"mode": "hidden"},
                            }
                        }
                    }
                }
            },
        },
    }
    report_dir = write_report(
        pages=[PageSpec(visuals=[clean_visual])],
        report_name="ValidBookmarkReport",
        output_dir=tmp_path,
        bookmarks=[bm],
    )
    errors = validate_pbir_report(report_dir, raise_on_error=True)
    assert errors == []


def test_bookmark_with_visible_mode_fails_validation(
    tmp_path: Path, clean_visual: dict[str, Any]
) -> None:
    bm = {
        "name": "bm1",
        "displayName": "Invalid Mode Bookmark",
        "options": {
            "applyOnlyToTargetVisuals": True,
            "targetVisualNames": ["v1"],
        },
        "explorationState": {
            "version": "1.3",
            "activeSection": "p1",
            "sections": {
                "p1": {
                    "visualContainers": {
                        "v1": {
                            "singleVisual": {
                                "visualType": "card",
                                "objects": {},
                                "display": {"mode": "visible"},
                            }
                        }
                    }
                }
            },
        },
    }
    # write_report runs validate_pbir_report automatically, which should raise PBIRValidationError
    with pytest.raises(PBIRValidationError, match=r"invalid display\.mode='visible'"):
        write_report(
            pages=[PageSpec(visuals=[clean_visual])],
            report_name="InvalidBookmarkReport",
            output_dir=tmp_path,
            bookmarks=[bm],
        )


def test_bookmark_referencing_nonexistent_visual_fails_validation(
    tmp_path: Path, clean_visual: dict[str, Any]
) -> None:
    bm = {
        "name": "bm1",
        "displayName": "Nonexistent Visual Bookmark",
        "options": {
            "applyOnlyToTargetVisuals": True,
            "targetVisualNames": ["nonexistent_guid"],
        },
        "explorationState": {
            "version": "1.3",
            "activeSection": "p1",
            "sections": {
                "p1": {
                    "visualContainers": {
                        "nonexistent_guid": {
                            "singleVisual": {
                                "visualType": "card",
                                "objects": {},
                            }
                        }
                    }
                }
            },
        },
    }
    with pytest.raises(PBIRValidationError, match=r"references non-existent visual GUID"):
        write_report(
            pages=[PageSpec(visuals=[clean_visual])],
            report_name="NonexistentVisualReport",
            output_dir=tmp_path,
            bookmarks=[bm],
        )

