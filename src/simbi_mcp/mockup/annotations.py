"""Annotation vocabulary for SimBI HTML mockups.

These constants define the data-pbi-* attribute contract between Phase 2
(HTML generator) and Phase 3 (PBIR emitter). Change only with coordination.
"""
from __future__ import annotations

from enum import StrEnum
from typing import TypedDict


class VisualSpec(TypedDict):
    required: dict[str, str]  # attr -> one-line description incl. value shape
    optional: dict[str, str]
    note: str                 # per-type callout, "" when none


class VisualType(StrEnum):
    CARD = "card"
    MULTI_ROW_CARD = "multiRowCard"
    KPI = "kpi"
    GAUGE = "gauge"
    COLUMN_CHART = "columnChart"   # vertical bars (PBI's name; X = category, Y = value)
    BAR_CHART = "barChart"         # horizontal bars (Y = category, X = value)
    LINE_CHART = "lineChart"
    SLICER = "slicer"
    TABLE = "table"
    CLUSTERED_COLUMN_CHART = "clusteredColumnChart"
    CLUSTERED_BAR_CHART = "clusteredBarChart"
    HUNDRED_PERCENT_STACKED_BAR_CHART = "hundredPercentStackedBarChart"
    HUNDRED_PERCENT_STACKED_COLUMN_CHART = "hundredPercentStackedColumnChart"
    AREA_CHART = "areaChart"
    PIE_CHART = "pieChart"
    DONUT_CHART = "donutChart"
    DOT_PLOT = "dotPlot"
    COMBO_CHART = "comboChart"
    TREEMAP = "treemap"
    FUNNEL_CHART = "funnelChart"
    HISTOGRAM = "histogram"
    SCATTER_CHART = "scatterChart"
    BUBBLE_CHART = "bubbleChart"
    WATERFALL_CHART = "waterfallChart"
    RIBBON_CHART = "ribbonChart"
    MAP = "map"
    FILLED_MAP = "filledMap"
    SHAPE_MAP = "shapeMap"
    FIELD_PARAM = "field-param"
    SHAPE = "shape"
    TEXT = "text"
    BUTTON = "button"
    BOOKMARK = "bookmark"


# Attributes valid on EVERY visual type. Documented once, validated everywhere.
UNIVERSAL_ATTRS: dict[str, str] = {
    "data-pbi-id": (
        '"<stable id>" — author-chosen id for THIS visual. Bookmarks and buttons '
        "reference it via data-pbi-visible/data-pbi-hidden/data-pbi-target. "
        "Required on any visual a bookmark toggles."
    ),
    "data-pbi-hidden": (
        '"true" — visual starts hidden on page load (emits isHidden on the '
        "container). Used with bookmarks for view toggles."
    ),
}

_VALUES_PARAM_DESC = (
    '"<ParamName>" — (optional) bind the value role to a field parameter '
    "instead of data-pbi-values"
)

