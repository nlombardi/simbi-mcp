"""Validates annotated HTML mockups against a ModelSchema.

Parses HTML with stdlib html.parser (no extra dependencies).
Raises ValidationError if any annotation references a measure or column
that does not exist in the schema — catching hallucinations before Phase 3.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

from simbi_mcp.mockup.annotations import VISUAL_ATTRS, VisualType
from simbi_mcp.types import ModelSchema

_COL_REF_RE = re.compile(r"^(.+)\[(.+)\]$")


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


def validate_mockup(html: str, schema: ModelSchema) -> None:
    """Parse html and validate every data-pbi element against schema.

    Raises ValidationError describing the first problem found.
    """
    collector = _AnnotationCollector()
    collector.feed(html)

    if not collector.nodes:
        raise ValidationError(
            "HTML contains no data-pbi elements — nothing to compile to PBIR"
        )

    for node in collector.nodes:
        _validate_node(node, schema)


def _validate_node(attrs: dict[str, str], schema: ModelSchema) -> None:
    raw_type = attrs.get("data-pbi", "")
    try:
        vtype = VisualType(raw_type)
    except ValueError as e:
        raise ValidationError(
            f"Unknown visual type: {raw_type!r}. "
            f"Valid types: {[v.value for v in VisualType]}"
        ) from e

    spec = VISUAL_ATTRS[vtype]
    for req in spec["required"]:
        if req not in attrs or not attrs[req].strip():
            raise ValidationError(
                f"Visual {raw_type!r} is missing required attribute {req!r}"
            )

    # Validate measure references
    for attr in ("data-pbi-measure", "data-pbi-values"):
        if attr in attrs:
            _check_measure(attrs[attr], schema, attr)

    # Validate column references (Table[Column] format)
    for attr in ("data-pbi-axis", "data-pbi-field", "data-pbi-series"):
        if attr in attrs:
            _check_column_ref(attrs[attr], schema, attr)

    # Validate table visual column list
    if vtype is VisualType.TABLE:
        for name in attrs.get("data-pbi-columns", "").split(","):
            name = name.strip()
            if name:
                _check_measure(name, schema, "data-pbi-columns")


def _check_measure(name: str, schema: ModelSchema, attr: str) -> None:
    if not schema.has_measure(name):
        available = [m.name for m in schema.measures]
        raise ValidationError(
            f"Attribute {attr!r} references unknown measure {name!r}. "
            f"Available: {available}"
        )


def _check_column_ref(ref: str, schema: ModelSchema, attr: str) -> None:
    m = _COL_REF_RE.match(ref)
    if not m:
        raise ValidationError(
            f"Attribute {attr!r} value {ref!r} must be in Table[Column] format"
        )
    table_name, col_name = m.group(1), m.group(2)
    table = next((t for t in schema.tables if t.name == table_name), None)
    if table is None:
        raise ValidationError(
            f"Attribute {attr!r} references unknown table {table_name!r}"
        )
    if col_name not in table.columns:
        raise ValidationError(
            f"Attribute {attr!r} references unknown column {col_name!r} "
            f"in table {table_name!r}"
        )
