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
    VisualType.MULTI_ROW_CARD: "multiRowCard",
    VisualType.KPI: "kpi",
    VisualType.GAUGE: "gauge",
    VisualType.COLUMN_CHART: "columnChart",
    VisualType.BAR_CHART: "barChart",
    VisualType.LINE_CHART: "lineChart",
    VisualType.SLICER: "slicer",
    VisualType.TABLE: "tableEx",
    VisualType.CLUSTERED_COLUMN_CHART: "clusteredColumnChart",
    VisualType.CLUSTERED_BAR_CHART: "clusteredBarChart",
    VisualType.HUNDRED_PERCENT_STACKED_BAR_CHART: "hundredPercentStackedBarChart",
    VisualType.HUNDRED_PERCENT_STACKED_COLUMN_CHART: "hundredPercentStackedColumnChart",
    VisualType.AREA_CHART: "areaChart",
    VisualType.PIE_CHART: "pieChart",
    VisualType.DONUT_CHART: "donutChart",
    # Catalog flags PBIR visualType for dotPlot as "not confirmed in samples".
    # Using `dotPlot` as the most plausible string; verify against a PBIR sample
    # if the visual fails to render after emit.
    VisualType.DOT_PLOT: "dotPlot",
    VisualType.COMBO_CHART: "lineClusteredColumnComboChart",
    VisualType.TREEMAP: "treemap",
    # Annotation token is "funnelChart"; PBIR visualType is "funnel" (catalog-confirmed).
    VisualType.FUNNEL_CHART: "funnel",
    # Histogram = barChart with axis bin config (no distinct PBIR type).
    VisualType.HISTOGRAM: "barChart",
    VisualType.SCATTER_CHART: "scatterChart",
    # Bubble = scatterChart + Size data role binding (catalog-confirmed: same PBIR type).
    VisualType.BUBBLE_CHART: "scatterChart",
    VisualType.WATERFALL_CHART: "waterfallChart",
    VisualType.RIBBON_CHART: "ribbonChart",
    VisualType.MAP: "map",
    VisualType.FILLED_MAP: "filledMap",
    VisualType.SHAPE_MAP: "shapeMap",
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
        slicer_style = node.attrs.get("data-pbi-style", "dropdown").lower()
        if slicer_style not in ("dropdown", "list", "between"):
            raise ValueError(
                f"data-pbi-style={slicer_style!r} is invalid; use 'dropdown', 'list', or 'between'"
            )
        # Legacy `slicer` visual mode lives on the `data` card as `mode`.
        # PBIR values: 'Dropdown' (compact), 'Basic' (vertical list), 'Between'
        # (range slider). Note 'list' maps to 'Basic' — Power BI's internal name.
        # advancedSlicerVisual's `general.style` is a different property and
        # renders empty tiles for these values, so we use the classic slicer.
        pbi_mode = {"dropdown": "Dropdown", "list": "Basic", "between": "Between"}[slicer_style]
        visual["objects"] = {
            "data": [
                {
                    "properties": {
                        "mode": {"expr": {"Literal": {"Value": f"'{pbi_mode}'"}}}
                    }
                }
            ]
        }
        col_proj = _column_proj(node.attrs["data-pbi-field"])
        filter_type = "Advanced" if slicer_style == "between" else "Categorical"
        container["filterConfig"] = {
            "filters": [
                {
                    "name": _new_guid(),
                    "field": col_proj["field"],
                    "type": filter_type,
                }
            ]
        }
    if vtype is VisualType.HISTOGRAM and "data-pbi-bins" in node.attrs:
        # Bin count is an axis-level property on the underlying barChart.
        # Catalog flags the exact PBIR property name as TBD — using `binCount`
        # as the most likely Power BI property; adjust if a PBIR sample disagrees.
        try:
            bin_count = int(node.attrs["data-pbi-bins"])
        except ValueError as e:
            raise ValueError(
                f"data-pbi-bins must be an integer, got {node.attrs['data-pbi-bins']!r}"
            ) from e
        visual.setdefault("objects", {})["categoryAxis"] = [
            {"properties": {"binCount": {"expr": {"Literal": {"Value": f"{bin_count}L"}}}}}
        ]
    if vtype is VisualType.SHAPE_MAP and "data-pbi-topojson" in node.attrs:
        # Shape Map TopoJSON source — PBIR property name not fully documented in
        # public samples; emitting a placeholder `mapShape` objects entry. Users
        # configuring custom shapes will likely need to set this via Power BI
        # Desktop after open; the path is preserved here for downstream tooling.
        visual.setdefault("objects", {})["mapShape"] = [
            {"properties": {"shapeFile": {"expr": {"Literal": {
                "Value": f"'{node.attrs['data-pbi-topojson']}'"
            }}}}}
        ]
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

    if vtype is VisualType.MULTI_ROW_CARD:
        names = [n.strip() for n in attrs["data-pbi-measures"].split(",") if n.strip()]
        return {"Values": {"projections": [_measure_proj(n, schema) for n in names]}}

    if vtype is VisualType.KPI:
        return {
            "Indicator": {"projections": [_measure_proj(attrs["data-pbi-measure"], schema)]},
            "TrendLine": {"projections": [_column_proj(attrs["data-pbi-trend"], active=True)]},
            "Goals": {"projections": [_measure_proj(attrs["data-pbi-target"], schema)]},
        }

    if vtype is VisualType.GAUGE:
        qs: dict[str, Any] = {
            "Y": {"projections": [_measure_proj(attrs["data-pbi-measure"], schema)]},
        }
        if "data-pbi-min" in attrs:
            qs["MinValue"] = {"projections": [_measure_proj(attrs["data-pbi-min"], schema)]}
        if "data-pbi-max" in attrs:
            qs["MaxValue"] = {"projections": [_measure_proj(attrs["data-pbi-max"], schema)]}
        if "data-pbi-target" in attrs:
            qs["TargetValue"] = {"projections": [_measure_proj(attrs["data-pbi-target"], schema)]}
        return qs

    if vtype is VisualType.DOT_PLOT:
        return {
            "Category": {"projections": [_column_proj(attrs["data-pbi-axis"], active=True)]},
            "X": {"projections": [_measure_proj(attrs["data-pbi-values"], schema)]},
        }

    if vtype is VisualType.COMBO_CHART:
        return {
            "Category": {"projections": [_column_proj(attrs["data-pbi-axis"], active=True)]},
            "Y": {"projections": [_measure_proj(attrs["data-pbi-column-values"], schema)]},
            "Y2": {"projections": [_measure_proj(attrs["data-pbi-line-values"], schema)]},
        }

    if vtype is VisualType.TREEMAP:
        qs = {
            "Group": {"projections": [_column_proj(attrs["data-pbi-group"], active=True)]},
            "Values": {"projections": [_measure_proj(attrs["data-pbi-values"], schema)]},
        }
        if "data-pbi-details" in attrs:
            qs["Details"] = {"projections": [_column_proj(attrs["data-pbi-details"])]}
        return qs

    if vtype is VisualType.FUNNEL_CHART:
        return {
            "Category": {"projections": [_column_proj(attrs["data-pbi-axis"], active=True)]},
            "Y": {"projections": [_measure_proj(attrs["data-pbi-values"], schema)]},
        }

    if vtype is VisualType.HISTOGRAM:
        # Emits as a barChart with the measure on Y. Bin count is applied at the
        # visual `objects` level by build_visual_json (not in queryState).
        return {
            "Y": {"projections": [_measure_proj(attrs["data-pbi-values"], schema)]},
        }

    if vtype in (VisualType.SCATTER_CHART, VisualType.BUBBLE_CHART):
        qs = {
            "X": {"projections": [_measure_proj(attrs["data-pbi-x"], schema)]},
            "Y": {"projections": [_measure_proj(attrs["data-pbi-y"], schema)]},
        }
        if vtype is VisualType.BUBBLE_CHART:
            qs["Size"] = {"projections": [_measure_proj(attrs["data-pbi-size"], schema)]}
        if "data-pbi-details" in attrs:
            qs["Details"] = {"projections": [_column_proj(attrs["data-pbi-details"])]}
        return qs

    if vtype is VisualType.WATERFALL_CHART:
        qs = {
            "Category": {"projections": [_column_proj(attrs["data-pbi-axis"], active=True)]},
            "Y": {"projections": [_measure_proj(attrs["data-pbi-values"], schema)]},
        }
        if "data-pbi-breakdown" in attrs:
            qs["Breakdown"] = {"projections": [_column_proj(attrs["data-pbi-breakdown"])]}
        return qs

    if vtype is VisualType.RIBBON_CHART:
        return {
            "Category": {"projections": [_column_proj(attrs["data-pbi-axis"], active=True)]},
            "Y": {"projections": [_measure_proj(attrs["data-pbi-values"], schema)]},
            "Series": {"projections": [_column_proj(attrs["data-pbi-series"])]},
        }

    if vtype is VisualType.MAP:
        qs = {
            "Location": {"projections": [_column_proj(attrs["data-pbi-location"], active=True)]},
            "Size": {"projections": [_measure_proj(attrs["data-pbi-size"], schema)]},
        }
        if "data-pbi-legend" in attrs:
            qs["Legend"] = {"projections": [_column_proj(attrs["data-pbi-legend"])]}
        return qs

    if vtype in (VisualType.FILLED_MAP, VisualType.SHAPE_MAP):
        return {
            "Location": {"projections": [_column_proj(attrs["data-pbi-location"], active=True)]},
            "Color saturation": {
                "projections": [_measure_proj(attrs["data-pbi-color-saturation"], schema)]
            },
        }

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