# Required and optional data-pbi-* attributes per visual type.
# Phase 3 uses this same dict to know which attributes to read.
VISUAL_ATTRS: dict[VisualType, VisualSpec] = {
    VisualType.CARD: {
        "required": {"data-pbi-measure": '"<Measure Name>" — exact measure name from the schema'},
        "optional": {},
        "note": "",
    },
    VisualType.MULTI_ROW_CARD: {
        "required": {"data-pbi-measures": '"<M1>, <M2>, ..." — comma-separated measure names'},
        "optional": {},
        "note": "",
    },
    VisualType.KPI: {
        "required": {
            "data-pbi-measure": '"<Indicator Measure>" — actual / current measure',
            "data-pbi-target": '"<Target Measure>" — goal measure',
            "data-pbi-trend": '"<Table>[<Column>]" — date column for trend axis',
        },
        "optional": {},
        "note": "",
    },
    VisualType.GAUGE: {
        "required": {"data-pbi-measure": '"<Value Measure>" — current value (needle)'},
        "optional": {
            "data-pbi-min": '"<Measure>" — minimum (arc start)',
            "data-pbi-max": '"<Measure>" — maximum (arc end)',
            "data-pbi-target": '"<Measure>" — target marker',
        },
        "note": "",
    },
    VisualType.COLUMN_CHART: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — dimension column for the X axis',
            "data-pbi-values": '"<Measure Name>" — measure for the Y axis (bar height)',
        },
        "optional": {
            "data-pbi-series": '"<Table>[<Column>]" — series/legend split (renders as stacked column)',
            "data-pbi-values-param": _VALUES_PARAM_DESC,
        },
        "note": "VERTICAL bars (category on X). This is what most people call a 'bar chart'.",
    },
    VisualType.BAR_CHART: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — category column, placed on the Y axis',
            "data-pbi-values": '"<Measure Name>" — measure for the X axis (bar length)',
        },
        "optional": {
            "data-pbi-series": '"<Table>[<Column>]" — series/legend split (renders as stacked bar)',
            "data-pbi-values-param": _VALUES_PARAM_DESC,
        },
        "note": (
            "⚠ HORIZONTAL bars — category on Y, value on X (Power BI naming). "
            "For vertical bars (e.g. years along the X axis) use columnChart."
        ),
    },
    VisualType.LINE_CHART: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — dimension for the X axis',
            "data-pbi-values": '"<Measure Name>" — measure for the Y axis',
        },
        "optional": {
            "data-pbi-series": '"<Table>[<Column>]" — series/legend split',
            "data-pbi-values-param": _VALUES_PARAM_DESC,
        },
        "note": "",
    },
    VisualType.SLICER: {
        "required": {"data-pbi-field": '"<Table>[<Column>]" — field to filter on'},
        "optional": {
            "data-pbi-style": (
                '"dropdown|list|between" — slicer style; DEFAULT "dropdown" when omitted. '
                'Use "between" for numeric/date ranges, "list" for short enums shown inline. '
                "Set it explicitly — the default is right only for text/category fields."
            ),
        },
        "note": "",
    },
    VisualType.TABLE: {
        "required": {
            "data-pbi-columns": (
                '"<tok1>,<tok2>,..." — comma-separated mix of bare measure names and '
                "Table[Column] refs. Column tokens become row groupings; measure tokens "
                "become aggregated value columns."
            ),
        },
        "optional": {},
        "note": "",
    },
    VisualType.CLUSTERED_COLUMN_CHART: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — dimension column for the X axis',
            "data-pbi-values": '"<Measure Name>" — measure for the Y axis',
            "data-pbi-series": '"<Table>[<Column>]" — series/legend split for clusters',
        },
        "optional": {"data-pbi-values-param": _VALUES_PARAM_DESC},
        "note": "VERTICAL clustered bars (category on X).",
    },
    VisualType.CLUSTERED_BAR_CHART: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — category column, placed on the Y axis',
            "data-pbi-values": '"<Measure Name>" — measure for the X axis',
            "data-pbi-series": '"<Table>[<Column>]" — series/legend split for clusters',
        },
        "optional": {"data-pbi-values-param": _VALUES_PARAM_DESC},
        "note": "⚠ HORIZONTAL clustered bars. For vertical clusters use clusteredColumnChart.",
    },
    VisualType.HUNDRED_PERCENT_STACKED_BAR_CHART: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — category column, placed on the Y axis',
            "data-pbi-values": '"<Measure Name>" — measure for the X axis',
            "data-pbi-series": '"<Table>[<Column>]" — series/legend split for stacking',
        },
        "optional": {"data-pbi-values-param": _VALUES_PARAM_DESC},
        "note": "⚠ HORIZONTAL 100% stacked bars. For vertical use hundredPercentStackedColumnChart.",
    },
    VisualType.HUNDRED_PERCENT_STACKED_COLUMN_CHART: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — dimension column for the X axis',
            "data-pbi-values": '"<Measure Name>" — measure for the Y axis',
            "data-pbi-series": '"<Table>[<Column>]" — series/legend split for stacking',
        },
        "optional": {"data-pbi-values-param": _VALUES_PARAM_DESC},
        "note": "VERTICAL 100% stacked bars (category on X).",
    },
    VisualType.AREA_CHART: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — dimension for the X axis',
            "data-pbi-values": '"<Measure Name>" — measure for the Y axis',
        },
        "optional": {
            "data-pbi-series": '"<Table>[<Column>]" — series/legend split (renders as stacked area)',
            "data-pbi-values-param": _VALUES_PARAM_DESC,
        },
        "note": "",
    },
    VisualType.PIE_CHART: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — category dimension for slices',
            "data-pbi-values": '"<Measure Name>" — measure for slice size',
        },
        "optional": {},
        "note": "Max 5 slices — use a sorted barChart beyond that.",
    },
    VisualType.DONUT_CHART: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — category dimension for slices',
            "data-pbi-values": '"<Measure Name>" — measure for slice size',
        },
        "optional": {},
        "note": "Max 5 slices — use a sorted barChart beyond that.",
    },
    VisualType.DOT_PLOT: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — category column',
            "data-pbi-values": '"<Measure Name>" — measure plotted as dot position',
        },
        "optional": {},
        "note": "",
    },
    VisualType.COMBO_CHART: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — shared dimension for the X axis',
            "data-pbi-column-values": '"<Measure>" — measure rendered as columns',
            "data-pbi-line-values": '"<Measure>" — measure rendered as line',
        },
        "optional": {},
        "note": "",
    },
    VisualType.TREEMAP: {
        "required": {
            "data-pbi-group": '"<Table>[<Column>]" — primary category column',
            "data-pbi-values": '"<Measure Name>" — measure for rectangle size',
        },
        "optional": {"data-pbi-details": '"<Table>[<Column>]" — secondary hierarchy column'},
        "note": "",
    },
    VisualType.FUNNEL_CHART: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — stage column (preserve source order)',
            "data-pbi-values": '"<Measure Name>" — measure per stage',
        },
        "optional": {},
        "note": "",
    },
    VisualType.HISTOGRAM: {
        "required": {"data-pbi-values": '"<Measure Name>" — measure to bin'},
        "optional": {"data-pbi-bins": '"<int>" — bin count (integer literal, not schema-checked)'},
        "note": "Renders as a binned barChart in PBIR.",
    },
    VisualType.SCATTER_CHART: {
        "required": {
            "data-pbi-x": '"<X Measure>" — measure on the X axis',
            "data-pbi-y": '"<Y Measure>" — measure on the Y axis',
        },
        "optional": {"data-pbi-details": '"<Table>[<Column>]" — per-point label/group'},
        "note": "",
    },
    VisualType.BUBBLE_CHART: {
        "required": {
            "data-pbi-x": '"<X Measure>" — measure on the X axis',
            "data-pbi-y": '"<Y Measure>" — measure on the Y axis',
            "data-pbi-size": '"<Size Measure>" — measure for bubble size',
        },
        "optional": {"data-pbi-details": '"<Table>[<Column>]" — per-point label/group'},
        "note": "",
    },
    VisualType.WATERFALL_CHART: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — ordered category/stage column',
            "data-pbi-values": '"<Measure Name>" — delta measure per category',
        },
        "optional": {"data-pbi-breakdown": '"<Table>[<Column>]" — sub-group dimension'},
        "note": "",
    },
    VisualType.RIBBON_CHART: {
        "required": {
            "data-pbi-axis": '"<Table>[<Column>]" — time/period column',
            "data-pbi-values": '"<Measure Name>" — measure determining rank',
            "data-pbi-series": '"<Table>[<Column>]" — ranked category column',
        },
        "optional": {},
        "note": "Rank changes over time.",
    },
    VisualType.MAP: {
        "required": {
            "data-pbi-location": '"<Table>[<Column>]" — place/lat-lon column',
            "data-pbi-size": '"<Size Measure>" — bubble size measure',
        },
        "optional": {"data-pbi-legend": '"<Table>[<Column>]" — category legend'},
        "note": "Bubble map; requires Bing geocoding in tenant.",
    },
    VisualType.FILLED_MAP: {
        "required": {
            "data-pbi-location": '"<Table>[<Column>]" — region column',
            "data-pbi-color-saturation": '"<Measure>" — measure driving fill intensity',
        },
        "optional": {},
        "note": "Choropleth; requires Bing geocoding in tenant.",
    },
    VisualType.SHAPE_MAP: {
        "required": {
            "data-pbi-location": '"<Table>[<Column>]" — region-key column matching TopoJSON',
            "data-pbi-color-saturation": '"<Measure>" — measure driving fill intensity',
        },
        "optional": {"data-pbi-topojson": '"<path-or-url>" — user-supplied TopoJSON (not schema-checked)'},
        "note": "Custom TopoJSON regions.",
    },
    VisualType.FIELD_PARAM: {
        "required": {
            "data-pbi-param-name": '"<ParamName>" — field parameter table/column name',
            "data-pbi-measures": '"<M1>, <M2>, ..." — comma-separated measures the param switches between',
        },
        "optional": {"data-pbi-style": '"tabs|dropdown|list" — slicer style; default "tabs"'},
        "note": "Emits a slicer bound to the field parameter's own column.",
    },
    VisualType.SHAPE: {
        "required": {},
        "optional": {
            "data-pbi-shape": '"rectangle|line" — shape kind; default "rectangle"',
            "data-pbi-fill": '"<color>" — fill color; overrides the element\'s CSS background-color',
            "data-pbi-stroke": '"<color>" — outline color; overrides the element\'s CSS border color',
        },
        "note": (
            "Chrome rectangle/line, no data query. Fill/outline come from data-pbi-fill/"
            "data-pbi-stroke or, when absent, the element's own CSS background-color/border."
        ),
    },
    VisualType.TEXT: {
        "required": {
            "data-pbi-text": (
                '"<literal text>" — text content (shown as-is, or used as fallback label '
                "when data-pbi-title-measure is set)"
            ),
        },
        "optional": {
            "data-pbi-role": '"title|subtitle|label|tab" — styling role (applied by theme)',
            "data-pbi-color": '"#RRGGBB" — overrides the role color (use white on dark backgrounds)',
            "data-pbi-title-measure": (
                '"<MeasureName>" — binds the textbox text to a DAX measure so the title '
                "updates dynamically (measure must return a string); data-pbi-text stays "
                "as the HTML preview fallback"
            ),
        },
        "note": "Chrome textbox, no data query.",
    },
    VisualType.BUTTON: {
        "required": {"data-pbi-action": '"bookmark|navigate|back|reset|blank" — button behavior'},
        "optional": {
            "data-pbi-text": '"<label>" — button label text',
            "data-pbi-bookmark": '"<Bookmark Name>" — target bookmark (required when action="bookmark")',
        },
        "note": "Chrome action button, no data query.",
    },
    VisualType.BOOKMARK: {
        "required": {
            "data-pbi-name": '"<Bookmark Name>" — display name buttons reference via data-pbi-bookmark',
        },
        "optional": {
            "data-pbi-captures": '"visibility,data,..." — captured aspects (default none)',
            "data-pbi-target": '"<id1>,<id2>" — data-pbi-id list it applies to; default all',
            "data-pbi-visible": '"<id1>,<id2>" — data-pbi-id list shown',
            "data-pbi-hidden": '"<id1>,<id2>" — data-pbi-id list hidden',
        },
        "note": "Page-state metadata — emits no visual; wires buttons/visibility.",
    },
}

