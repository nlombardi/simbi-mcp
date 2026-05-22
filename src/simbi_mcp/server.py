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
from simbi_mcp.mockup.validator import (
    ValidationError,
    count_annotated_visuals,
    validate_mockup,
)
from simbi_mcp.pbir.emitter import emit_pbir
from simbi_mcp.semantic.schema_reader import parse_tmdl_schema
from simbi_mcp.types import ModelSchema

mcp: FastMCP = FastMCP(
    "SimBI",
    instructions=(
        "Generate Power BI dashboards from natural language.\n\n"
        "END-TO-END WORKFLOW (Power BI Desktop is the source of truth for the\n"
        "data model — SimBI only writes the .Report folder):\n"
        "  1. Build the semantic model in the live Power BI Desktop instance\n"
        "     via the Power BI MCP (create tables, measures, relationships,\n"
        "     calculated tables, etc.).\n"
        "  2. **SYNC TMDL TO DISK** — call the Power BI MCP's\n"
        "     database_operations.ExportToTmdlFolder with tmdlFolderPath set to\n"
        "     `<project>/<Name>.SemanticModel/definition`. Without this step,\n"
        "     model changes live only in PBI Desktop memory; reopening the\n"
        "     .pbip will show none of your measures or relationships.\n"
        "  3. Call SimBI.parse_schema with the same folder path (or any folder\n"
        "     produced by ExportTMDL/ExportToTmdlFolder) to get the schema JSON.\n"
        "  4. Generate annotated HTML using the schema and the vocabulary below.\n"
        "  5. Call SimBI.validate_mockup_html to lint the HTML cheaply.\n"
        "  6. Call SimBI.emit_report to write the .Report folder beside the .pbip.\n"
        "  7. The user reloads the .pbip in Power BI Desktop and sees a complete\n"
        "     dashboard with measures, relationships, and visuals all wired.\n\n"
        + ANNOTATION_SPEC_TEXT
        + "\n"
        + CSS_CLASS_CATALOG
    ),
)


def _resolve_pbip(pbip_path: str) -> Path:
    """Resolve pbip_path to an existing .pbip file.

    Accepts either the .pbip file path directly, or a folder that contains
    exactly one .pbip. Anything else raises ValueError with guidance.
    """
    candidate = Path(pbip_path)
    if candidate.is_file() and candidate.suffix.lower() == ".pbip":
        return candidate
    if candidate.is_dir():
        matches = sorted(candidate.glob("*.pbip"))
        if not matches:
            raise ValueError(
                f"No .pbip file found in folder {pbip_path!r}. Create one "
                f"first via Power BI Desktop (File → Save As .pbip) or the "
                f"Power BI MCP, then re-call emit_report. SimBI does not "
                f"create new .pbip projects."
            )
        if len(matches) > 1:
            names = [p.name for p in matches]
            raise ValueError(
                f"Folder {pbip_path!r} contains multiple .pbip files: "
                f"{names}. Pass the specific .pbip file path instead."
            )
        return matches[0]
    raise ValueError(
        f"pbip_path={pbip_path!r} must point to an EXISTING .pbip file or "
        f"a folder containing one. Create the project first via Power BI "
        f"Desktop or the Power BI MCP. SimBI does not create new .pbip projects."
    )


@mcp.resource("simbi://annotation-vocabulary")
def annotation_vocabulary() -> str:
    """HTML annotation vocabulary and CSS class catalog for dashboard mockups."""
    return ANNOTATION_SPEC_TEXT + "\n" + CSS_CLASS_CATALOG


@mcp.tool()
def parse_schema(tmdl: str) -> str:
    """Convert TMDL to schema JSON.

    `tmdl` accepts either:
      - inline TMDL text (the contents of a single table .tmdl, or concatenated files), OR
      - a path to ANY folder containing .tmdl files. All .tmdl files in the folder
        (recursively) are concatenated in sorted order before parsing. Typical sources:
          * a folder produced by Power BI MCP's ExportTMDL / ExportToTmdlFolder, OR
          * the live `<Name>.SemanticModel/definition` folder of a .pbip project
            (Power BI Desktop's TMDL layout, with a `tables/` subdirectory) — preferred,
            since it stays in sync after a Power BI MCP ExportToTmdlFolder back into it.

    Returns a JSON-serialised ModelSchema that can be passed to emit_report.
    """
    tmdl_text = tmdl
    if len(tmdl) < 1024 and "\n" not in tmdl:
        try:
            candidate = Path(tmdl)
        except (OSError, ValueError):
            candidate = None
        if candidate is not None and candidate.is_dir():
            tmdl_text = "\n".join(
                p.read_text(encoding="utf-8") for p in sorted(candidate.rglob("*.tmdl"))
            )
            if not tmdl_text.strip():
                raise ValueError(f"No .tmdl files found in {candidate}")
    schema = parse_tmdl_schema(tmdl_text)
    return schema.model_dump_json()


