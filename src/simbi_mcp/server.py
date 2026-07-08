"""SimBI MCP server — exposes Phase 1-3 pipelines as MCP tools.

Tools (typical call order):
  parse_schema   TMDL str → ModelSchema JSON
  emit_report    HTML + schema JSON → multi-line emission report (PBIR folder path + warnings)

Resources:
  simbi://annotation-vocabulary   data-pbi-* spec + CSS class catalog
"""
from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from simbi_mcp.dax.linter import lint_measures as _lint_measures
from simbi_mcp.mockup.annotations import ANNOTATION_SPEC_TEXT, CSS_CLASS_CATALOG
from simbi_mcp.mockup.validator import (
    ValidationError,
    count_annotated_visuals,
    validate_mockup,
)
from simbi_mcp.pbir.emitter import EmitResult, emit_pbir
from simbi_mcp.pbir.reserved_names import sanitize_schema, sanitize_semantic_model_dir
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
        "  2. INSPECT THE SOURCE BEFORE WRITING ANY DAX. Open the CSV/Excel\n"
        "     and confirm:\n"
        "       - Exact column names and dtypes (case-sensitive). Do not guess.\n"
        "       - SHAPE: long (one row per fact, single value column with a\n"
        "         key column like Year/Period) vs WIDE (one column per period,\n"
        "         e.g. [2024], [2025], [2026]). Most economic / financial\n"
        "         exports are WIDE.\n"
        "       - If WIDE: your TMDL MUST include an unpivoted table (Power\n"
        "         Query M `Table.UnpivotOtherColumns`) producing Year + Value\n"
        "         columns. Then aggregate Value with a FILTER on Year. Do NOT\n"
        "         write SUM(t[2026]) — aggregating a single period column is\n"
        "         almost always wrong.\n"
        "       - If filtering by a category encoded as a row value (e.g.\n"
        "         INDICATOR='Consumer prices'), prefer a stable ID column\n"
        "         (INDICATOR.ID, SERIES_CODE) over substring matches on the\n"
        "         display name. SEARCH() raises on no-match; if you must use\n"
        "         it, pass a 4th arg (BLANK()) or use CONTAINSSTRING().\n"
        "  3. Write TMDL yourself from the inspected source. Include:\n"
        "       - A table block with the correct column names and dataTypes\n"
        "         (string, int64, double, dateTime)\n"
        "       - NAMING: a table may NOT be named the reserved word 'Measures'\n"
        "         (Power BI refuses to open the .pbip: \"the name of the object\n"
        "         'Table' cannot be the reserved string 'Measures'\"). For a\n"
        "         dedicated measures-holding table use '_Measures' or\n"
        "         'Key Measures' instead.\n"
        "       - For wide sources: a second table block with an unpivot\n"
        "         partition (M: Table.UnpivotOtherColumns) producing long form\n"
        "       - Measure definitions with DAX expressions and formatStrings\n"
        "         (e.g. measure 'Total Revenue' = SUM(sales[Revenue]))\n"
        "       - A partition block pointing at the CSV/Excel file path\n"
        "     Do NOT call the Power BI MCP. Write the TMDL as inline text.\n"
        "  4. Call SimBI.lint_measures with the TMDL. Fix every ERROR; review\n"
        "     each WARNING and either fix it or confirm it is a deliberate\n"
        "     choice. A clean lint does NOT prove the DAX is correct — it\n"
        "     proves the known footguns are absent.\n"
        "  5. Call SimBI.parse_schema with the TMDL text you wrote in step 3.\n"
        "  6. Generate annotated HTML using the schema (see VOCABULARY below).\n"
        "     Every visual element MUST have non-zero CSS dimensions — use the\n"
        "     dashboard.css classes (db-page, db-grid, db-card, db-chart-area).\n"
        "  7. Call SimBI.validate_mockup_html to lint the HTML.\n"
        "  8. Call SimBI.emit_report with pbip_path pointing to the .pbip.\n"
        "     emit_report automatically writes the measures from step 3 into the\n"
        "     SemanticModel so they appear in Power BI Desktop on open.\n"
        "  9. Open the .pbip fresh in Power BI Desktop. Visuals render immediately\n"
        "     but show empty data — use Home → Transform data to connect the CSV.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "PATH 2 — Microsoft Power BI MCP + SimBI\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Use this path when the Power BI MCP is configured and a live Power BI\n"
        "Desktop instance is available. Produces a fully data-connected report.\n\n"
        "  1. Open the .pbip in Power BI Desktop (leave it open).\n"
        "  2. Use the Power BI MCP to build the semantic model (create tables,\n"
        "     measures, relationships, calculated tables, refresh data, etc.).\n"
        "     NAMING: never create a table named 'Measures' — it is reserved and\n"
        "     Power BI refuses to open the resulting .pbip. For a disconnected\n"
        "     measures-holding table use '_Measures' or 'Key Measures'.\n"
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
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "FALLBACK — Power BI MCP listed but not connected\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "If the Power BI MCP tools are visible but any call returns an error like\n"
        "'No connectionName provided', 'connect to a server first', 'no last used\n"
        "connection available', or any other not-connected error: do NOT retry the\n"
        "Power BI MCP call, and do NOT ask the user to open Power BI Desktop just\n"
        "to create measures. Switch to PATH 1 immediately.\n\n"
        "SimBI does NOT need a live Power BI connection to create measures,\n"
        "tables, or relationships. Everything is file-based:\n"
        "  - Write the full TMDL (tables + measure blocks + partitions) as inline\n"
        "    text and pass it to SimBI.parse_schema.\n"
        "  - SimBI.emit_report then writes those measures into the .SemanticModel\n"
        "    on disk via patch_semantic_model_measures — no XMLA, no live session.\n"
        "  - The user opens the .pbip fresh and the measures are already there.\n\n"
        "Reach for Power BI MCP only when you have already confirmed a live\n"
        "connection exists. The presence of the tool in the catalog is NOT proof\n"
        "of a connection.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "DESIGN PRINCIPLES — apply when generating the HTML mockup\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Distilled from docs/dashboard-design-playbook.md. These are not\n"
        "suggestions — they shape what gets emitted into Power BI.\n\n"
        "  LAYOUT\n"
        "    - Canvas is fixed 1280 × 720 (db-page). Never assume scroll.\n"
        "    - Backbone: KPI strip (top, db-row-1) → primary chart (largest\n"
        "      cell, typically db-col-2/3 + db-row-2) → supporting detail. If\n"
        "      you can't identify the primary chart, the dashboard has no\n"
        "      purpose yet — ask the user.\n"
        "    - F-pattern reading: most-important KPI top-left. Z-pattern only\n"
        "      for executive landing pages.\n"
        "    - Whitespace is signal, not waste. Don't fill cells just because\n"
        "      they are empty.\n\n"
        "  SLICER PLACEMENT\n"
        "    - Slicers go in ONE of two locations: a top rail (full canvas\n"
        "      width) OR a dedicated left column (single db-col-1). Never\n"
        "      scatter them. A scattered slicer is a broken slicer — readers\n"
        "      who cannot find the controls assume there are none.\n"
        "    - Default state: 'Select all'. Do NOT pre-filter unless the\n"
        "      dashboard title explicitly states the scope.\n"
        "    - SLICER STYLE — REQUIRED on every slicer, no exceptions:\n"
        "        data-pbi-style='dropdown'  text/category fields (default)\n"
        "        data-pbi-style='list'      short enum fields (≤10 items shown)\n"
        "        data-pbi-style='between'   numeric or date range fields (e.g. Year)\n"
        "      A slicer without this attribute WILL render as an unusable\n"
        "      tile/button layout in Power BI Desktop. There is no default.\n\n"
        "  CHART CHOICE\n"
        "    - 'Comparison across categories' → bar/column chart.\n"
        "    - 'Trend over time' → line chart (or area for cumulative).\n"
        "    - 'Part-to-whole' with ≤5 parts → pie/donut; ≥6 parts → sorted\n"
        "      bar (humans cannot compare arc lengths past a handful).\n"
        "    - 'Two measures, is there a relationship' → scatter/bubble.\n"
        "    - 'Single headline number' → card; with target → KPI.\n"
        "    - 'Process drop-off through stages' → funnel.\n"
        "    - When unsure, see docs/chart-catalog.md decision tree.\n\n"
        "  COLOUR\n"
        "    - SimBI ships a theme: Microsoft CY25SU10 palette + opinionated\n"
        "      visualStyles (gridlines off, no visual borders, lean cards).\n"
        "      You generally do NOT need to specify colours.\n"
        "    - Semantic colour is RESERVED: green = good, red = bad,\n"
        "      grey = neutral/inactive. Never reassign these to categorical\n"
        "      data (a red bar for APAC makes APAC look like an alert).\n"
        "    - Ordinal data (Low/Medium/High, 1-5 ratings) MUST use a\n"
        "      sequential palette — never categorical/rainbow.\n"
        "    - Never encode information by colour alone. ~8% of men have\n"
        "      colour-vision deficiency. Reinforce with label, shape, or\n"
        "      position (e.g. direct-label lines instead of relying on legend).\n\n"
        "  TYPOGRAPHY & NUMBERS\n"
        "    - One typeface, three sizes max. db-label (small muted) for the\n"
        "      dimension name; db-value (large bold) for the KPI number;\n"
        "      add a title size only for section headers.\n"
        "    - Right-align numerics. Hold precision constant within a column.\n"
        "    - Abbreviate at scale (1.2M not 1,234,567) but only consistently\n"
        "      across the whole column. Thousand-separators are mandatory.\n\n"
        "  ANTI-PATTERNS — refuse these even if the user asks for them, and\n"
        "  explain why\n"
        "    - 3D bars/pies/anything. Foreground reads taller; back slice\n"
        "      reads smaller. The chart encodes a lie before the numbers are\n"
        "      read. Use flat 2D.\n"
        "    - Pie or donut with more than 5 slices. Arc-length comparison\n"
        "      breaks down. Use a sorted bar chart.\n"
        "    - Dual-axis charts where the two axes don't share a meaningful\n"
        "      zero or unit. Implies correlation that may not exist. Use\n"
        "      small multiples (two line charts side-by-side) instead.\n"
        "    - Rainbow palettes on ordinal data. Hides the order. Use a\n"
        "      sequential palette.\n"
        "    - Decoration (gradients on bars, drop shadows on bars,\n"
        "      backgrounds, per-visual branding). Every non-data pixel\n"
        "      spends the reader's finite attention. Brand belongs in the\n"
        "      theme and page header, not on every visual.\n\n"
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