# Concrete correct-shape example per visual type — appended to every error
# so the LLM client gets an actionable template, not just a complaint.
EXAMPLES: dict[VisualType, str] = {
    VisualType.CARD: '<div data-pbi="card" data-pbi-measure="Total Revenue"></div>',
    VisualType.COLUMN_CHART: (
        '<div data-pbi="columnChart" data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue"></div>'
    ),
    VisualType.BAR_CHART: (
        '<div data-pbi="barChart" data-pbi-id="chartByRegion" data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue"></div>'
    ),
    VisualType.LINE_CHART: (
        '<div data-pbi="lineChart" data-pbi-id="chartTrend" data-pbi-axis="sales[OrderDate]" '
        'data-pbi-values="Total Revenue"></div>'
    ),
    VisualType.SLICER: '<div data-pbi="slicer" data-pbi-field="sales[Region]"></div>',
    VisualType.TABLE: (
        '<div data-pbi="table" '
        'data-pbi-columns="sales[Region],Total Revenue,Order Count"></div>'
    ),
    VisualType.CLUSTERED_COLUMN_CHART: (
        '<div data-pbi="clusteredColumnChart" data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue" data-pbi-series="sales[OrderDate]"></div>'
    ),
    VisualType.CLUSTERED_BAR_CHART: (
        '<div data-pbi="clusteredBarChart" data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue" data-pbi-series="sales[OrderDate]"></div>'
    ),
    VisualType.HUNDRED_PERCENT_STACKED_BAR_CHART: (
        '<div data-pbi="hundredPercentStackedBarChart" data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue" data-pbi-series="sales[OrderDate]"></div>'
    ),
    VisualType.HUNDRED_PERCENT_STACKED_COLUMN_CHART: (
        '<div data-pbi="hundredPercentStackedColumnChart" data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue" data-pbi-series="sales[OrderDate]"></div>'
    ),
    VisualType.AREA_CHART: (
        '<div data-pbi="areaChart" data-pbi-axis="sales[OrderDate]" '
        'data-pbi-values="Total Revenue"></div>'
    ),
    VisualType.PIE_CHART: (
        '<div data-pbi="pieChart" data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue"></div>'
    ),
    VisualType.DONUT_CHART: (
        '<div data-pbi="donutChart" data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue"></div>'
    ),
    VisualType.MULTI_ROW_CARD: (
        '<div data-pbi="multiRowCard" '
        'data-pbi-measures="Total Revenue,Order Count"></div>'
    ),
    VisualType.KPI: (
        '<div data-pbi="kpi" data-pbi-measure="Total Revenue" '
        'data-pbi-target="Revenue Target" data-pbi-trend="sales[OrderDate]"></div>'
    ),
    VisualType.GAUGE: (
        '<div data-pbi="gauge" data-pbi-measure="Total Revenue" '
        'data-pbi-target="Revenue Target"></div>'
    ),
    VisualType.DOT_PLOT: (
        '<div data-pbi="dotPlot" data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue"></div>'
    ),
    VisualType.COMBO_CHART: (
        '<div data-pbi="comboChart" data-pbi-axis="sales[OrderDate]" '
        'data-pbi-column-values="Total Revenue" data-pbi-line-values="Gross Margin"></div>'
    ),
    VisualType.TREEMAP: (
        '<div data-pbi="treemap" data-pbi-group="sales[Region]" '
        'data-pbi-values="Total Revenue"></div>'
    ),
    VisualType.FUNNEL_CHART: (
        '<div data-pbi="funnelChart" data-pbi-axis="sales[Stage]" '
        'data-pbi-values="Lead Count"></div>'
    ),
    VisualType.HISTOGRAM: (
        '<div data-pbi="histogram" data-pbi-values="Order Value" data-pbi-bins="20"></div>'
    ),
    VisualType.SCATTER_CHART: (
        '<div data-pbi="scatterChart" data-pbi-x="Ad Spend" '
        'data-pbi-y="Total Revenue" data-pbi-details="sales[Market]"></div>'
    ),
    VisualType.BUBBLE_CHART: (
        '<div data-pbi="bubbleChart" data-pbi-x="Ad Spend" '
        'data-pbi-y="Total Revenue" data-pbi-size="Order Count" '
        'data-pbi-details="sales[Market]"></div>'
    ),
    VisualType.WATERFALL_CHART: (
        '<div data-pbi="waterfallChart" data-pbi-axis="sales[Driver]" '
        'data-pbi-values="Variance"></div>'
    ),
    VisualType.RIBBON_CHART: (
        '<div data-pbi="ribbonChart" data-pbi-axis="sales[OrderDate]" '
        'data-pbi-values="Total Revenue" data-pbi-series="sales[Category]"></div>'
    ),
    VisualType.MAP: (
        '<div data-pbi="map" data-pbi-location="sales[City]" '
        'data-pbi-size="Total Revenue"></div>'
    ),
    VisualType.FILLED_MAP: (
        '<div data-pbi="filledMap" data-pbi-location="sales[Country]" '
        'data-pbi-color-saturation="Total Revenue"></div>'
    ),
    VisualType.SHAPE_MAP: (
        '<div data-pbi="shapeMap" data-pbi-location="sales[Territory]" '
        'data-pbi-color-saturation="Total Revenue"></div>'
    ),
    VisualType.FIELD_PARAM: (
        '<div data-pbi="field-param" data-pbi-param-name="Indicator" '
        'data-pbi-measures="Total Revenue,Order Count"></div>'
    ),
    VisualType.SHAPE: '<div data-pbi="shape" data-pbi-shape="rectangle"></div>',
    VisualType.TEXT: '<div data-pbi="text" data-pbi-text="Section Title" data-pbi-role="title"></div>',
    VisualType.BUTTON: '<div data-pbi="button" data-pbi-action="bookmark" data-pbi-bookmark="View: Bar" data-pbi-text="Bar"></div>',
    VisualType.BOOKMARK: '<div data-pbi="bookmark" data-pbi-name="View: Bar" data-pbi-captures="visibility" data-pbi-visible="chartBar" data-pbi-hidden="chartLine"></div>',
}

