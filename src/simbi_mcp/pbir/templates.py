"""PBIR visual JSON template builders.

Pure functions: VisualNode + ModelSchema → visual.json dict.
No I/O, no Playwright. Each function corresponds to one Power BI visual type.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from simbi_mcp.mockup.annotations import VisualType
from simbi_mcp.pbir.extractor import VisualNode
from simbi_mcp.types import ModelSchema

_COL_REF_RE = re.compile(r"^(.+)\[(.+)\]$")

_VISUAL_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report"
    "/definition/visualContainer/2.3.0/schema.json"
)

# Maps our annotation VisualType to the Power BI visualType string in JSON.
# "table" in our vocabulary maps to "tableEx" — Power BI's internal type name.
_PBI_VISUAL_TYPE: dict[VisualType, str] = {
    VisualType.CARD: "card",
    VisualType.COLUMN_CHART: "columnChart",
    VisualType.BAR_CHART: "barChart",
    VisualType.LINE_CHART: "lineChart",
    VisualType.SLICER: "advancedSlicerVisual",
    VisualType.TABLE: "tableEx",
    VisualType.CLUSTERED_COLUMN_CHART: "clusteredColumnChart",
    VisualType.CLUSTERED_BAR_CHART: "clusteredBarChart",
    VisualType.HUNDRED_PERCENT_STACKED_BAR_CHART: "hundredPercentStackedBarChart",
    VisualType.HUNDRED_PERCENT_STACKED_COLUMN_CHART: "hundredPercentStackedColumnChart",
    VisualType.AREA_CHART: "areaChart",
    VisualType.PIE_CHART: "pieChart",
    VisualType.DONUT_CHART: "donutChart",
}


def build_visual_json(
    node: VisualNode,
    z_order: int,
    schema: ModelSchema,
) -> dict[str, Any]:
    """Build the full visual.json dict for a single annotated DOM node."""
    vtype = node.visual_type
    visual: dict[str, Any] = {
        "visualType": _PBI_VISUAL_TYPE[vtype],
        "query": {"queryState": _build_query_state(vtype, node.attrs, schema)},
        "drillFilterOtherVisuals": True,
    }
    container: dict[str, Any] = {
        "$schema": _VISUAL_SCHEMA,
        "name": _new_guid(),
        "position": {
            "x": node.x,
            "y": node.y,
            "z": z_order,
            "height": node.height,
            "width": node.width,
            "tabOrder": z_order,
        },
        "visual": visual,
    }
    if vtype is VisualType.SLICER:
        visual["objects"] = {"general": [{"properties": {}}]}
        col_proj = _column_proj(node.attrs["data-pbi-field"])
        container["filterConfig"] = {
            "filters": [
                {
                    "name": _new_guid(),
                    "field": col_proj["field"],
                    "type": "Categorical",
                }
            ]
        }
    return container


def _new_guid() -> str:
    return uuid.uuid4().hex[:20]


def _build_query_state(
    vtype: VisualType,
    attrs: dict[str, str],
    schema: ModelSchema,
) -> dict[str, Any]:
    if vtype is VisualType.CARD:
        return {"Values": {"projections": [_measure_proj(attrs["data-pbi-measure"], schema)]}}

    if vtype in (VisualType.COLUMN_CHART, VisualType.BAR_CHART):
        qs = {
            "Category": {"projections": [_column_proj(attrs["data-pbi-axis"], active=True)]},
            "Y": {"projections": [_measure_proj(attrs["data-pbi-values"], schema)]},
        }
        if "data-pbi-series" in attrs:
            qs["Series"] = {"projections": [_column_proj(attrs["data-pbi-series"])]}
        return qs

    if vtype in (VisualType.PIE_CHART, VisualType.DONUT_CHART):
        return {
            "Category": {"projections": [_column_proj(attrs["data-pbi-axis"], active=True)]},
            "Y": {"projections": [_measure_proj(attrs["data-pbi-values"], schema)]},
        }

    if vtype in (
        VisualType.CLUSTERED_COLUMN_CHART,
        VisualType.CLUSTERED_BAR_CHART,
        VisualType.HUNDRED_PERCENT_STACKED_BAR_CHART,
        VisualType.HUNDRED_PERCENT_STACKED_COLUMN_CHART,
    ):
        return {
            "Category": {"projections": [_column_proj(attrs["data-pbi-axis"], active=True)]},
            "Y": {"projections": [_measure_proj(attrs["data-pbi-values"], schema)]},
            "Series": {"projections": [_column_proj(attrs["data-pbi-series"])]},
        }

    if vtype in (VisualType.LINE_CHART, VisualType.AREA_CHART):
        qs: dict[str, Any] = {
            "Category": {"projections": [_column_proj(attrs["data-pbi-axis"], active=True)]},
            "Y": {"projections": [_measure_proj(attrs["data-pbi-values"], schema)]},
        }
        if "data-pbi-series" in attrs:
            qs["Series"] = {"projections": [_column_proj(attrs["data-pbi-series"])]}
        return qs

    if vtype is VisualType.SLICER:
        return {"Values": {"projections": [_column_proj(attrs["data-pbi-field"])]}}

    if vtype is VisualType.TABLE:
        tokens = [n.strip() for n in attrs["data-pbi-columns"].split(",") if n.strip()]
        projections: list[dict[str, Any]] = []
        for token in tokens:
            if _COL_REF_RE.match(token):
                projections.append(_column_proj(token))
            else:
                projections.append(_measure_proj(token, schema))
        return {"Values": {"projections": projections}}

    raise ValueError(f"Unsupported visual type: {vtype!r}")


def _measure_proj(name: str, schema: ModelSchema) -> dict[str, Any]:
    m = schema.find_measure(name)
    return {
        "field": {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": m.table}},
                "Property": name,
            }
        },
        "queryRef": f"{m.table}.{name}",
        "nativeQueryRef": name,
    }


def _column_proj(ref: str, active: bool = False) -> dict[str, Any]:
    match = _COL_REF_RE.match(ref)
    if not match:
        raise ValueError(f"Invalid column reference {ref!r} — expected Table[Column]")
    table, col = match.group(1), match.group(2)
    proj: dict[str, Any] = {
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": table}},
                "Property": col,
            }
        },
        "queryRef": f"{table}.{col}",
        "nativeQueryRef": col,
    }
    if active:
        proj["active"] = True
    return proj
