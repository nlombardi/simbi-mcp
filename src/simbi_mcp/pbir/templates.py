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
    # field-param renders as a legacy slicer bound to the param's own column.
    VisualType.FIELD_PARAM: "slicer",
    # Chrome visuals with no data query.
    VisualType.SHAPE: "shape",
    VisualType.TEXT: "textbox",
    VisualType.BUTTON: "actionButton",
}

# Chart visual types whose built-in (per-measure) title is redundant with
# SimBI's separate `text` title visual. We force the container title off so it
# doesn't duplicate/clutter the layout.
_CHART_TITLE_OFF_TYPES: set[VisualType] = {
    VisualType.COLUMN_CHART,
    VisualType.BAR_CHART,
    VisualType.CLUSTERED_COLUMN_CHART,
    VisualType.CLUSTERED_BAR_CHART,
    VisualType.HUNDRED_PERCENT_STACKED_BAR_CHART,
    VisualType.HUNDRED_PERCENT_STACKED_COLUMN_CHART,
    VisualType.LINE_CHART,
    VisualType.AREA_CHART,
}

# Minimum render heights (px) for interactive visuals that clip when too short
# in Power BI Desktop. Heights below the floor are raised; nothing is shrunk.
_MIN_HEIGHT: dict[VisualType, float] = {
    VisualType.SLICER: 40,
    VisualType.FIELD_PARAM: 40,
    VisualType.BUTTON: 32,
    VisualType.TEXT: 24,
}

# Role -> text styling for `text` chrome visuals (textbox textRuns).
_TEXT_ROLE_STYLE: dict[str, dict[str, str]] = {
    "title":    {"fontWeight": "bold", "fontFamily": "Segoe UI", "fontSize": "16pt", "color": "#003087"},
    "subtitle": {"fontWeight": "normal", "fontFamily": "Segoe UI", "fontSize": "12pt", "color": "#475569"},
    "label":    {"fontWeight": "bold", "fontFamily": "Segoe UI", "fontSize": "9pt", "color": "#64748B"},
    "tab":      {"fontWeight": "bold", "fontFamily": "Segoe UI", "fontSize": "11pt", "color": "#003087"},
}


