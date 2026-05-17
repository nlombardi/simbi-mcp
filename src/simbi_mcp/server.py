"""SimBI MCP server — exposes Phase 1-3 pipelines as MCP tools.

Tools (typical call order):
  parse_schema   TMDL str → ModelSchema JSON
  emit_report    HTML + schema JSON → PBIR folder path

Resources:
  simbi://annotation-vocabulary   data-pbi-* spec + CSS class catalog
"""
from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from simbi_mcp.mockup.annotations import ANNOTATION_SPEC_TEXT, CSS_CLASS_CATALOG
from simbi_mcp.pbir.emitter import emit_pbir
from simbi_mcp.semantic.schema_reader import parse_tmdl_schema
from simbi_mcp.types import ModelSchema

mcp: FastMCP = FastMCP(
    "SimBI",
    instructions=(
        "Generate Power BI dashboards from natural language. "
        "Workflow: (1) read simbi://annotation-vocabulary to learn the HTML annotation spec, "
        "(2) call parse_schema to parse TMDL into a schema, "
        "(3) generate annotated HTML yourself using the schema and vocabulary, "
        "(4) call emit_report to produce the .pbip Report folder."
    ),
)


@mcp.resource("simbi://annotation-vocabulary")
def annotation_vocabulary() -> str:
    """HTML annotation vocabulary and CSS class catalog for dashboard mockups."""
    return ANNOTATION_SPEC_TEXT + "\n" + CSS_CLASS_CATALOG


@mcp.tool()
def parse_schema(tmdl: str) -> str:
    """Convert a TMDL string (from Power BI MCP's ExportTMDL) to schema JSON.

    Returns a JSON-serialised ModelSchema that can be passed to emit_report.
    """
    schema = parse_tmdl_schema(tmdl)
    return schema.model_dump_json()


@mcp.tool()
async def emit_report(
    html: str,
    schema_json: str,
    report_name: str,
    output_dir: str,
) -> str:
    """Render an annotated HTML mockup and write a Power BI Report folder.

    html: annotated HTML you generated using the simbi://annotation-vocabulary spec.
    schema_json: ModelSchema JSON from parse_schema.
    report_name: base name for the report, e.g. "SalesDashboard".
    output_dir: directory where the project files will be created.
    Returns the absolute path to <report_name>.pbip — open this in Power BI Desktop.
    """
    schema = ModelSchema.model_validate_json(schema_json)
    report_dir = await emit_pbir(
        html=html,
        schema=schema,
        report_name=report_name,
        output_dir=Path(output_dir),
    )
    return str(report_dir)


def main() -> None:
    mcp.run()
