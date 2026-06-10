"""Annotation vocabulary for SimBI HTML mockups.

These constants define the data-pbi-* attribute contract between Phase 2
(HTML generator) and Phase 3 (PBIR emitter). Change only with coordination.
"""
from __future__ import annotations

from enum import StrEnum
from typing import TypedDict


class VisualAttrSpec(TypedDict):
    required: list[str]
    optional: list[str]


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


# Required and optional data-pbi-* attributes per visual type.
# Phase 3 uses this same dict to know which attributes to read.
VISUAL_ATTRS: dict[VisualType, VisualAttrSpec] = {
    VisualType.CARD: {
        "required": ["data-pbi-measure"],
        "optional": [],
    },
    VisualType.MULTI_ROW_CARD: {
        "required": ["data-pbi-measures"],
        "optional": [],
    },
    VisualType.KPI: {
        "required": ["data-pbi-measure", "data-pbi-target", "data-pbi-trend"],
        "optional": [],
    },
    VisualType.GAUGE: {
        "required": ["data-pbi-measure"],
        "optional": ["data-pbi-min", "data-pbi-max", "data-pbi-target"],
    },
    VisualType.COLUMN_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values"],
        "optional": ["data-pbi-series", "data-pbi-values-param"],
    },
    VisualType.BAR_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values"],
        "optional": ["data-pbi-series", "data-pbi-values-param"],
    },
    VisualType.LINE_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values"],
        "optional": ["data-pbi-series", "data-pbi-values-param", "data-pbi-hidden"],
    },
    VisualType.SLICER: {
        "required": ["data-pbi-field"],
        "optional": ["data-pbi-style"],
    },
    VisualType.TABLE: {
        "required": ["data-pbi-columns"],
        "optional": ["data-pbi-hidden"],
    },
    VisualType.CLUSTERED_COLUMN_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values", "data-pbi-series"],
        "optional": ["data-pbi-values-param", "data-pbi-hidden"],
    },
    VisualType.CLUSTERED_BAR_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values", "data-pbi-series"],
        "optional": ["data-pbi-values-param"],
    },
    VisualType.HUNDRED_PERCENT_STACKED_BAR_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values", "data-pbi-series"],
        "optional": ["data-pbi-values-param"],
    },
    VisualType.HUNDRED_PERCENT_STACKED_COLUMN_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values", "data-pbi-series"],
        "optional": ["data-pbi-values-param"],
    },
    VisualType.AREA_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values"],
        "optional": ["data-pbi-series", "data-pbi-values-param"],
    },
    VisualType.PIE_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values"],
        "optional": [],
    },
    VisualType.DONUT_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values"],
        "optional": [],
    },
    VisualType.DOT_PLOT: {
        "required": ["data-pbi-axis", "data-pbi-values"],
        "optional": [],
    },
    VisualType.COMBO_CHART: {
        "required": ["data-pbi-axis", "data-pbi-column-values", "data-pbi-line-values"],
        "optional": [],
    },
    VisualType.TREEMAP: {
        "required": ["data-pbi-group", "data-pbi-values"],
        "optional": ["data-pbi-details"],
    },
    VisualType.FUNNEL_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values"],
        "optional": [],
    },
    VisualType.HISTOGRAM: {
        "required": ["data-pbi-values"],
        "optional": ["data-pbi-bins"],
    },
    VisualType.SCATTER_CHART: {
        "required": ["data-pbi-x", "data-pbi-y"],
        "optional": ["data-pbi-details"],
    },
    VisualType.BUBBLE_CHART: {
        "required": ["data-pbi-x", "data-pbi-y", "data-pbi-size"],
        "optional": ["data-pbi-details"],
    },
    VisualType.WATERFALL_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values"],
        "optional": ["data-pbi-breakdown"],
    },
    VisualType.RIBBON_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values", "data-pbi-series"],
        "optional": [],
    },
    VisualType.MAP: {
        "required": ["data-pbi-location", "data-pbi-size"],
        "optional": ["data-pbi-legend"],
    },
    VisualType.FILLED_MAP: {
        "required": ["data-pbi-location", "data-pbi-color-saturation"],
        "optional": [],
    },
    VisualType.SHAPE_MAP: {
        "required": ["data-pbi-location", "data-pbi-color-saturation"],
        "optional": ["data-pbi-topojson"],
    },
    VisualType.FIELD_PARAM: {
        "required": ["data-pbi-param-name", "data-pbi-measures"],
        "optional": ["data-pbi-style", "data-pbi-id"],
    },
    VisualType.SHAPE: {
        "required": [],
        "optional": ["data-pbi-shape", "data-pbi-fill", "data-pbi-stroke", "data-pbi-id"],
    },
    VisualType.TEXT: {
        "required": ["data-pbi-text"],
        "optional": ["data-pbi-role", "data-pbi-color", "data-pbi-id", "data-pbi-title-measure"],
    },
    VisualType.BUTTON: {
        "required": ["data-pbi-action"],
        "optional": ["data-pbi-text", "data-pbi-bookmark", "data-pbi-id"],
    },
    VisualType.BOOKMARK: {
        "required": ["data-pbi-name"],
        "optional": [
            "data-pbi-captures",
            "data-pbi-target",
            "data-pbi-visible",
            "data-pbi-hidden",
        ],
    },
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
