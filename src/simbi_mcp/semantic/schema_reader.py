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
- Indentation uses TABS (not spaces)
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
    ModelMeasure,
    ModelSchema,
    ModelTable,
)

_TABLE_RE = re.compile(r"^table (.+)$")
_MEASURE_RE = re.compile(r"^\t+measure (?:'(.+?)'|(\S+)) = (.+)$")
_COLUMN_RE = re.compile(r"^\t+column (.+)$")
_FORMAT_RE = re.compile(r"^\t+formatString: (.+)$")
_REF_TABLE_RE = re.compile(r"^ref table ")
_COMMENT_RE = re.compile(r"^///")
_MODEL_RE = re.compile(r"^model ")
_PARTITION_RE = re.compile(r"^\t+partition ")


@dataclass
class _PendingMeasure:
    name: str
    table: str
    expression: str


@dataclass
class _TableAccumulator:
    name: str
    columns: list[str] = field(default_factory=list)
    measures: list[ModelMeasure] = field(default_factory=list)
    _pending_measure: _PendingMeasure | None = field(default=None, repr=False)
    _pending_format: str = field(default="", repr=False)

    def set_format(self, fmt: str) -> None:
        self._pending_format = fmt

    def finalise_measure(self) -> None:
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
            partition_depth = len(line) - len(line.lstrip("\t"))
            in_partition = True
            continue
        if in_partition:
            current_depth = len(line) - len(line.lstrip("\t"))
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
            current = _TableAccumulator(name=m.group(1).strip())
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

        # Column
        m = _COLUMN_RE.match(line)
        if m:
            current.finalise_measure()
            col_name = m.group(1).strip()
            # Skip if it looks like a sub-property (contains colon = it's a property line)
            if ":" not in col_name:
                current.columns.append(col_name)
            continue

    # Flush last table
    if current:
        current.finalise_measure()
        tables.append(current)

    return ModelSchema(
        tables=[ModelTable(name=t.name, columns=t.columns) for t in tables],
        measures=[m for t in tables for m in t.measures],
        relationships=[],
    )


def _infer_return_type(fmt: str) -> str:
    if "$" in fmt or "\\$" in fmt:
        return "currency"
    if "%" in fmt:
        return "percentage"
    if "#,0" in fmt and "." not in fmt:
        return "integer"
    return "number"
