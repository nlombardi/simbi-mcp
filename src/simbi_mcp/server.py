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
from simbi_mcp.pbir.semantic_patcher import patch_semantic_model_measures
from simbi_mcp.semantic.schema_reader import parse_tmdl_schema
from simbi_mcp.types import ModelSchema

mcp: FastMCP = FastMCP(
    "SimBI",
    instructions=(
        "Generate Power BI dashboards from natural language.\n\n"
        "CHOOSE YOUR PATH based on whether the Microsoft Power BI MCP is available:\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "PATH 1 — SimBI only (no Microsoft Power BI MCP)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Use this path when the user has a CSV and no live Power BI Desktop\n"
        "connection, or when the Power BI MCP is not configured.\n\n"
        "  1. The user must first create a blank .pbip in Power BI Desktop\n"
        "     (File → New → File → Save As → Power BI Project format) and\n"
        "     then CLOSE Power BI Desktop.\n"
        "  2. Write TMDL yourself from the user's CSV description. Include:\n"
        "       - A table block with the correct column names and dataTypes\n"
        "         (string, int64, double, dateTime)\n"
        "       - Measure definitions with DAX expressions and formatStrings\n"
        "         (e.g. measure 'Total Revenue' = SUM(sales[Revenue]))\n"
        "       - A partition block pointing at the CSV file path\n"
        "     Do NOT call the Power BI MCP. Write the TMDL as inline text.\n"
        "  3. Call SimBI.parse_schema with the TMDL text you wrote in step 2.\n"
        "  4. Generate annotated HTML using the schema (see VOCABULARY below).\n"
        "     Every visual element MUST have non-zero CSS dimensions — use the\n"
        "     dashboard.css classes (db-page, db-grid, db-card, db-chart-area).\n"
        "  5. Call SimBI.validate_mockup_html to lint the HTML.\n"
        "  6. Call SimBI.emit_report with pbip_path pointing to the .pbip.\n"
        "     emit_report automatically writes the measures from step 2 into the\n"
        "     SemanticModel so they appear in Power BI Desktop on open.\n"
        "  7. Open the .pbip fresh in Power BI Desktop. Visuals render immediately\n"
        "     but show empty data — use Home → Transform data to connect the CSV.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "PATH 2 — Microsoft Power BI MCP + SimBI\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Use this path when the Power BI MCP is configured and a live Power BI\n"
        "Desktop instance is available. Produces a fully data-connected report.\n\n"
        "  1. Open the .pbip in Power BI Desktop (leave it open).\n"
        "  2. Use the Power BI MCP to build the semantic model (create tables,\n"
        "     measures, relationships, calculated tables, refresh data, etc.).\n"
        "  3. SYNC TO DISK — call Power BI MCP database_operations\n"
        "     ExportToTmdlFolder, tmdlFolderPath = <Name>.SemanticModel/definition.\n"
        "     Without this step all model changes are lost on next open.\n"
        "  4. CLOSE Power BI Desktop. This is MANDATORY before emit_report.\n"
        "     Power BI Desktop caches the Report in memory — SimBI's writes to\n"
        "     .Report/ are silently ignored until a fresh cold open.\n"
        "  5. Call SimBI.parse_schema with the SemanticModel/definition folder path.\n"
        "  6. Generate annotated HTML using the schema (see VOCABULARY below).\n"
        "     Every visual element MUST have non-zero CSS dimensions — use the\n"
        "     dashboard.css classes (db-page, db-grid, db-card, db-chart-area).\n"
        "  7. Call SimBI.validate_mockup_html to lint the HTML.\n"
        "  8. Call SimBI.emit_report with pbip_path pointing to the .pbip.\n"
        "  9. Open the .pbip fresh in Power BI Desktop. All visuals appear with\n"
        "     live data immediately — no refresh needed.\n\n"
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

    PREREQUISITE — Power BI Desktop MUST be closed before calling this tool:
      Power BI Desktop caches the Report in memory while the file is open.
      Any files SimBI writes to the .Report folder while the file is open will
      be silently ignored when the user reloads — visuals will appear missing.
      The correct sequence is: (1) use Power BI MCP to build the model,
      (2) ExportToTmdlFolder → SemanticModel/definition, (3) CLOSE Power BI
      Desktop, (4) call this tool, (5) open the .pbip fresh.

    PREREQUISITE — the .pbip MUST already exist before calling this tool:
      Power BI Desktop or the Power BI MCP creates the .pbip and its
      .SemanticModel (which holds the live data model). SimBI ONLY contributes
      the .Report/ folder. If no .pbip exists at pbip_path, this tool raises
      ValueError telling you to create it first — do not invent a new path.

    HTML SIZING — every visual element MUST have non-zero CSS dimensions:
      SimBI renders the HTML in headless Chrome to extract bounding boxes.
      A visual element with zero width/height produces an error. Use the
      dashboard.css classes (db-page, db-grid, db-card, db-chart-area, etc.)
      to ensure every element has a real computed size.

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
    # Path 1 only: if the SemanticModel exists but is missing measures (i.e. a
    # blank .pbip created by Power BI Desktop with no data connected), write the
    # measures into the TMDL so visuals aren't broken on open.
    # This check reads the TMDL and skips silently when measures are already
    # present, so Path 2 (measures written by the MS Power BI MCP) is untouched.
    semantic_model_dir = pbip.parent / f"{pbip.stem}.SemanticModel"
    if semantic_model_dir.exists():
        patch_semantic_model_measures(schema, semantic_model_dir)
    return str(report_dir)


def main() -> None:
    mcp.run()
