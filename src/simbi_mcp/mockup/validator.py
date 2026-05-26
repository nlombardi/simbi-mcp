"""Validates annotated HTML mockups against a ModelSchema.

Parses HTML with stdlib html.parser (no extra dependencies).
Raises ValidationError if any annotation references a measure or column
that does not exist in the schema — catching hallucinations before Phase 3.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

from simbi_mcp.mockup.annotations import COLUMN_REF_ATTRS, MEASURE_ATTRS, VISUAL_ATTRS, VisualType
from simbi_mcp.types import ModelSchema

_COL_REF_RE = re.compile(r"^(.+)\[(.+)\]$")

# Concrete correct-shape example per visual type — appended to every error
# so the LLM client gets an actionable template, not just a complaint.
_EXAMPLES: dict[VisualType, str] = {
    VisualType.CARD: '<div data-pbi="card" data-pbi-measure="Total Revenue"></div>',
    VisualType.COLUMN_CHART: (
        '<div data-pbi="columnChart" data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue"></div>'
    ),
    VisualType.BAR_CHART: (
        '<div data-pbi="barChart" data-pbi-axis="sales[Region]" '
        'data-pbi-values="Total Revenue"></div>'
    ),
    VisualType.LINE_CHART: (
        '<div data-pbi="lineChart" data-pbi-axis="sales[OrderDate]" '
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
}


def _example_for(vtype: VisualType | None) -> str:
    if vtype is None:
        return "\n".join(_EXAMPLES.values())
    return _EXAMPLES[vtype]


class ValidationError(Exception):
    """Raised when an annotation fails schema validation."""


class _AnnotationCollector(HTMLParser):
    """Collects all data-pbi elements with their attributes."""

    def __init__(self) -> None:
        super().__init__()
        self.nodes: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k: v or "" for k, v in attrs}
        if "data-pbi" in attr_dict:
            self.nodes.append(attr_dict)


def count_annotated_visuals(html: str) -> int:
    """Count data-pbi elements in html — used for validator success messages."""
    collector = _AnnotationCollector()
    collector.feed(html)
    return len(collector.nodes)


def validate_mockup(html: str, schema: ModelSchema) -> None:
    """Parse html and validate every data-pbi element against schema.

    Raises ValidationError on the first problem found. Stops at the first
    failure — callers that need all errors should call validate_mockup inside
    a loop with corrected HTML between iterations.
    """
    collector = _AnnotationCollector()
    collector.feed(html)

    if not collector.nodes:
        raise ValidationError(
            "HTML contains no data-pbi elements — nothing to compile to PBIR. "
            "Every visual must be a single element tagged with data-pbi=<type> "
            "plus the type's required attributes. Correct shapes:\n"
            f"{_example_for(None)}"
        )

    for node in collector.nodes:
        _validate_node(node, schema)


def _validate_node(attrs: dict[str, str], schema: ModelSchema) -> None:
    raw_type = attrs.get("data-pbi", "")
    try:
        vtype = VisualType(raw_type)
    except ValueError as e:
        raise ValidationError(
            f"Unknown data-pbi value: {raw_type!r}. "
            f"Must be one of: {[v.value for v in VisualType]}\n"
            f"Correct shapes for each type:\n{_example_for(None)}"
        ) from e

    spec = VISUAL_ATTRS[vtype]
    for req in spec["required"]:
        if req not in attrs or not attrs[req].strip():
            raise ValidationError(
                f"Visual data-pbi={raw_type!r} is missing required attribute "
                f"{req!r}.\nCorrect shape:\n{_example_for(vtype)}"
            )

    for attr in MEASURE_ATTRS:
        if attr in attrs:
            _check_measure(attrs[attr], schema, attr, vtype)

    for attr in COLUMN_REF_ATTRS:
        if attr in attrs:
            _check_column_ref(attrs[attr], schema, attr, vtype)

    # Validate table visual column list — each token is either a Table[Column]
    # ref or a bare measure name. The shape decides which check runs.
    if vtype is VisualType.TABLE:
        for token in attrs.get("data-pbi-columns", "").split(","):
            token = token.strip()
            if not token:
                continue
            if _COL_REF_RE.match(token):
                _check_column_ref(token, schema, "data-pbi-columns", vtype)
            else:
                _check_measure(token, schema, "data-pbi-columns", vtype)


def _check_measure(name: str, schema: ModelSchema, attr: str, vtype: VisualType) -> None:
    if not schema.has_measure(name):
        available = [m.name for m in schema.measures]
        raise ValidationError(
            f"Attribute {attr}={name!r} references a measure that does not "
            f"exist in the schema. Available measures: {available}\n"
            f"Correct shape:\n{_example_for(vtype)}"
        )


def _check_column_ref(ref: str, schema: ModelSchema, attr: str, vtype: VisualType) -> None:
    m = _COL_REF_RE.match(ref)
    if not m:
        raise ValidationError(
            f"Attribute {attr}={ref!r} must be in Table[Column] format "
            f"(e.g. 'sales[Region]'), not a bare measure name.\n"
            f"Correct shape:\n{_example_for(vtype)}"
        )
    table_name, col_name = m.group(1), m.group(2)
    table = next((t for t in schema.tables if t.name == table_name), None)
    if table is None:
        available = [t.name for t in schema.tables]
        raise ValidationError(
            f"Attribute {attr}={ref!r} references unknown table "
            f"{table_name!r}. Available tables: {available}"
        )
    if col_name not in {c.name for c in table.columns}:
        available = [c.name for c in table.columns]
        raise ValidationError(
            f"Attribute {attr}={ref!r} references unknown column "
            f"{col_name!r} in table {table_name!r}. "
            f"Available columns in {table_name}: {available}"
        )
