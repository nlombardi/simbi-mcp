"""PBIR Report folder writer — generates only the .Report half of a .pbip project.

The .pbip and .SemanticModel are produced by Power BI Desktop / Power BI MCP;
SimBI never creates or touches them. This writer outputs only:
  - <name>.Report/definition.pbir (dataset reference)
  - <name>.Report/definition/version.json
  - <name>.Report/definition/report.json (static template)
  - <name>.Report/definition/pages/pages.json
  - <name>.Report/definition/pages/<page-guid>/page.json
  - <name>.Report/definition/pages/<page-guid>/visuals/<visual-guid>/visual.json
  - <name>.Report/StaticResources/SharedResources/BaseThemes/<theme-name>.json
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


def _report_json(theme_name: str) -> dict[str, Any]:
    return {
        "$schema": _REPORT_SCHEMA,
        "themeCollection": {
            "baseTheme": {
                "name": theme_name,
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
                    {"name": theme_name, "path": f"BaseThemes/{theme_name}.json", "type": "BaseTheme"}
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
    theme: dict[str, Any] | None = None,
) -> Path:
    """Write the PBIR Report folder and return its path.

    The folder is named <report_name>.Report and created inside output_dir.
    semantic_model_rel_path defaults to ../<report_name>.SemanticModel, which
    places it as a sibling of the Report folder — the standard Power BI layout.

    `theme` is a fully-resolved PBIR theme dict (typically from
    simbi_mcp.pbir.theme.resolve_theme). When None, the static SimBIDefault
    theme is loaded from disk — preserving backward compatibility for callers
    that haven't been updated.
    """
    if semantic_model_rel_path is None:
        semantic_model_rel_path = f"../{report_name}.SemanticModel"

    if theme is None:
        # Lazy import keeps theme module out of writer's import path for callers
        # that pass an explicit theme dict (the common case from emit_pbir).
        from simbi_mcp.pbir.theme import resolve_theme
        theme = resolve_theme(user_theme_path=None)

    theme_name = theme.get("name") or "SimBIDefault"

    report_dir = output_dir / f"{report_name}.Report"

    # Wipe any previous pages/ so repeated emit_report calls don't accumulate
    # orphaned page-GUID folders that Power BI Desktop chokes on.
    pages_dir = report_dir / "definition" / "pages"
    if pages_dir.exists():
        shutil.rmtree(pages_dir)

    # Also clear out any stale theme JSON from a previous emit so a renamed
    # theme doesn't leave orphan files alongside the active one.
    base_themes_dir = report_dir / "StaticResources" / "SharedResources" / "BaseThemes"
    if base_themes_dir.exists():
        shutil.rmtree(base_themes_dir)

    page_guid = _new_guid()

    _write_json(
        report_dir / "definition.pbir",
        {"version": "4.0", "datasetReference": {"byPath": {"path": semantic_model_rel_path}}},
    )
    _write_json(
        report_dir / "definition" / "version.json",
        {"$schema": _VERSION_SCHEMA, "version": "2.0.0"},
    )
    _write_json(report_dir / "definition" / "report.json", _report_json(theme_name))
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

    theme_dest = base_themes_dir / f"{theme_name}.json"
    theme_dest.parent.mkdir(parents=True, exist_ok=True)
    theme_dest.write_text(json.dumps(theme, indent=2), encoding="utf-8")

    return report_dir


def _new_guid() -> str:
    return uuid.uuid4().hex[:20]


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
