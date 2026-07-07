"""Validates annotated HTML mockups against a ModelSchema.

Parses HTML with stdlib html.parser (no extra dependencies).
Raises ValidationError if any annotation references a measure or column
that does not exist in the schema — catching hallucinations before Phase 3.
"""
from __future__ import annotations

import difflib
import re
from html.parser import HTMLParser

from simbi_mcp.mockup.annotations import (
    COLUMN_REF_ATTRS,
    EXAMPLES,
    MEASURE_ATTRS,
    UNIVERSAL_ATTRS,
    VISUAL_ATTRS,
    VisualType,
)
from simbi_mcp.types import ModelSchema

_COL_REF_RE = re.compile(r"^(.+)\[(.+)\]$")
_TIME_TOKENS: frozenset[str] = frozenset(
    {"year", "date", "month", "quarter", "period", "week", "day", "time"}
)
_HBAR_TYPES: frozenset[VisualType] = frozenset({
    VisualType.BAR_CHART,
    VisualType.CLUSTERED_BAR_CHART,
    VisualType.HUNDRED_PERCENT_STACKED_BAR_CHART,
})
_NAME_TOKEN_RE = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")
_UNSUPPORTED_INLINE_PROPS: frozenset[str] = frozenset({
    "color", "font-family", "font-size", "font-weight", "font-style",
    "opacity", "text-align", "background-image",
})


def _example_for(vtype: VisualType | None) -> str:
    if vtype is None:
        return "\n".join(EXAMPLES.values())
    return EXAMPLES[vtype]


def _check_unknown_attrs(attrs: dict[str, str], vtype: VisualType, raw_type: str) -> None:
    spec = VISUAL_ATTRS[vtype]
    allowed = (
        {"data-pbi", "data-pbi-page"}
        | set(UNIVERSAL_ATTRS)
        | set(spec["required"])
        | set(spec["optional"])
    )
    for attr in attrs:
        if not attr.startswith("data-pbi") or attr in allowed:
            continue
        suggestion = difflib.get_close_matches(attr, sorted(allowed - {"data-pbi", "data-pbi-page"}), n=1)
        hint = f" Did you mean {suggestion[0]!r}?" if suggestion else ""
        raise ValidationError(
            f"Unknown attribute {attr!r} on data-pbi={raw_type!r}.{hint}\n"
            f"Valid attributes for {raw_type}: "
            f"{sorted(allowed - {'data-pbi', 'data-pbi-page'})}\n"
            f"Correct shape:\n{_example_for(vtype)}"
        )


def _table_of_column_ref(ref: str) -> str | None:
    m = _COL_REF_RE.match(ref)
    return m.group(1) if m else None


def _tables_related(schema: ModelSchema, a: str, b: str) -> bool:
    if a == b:
        return True
    # Direct relationship only (multi-hop paths are out of scope).
    for r in schema.relationships:
        if {r.from_table, r.to_table} == {a, b}:
            return True
    return False


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


