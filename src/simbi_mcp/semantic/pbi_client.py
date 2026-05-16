"""Adapter around the Microsoft Power BI MCP.

This is the ONLY file in our codebase that knows MS MCP tool names and
argument shapes. Everything else uses our typed interface.

Tool documentation: spikes/02_ms_mcp_smoke/NOTES.md
"""
from __future__ import annotations

from typing import Any

from simbi_mcp.types import ColumnProfile, ColumnRole, DatasetProfile, MeasurePlan

# --- MS MCP tool names ---
_TOOL_TABLE = "table_operations"
_TOOL_MEASURE = "measure_operations"
_TOOL_MODEL = "model_operations"

# --- PBI DataType mapping ---
_DTYPE_MAP: dict[str, str] = {
    "Int64": "Int64",
    "Float64": "Double",
    "Float32": "Double",
    "String": "String",
    "Utf8": "String",
    "Date": "DateTime",
    "Datetime": "DateTime",
    "Boolean": "Boolean",
}

# --- M expression type mapping ---
_M_TYPE_MAP: dict[str, str] = {
    "Int64": "Int64.Type",
    "Double": "type number",
    "String": "type text",
    "DateTime": "type date",
    "Boolean": "type logical",
}

# --- FormatString by MeasurePlan.return_type ---
_FORMAT_MAP: dict[str, str] = {
    "currency": r"\$#,0.00;(\$#,0.00)",
    "integer": "#,0",
    "percentage": "0.00%;-0.00%;0.00%",
    "number": "#,0.00",
}


class PbiClient:
    """Typed wrapper around a Microsoft Power BI MCP session.

    The MCP is session-scoped: all calls operate on the same connected model.
    No identifiers are passed between calls.
    """

    def __init__(self, *, session: Any) -> None:
        self._session = session

    async def create_table(self, profile: DatasetProfile) -> None:
        """Create a table in the connected model from a dataset profile."""
        await self._session.call_tool(
            _TOOL_TABLE,
            arguments={
                "operation": "Create",
                "definitions": [_build_table_definition(profile)],
            },
        )

    async def refresh_table(self, table_name: str) -> None:
        """Refresh (load data into) a table after creation."""
        await self._session.call_tool(
            _TOOL_TABLE,
            arguments={
                "operation": "RefreshWithXMLA",
                "definitions": [{"Name": table_name}],
            },
        )

    async def create_measures(
        self,
        *,
        table_name: str,
        measures: list[MeasurePlan],
    ) -> None:
        """Create all measures in a single batched call."""
        if not measures:
            return
        await self._session.call_tool(
            _TOOL_MEASURE,
            arguments={
                "operation": "Create",
                "definitions": [
                    _build_measure_definition(table_name, m) for m in measures
                ],
            },
        )

    async def get_raw_schema(self) -> str:
        """Export the current model as a TMDL string."""
        result = await self._session.call_tool(
            _TOOL_MODEL,
            arguments={
                "operation": "ExportTMDL",
                "tmdlExportOptions": {"maxReturnCharacters": -1},
            },
        )
        return _extract_tmdl(result)


# --- Private helpers ---

def _build_table_definition(profile: DatasetProfile) -> dict[str, Any]:
    """Construct the table_operations.Create definition from a DatasetProfile."""
    path = profile.source_path.replace("\\", "\\\\")
    col_count = len(profile.columns)

    type_pairs = ", ".join(
        f'{{"{c.name}", {_m_type(c.dtype)}}}'
        for c in profile.columns
    )
    m_expr = (
        "let\n"
        f'    Source = Csv.Document(File.Contents("{path}"), '
        f"[Delimiter=\",\", Columns={col_count}, Encoding=1252, QuoteStyle=QuoteStyle.None]),\n"
        "    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),\n"
        f"    ChangedTypes = Table.TransformColumnTypes(PromotedHeaders, {{{type_pairs}}})\n"
        "in\n"
        "    ChangedTypes"
    )

    columns = [
        _build_column_entry(c, i) for i, c in enumerate(profile.columns)
    ]

    return {
        "Name": profile.table_name,
        "Mode": "Import",
        "MExpression": m_expr,
        "Columns": columns,
    }


def _build_column_entry(col: ColumnProfile, ordinal: int) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "Name": col.name,
        "DataType": _pbi_dtype(col.dtype),
        "Ordinal": ordinal,
        "SummarizeBy": "Sum" if col.role == ColumnRole.MEASURE else "None",
    }
    if col.role == ColumnRole.DATE:
        entry["FormatString"] = "Short Date"
    elif col.role == ColumnRole.MEASURE and "Float" in col.dtype:
        entry["FormatString"] = r"\$#,0.00;(\$#,0.00)"
    return entry


def _build_measure_definition(table_name: str, measure: MeasurePlan) -> dict[str, Any]:
    return {
        "TableName": table_name,
        "Name": measure.name,
        "Expression": measure.expression,
        "FormatString": _FORMAT_MAP.get(measure.return_type, "#,0.00"),
    }


def _pbi_dtype(polars_dtype: str) -> str:
    return _DTYPE_MAP.get(polars_dtype, "String")


def _m_type(polars_dtype: str) -> str:
    pbi = _DTYPE_MAP.get(polars_dtype, "String")
    return _M_TYPE_MAP.get(pbi, "type text")


def _extract_tmdl(result: Any) -> str:
    """Extract the TMDL string from an MCP tool result."""
    content = getattr(result, "content", None)
    if not content:
        raise ValueError("MS MCP returned empty content")
    first = content[0]
    # Dict-style content
    if isinstance(first, dict):
        for key in ("tmdlDocument", "tmdl", "result", "content"):
            if key in first and isinstance(first[key], str):
                return str(first[key])
        raise ValueError(f"No TMDL string found in response keys: {list(first.keys())}")
    # Text block style (some MCP transports)
    if hasattr(first, "text"):
        return str(first.text)  # str() ensures return type is str, not Any
    raise ValueError(f"Unexpected MS MCP content shape: {type(first)}")
