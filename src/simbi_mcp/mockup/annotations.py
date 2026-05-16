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
    COLUMN_CHART = "columnChart"
    LINE_CHART = "lineChart"
    SLICER = "slicer"
    TABLE = "table"


# Required and optional data-pbi-* attributes per visual type.
# Phase 3 uses this same dict to know which attributes to read.
VISUAL_ATTRS: dict[VisualType, VisualAttrSpec] = {
    VisualType.CARD: {
        "required": ["data-pbi-measure"],
        "optional": [],
    },
    VisualType.COLUMN_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values"],
        "optional": [],
    },
    VisualType.LINE_CHART: {
        "required": ["data-pbi-axis", "data-pbi-values"],
        "optional": ["data-pbi-series"],
    },
    VisualType.SLICER: {
        "required": ["data-pbi-field"],
        "optional": [],
    },
    VisualType.TABLE: {
        "required": ["data-pbi-columns"],
        "optional": [],
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

  columnChart
    data-pbi-axis="<Table>[<Column>]"      ← dimension column for X axis
    data-pbi-values="<Measure Name>"       ← measure for Y axis

  lineChart
    data-pbi-axis="<Table>[<Column>]"      ← dimension for X axis
    data-pbi-values="<Measure Name>"       ← measure for Y axis
    data-pbi-series="<Table>[<Column>]"    ← (optional) series/legend split

  slicer
    data-pbi-field="<Table>[<Column>]"     ← field to filter on

  table
    data-pbi-columns="<name1>,<name2>"     ← comma-separated measure names

RULES:
- data-pbi-measure and data-pbi-values must be exact measure names from the schema.
- data-pbi-axis, data-pbi-field, data-pbi-series must use Table[Column] format.
- Never invent a measure or column name not present in the schema.
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
# data-pbi-columns is intentionally absent: it holds comma-separated measure
# names and is validated by a dedicated split-and-check loop, not a single lookup.
MEASURE_ATTRS: frozenset[str] = frozenset({"data-pbi-measure", "data-pbi-values"})
COLUMN_REF_ATTRS: frozenset[str] = frozenset({"data-pbi-axis", "data-pbi-field", "data-pbi-series"})