def validate_mockup(html: str, schema: ModelSchema) -> list[str]:
    """Parse html and validate every data-pbi element against schema.

    Raises ValidationError on the first fatal problem found. Stops at the first
    failure — callers that need all errors should call validate_mockup inside
    a loop with corrected HTML between iterations.

    Returns a list of non-fatal warnings (empty when clean) — e.g. cross-table
    axis/series that still renders because a relationship exists but is fragile.
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

    all_warnings: list[str] = []
    for node in collector.nodes:
        all_warnings.extend(_validate_node(node, schema))

    # Cross-visual checks: duplicate ids, bookmark/button references
    _check_cross_references(collector.nodes)

    return all_warnings


def _bar_time_axis_warning(
    vtype: VisualType, attrs: dict[str, str], schema: ModelSchema
) -> str | None:
    if vtype not in _HBAR_TYPES:
        return None
    ref = attrs.get("data-pbi-axis", "")
    m = _COL_REF_RE.match(ref)
    if not m:
        return None
    table_name, col_name = m.group(1), m.group(2)
    table = next((t for t in schema.tables if t.name == table_name), None)
    col = next((c for c in table.columns if c.name == col_name), None) if table else None
    is_datetime = col is not None and col.data_type.lower() == "datetime"
    tokens = {t.lower() for t in _NAME_TOKEN_RE.findall(col_name)}
    if is_datetime or tokens & _TIME_TOKENS:
        return (
            f"Visual data-pbi={vtype.value!r}: {vtype.value} draws HORIZONTAL bars, and "
            f"axis column {ref!r} looks like a time dimension. Time on the axis usually "
            f"wants columnChart (vertical) or lineChart. Keep {vtype.value} only if "
            f"horizontal category rows are intended."
        )
    return None


def _inline_style_warnings(attrs: dict[str, str]) -> list[str]:
    """Warn about inline CSS that will NOT transfer to Power BI. Only inline
    styles are checked — computed styles always resolve to a value, so checking
    them would flag every element."""
    out: list[str] = []
    label = attrs.get("data-pbi", "?")
    for decl in attrs.get("style", "").split(";"):
        prop, sep, value = decl.partition(":")
        if not sep:
            continue
        prop = prop.strip().lower()
        if prop in _UNSUPPORTED_INLINE_PROPS:
            out.append(
                f"Visual data-pbi={label!r}: inline '{prop}' does not transfer to "
                f"Power BI — use the theme, data-pbi-role, or data-pbi-color instead."
            )
        elif "gradient(" in value:
            out.append(
                f"Visual data-pbi={label!r}: inline '{prop}' uses a gradient, which does "
                f"not transfer to Power BI — only solid colors transfer."
            )
    return out


def _validate_node(attrs: dict[str, str], schema: ModelSchema) -> list[str]:
    raw_type = attrs.get("data-pbi", "")
    try:
        vtype = VisualType(raw_type)
    except ValueError as e:
        raise ValidationError(
            f"Unknown data-pbi value: {raw_type!r}. "
            f"Must be one of: {[v.value for v in VisualType]}\n"
            f"Correct shapes for each type:\n{_example_for(None)}"
        ) from e

    _check_unknown_attrs(attrs, vtype, raw_type)

    spec = VISUAL_ATTRS[vtype]
    for req in spec["required"]:
        # Charts bound to a field parameter via data-pbi-values-param do not
        # also need data-pbi-values — the param supplies the value role.
        if req == "data-pbi-values" and "data-pbi-values-param" in attrs:
            continue
        if req not in attrs or not attrs[req].strip():
            raise ValidationError(
                f"Visual data-pbi={raw_type!r} is missing required attribute "
                f"{req!r}.\nCorrect shape:\n{_example_for(vtype)}"
            )

    for attr in MEASURE_ATTRS:
        if attr in attrs:
            # Bookmarks use data-pbi-target/visible/hidden as visual ids, not measures
            if vtype is VisualType.BOOKMARK and attr in ("data-pbi-target", "data-pbi-visible", "data-pbi-hidden"):
                continue
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

    # Validate slicer style — must be one of the three accepted values.
    if vtype is VisualType.SLICER and "data-pbi-style" in attrs:
        style = attrs["data-pbi-style"].lower()
        if style not in ("dropdown", "list", "between"):
            raise ValidationError(
                f"data-pbi-style={attrs['data-pbi-style']!r} is invalid. "
                f"Must be one of: 'dropdown', 'list', 'between'.\n"
                f"Correct shape:\n{_example_for(vtype)}"
            )

    # field-param's data-pbi-measures is intentionally left unvalidated for now
    # (measure-list checking for field parameters is out of scope for this task).

    # Validate multiRowCard measure list — every token must be a measure name.
    if vtype is VisualType.MULTI_ROW_CARD:
        for token in attrs.get("data-pbi-measures", "").split(","):
            token = token.strip()
            if not token:
                continue
            _check_measure(token, schema, "data-pbi-measures", vtype)

    # Cross-table axis/series reliability guardrail. When a chart groups by a
    # series column on a different table than its axis column, the visual is
    # blank in Power BI unless a relationship connects the two tables. We only
    # check when BOTH an axis and a series are present — the series grouping is
    # the fragile part. (data-pbi-values-param is irrelevant here: this guard is
    # purely about axis vs series, so the `if axis and series` check covers it.)
    warnings: list[str] = []
    axis = attrs.get("data-pbi-axis")
    series = attrs.get("data-pbi-series")
    if axis and series:
        axis_tbl = _table_of_column_ref(axis)
        series_tbl = _table_of_column_ref(series)
        if axis_tbl and series_tbl and axis_tbl != series_tbl:
            if not _tables_related(schema, axis_tbl, series_tbl):
                raise ValidationError(
                    f"Visual data-pbi={raw_type!r}: axis column is on table "
                    f"{axis_tbl!r} but series is on table {series_tbl!r}, and no "
                    f"relationship connects them. The visual will be blank in Power "
                    f"BI. Use columns from the same table, or add a relationship.\n"
                    f"Correct shape:\n{_example_for(vtype)}"
                )
            warnings.append(
                f"Visual data-pbi={raw_type!r}: axis is on {axis_tbl!r} and series "
                f"on {series_tbl!r} (different tables). A relationship exists so it "
                f"will render, but cross-table axis/series can behave unexpectedly. "
                f"Prefer axis + series from the same table when possible."
            )

    # Check for bar chart time-axis heuristic warning
    bar_time_warning = _bar_time_axis_warning(vtype, attrs, schema)
    if bar_time_warning:
        warnings.append(bar_time_warning)

    # Check for inline styles that will not transfer to Power BI
    warnings.extend(_inline_style_warnings(attrs))

    return warnings


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


def _split_ids(value: str) -> list[str]:
    return [t.strip() for t in value.split(",") if t.strip()]


def _check_cross_references(nodes: list[dict[str, str]]) -> None:
    """Cross-visual checks: data-pbi-id uniqueness, bookmark id refs, button
    bookmark refs. Mirrors what the emitter resolves later so failures surface
    at lint time, not emit time."""
    ids = [n["data-pbi-id"] for n in nodes if n.get("data-pbi-id")]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValidationError(
            f"Duplicate data-pbi-id value(s): {dupes}. Each visual id must be unique."
        )
    id_set = set(ids)

    bookmark_names = [
        n.get("data-pbi-name", "") for n in nodes if n.get("data-pbi") == "bookmark"
    ]
    dup_names = sorted({b for b in bookmark_names if bookmark_names.count(b) > 1})
    if dup_names:
        raise ValidationError(f"Duplicate bookmark data-pbi-name value(s): {dup_names}.")
    name_set = set(bookmark_names)

    for n in nodes:
        if n.get("data-pbi") == "bookmark":
            for attr in ("data-pbi-visible", "data-pbi-hidden", "data-pbi-target"):
                value = n.get(attr, "")
                if attr == "data-pbi-target" and value.strip() == "all":
                    continue
                for token in _split_ids(value):
                    if token not in id_set:
                        raise ValidationError(
                            f"Bookmark {n.get('data-pbi-name', '?')!r} ({attr}) references "
                            f"unknown visual id {token!r}. Known ids: {sorted(id_set)}. "
                            f"Give the target visual a data-pbi-id attribute."
                        )
        elif n.get("data-pbi") == "button" and n.get("data-pbi-action") == "bookmark":
            bm = n.get("data-pbi-bookmark", "").strip()
            if not bm:
                raise ValidationError(
                    'Button with data-pbi-action="bookmark" is missing data-pbi-bookmark. '
                    f"Known bookmarks: {sorted(name_set)}"
                )
            if bm not in name_set:
                raise ValidationError(
                    f"Button references unknown bookmark {bm!r}. "
                    f"Known bookmarks: {sorted(name_set)}"
                )