def build_visual_json(
    node: VisualNode,
    z_order: int,
    schema: ModelSchema,
    field_params: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Build the full visual.json dict for a single annotated DOM node.

    `field_params` maps a field-parameter name to its ordered measure names
    (first = the default measure). Charts that bind a value role to a parameter
    via `data-pbi-values-param` look up the param's measures here to emit the
    two-part Y role (default measure projection + fieldParameters array).
    """
    vtype = node.visual_type
    visual: dict[str, Any]
    # Chrome visuals (shape/text/button) have no data binding — no `query`.
    if vtype in (VisualType.SHAPE, VisualType.TEXT, VisualType.BUTTON):
        visual = _build_chrome_visual(vtype, node.attrs, schema)
    else:
        visual = {
            "visualType": _PBI_VISUAL_TYPE[vtype],
            "query": {"queryState": _build_query_state(vtype, node.attrs, schema, field_params)},
            "drillFilterOtherVisuals": True,
        }
    # Charts carry a built-in title that repeats per-measure and duplicates the
    # separate SimBI `text` title visual. Force the container title off.
    if vtype in _CHART_TITLE_OFF_TYPES:
        visual.setdefault("visualContainerObjects", {})["title"] = [
            {"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}
        ]
    # Floor interactive-visual heights so short mockup boxes don't clip in
    # Power BI Desktop. Only raises sub-minimum heights; never shrinks.
    # `between` slicers carry a slider that needs more vertical room than a
    # plain slicer's 40px floor, so bump their floor to 56px.
    floor = _MIN_HEIGHT.get(vtype, 0)
    if vtype is VisualType.SLICER and node.attrs.get("data-pbi-style", "").lower() == "between":
        floor = max(floor, 56)
    height = max(node.height, floor)
    container: dict[str, Any] = {
        "$schema": _VISUAL_SCHEMA,
        "name": _new_guid(),
        "position": {
            "x": node.x,
            "y": node.y,
            "z": z_order,
            "height": height,
            "width": node.width,
            "tabOrder": z_order,
        },
        "visual": visual,
    }
    if "data-pbi-id" in node.attrs:
        # Author-facing stable id, used to resolve bookmark/button targets in a
        # second pass. Stripped from the final visual.json by the writer (it is
        # not a PBIR property). Kept separate from the random `name` guid.
        container["simbiId"] = node.attrs["data-pbi-id"]
    if node.attrs.get("data-pbi-hidden", "").lower() == "true":
        # Power BI's verified top-level container flag for a visual hidden on page
        # load. Applies to ANY visual type (chrome and query-bearing) since it
        # operates on `container` after it is built. Used with bookmarks for
        # view-toggle stacked charts that default to one visible chart.
        container["isHidden"] = True
    if vtype is VisualType.BUTTON:
        # The bookmark ACTION resolves in a later pass once bookmark GUIDs are
        # known. Stash the intent on the container; the writer rewrites it into
        # visualContainerObjects.visualLink (and strips simbiButtonAction).
        action = node.attrs["data-pbi-action"]
        intent: dict[str, str] = {"type": action}
        if action == "bookmark":
            intent["bookmark"] = node.attrs.get("data-pbi-bookmark", "")
        container["simbiButtonAction"] = intent
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
        if slicer_style == "between":
            # Between mode alone renders two numeric input boxes. The draggable
            # slider track/handles are controlled by the separate `slider.show`
            # property, which we must enable to get the slider UI.
            visual["objects"]["slider"] = [
                {"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}
            ]
            # With Responsive ON, the between slider renders oversized round
            # handles. Turning it off yields compact "|" handles (verified in
            # Power BI Desktop: General > Options > Advanced > Responsive off).
            visual["objects"]["general"] = [
                {"properties": {"responsive": {"expr": {"Literal": {"Value": "false"}}}}}
            ]
        # Turn off the slicer's own built-in header (the field name). SimBI
        # emits explicit `text` label visuals above slicers, so the native
        # header just duplicates/clutters.
        visual["objects"]["header"] = [
            {"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}
        ]
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
    if vtype is VisualType.FIELD_PARAM:
        pname = node.attrs["data-pbi-param-name"]
        style = node.attrs.get("data-pbi-style", "tabs").lower()
        # tabs is a styled dropdown for now; visual chrome refined in a later task.
        mode = {"tabs": "Dropdown", "dropdown": "Dropdown", "list": "Basic"}.get(style, "Dropdown")
        visual["objects"] = {
            "data": [
                {"properties": {"mode": {"expr": {"Literal": {"Value": f"'{mode}'"}}}}}
            ],
            # Hide the slicer's built-in header (field name); SimBI emits an
            # explicit `text` label above it.
            "header": [
                {"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}
            ],
        }
        # Single-select slicer bound to the field parameter's own column.
        container["filterConfig"] = {
            "filters": [
                {
                    "name": _new_guid(),
                    "field": {"Column": {
                        "Expression": {"SourceRef": {"Entity": pname}},
                        "Property": pname,
                    }},
                    "type": "Categorical",
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


def _build_chrome_visual(
    vtype: VisualType,
    attrs: dict[str, str],
    schema: ModelSchema | None = None,
) -> dict[str, Any]:
    """Build the `visual` object for a no-query chrome visual (shape/text/button).

    These never carry a `query` key. Fill/stroke/role styling is owned by the
    theme (Task 9); only the structural content (shapeType / paragraph text /
    button label) is emitted here. The button's bookmark action is stashed on
    the container by build_visual_json, not here, because it resolves in a later
    pass once bookmark GUIDs are known.
    `schema` is required when attrs contains `data-pbi-title-measure`.
    """
    visual: dict[str, Any] = {
        "visualType": _PBI_VISUAL_TYPE[vtype],
        "drillFilterOtherVisuals": True,
    }
    if vtype is VisualType.SHAPE:
        shape_kind = attrs.get("data-pbi-shape", "rectangle")
        visual["objects"] = {
            "shape": [
                {"properties": {"tileShape": {"expr": {"Literal": {"Value": f"'{shape_kind}'"}}}}}
            ]
        }
    elif vtype is VisualType.BUTTON:
        label = attrs.get("data-pbi-text", "")
        visual["objects"] = {
            "text": [
                {"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}},
                {
                    "properties": {"text": {"expr": {"Literal": {"Value": f"'{label}'"}}}},
                    "selector": {"id": "default"},
                },
            ]
        }
    else:  # VisualType.TEXT
        text = attrs["data-pbi-text"]
        role = attrs.get("data-pbi-role", "")
        # Start from the role style (copy so we never mutate the module dict).
        # An explicit data-pbi-color overrides the role's color (e.g. white text
        # on a dark band). Only attach textStyle if something was set.
        style = dict(_TEXT_ROLE_STYLE.get(role, {}))
        if "data-pbi-color" in attrs:
            style["color"] = attrs["data-pbi-color"]
        if "data-pbi-title-measure" in attrs:
            # Dynamic title: textRun uses a Measure expr so the displayed text
            # updates whenever the measure value changes (e.g. field parameter
            # selection). The static data-pbi-text serves as the HTML preview
            # fallback only; PBIR gets the live measure expression.
            if schema is None:
                raise ValueError(
                    "data-pbi-title-measure requires a schema to resolve the measure table"
                )
            m = schema.find_measure(attrs["data-pbi-title-measure"])
            run: dict[str, Any] = {
                "expr": {
                    "Measure": {
                        "Expression": {"SourceRef": {"Entity": m.table}},
                        "Property": m.name,
                    }
                }
            }
        else:
            run = {"value": text}
        if style:
            run["textStyle"] = style
        visual["objects"] = {
            "general": [
                {"properties": {"paragraphs": [{"textRuns": [run]}]}}
            ]
        }
    return visual


def _new_guid() -> str:
    return uuid.uuid4().hex[:20]


def _build_query_state(
    vtype: VisualType,
    attrs: dict[str, str],
    schema: ModelSchema,
    field_params: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    if vtype is VisualType.CARD:
        return {"Values": {"projections": [_measure_proj(attrs["data-pbi-measure"], schema)]}}

    if vtype in (VisualType.COLUMN_CHART, VisualType.BAR_CHART):
        y_role = _resolve_y_role(attrs, schema, field_params)
        qs = {
            "Category": {"projections": [_column_proj(attrs["data-pbi-axis"], active=True)]},
            "Y": y_role,
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
            "Y": _resolve_y_role(attrs, schema, field_params),
            "Series": {"projections": [_column_proj(attrs["data-pbi-series"])]},
        }

    if vtype in (VisualType.LINE_CHART, VisualType.AREA_CHART):
        qs: dict[str, Any] = {
            "Category": {"projections": [_column_proj(attrs["data-pbi-axis"], active=True)]},
            "Y": _resolve_y_role(attrs, schema, field_params),
        }
        if "data-pbi-series" in attrs:
            qs["Series"] = {"projections": [_column_proj(attrs["data-pbi-series"])]}
        return qs

    if vtype is VisualType.SLICER:
        return {"Values": {"projections": [_column_proj(attrs["data-pbi-field"])]}}

    if vtype is VisualType.FIELD_PARAM:
        pname = attrs["data-pbi-param-name"]
        return {"Values": {"projections": [{
            "field": {"Column": {
                "Expression": {"SourceRef": {"Entity": pname}},
                "Property": pname,
            }},
            "queryRef": f"{pname}.{pname}",
            "nativeQueryRef": pname,
        }]}}

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


def _resolve_y_role(
    attrs: dict[str, str],
    schema: ModelSchema,
    field_params: dict[str, list[str]] | None,
) -> dict[str, Any]:
    """Build a chart's Y/value role from either a field parameter or a measure.

    When `data-pbi-values-param` is present, returns the two-part param Y dict
    (default measure projection + fieldParameters array). Otherwise returns the
    plain measure projection wrapper.
    """
    if "data-pbi-values-param" in attrs:
        pname = attrs["data-pbi-values-param"]
        measures = (field_params or {}).get(pname)
        if not measures:
            raise ValueError(
                f"Chart uses data-pbi-values-param={pname!r} but no field-param "
                f"node defines it (need a data-pbi='field-param' with data-pbi-param-name={pname!r})."
            )
        return _param_y_role(pname, measures, schema)
    return {"projections": [_measure_proj(attrs["data-pbi-values"], schema)]}


def _param_y_role(param_name: str, measures: list[str], schema: ModelSchema) -> dict[str, Any]:
    """Build the full Y/value role for a field parameter: the default measure
    projection plus the fieldParameters array Power BI uses to recognize the
    parameter. `measures` is the parameter's ordered measure names (first = default)."""
    default_measure = measures[0]
    proj = _measure_proj(default_measure, schema)
    proj["displayName"] = default_measure  # PBI includes displayName on param-driven measures
    return {
        "projections": [proj],
        "fieldParameters": [
            {
                "parameterExpr": {
                    "Column": {
                        "Expression": {"SourceRef": {"Entity": param_name}},
                        "Property": param_name,
                    }
                },
                "index": 0,
                "length": 1,
            }
        ],
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
