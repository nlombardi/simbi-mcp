"""Parses TMDL strings (from model_operations.ExportTMDL) into typed ModelSchema.

TMDL is the Tabular Model Definition Language — a YAML-like text format used by
Power BI Desktop and the MS MCP to represent semantic models.

Format reference (from spikes/02_ms_mcp_smoke/NOTES.md):
  table <TableName>
      measure '<Measure Name>' = <DAX expression>
          formatString: <format>
      column <ColumnName>
          dataType: <type>
      partition ...   <- ignored

Key parsing rules:
- Indentation uses spaces (4-space indent from MS MCP) or tabs — both accepted
- Measure names with spaces are single-quoted: 'Total Revenue'
- Measure names without spaces are unquoted: OrderCount
- Lines starting with /// are doc-comments — skip
- 'ref table <Name>' lines in model.tmdl are references, not definitions — skip
- 'model Model' blocks (culture, annotation) are ignored
- FormatString -> return_type inference: $ -> currency, % -> percentage, #,0 -> integer, else number
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from simbi_mcp.types import (
    ModelColumn,
    ModelMeasure,
    ModelRelationship,
    ModelSchema,
    ModelTable,
)

# Tables may appear at column 0 (per-table file) OR indented under `model Model`
# (consolidated model.tmdl). Both forms exist in real MS Power BI MCP exports.
_TABLE_RE = re.compile(r"^[ \t]*table (?:'(.+?)'|(\S+))\s*$")
_MEASURE_RE = re.compile(r"^[ \t]+measure (?:'(.+?)'|(\S+)) = (.+)$")
_COLUMN_RE = re.compile(r"^[ \t]+column (.+)$")
_FORMAT_RE = re.compile(r"^[ \t]+formatString: (.+)$")
_DATATYPE_RE = re.compile(r"^[ \t]+dataType: (.+)$")
_REF_TABLE_RE = re.compile(r"^[ \t]*ref table ")
_COMMENT_RE = re.compile(r"^[ \t]*///")
_MODEL_RE = re.compile(r"^model ")
_PARTITION_RE = re.compile(r"^[ \t]+partition ")
_RELATIONSHIP_RE = re.compile(r"^[ \t]*relationship (\S+)\s*$")
_FROM_COL_RE = re.compile(r"^[ \t]+fromColumn: (.+)\.([^.]+)\s*$")
_TO_COL_RE = re.compile(r"^[ \t]+toColumn: (.+)\.([^.]+)\s*$")

_TMDL_TO_BIM: dict[str, str] = {
    "double": "double",
    "decimal": "decimal",
    "int64": "int64",
    "wholenumber": "int64",
    "currency": "decimal",
    "datetime": "dateTime",
    "boolean": "boolean",
    "binary": "binary",
    "string": "string",
}


def _map_tmdl_type(tmdl_type: str) -> str:
    return _TMDL_TO_BIM.get(tmdl_type.lower(), "string")


# Names that overwhelmingly map to one type even with no format-string signal.
# Limited to truly unambiguous cases. Things like "Quarter" or "Year" stay out
# because in calculated tables they're often string labels (e.g. "Q1 2025").
_UNAMBIGUOUS_DATE_NAMES: frozenset[str] = frozenset({"date", "datetime", "datekey"})


def _infer_calc_column_type(name: str, format_string: str) -> str:
    """Infer a column data type when the TMDL omits `dataType:`.

    Calculated tables (CALENDARAUTO + ADDCOLUMNS, SUMMARIZECOLUMNS, etc.) don't
    serialize per-column dataType lines — Power BI infers at runtime. We mirror
    that with a conservative heuristic: format-string is the strong signal,
    column name covers a tiny set of unambiguous cases (literally "Date"), and
    everything else falls back to "string". We deliberately do NOT guess types
    from names like Year/Month/Quarter — those are commonly string labels in
    DAX calculated tables.
    """
    fmt = format_string.lower()
    if any(token in fmt for token in ("general date", "short date", "long date", "date format")):
        return "dateTime"
    if fmt in {"0", "#,0", "#,##0"}:
        return "int64"
    if "$" in fmt or "\\$" in fmt:
        return "decimal"
    if "0.00" in fmt or "#,0.00" in fmt:
        return "double"
    if "%" in fmt:
        return "double"

    if name.lower() in _UNAMBIGUOUS_DATE_NAMES:
        return "dateTime"
    return "string"


@dataclass
class _PendingMeasure:
    name: str
    table: str
    expression: str


@dataclass
class _TableAccumulator:
    name: str
    columns: list[ModelColumn] = field(default_factory=list)
    measures: list[ModelMeasure] = field(default_factory=list)
    _pending_measure: _PendingMeasure | None = field(default=None, repr=False)
    _pending_format: str = field(default="", repr=False)
    _pending_col_name: str | None = field(default=None, repr=False)
    _pending_col_type: str = field(default="string", repr=False)
    _pending_col_type_explicit: bool = field(default=False, repr=False)
    _pending_col_format: str = field(default="", repr=False)

    def set_format(self, fmt: str) -> None:
        # formatString is shared by measure and column contexts. We always store
        # it on the measure-format slot AND, while we're inside a column block,
        # also stash it on the column-format slot so type inference can use it.
        self._pending_format = fmt
        if self._pending_col_name is not None and self._pending_measure is None:
            self._pending_col_format = fmt

    def set_col_type(self, dtype: str) -> None:
        self._pending_col_type = dtype
        self._pending_col_type_explicit = True

    def start_column(self, name: str) -> None:
        self._flush_column()
        self._pending_col_name = name
        self._pending_col_type = "string"
        self._pending_col_type_explicit = False
        self._pending_col_format = ""

    def _flush_column(self) -> None:
        if self._pending_col_name is not None:
            if self._pending_col_type_explicit:
                data_type = _map_tmdl_type(self._pending_col_type)
            else:
                data_type = _infer_calc_column_type(
                    self._pending_col_name, self._pending_col_format
                )
            self.columns.append(
                ModelColumn(name=self._pending_col_name, data_type=data_type)
            )
            self._pending_col_name = None
            self._pending_col_type = "string"
            self._pending_col_type_explicit = False
            self._pending_col_format = ""

    def finalise_measure(self) -> None:
        self._flush_column()
        if self._pending_measure is not None:
            return_type = (
                _infer_return_type(self._pending_format)
                if self._pending_format
                else "number"
            )
            self.measures.append(
                ModelMeasure(
                    name=self._pending_measure.name,
                    table=self._pending_measure.table,
                    expression=self._pending_measure.expression,
                    return_type=return_type,
                )
            )
            self._pending_measure = None
            self._pending_format = ""


def parse_tmdl_schema(tmdl: str) -> ModelSchema:
    """Parse a TMDL string returned by model_operations.ExportTMDL."""
    if not tmdl.strip():
        raise ValueError("Cannot parse empty TMDL string")

    tables: list[_TableAccumulator] = []
    current: _TableAccumulator | None = None
    in_partition = False
    partition_depth = 0

    for raw_line in tmdl.splitlines():
        line = raw_line.rstrip()

        # Skip comments, blank lines, model-level blocks, ref-table lines
        if (
            not line
            or _COMMENT_RE.match(line)
            or _MODEL_RE.match(line)
            or _REF_TABLE_RE.match(line)
        ):
            continue

        # Partition block — skip content until indentation returns to partition level.
        # Tracks depth so measures/columns after a partition are not lost.
        if current and _PARTITION_RE.match(line):
            partition_depth = len(line) - len(line.lstrip(" \t"))
            in_partition = True
            continue
        if in_partition:
            current_depth = len(line) - len(line.lstrip(" \t"))
            if current_depth > partition_depth:
                continue
            in_partition = False
            # Fall through — process this line normally

        # New table definition
        m = _TABLE_RE.match(line)
        if m:
            if current:
                current.finalise_measure()
                tables.append(current)
            current = _TableAccumulator(name=(m.group(1) or m.group(2)).strip())
            in_partition = False
            continue

        if current is None:
            continue

        # Measure
        m = _MEASURE_RE.match(line)
        if m:
            current.finalise_measure()
            name = m.group(1) or m.group(2)  # quoted or unquoted
            expr = m.group(3).strip()
            current._pending_measure = _PendingMeasure(
                name=name,
                table=current.name,
                expression=expr,
            )
            continue

        # FormatString (sub-property of a measure)
        m = _FORMAT_RE.match(line)
        if m:
            current.set_format(m.group(1).strip())
            continue

        # dataType (sub-property of a column)
        m = _DATATYPE_RE.match(line)
        if m:
            current.set_col_type(m.group(1).strip())
            continue

        # Column
        m = _COLUMN_RE.match(line)
        if m:
            current.finalise_measure()
            col_name = m.group(1).strip()
            # Skip if it looks like a sub-property (contains colon = property line)
            if ":" in col_name:
                continue
            # Calculated column: "column Year = YEAR([Date])" → keep just "Year"
            col_name = col_name.split("=", 1)[0].strip().strip("'")
            if col_name:
                current.start_column(col_name)
            continue

    # Flush last table
    if current:
        current.finalise_measure()
        tables.append(current)

    return ModelSchema(
        tables=[ModelTable(name=t.name, columns=t.columns) for t in tables],
        measures=[m for t in tables for m in t.measures],
        relationships=_parse_relationships(tmdl),
    )


def _parse_relationships(tmdl: str) -> list[ModelRelationship]:
    """Second pass: collect `relationship` blocks from anywhere in the TMDL."""
    rels: list[ModelRelationship] = []
    pending: dict[str, str] = {}

    def _flush() -> None:
        if {"from_table", "from_column", "to_table", "to_column"} <= pending.keys():
            rels.append(ModelRelationship(**pending))
        pending.clear()

    in_rel = False
    for raw in tmdl.splitlines():
        line = raw.rstrip()
        if _RELATIONSHIP_RE.match(line):
            _flush()
            in_rel = True
            continue
        if not in_rel:
            continue
        m = _FROM_COL_RE.match(line)
        if m:
            pending["from_table"] = m.group(1).strip().strip("'")
            pending["from_column"] = m.group(2).strip()
            continue
        m = _TO_COL_RE.match(line)
        if m:
            pending["to_table"] = m.group(1).strip().strip("'")
            pending["to_column"] = m.group(2).strip()
            continue
        # Boundary: a new top-level construct ends the relationship block.
        if line and re.match(
            r"^[ \t]*(table |ref table |cultureInfo |annotation [A-Za-z_])", line
        ):
            _flush()
            in_rel = False
    _flush()
    return rels


def _infer_return_type(fmt: str) -> str:
    if "$" in fmt or "\\$" in fmt:
        return "currency"
    if "%" in fmt:
        return "percentage"
    if "#,0" in fmt and "." not in fmt:
        return "integer"
    return "number"