def _format_emit_result(result: EmitResult, validator_warnings: list[str]) -> str:
    lines = [f".Report written: {result.report_dir}"]
    if result.previews:
        lines.append("Preview (HTML mockup render, NOT a Power BI render):")
        lines.extend(f"  {p}" for p in result.previews)
    if result.styling_notes:
        lines.append("Styling transferred:")
        lines.extend(f"  {n}" for n in result.styling_notes)
    all_warnings = list(validator_warnings) + list(result.warnings)
    if all_warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {w}" for w in all_warnings)
    return "\n".join(lines)


@mcp.resource("simbi://annotation-vocabulary")
def annotation_vocabulary() -> str:
    """HTML annotation vocabulary and CSS class catalog for dashboard mockups."""
    return ANNOTATION_SPEC_TEXT + "\n" + CSS_CLASS_CATALOG


@mcp.tool()
def parse_schema(tmdl: str) -> str:
    """Convert TMDL to schema JSON.

    `tmdl` accepts either:
      - inline TMDL text that YOU write (the contents of a single table .tmdl, or
        concatenated files). This is the supported way to define tables, columns,
        partitions, AND measures WITHOUT a live Power BI MCP connection — include
        `measure` blocks directly in the TMDL text and emit_report will write them
        into the .SemanticModel on disk. You do NOT need Power BI MCP to create
        measures; SimBI handles the persistence itself.
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
    schema = sanitize_schema(parse_tmdl_schema(tmdl_text))
    return schema.model_dump_json()


@mcp.tool()
def lint_measures(tmdl: str) -> str:
    """Advisory lint of DAX measures in TMDL text. NOT a correctness check.

    Call this AFTER drafting your TMDL and BEFORE parse_schema, to catch a
    small set of mechanical mistakes that produce confusing runtime errors:

      ERROR    Reference to a table or column that does not exist in the TMDL.
               Almost always a typo or stale ref. Must be fixed.
      ERROR    Relationship GUID is not a valid random UUID. Sequential or
               hand-crafted GUIDs (e.g. a1b2c3d4-e5f6-7890-abcd-ef1234567890)
               cause Power BI Desktop to crash with "invalid column ID" on open.
               Generate a real random UUID for every relationship identifier.
      ERROR    lineageTag is not a full UUID. Truncated hex tags (20 chars) are
               silently misread by the TMDL parser. All lineageTag values must be
               xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx format.
      ERROR    Calculated table column missing sourceColumn property. Power BI
               Desktop requires sourceColumn even on calculated tables — it maps
               to the DAX output column name. Omitting it causes a load failure.
      WARNING  SEARCH() called without a 4th argument. SEARCH raises a runtime
               error when the substring is not found; pass a 4th arg (e.g.
               SEARCH(find, within, 1, BLANK())) or use CONTAINSSTRING.
      WARNING  Aggregation (SUM/AVERAGE/MIN/MAX/etc.) applied to a column whose
               name is a 4-digit year (e.g. SUM(t[2026])). Strong signal of a
               wide-format source that should be unpivoted to Year/Value first.

    Returns:
      "OK — no lint findings" when nothing triggered, OR a multi-line report
      with one finding per line. Findings have the form:
        [SEVERITY] <measure name> (<rule>): <message>
      A clean report does NOT mean the DAX is semantically correct — it means
      these specific footguns are absent. Semantic correctness still requires
      thought.

    This tool is advisory and non-exhaustive. The rule set is deliberately
    narrow to keep precision high; many real bugs are out of scope.
    """
    findings = _lint_measures(tmdl)
    if not findings:
        return "OK — no lint findings"
    return "\n".join(str(f) for f in findings)


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
    schema = sanitize_schema(ModelSchema.model_validate_json(schema_json))
    try:
        warnings = validate_mockup(html, schema)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    msg = f"OK — {count_annotated_visuals(html)} visuals validated"
    if warnings:
        msg += "\n\nWarnings:\n" + "\n".join(f"  - {w}" for w in warnings)
    return msg


@mcp.tool()
async def emit_report(
    html: str,
    schema_json: str,
    pbip_path: str,
    theme_path: str | None = None,
) -> str:
    """Render annotated HTML and write the .Report folder beside an existing .pbip.

    Args:
      html: HTML mockup where every visual element carries a `data-pbi` attribute
            plus the required field bindings (see VOCABULARY below).

            MULTI-PAGE: wrap each page's visuals in a `data-pbi-page` container.
            The container's attribute value becomes the page display name. All
            pages must be in a SINGLE html string passed in ONE call to this tool.

              <div data-pbi-page="Overview">
                <div data-pbi="card" data-pbi-measure="GDP Growth">...</div>
                ...
              </div>
              <div data-pbi-page="Details">
                <div data-pbi="lineChart" ...>...</div>
                ...
              </div>

            NEVER call emit_report multiple times to build a multi-page report —
            each call wipes the previous pages and corrupts the output. All pages
            go in ONE call. Without data-pbi-page containers, all visuals land on
            a single page named "Page 1".

      schema_json: the JSON string returned by parse_schema.
      pbip_path: EITHER the absolute path to an EXISTING .pbip file, OR the
            absolute path to a folder that already contains one. When given
            a folder, SimBI auto-discovers the single .pbip inside (if there
            are zero or multiple .pbip files in the folder, you get a clear
            error and must pass the file path explicitly). The .pbip and its
            sibling .SemanticModel — created earlier by Power BI Desktop or
            the Power BI MCP — are left untouched.
      theme_path: OPTIONAL absolute path to a partial PBIR theme JSON file
            (corp branding, custom palette, textClasses overrides, etc.).
            When omitted, SimBI emits its opinionated default theme:
            Microsoft CY25SU10 colour science + SimBI visualStyles enforcing
            the design playbook (hidden gridlines, lean cards, no visual
            borders, consistent Segoe UI typography). User themes deep-merge
            ONTO that default — pass only `dataColors` to rebrand without
            losing SimBI's visualStyles opinions.

    Returns: a multi-line human-readable report. The FIRST line is always
      ".Report written: <absolute path to the .Report folder>". Subsequent
      sections (each optional, present only when non-empty) list HTML mockup
      preview screenshots (NOT a Power BI render — a rough visual sanity
      check), WYSIWYG CSS styling transferred onto visuals, and warnings from
      both HTML validation and emission.

    PREREQUISITE — Power BI Desktop MUST be closed before calling this tool:
      Power BI Desktop caches the Report in memory while the file is open.
      Any files SimBI writes to the .Report folder while the file is open will
      be silently ignored when the user reloads — visuals will appear missing.

      Two supported sequences (pick based on whether you have a live Power BI
      MCP connection — NOT just whether the tool is listed in the catalog):

      Path 1 (no live connection — fully offline, file-based):
        (1) Write TMDL inline (tables + measure blocks + partitions),
        (2) parse_schema(tmdl), (3) ensure Power BI Desktop is CLOSED,
        (4) call this tool — measures are written into .SemanticModel
        automatically via patch_semantic_model_measures,
        (5) open the .pbip fresh.

      Path 2 (live Power BI MCP connection already established):
        (1) Use Power BI MCP to build the model in the live session,
        (2) ExportToTmdlFolder → SemanticModel/definition,
        (3) CLOSE Power BI Desktop, (4) parse_schema(<definition folder>),
        (5) call this tool, (6) open the .pbip fresh.

      If a Power BI MCP call fails with a not-connected error, do not retry —
      use Path 1 instead. SimBI does not require the live connection.

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
      <div data-pbi="slicer"      data-pbi-field="sales[Region]"   data-pbi-style="dropdown">...</div>
      <div data-pbi="slicer"      data-pbi-field="sales[Year]"     data-pbi-style="between">...</div>
      <div data-pbi="table"       data-pbi-columns="sales[Region],Total Revenue,Order Count">...</div>

    HARD RULES (these are the ONLY accepted shapes — anything else is rejected):
      - data-pbi-measure and data-pbi-values hold bare MEASURE names from the
        schema (e.g. "Total Revenue"). Never Table[Column].
      - data-pbi-axis, data-pbi-field, data-pbi-series hold Table[Column] refs
        (e.g. "sales[Region]"). Never a bare measure name.
      - Every slicer MUST have data-pbi-style="dropdown", "list", or "between".
        Omitting it is a hard error — Power BI will render an unusable button tile.
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
    schema = sanitize_schema(ModelSchema.model_validate_json(schema_json))
    try:
        validator_warnings = validate_mockup(html, schema)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    result = await emit_pbir(
        html=html,
        schema=schema,
        report_name=pbip.stem,
        output_dir=pbip.parent,
        theme_path=Path(theme_path) if theme_path else None,
    )
    # Path 1 only: if the SemanticModel exists but is missing measures (i.e. a
    # blank .pbip created by Power BI Desktop with no data connected), write the
    # measures into the TMDL so visuals aren't broken on open.
    # This check reads the TMDL and skips silently when measures are already
    # present, so Path 2 (measures written by the MS Power BI MCP) is untouched.
    semantic_model_dir = pbip.parent / f"{pbip.stem}.SemanticModel"
    if semantic_model_dir.exists():
        # Rename any reserved-named table the upstream authoring tool (Power BI
        # MCP / Desktop) wrote — e.g. "Measures" — BEFORE patching measures, so
        # the patcher sees the renamed file (measures already present) and the
        # model matches the report SimBI emitted from the sanitized schema.
        sanitize_semantic_model_dir(semantic_model_dir)
        patch_semantic_model_measures(schema, semantic_model_dir)
    return _format_emit_result(result, validator_warnings)


def main() -> None:
    mcp.run()