@mcp.tool()
def validate_mockup_html(html: str, schema_json: str) -> str:
    """Dry-run check that annotated HTML conforms to the data-pbi vocabulary.

    Fast linter — no Chrome render, no files written. Call this BEFORE emit_report
    to iterate on annotations cheaply. Run it after every HTML edit.

    Args:
      html: the annotated HTML to check.
      schema_json: the JSON string returned by parse_schema.

    Returns:
      On success: "OK — N visuals validated" where N is the count of data-pbi
      elements found. The same HTML will pass emit_report's validation step.
      On failure: raises ValueError with the exact offending attribute and a
      correct-shape example. Fix the HTML and call this tool again.
    """
    schema = ModelSchema.model_validate_json(schema_json)
    try:
        validate_mockup(html, schema)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    return f"OK — {count_annotated_visuals(html)} visuals validated"


@mcp.tool()
async def emit_report(
    html: str,
    schema_json: str,
    pbip_path: str,
) -> str:
    """Render annotated HTML and write the .Report folder beside an existing .pbip.

    Args:
      html: HTML mockup where every visual element carries a `data-pbi` attribute
            plus the required field bindings (see VOCABULARY below).
      schema_json: the JSON string returned by parse_schema.
      pbip_path: EITHER the absolute path to an EXISTING .pbip file, OR the
            absolute path to a folder that already contains one. When given
            a folder, SimBI auto-discovers the single .pbip inside (if there
            are zero or multiple .pbip files in the folder, you get a clear
            error and must pass the file path explicitly). The .pbip and its
            sibling .SemanticModel — created earlier by Power BI Desktop or
            the Power BI MCP — are left untouched.

    Returns: absolute path to the .Report folder that was written.

    PREREQUISITE — the .pbip MUST already exist before calling this tool:
      Power BI Desktop or the Power BI MCP creates the .pbip and its
      .SemanticModel (which holds the live data model). SimBI ONLY contributes
      the .Report/ folder. If no .pbip exists at pbip_path, this tool raises
      ValueError telling you to create it first — do not invent a new path.

    VOCABULARY — every visual MUST be a single element tagged like this:

      <div data-pbi="card"        data-pbi-measure="Total Revenue">...</div>
      <div data-pbi="columnChart" data-pbi-axis="sales[Region]"
                                  data-pbi-values="Total Revenue">...</div>
      <div data-pbi="barChart"    data-pbi-axis="sales[Region]"
                                  data-pbi-values="Total Revenue">...</div>
      <div data-pbi="lineChart"   data-pbi-axis="sales[OrderDate]"
                                  data-pbi-values="Total Revenue"
                                  data-pbi-series="sales[Category]">...</div>
      <div data-pbi="slicer"      data-pbi-field="sales[Region]">...</div>
      <div data-pbi="table"       data-pbi-columns="sales[Region],Total Revenue,Order Count">...</div>

    HARD RULES (these are the ONLY accepted shapes — anything else is rejected):
      - data-pbi-measure and data-pbi-values hold bare MEASURE names from the
        schema (e.g. "Total Revenue"). Never Table[Column].
      - data-pbi-axis, data-pbi-field, data-pbi-series hold Table[Column] refs
        (e.g. "sales[Region]"). Never a bare measure name.
      - data-pbi-columns (table visual) is comma-separated; each token is EITHER
        a bare measure name OR a Table[Column] ref. Column tokens become row
        groupings; measure tokens become aggregated value columns.
      - The value of data-pbi MUST be one of: card, columnChart, barChart,
        lineChart, slicer, table. Anything else is rejected.
      - Use absolute pixel positions (left/top/width/height) on each visual
        so the renderer can capture geometry. CSS grid/flex is fine for layout
        but each visual element needs computable bounding box.

    On any annotation problem, this tool raises ValueError with the exact
    element that failed and a corrected example — fix the HTML and call again.
    """
    pbip = _resolve_pbip(pbip_path)
    schema = ModelSchema.model_validate_json(schema_json)
    try:
        validate_mockup(html, schema)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    report_dir = await emit_pbir(
        html=html,
        schema=schema,
        report_name=pbip.stem,
        output_dir=pbip.parent,
    )
    return str(report_dir)


def main() -> None:
    mcp.run()
