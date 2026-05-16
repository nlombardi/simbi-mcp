"""SimBI MCP server — exposes the three pipeline phases as MCP tools.

Tools (typical call order):
  parse_schema            TMDL str → ModelSchema JSON
  create_dashboard_mockup prompt + schema JSON → annotated HTML
  emit_report             HTML + schema JSON → PBIR folder path
  generate_dashboard      convenience: TMDL + prompt → PBIR folder path
"""
from __future__ import annotations

import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from simbi_mcp.mockup.generator import generate_mockup as _generate_mockup
from simbi_mcp.pbir.emitter import emit_pbir
from simbi_mcp.semantic.schema_reader import parse_tmdl_schema
from simbi_mcp.types import ModelSchema

load_dotenv()

mcp: FastMCP = FastMCP(
    "SimBI",
    instructions=(
        "Generate Power BI dashboards from natural language. "
        "Typical flow: parse_schema → create_dashboard_mockup → emit_report."
    ),
)


def _anthropic_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")
    return anthropic.Anthropic(api_key=api_key)


@mcp.tool()
def parse_schema(tmdl: str) -> str:
    """Convert a TMDL string (from Power BI MCP's ExportTMDL) to schema JSON.

    Returns a JSON-serialised ModelSchema that can be passed to other SimBI tools.
    """
    schema = parse_tmdl_schema(tmdl)
    return schema.model_dump_json()


@mcp.tool()
def create_dashboard_mockup(prompt: str, schema_json: str) -> str:
    """Generate an annotated HTML dashboard mockup from a schema.

    prompt: natural language description of the desired dashboard.
    schema_json: ModelSchema JSON returned by parse_schema.
    Returns the raw HTML string.
    """
    schema = ModelSchema.model_validate_json(schema_json)
    client = _anthropic_client()
    return _generate_mockup(prompt=prompt, schema=schema, client=client)


@mcp.tool()
async def emit_report(
    html: str,
    schema_json: str,
    report_name: str,
    output_dir: str,
) -> str:
    """Render an annotated HTML mockup and write a Power BI Report folder.

    html: annotated HTML from create_dashboard_mockup.
    schema_json: ModelSchema JSON from parse_schema.
    report_name: base name for the report, e.g. "SalesDashboard".
    output_dir: directory where <report_name>.Report will be created.
    Returns the absolute path to the created Report folder.
    """
    schema = ModelSchema.model_validate_json(schema_json)
    report_dir = await emit_pbir(
        html=html,
        schema=schema,
        report_name=report_name,
        output_dir=Path(output_dir),
    )
    return str(report_dir)


@mcp.tool()
async def generate_dashboard(
    prompt: str,
    tmdl: str,
    report_name: str,
    output_dir: str,
) -> str:
    """Full pipeline: TMDL + prompt → Power BI Report folder.

    prompt: natural language description of the desired dashboard.
    tmdl: TMDL string from Power BI MCP's ExportTMDL operation.
    report_name: base name for the report, e.g. "SalesDashboard".
    output_dir: directory where <report_name>.Report will be created.
    Returns the absolute path to the created Report folder.
    """
    schema = parse_tmdl_schema(tmdl)
    client = _anthropic_client()
    html = _generate_mockup(prompt=prompt, schema=schema, client=client)
    report_dir = await emit_pbir(
        html=html,
        schema=schema,
        report_name=report_name,
        output_dir=Path(output_dir),
    )
    return str(report_dir)


def main() -> None:
    mcp.run()
