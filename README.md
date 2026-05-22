# SimBI MCP

An MCP server that generates Power BI dashboards from natural language. Point it at a CSV and describe the dashboard you want — it produces a `.pbip` Report folder that Power BI Desktop can open directly.

## How it works

SimBI chains three phases into two MCP tools and one resource:

```
User prompt + CSV
      │
      ▼  [MS Power BI MCP]  ← optional: provides a real data model
  Semantic model  ──→  TMDL string
      │
      ▼  parse_schema
  ModelSchema JSON
      │
      ▼  [Claude reads simbi://annotation-vocabulary and generates HTML in-context]
  Annotated HTML mockup  (data-pbi-* annotations)
      │
      ▼  emit_report
  <name>.pbip + <name>.Report/ + <name>.SemanticModel/
  (Playwright renders HTML → extracts bounding boxes → writes PBIR files + BIM model stub)
```

Claude generates the HTML mockup itself using the annotation vocabulary exposed as an MCP resource. `emit_report` always produces a complete, openable `.pbip` project — a BIM model stub is generated from the schema so Power BI Desktop can open the file even without the MS Power BI MCP.

When the MS Power BI MCP is also configured, it creates a real semantic model from the CSV (with actual loaded data). SimBI's stub is then a placeholder that can be replaced with the real model.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Google Chrome (system install — used by Playwright for PBIR layout extraction)
- The [Microsoft Power BI MCP](https://github.com/microsoft/power-bi-mcp) configured in your MCP client (for semantic model creation)

## Installation

```bash
git clone <repo>
cd "SimBI MCP"
uv sync
```

## Running the server

```bash
uv run simbi-mcp
```

The server speaks the MCP stdio protocol. Configure it in Claude Desktop or Claude Code alongside the Microsoft Power BI MCP.

### Claude Desktop config example

```json
{
  "mcpServers": {
    "simbi": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/SimBI MCP", "simbi-mcp"]
    },
	  "powerbi-modeling-mcp": {
			"type": "stdio",
			"command": "npx",
			"args": [
				"-y",
				"@microsoft/powerbi-modeling-mcp@latest",
				"--start"				
			]
		}	
  }
}
```

## Resource

### `simbi://annotation-vocabulary`

The `data-pbi-*` HTML annotation spec and CSS class catalog. Claude reads this once per session to learn how to annotate visuals and which layout classes are available. No tool call needed — it's reference data.

## Tools

### `parse_schema`

Converts a TMDL string (from the Power BI MCP's `ExportTMDL` operation) into a SimBI schema JSON that the other tools consume.

```
Input:  tmdl: str
Output: ModelSchema JSON string
```

### `emit_report`

Renders an annotated HTML mockup in Chrome, extracts visual bounding boxes, and writes a complete `.pbip` project into `output_dir`.

```
Input:  html: str, schema_json: str, report_name: str, output_dir: str
Output: absolute path to <report_name>.pbip  ← open this in Power BI Desktop
Needs:  system Chrome
```

`output_dir` should be a dedicated project folder (e.g. `C:/Reports/SalesDashboard/`). Three sibling artifacts are written there: `<name>.pbip`, `<name>.Report/`, and `<name>.SemanticModel/` (stub generated from schema, skipped if folder already exists).

## End-to-end usage

`emit_report` writes three sibling files into `output_dir`:

```
<output_dir>/
  <name>.pbip                ← open this in Power BI Desktop
  <name>.Report/             ← PBIR report layout
  <name>.SemanticModel/      ← semantic model (real or stub, see paths below)
```

`output_dir` should be a dedicated project folder — **not** the SimBI MCP repo. For example: `C:/Reports/SalesDashboard/`.

---

### Path 1 — SimBI builds everything (no MS Power BI MCP needed)

SimBI generates the layout and a schema-correct semantic model stub from your CSV description. The stub has the right tables and measures but no loaded data — visuals open empty in PBI Desktop until you connect a data source.

**Prompt Claude:**
```
Build me a sales dashboard. My data is at C:/Data/sales.csv with columns:
Region, OrderDate, Revenue, Units, Category

Measures I want: Total Revenue (SUM of Revenue), Order Count (COUNTROWS),
Avg Unit Price (Revenue / Units)

Save the report to C:/Reports/SalesDashboard as "SalesDashboard"
```

**What Claude does:**
1. Reads `simbi://annotation-vocabulary`
2. Calls `parse_schema` with TMDL derived from your CSV description
3. Generates the annotated HTML mockup in-context
4. Calls `emit_report(report_name="SalesDashboard", output_dir="C:/Reports/SalesDashboard")`

**Output:**
```
C:/Reports/SalesDashboard/
  SalesDashboard.pbip        ← open this
  SalesDashboard.Report/
  SalesDashboard.SemanticModel/   ← stub: correct structure, no loaded data
```

---

### Path 2 — MS Power BI MCP builds the semantic model, SimBI builds the report

The MS Power BI MCP builds the full live semantic model (measures, calculated tables, relationships, loaded data). SimBI generates the report layout. The result is a fully data-connected report.

> **Critical ordering rule:** Power BI Desktop must be **open** while the MCP builds the model, and **closed** before SimBI emits the report. Writing to the `.Report` folder while the file is open has no effect — Power BI Desktop serves its cached in-memory Report and ignores disk changes until a cold open.

**Step 1 — Open the .pbip in Power BI Desktop, then build the model with the MS Power BI MCP:**
```
The file C:/Reports/SalesDashboard/SalesDashboard.pbip is open in Power BI Desktop.

Use the Power BI MCP to:
1. Connect to the running Power BI Desktop instance
2. Refresh data to load C:/Data/sales.csv
3. Create a Calendar calculated table:
   ADDCOLUMNS(CALENDARAUTO(), "MonthName", FORMAT([Date], "MMM YYYY"), ...)
4. Create a relationship from sales[OrderDate] (Many) to Calendar[Date] (One)
5. Mark Calendar as the date table
6. Create measures: Total Revenue, Order Count, Avg Unit Price
7. Full model refresh
8. ExportToTmdlFolder → C:/Reports/SalesDashboard/SalesDashboard.SemanticModel/definition
```

**Step 2 — Close Power BI Desktop.**

This is mandatory. Do not skip it.

**Step 3 — Have SimBI generate the report:**
```
Power BI Desktop is now closed.

Use SimBI to build a sales dashboard:
1. parse_schema from C:/Reports/SalesDashboard/SalesDashboard.SemanticModel/definition
2. Generate HTML using db-page, db-grid, db-card, db-chart-area classes
   (every visual needs real CSS dimensions — zero-size elements are rejected)
3. validate_mockup_html
4. emit_report with pbip_path = C:/Reports/SalesDashboard/SalesDashboard.pbip
```

**Step 4 — Open the .pbip fresh in Power BI Desktop.**

Both the semantic model and the report are read from disk on cold open — all visuals appear with live data immediately, no refresh needed.

**Output:**
```
C:/Reports/SalesDashboard/
  SalesDashboard.pbip
  SalesDashboard.Report/
    definition/pages/<guid>/visuals/   ← visual.json files
  SalesDashboard.SemanticModel/
    definition/
      tables/Calendar.tmdl             ← calculated date table
      tables/sales_small.tmdl          ← measures + partition
      relationships.tmdl               ← active Calendar relationship
```

---

### Smoke-test the server locally

```bash
uv run simbi-mcp
```

The server starts silently (stdio protocol). Ctrl+C to exit. If it starts without errors the entry point and imports are working.

## Development

```bash
# Run unit tests (no API key or Chrome needed)
uv run pytest tests/unit/ -v

# Run integration tests (Chrome required)
uv run pytest -m integration -v

# Lint and typecheck
uv run ruff check src tests
uv run mypy src
```

## Project structure

```
src/simbi_mcp/
├── server.py          MCP tools (FastMCP)
├── semantic/          Phase 1: dataset profiling, measure planning, MS MCP adapter
├── mockup/            Phase 2: HTML generator, annotation vocabulary, validator
└── pbir/              Phase 3: DOM extractor, visual JSON templates, PBIR writer
```

## Supported visual types

| Annotation | Power BI visual | Fields |
|---|---|---|
| `card` | Card | `data-pbi-measure` |
| `columnChart` | Clustered column chart | `data-pbi-axis`, `data-pbi-values` |
| `lineChart` | Line chart | `data-pbi-axis`, `data-pbi-values`, `data-pbi-series` (optional) |
| `slicer` | Slicer | `data-pbi-field` |
| `table` | Table | `data-pbi-columns` (comma-separated measures) |