# Embedded in generator system prompt — tells Claude the annotation vocabulary.
ANNOTATION_SPEC_TEXT: str = """\
ANNOTATION VOCABULARY
=====================
Every visual must have a data-pbi attribute identifying its type, plus the
required data-pbi-* attributes shown below.

  card
    data-pbi-measure="<Measure Name>"      ← exact measure name from the schema

  multiRowCard
    data-pbi-measures="<M1>, <M2>, ..."    ← comma-separated measure names

  kpi
    data-pbi-measure="<Indicator Measure>" ← actual / current measure
    data-pbi-target="<Target Measure>"     ← goal measure
    data-pbi-trend="<Table>[<Column>]"     ← date column for trend axis

  gauge
    data-pbi-measure="<Value Measure>"     ← current value (needle)
    data-pbi-min="<Measure>"               ← (optional) minimum (arc start)
    data-pbi-max="<Measure>"               ← (optional) maximum (arc end)
    data-pbi-target="<Measure>"            ← (optional) target marker

  columnChart      (vertical bars — category on X axis)
    data-pbi-axis="<Table>[<Column>]"      ← dimension column for X axis
    data-pbi-values="<Measure Name>"       ← measure for Y axis
    data-pbi-series="<Table>[<Column>]"    ← (optional) series/legend split (renders as stacked column)
    data-pbi-values-param="<ParamName>"    ← (optional) bind Y to a field parameter instead of data-pbi-values

  clusteredColumnChart (clustered vertical bars — category on X, series split)
    data-pbi-axis="<Table>[<Column>]"      ← dimension column for X axis
    data-pbi-values="<Measure Name>"       ← measure for Y axis
    data-pbi-series="<Table>[<Column>]"    ← series/legend split for clusters
    data-pbi-values-param="<ParamName>"    ← (optional) bind Y to a field parameter instead of data-pbi-values

  hundredPercentStackedColumnChart (100% stacked vertical bars — category on X)
    data-pbi-axis="<Table>[<Column>]"      ← dimension column for X axis
    data-pbi-values="<Measure Name>"       ← measure for Y axis
    data-pbi-series="<Table>[<Column>]"    ← series/legend split for stacking
    data-pbi-values-param="<ParamName>"    ← (optional) bind Y to a field parameter instead of data-pbi-values

  barChart         (horizontal bars — category on Y axis)
    data-pbi-axis="<Table>[<Column>]"      ← dimension column for Y axis
    data-pbi-values="<Measure Name>"       ← measure for X axis
    data-pbi-series="<Table>[<Column>]"    ← (optional) series/legend split (renders as stacked bar)
    data-pbi-values-param="<ParamName>"    ← (optional) bind Y to a field parameter instead of data-pbi-values

  clusteredBarChart (clustered horizontal bars — category on Y, series split)
    data-pbi-axis="<Table>[<Column>]"      ← dimension column for Y axis
    data-pbi-values="<Measure Name>"       ← measure for X axis
    data-pbi-series="<Table>[<Column>]"    ← series/legend split for clusters
    data-pbi-values-param="<ParamName>"    ← (optional) bind Y to a field parameter instead of data-pbi-values

  hundredPercentStackedBarChart (100% stacked horizontal bars — category on Y)
    data-pbi-axis="<Table>[<Column>]"      ← dimension column for Y axis
    data-pbi-values="<Measure Name>"       ← measure for X axis
    data-pbi-series="<Table>[<Column>]"    ← series/legend split for stacking
    data-pbi-values-param="<ParamName>"    ← (optional) bind Y to a field parameter instead of data-pbi-values

  dotPlot          (dot per category at exact measure value)
    data-pbi-axis="<Table>[<Column>]"      ← category column
    data-pbi-values="<Measure Name>"       ← measure plotted as dot position

  lineChart
    data-pbi-axis="<Table>[<Column>]"      ← dimension for X axis
    data-pbi-values="<Measure Name>"       ← measure for Y axis
    data-pbi-series="<Table>[<Column>]"    ← (optional) series/legend split
    data-pbi-values-param="<ParamName>"    ← (optional) bind Y to a field parameter instead of data-pbi-values

  areaChart
    data-pbi-axis="<Table>[<Column>]"      ← dimension for X axis
    data-pbi-values="<Measure Name>"       ← measure for Y axis
    data-pbi-series="<Table>[<Column>]"    ← (optional) series/legend split (renders as stacked area)
    data-pbi-values-param="<ParamName>"    ← (optional) bind Y to a field parameter instead of data-pbi-values

  comboChart       (column + line on shared axis)
    data-pbi-axis="<Table>[<Column>]"      ← shared dimension for X axis
    data-pbi-column-values="<Measure>"     ← measure rendered as columns
    data-pbi-line-values="<Measure>"       ← measure rendered as line

  pieChart
    data-pbi-axis="<Table>[<Column>]"      ← category dimension for slices
    data-pbi-values="<Measure Name>"       ← measure for slice size

  donutChart
    data-pbi-axis="<Table>[<Column>]"      ← category dimension for slices
    data-pbi-values="<Measure Name>"       ← measure for slice size

  treemap
    data-pbi-group="<Table>[<Column>]"     ← primary category column
    data-pbi-values="<Measure Name>"       ← measure for rectangle size
    data-pbi-details="<Table>[<Column>]"   ← (optional) secondary hierarchy column

  funnelChart
    data-pbi-axis="<Table>[<Column>]"      ← stage column (preserve source order)
    data-pbi-values="<Measure Name>"       ← measure per stage

  histogram        (renders as a binned barChart in PBIR)
    data-pbi-values="<Measure Name>"       ← measure to bin
    data-pbi-bins="<int>"                  ← (optional) bin count

  scatterChart
    data-pbi-x="<X Measure>"               ← measure on X axis
    data-pbi-y="<Y Measure>"               ← measure on Y axis
    data-pbi-details="<Table>[<Column>]"   ← (optional) per-point label/group

  bubbleChart      (scatter with bubble size = third measure)
    data-pbi-x="<X Measure>"               ← measure on X axis
    data-pbi-y="<Y Measure>"               ← measure on Y axis
    data-pbi-size="<Size Measure>"         ← measure for bubble size
    data-pbi-details="<Table>[<Column>]"   ← (optional) per-point label/group

  waterfallChart
    data-pbi-axis="<Table>[<Column>]"      ← ordered category/stage column
    data-pbi-values="<Measure Name>"       ← delta measure per category
    data-pbi-breakdown="<Table>[<Column>]" ← (optional) sub-group dimension

  ribbonChart      (rank changes over time)
    data-pbi-axis="<Table>[<Column>]"      ← time/period column
    data-pbi-values="<Measure Name>"       ← measure determining rank
    data-pbi-series="<Table>[<Column>]"    ← ranked category column

  map              (bubble map; requires Bing geocoding in tenant)
    data-pbi-location="<Table>[<Column>]"  ← place/lat-lon column
    data-pbi-size="<Size Measure>"         ← bubble size measure
    data-pbi-legend="<Table>[<Column>]"    ← (optional) category legend

  filledMap        (choropleth; requires Bing geocoding in tenant)
    data-pbi-location="<Table>[<Column>]"  ← region column
    data-pbi-color-saturation="<Measure>"  ← measure driving fill intensity

  shapeMap         (custom TopoJSON regions)
    data-pbi-location="<Table>[<Column>]"  ← region-key column matching TopoJSON
    data-pbi-color-saturation="<Measure>"  ← measure driving fill intensity
    data-pbi-topojson="<path-or-url>"      ← (optional) user-supplied TopoJSON

  slicer
    data-pbi-field="<Table>[<Column>]"     ← field to filter on
    data-pbi-style="dropdown|list|between" ← (optional) slicer style; default "dropdown"
                                              Use "between" for numeric/date range slicers.
                                              Use "list" when showing all values inline.

  field-param      (emits a slicer bound to a field parameter's own column)
    data-pbi-param-name="<ParamName>"      ← field parameter table/column name
    data-pbi-measures="<M1>, <M2>, ..."    ← comma-separated measures the param switches between
    data-pbi-style="tabs|dropdown|list"    ← (optional) slicer style; default "tabs"

  shape            (chrome rectangle/line — no data query)
    data-pbi-shape="rectangle|line"        ← (optional) shape kind; default "rectangle"
    data-pbi-fill="<color>"                ← (optional) fill color (applied by theme)
    data-pbi-stroke="<color>"              ← (optional) stroke color (applied by theme)

  text             (chrome textbox — no data query)
    data-pbi-text="<literal text>"         ← text content of the textbox (shown as-is, or used as
                                              fallback label when data-pbi-title-measure is set)
    data-pbi-role="title|subtitle|label|tab" ← (optional) styling role (applied by theme)
    data-pbi-color="#RRGGBB"               ← (optional) overrides the role color (use white on dark backgrounds)
    data-pbi-title-measure="<MeasureName>" ← (optional) binds the textbox text to a DAX measure so
                                              the title updates dynamically (e.g. when a field parameter
                                              changes). Use this when the title should reflect the
                                              currently selected indicator/measure. The measure must
                                              return a string. data-pbi-text still provides the
                                              fallback visible text in the HTML preview.

  button           (chrome action button — no data query)
    data-pbi-action="bookmark|navigate|back|reset|blank" ← button behavior
    data-pbi-text="<label>"                ← (optional) button label text
    data-pbi-bookmark="<Bookmark Name>"    ← (optional) target bookmark (for action="bookmark")

  bookmark         (page-state metadata — emits no visual; wires buttons/visibility)
    data-pbi-name="<Bookmark Name>"        ← display name buttons reference via data-pbi-bookmark
    data-pbi-captures="visibility,data,..." ← (optional) captured aspects (default none)
    data-pbi-target="<id1>,<id2>"          ← (optional) visual ids it applies to; default all
    data-pbi-visible="<id1>,<id2>"         ← (optional) visual ids shown
    data-pbi-hidden="<id1>,<id2>"          ← (optional) visual ids hidden

  table
    data-pbi-columns="<tok1>,<tok2>,..."   ← comma-separated mix of measure names
                                              and Table[Column] refs. Each token is
                                              independently either a bare measure name
                                              (e.g. "Total Revenue") or a column ref
                                              (e.g. "sales[Region]"). Column tokens
                                              become row groupings; measure tokens
                                              become aggregated value columns.

RULES:
- Measure-valued attributes hold a bare measure name from the schema (e.g.
  "Total Revenue"): data-pbi-measure, data-pbi-values, data-pbi-target,
  data-pbi-min, data-pbi-max, data-pbi-column-values, data-pbi-line-values,
  data-pbi-x, data-pbi-y, data-pbi-size, data-pbi-color-saturation.
- Column-ref attributes hold Table[Column] (e.g. "sales[Region]"):
  data-pbi-axis, data-pbi-field, data-pbi-series, data-pbi-trend,
  data-pbi-group, data-pbi-details, data-pbi-breakdown, data-pbi-location,
  data-pbi-legend.
- Multi-token attributes (data-pbi-columns on table, data-pbi-measures on
  multiRowCard) are comma-separated; tokens of each kind validated per
  position.
- data-pbi-bins (histogram) is an integer literal. data-pbi-topojson (shape
  map) is a file path or URL — neither schema-checked.
- Never invent a measure or column name not present in the schema.
- data-pbi-hidden="true" may be added to ANY visual to make it hidden on page
  load (emits a top-level "isHidden": true on the container). Used with
  bookmarks for view toggles where one chart of a stack defaults visible.
"""

