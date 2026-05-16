"""PBIR folder writer — generates the full Report folder structure from visual dicts.

Writes all required files for a valid Power BI .pbip Report:
  - definition.pbir (dataset reference)
  - definition/version.json
  - definition/report.json (static template)
  - definition/pages/pages.json
  - definition/pages/<page-guid>/page.json
  - definition/pages/<page-guid>/visuals/<visual-guid>/visual.json (one per visual)
  - StaticResources/SharedResources/BaseThemes/CY25SU10.json (bundled theme)

The SemanticModel sibling folder is created by the MS MCP tools in Phase 1 —
this writer only generates the Report side.
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

_STATIC_DIR = Path(__file__).parent / "static"

_PAGES_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json"
_PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json"
_VERSION_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json"
_REPORT_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json"

_REPORT_JSON_TEMPLATE: dict[str, Any] = {
    "$schema": _REPORT_SCHEMA,
    "themeCollection": {
        "baseTheme": {
            "name": "CY25SU10",
            "reportVersionAtImport": {"visual": "2.1.0", "report": "3.0.0", "page": "2.3.0"},
            "type": "SharedResources",
        }
    },
    "objects": {
        "section": [
            {
                "properties": {
                    "verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}
                }
            }
        ]
    },
    "resourcePackages": [
        {
            "name": "SharedResources",
            "type": "SharedResources",
            "items": [
                {"name": "CY25SU10", "path": "BaseThemes/CY25SU10.json", "type": "BaseTheme"}
            ],
        }
    ],
    "settings": {
        "useStylableVisualContainerHeader": True,
        "exportDataMode": "AllowSummarized",
        "defaultDrillFilterOtherVisuals": True,
        "allowChangeFilterTypes": True,
        "useEnhancedTooltips": True,
        "useDefaultAggregateDisplayName": True,
    },
}


def write_report(
    *,
    visuals: list[dict[str, Any]],
    report_name: str,
    output_dir: Path,
    semantic_model_rel_path: str | None = None,
) -> Path:
    """Write the PBIR Report folder and return its path.

    The folder is named <report_name>.Report and created inside output_dir.
    semantic_model_rel_path defaults to ../<report_name>.SemanticModel, which
    places it as a sibling of the Report folder — the standard Power BI layout.
    """
    if semantic_model_rel_path is None:
        semantic_model_rel_path = f"../{report_name}.SemanticModel"

    report_dir = output_dir / f"{report_name}.Report"
    page_guid = _new_guid()

    _write_json(
        report_dir / "definition.pbir",
        {"version": "4.0", "datasetReference": {"byPath": {"path": semantic_model_rel_path}}},
    )
    _write_json(
        report_dir / "definition" / "version.json",
        {"$schema": _VERSION_SCHEMA, "version": "2.0.0"},
    )
    _write_json(report_dir / "definition" / "report.json", _REPORT_JSON_TEMPLATE)
    _write_json(
        report_dir / "definition" / "pages" / "pages.json",
        {"$schema": _PAGES_SCHEMA, "pageOrder": [page_guid], "activePageName": page_guid},
    )
    _write_json(
        report_dir / "definition" / "pages" / page_guid / "page.json",
        {
            "$schema": _PAGE_SCHEMA,
            "name": page_guid,
            "displayName": "Page 1",
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
        },
    )

    for i, visual in enumerate(visuals):
        try:
            visual_name: str = visual["name"]
        except KeyError as exc:
            raise ValueError(
                f"visual dict at index {i} is missing required key 'name'"
            ) from exc
        _write_json(
            report_dir
            / "definition"
            / "pages"
            / page_guid
            / "visuals"
            / visual_name
            / "visual.json",
            visual,
        )

    theme_dest = (
        report_dir / "StaticResources" / "SharedResources" / "BaseThemes" / "CY25SU10.json"
    )
    theme_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(_STATIC_DIR / "CY25SU10.json", theme_dest)

    return report_dir


def _new_guid() -> str:
    return uuid.uuid4().hex[:20]


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
