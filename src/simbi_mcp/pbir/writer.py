"""PBIR folder writer — generates the full .pbip project structure from visual dicts.

Writes all required files for an openable Power BI .pbip project:
  - <name>.pbip (project entry point)
  - <name>.Report/definition.pbir (dataset reference)
  - <name>.Report/definition/version.json
  - <name>.Report/definition/report.json (static template)
  - <name>.Report/definition/pages/pages.json
  - <name>.Report/definition/pages/<page-guid>/page.json
  - <name>.Report/definition/pages/<page-guid>/visuals/<visual-guid>/visual.json
  - <name>.Report/StaticResources/SharedResources/BaseThemes/CY25SU10.json
  - <name>.SemanticModel/definition.pbism (stub — generated from ModelSchema)
  - <name>.SemanticModel/model.bim (empty-partition BIM model for PBI to open)
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from simbi_mcp.types import ModelSchema

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


_FORMAT_STRING: dict[str, str] = {
    "currency": "\\$#,0.00",
    "integer": "#,0",
    "percentage": "0.00%",
}


def write_semantic_model_stub(
    schema: ModelSchema,
    report_name: str,
    output_dir: Path,
) -> Path:
    """Write a minimal SemanticModel folder from a ModelSchema.

    Creates <report_name>.SemanticModel/ with definition.pbism and model.bim.
    The model has the correct table/column/measure structure but empty data
    partitions, so Power BI Desktop can open and display the report layout.
    Returns the path to the created SemanticModel folder.
    """
    model_dir = output_dir / f"{report_name}.SemanticModel"
    _write_json(model_dir / "definition.pbism", {"version": "4.2", "settings": {}})

    tables = []
    for table in schema.tables:
        columns = [
            {
                "name": col,
                "dataType": "string",
                "sourceColumn": col,
                "summarizeBy": "none",
            }
            for col in table.columns
        ]
        measures = [
            {
                "name": m.name,
                "expression": m.expression,
                "formatString": _FORMAT_STRING.get(m.return_type, "#,0.##"),
            }
            for m in schema.measures
            if m.table == table.name
        ]
        col_list = ", ".join(f'"{c}"' for c in table.columns)
        partition_expr = [
            "let",
            f"    Source = Table.FromRows({{}}, {{{col_list}}})",
            "in",
            "    Source",
        ]
        tables.append(
            {
                "name": table.name,
                "columns": columns,
                "measures": measures,
                "partitions": [
                    {
                        "name": table.name,
                        "mode": "import",
                        "source": {"type": "m", "expression": partition_expr},
                    }
                ],
            }
        )

    relationships = [
        {
            "name": f"rel_{i}",
            "fromTable": r.from_table,
            "fromColumn": r.from_column,
            "toTable": r.to_table,
            "toColumn": r.to_column,
        }
        for i, r in enumerate(schema.relationships)
    ]

    bim = {
        "compatibilityLevel": 1550,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True,
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": tables,
            "relationships": relationships,
        },
    }
    _write_json(model_dir / "model.bim", bim)
    return model_dir


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

    _write_json(
        output_dir / f"{report_name}.pbip",
        {
            "version": "1.0",
            "artifacts": [{"report": {"path": f"{report_name}.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )

    return report_dir


def _new_guid() -> str:
    return uuid.uuid4().hex[:20]


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