# Embedded in generator system prompt — lists every CSS class Claude may use.
CSS_CLASS_CATALOG: str = """\
AVAILABLE CSS CLASSES
=====================
Layout:
  db-page           1280x720 page container (use on <body> or outer div)
  db-grid           3-column grid container
  db-col-1          span 1 column
  db-col-2          span 2 columns
  db-col-3          span 3 columns (full width)
  db-row-1          span 1 row height
  db-row-2          span 2 rows height

Cards and charts:
  db-card           white card with shadow and padding (use as visual container)
  db-label          small muted label above a value
  db-value          large bold KPI number
  db-chart-area     placeholder area for chart content

Slicers:
  db-slicer-items   flex container for slicer pills
  db-pill           individual slicer option pill
  db-pill active    selected/active slicer pill

Do NOT use Tailwind classes or inline styles. Use only classes from this list.
"""

# Attribute-role sets used by the validator — single source of truth.
# data-pbi-columns (table) and data-pbi-measures (multiRowCard) are absent here:
# they hold comma-separated tokens and are validated by dedicated split-and-check
# loops rather than a single attribute lookup.
# data-pbi-bins (histogram) and data-pbi-topojson (shape map) are also absent —
# they are literals/paths, not measure or column references.
MEASURE_ATTRS: frozenset[str] = frozenset({
    "data-pbi-measure",
    "data-pbi-values",
    "data-pbi-target",
    "data-pbi-min",
    "data-pbi-max",
    "data-pbi-column-values",
    "data-pbi-line-values",
    "data-pbi-x",
    "data-pbi-y",
    "data-pbi-size",
    "data-pbi-color-saturation",
    "data-pbi-title-measure",
})
COLUMN_REF_ATTRS: frozenset[str] = frozenset({
    "data-pbi-axis",
    "data-pbi-field",
    "data-pbi-series",
    "data-pbi-trend",
    "data-pbi-group",
    "data-pbi-details",
    "data-pbi-breakdown",
    "data-pbi-location",
    "data-pbi-legend",
})
