![Markdown Logo](SimBI-MCP.jpg)

# SimBI MCP

An MCP server that generates Power BI dashboards from natural language. Point it at a CSV, or connect your data to an existing `.pbip` report and describe the dashboard you want, it produces a `.pbip` Report folder that Power BI Desktop can open directly.

## How it works

SimBI chains three phases into eight MCP tools and one resource:

```
.pbip created in Power BI Desktop (required first step)
      │
      ├─── [Path 1: SimBI-Only]
      │      │
      │      ▼  analyze_data_source  ← Profile CSV/Excel schema
      │      │
      │      ▼  lint_measures  ← Advisory DAX checks on written TMDL
      │      │
      │      ▼  write_semantic_model  ← Save/format TMDL into .SemanticModel/
      │
      └─── [Path 2: MS Power BI MCP] (Optional: builds live semantic model)
             │
             ▼  ExportToTmdlFolder  → SemanticModel/definition/
      │
      ▼  CLOSE Power BI Desktop  ← mandatory before emit_report
      │
      ▼  parse_schema (from in-memory TMDL or SemanticModel/definition/)
  ModelSchema JSON
      │
      ▼  [Claude calls get_vocabulary + reads simbi://annotation-vocabulary]
  Annotated HTML mockup  (data-pbi-* annotations)
      │
      ▼  validate_mockup_html  ← Cheap lint before render
      │
      ▼  emit_report (pbip_path → existing .pbip; optional theme_path)
  <name>.Report/   (Playwright renders HTML → extracts bounding boxes → writes
                    PBIR files + opinionated SimBIDefault theme baked in)
      │
      ▼  Open .pbip fresh in Power BI Desktop
  Live dashboard
```

**SimBI only writes the `.Report/` folder.** The `.pbip` and `.SemanticModel/` must already exist before calling `emit_report` — Power BI Desktop creates them. SimBI never creates or modifies the `.pbip` file itself.

**Power BI Desktop must be closed before `emit_report` runs.** While the file is open, Power BI Desktop caches the Report in memory and ignores any disk writes to the `.Report/` folder. Always close first, emit, then open fresh.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Google Chrome (system install — used by Playwright for PBIR layout extraction)
- The [Microsoft Power BI MCP](https://github.com/microsoft/power-bi-mcp) configured in your MCP client (for semantic model creation)

## Installation

```bash
git clone https://gitlab.com/ds-simbi/simbi-mcp.git
cd simbi-mcp
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

### `analyze_data_source`

Profiles a CSV or Excel file's structure before authoring TMDL. Call this to inspect column names, types, null stats, and identify wide-format structures that require an unpivot transformation.

```
Input:  path: str, sheet: str | None = None
Output: JSON profile string (tables, column names, types, distinct counts, sample values, and layout/pivot hints)
```

### `write_semantic_model`

Persists agent-authored TMDL (tables, relationships, measures, partitions) directly into the `.SemanticModel` folder. This tool automatically normalizes reserved table names (e.g. `Measures` -> `_Measures`), corrects indentation errors (replaces spaces with literal tabs), repairs partition syntax, and rejects load-blocking errors before anything is written to disk.

```
Input:  tmdl: str, pbip_path: str
Output: "Semantic model written to <path>" OR raises ValueError
```

### `parse_schema`

Converts TMDL into a SimBI schema JSON that the layout and validation tools consume. Accepts either inline TMDL text you drafted, or a path to a folder containing `.tmdl` files (e.g., `<Name>.SemanticModel/definition`).

```
Input:  tmdl: str   ← inline TMDL OR path to a folder of .tmdl files
Output: ModelSchema JSON string
```

### `lint_measures`

Advisory lint of DAX measures in TMDL text. **Not** a correctness check — catches a deliberately narrow set of mechanical mistakes that produce confusing runtime errors. Call this after drafting your TMDL and before parsing/persisting.

| Rule | Severity | Catches |
|---|---|---|
| `unknown-table` / `unknown-column` | ERROR | Reference to a table/column that doesn't exist in the TMDL (typos, stale refs) |
| `unknown-relationship-uuid` | ERROR | Relationship GUID is not a valid random UUID (crashes Power BI Desktop) |
| `lineage-tag-format` | ERROR | lineageTag is not a valid UUID (silently misread by Power BI) |
| `calculated-column-source` | ERROR | Calculated-table column is missing a sourceColumn (load failure) |
| `search-arity` | WARNING | `SEARCH()` called without a 4th argument — raises a runtime error on no-match; use `SEARCH(find, within, 1, BLANK())` or `CONTAINSSTRING(within, find)` instead |
| `year-literal-aggregation` | WARNING | `SUM`/`AVERAGE`/etc. applied to a column whose name is a 4-digit year (`SUM(t[2026])`) — usually a wide-format source that should be unpivoted to Year/Value first |

```
Input:  tmdl: str
Output: "OK — no lint findings"   OR   one finding per line
```

### `get_vocabulary`

Returns the full `data-pbi-*` annotation vocabulary, universal attributes, styling contract, and CSS class catalog for mockup layout. Call this before writing mockup HTML.

```
Input:  None
Output: Annotation spec and CSS catalog string
```

### `validate_mockup_html`

Cheap dry-run of the annotated HTML mockup against the parsed schema. No Chrome render, no files written — call it after every HTML edit to iterate on annotations without paying the emit cost.

```
Input:  html: str, schema_json: str
Output: "OK — N visuals validated"   OR   raises ValueError with the offending attribute + a correct-shape example
```

### `get_theme_schema`

Returns the report-wide theme JSON schema showing the three-tier resolution order (Microsoft CY25SU10 → SimBI opinionated `visualStyles` → optional `theme_path` deep-merged) and the actual defaults. Call this before writing a custom theme file.

```
Input:  None
Output: Theme schema documentation text
```

### `emit_report`

Renders an annotated HTML mockup in Chrome, extracts visual bounding boxes, and writes the `.Report/` folder beside an existing `.pbip`.

```
Input:  html: str, schema_json: str, pbip_path: str, theme_path: str | None = None
Output: absolute path to <name>.Report/  ← the written report folder
Needs:  system Chrome
```

`pbip_path` must point to an **existing** `.pbip` file (or a folder containing exactly one). SimBI writes the sibling `.Report/` folder and leaves the `.pbip` untouched.

`theme_path` is optional — see [Theming](#theming) below.

**Prerequisites:**
- Power BI Desktop must be **closed** before calling this tool.
- The `.pbip` must already exist (created by Power BI Desktop).

## Theming

Every report SimBI emits gets a baked-in theme: Microsoft's `CY25SU10` colour science (categorical palette, semantic green/neutral/red, diverging scale, neutrals, hyperlink colours) **plus** SimBI's opinionated `visualStyles` distilled from the [dashboard design playbook](docs/dashboard-design-playbook.md) — gridlines hidden, no visual borders or headers, lean white cards, consistent Segoe UI label typography. You typically need to do nothing; the default produces a professional-looking dashboard.

If you want to brand the report (corp palette, custom textClasses), pass a **partial** PBIR theme JSON via `theme_path`:

```json
{
  "name": "AcmeBrand",
  "dataColors": ["#003366", "#0066CC", "#3399FF", "#66B2FF", "#99CCFF"]
}
```

That partial deep-merges onto SimBI's baseline — your `dataColors` replace Microsoft's, but the `visualStyles` (gridlines off, lean cards, etc.) survive. The resolved theme is written under your `name` and registered as the report's base theme. Pass any subset of a PBIR theme — colours only, typography only, or full `visualStyles` overrides if you want to override SimBI's opinions.

## End-to-end usage

`emit_report` writes the `.Report/` folder beside your existing `.pbip`:

```
<project_dir>/
  <name>.pbip                ← created by Power BI Desktop (required before emit_report)
  <name>.Report/             ← written by SimBI
  <name>.SemanticModel/      ← created by Power BI Desktop or the MS Power BI MCP
```

Use a dedicated project folder — **not** the SimBI MCP repo. For example: `C:/Reports/SalesDashboard/`.

---

### Path 1 — SimBI only (no MS Power BI MCP needed)

SimBI generates the semantic model and the report layout from a TMDL description you write (or generate from data source profiling). No live Power BI Desktop connection is required.

**Step 1 — Create the .pbip in Power BI Desktop.**

Open Power BI Desktop → File → New. Then File → Save As, choose **Power BI Project (.pbip)** format, save to your output folder:

```
C:\Reports\SalesDashboard\SalesDashboard.pbip
```

**Step 2 — Close Power BI Desktop.**

**Step 3 — Prompt Claude:**
```
I have a CSV dataset at C:\Reports\SalesDashboard\Data\sales.csv.
The file C:\Reports\SalesDashboard\SalesDashboard.pbip exists and Power BI Desktop is closed.

Build a sales dashboard:
1. Call analyze_data_source to inspect the CSV column names and types.
2. Based on the profile and table-level hints, write a TMDL with appropriate tables, columns, partitions, and measures (e.g. Total Revenue, Order Count, Avg Unit Price).
3. Call lint_measures on the drafted TMDL and fix any findings.
4. Call write_semantic_model to persist the TMDL to the .SemanticModel folder.
5. Call parse_schema on the TMDL.
6. Call get_vocabulary to inspect visual options, then generate the annotated mockup HTML (using db-page/db-grid/db-card/db-chart-area layout classes).
7. Call validate_mockup_html to check annotations.
8. Call emit_report with pbip_path = "C:\Reports\SalesDashboard\SalesDashboard.pbip" to render and write the report layout.
```

**What Claude does:**
1. Calls `analyze_data_source(path="C:/Reports/SalesDashboard/Data/sales.csv")` to inspect the source.
2. Drafts the TMDL in-memory.
3. Calls `lint_measures(tmdl)` to verify DAX and format strings.
4. Calls `write_semantic_model(tmdl, pbip_path="C:/Reports/SalesDashboard/SalesDashboard.pbip")` to save the model definition to disk.
5. Calls `parse_schema(tmdl)` to load the model schema.
6. Calls `get_vocabulary()` and writes annotated HTML mockup using the schema.
7. Calls `validate_mockup_html(html, schema_json)` to check layout/roles.
8. Calls `emit_report(html, schema_json, pbip_path="C:/Reports/SalesDashboard/SalesDashboard.pbip")`.

> **Fallback rule:** If the Power BI MCP is configured but any call returns a connection error, Claude will switch to Path 1 automatically. SimBI does not require a live Power BI connection.

**Step 4 — Open the .pbip fresh in Power BI Desktop.**

Visuals render but show empty data — use Home → Transform data to connect `sales.csv`.

**Output:**
```
C:/Reports/SalesDashboard/
  SalesDashboard.pbip        ← created by you in Step 1
  SalesDashboard.Report/     ← written by SimBI
  SalesDashboard.SemanticModel/   ← created and updated by SimBI
```

---

### Path 2 — MS Power BI MCP builds the semantic model, SimBI builds the report

The MS Power BI MCP builds the full live semantic model (measures, calculated tables, relationships, loaded data). SimBI generates the report layout. The result is a fully data-connected report.

> **Ordering is critical and non-negotiable:**
> 1. Power BI Desktop must be **open** while the MCP builds the model
> 2. **ExportToTmdlFolder must be called** to sync the model to disk before closing
> 3. Power BI Desktop must be **closed** before SimBI runs `emit_report`
> 4. Open the `.pbip` **fresh** after SimBI finishes — never reload a file that was open during emit

**Step 1 — Create and open the .pbip in Power BI Desktop.**

File → New → File → Save As → Power BI Project format:
```
C:\Reports\SalesDashboard\SalesDashboard.pbip
```
Leave Power BI Desktop **open** for the next step.

**Step 2 — Build the semantic model with the MS Power BI MCP:**
```
The file C:\Reports\SalesDashboard\SalesDashboard.pbip is open in Power BI Desktop.

Use the Power BI MCP to:
1. Connect to the running Power BI Desktop instance
2. Refresh data to load C:\Reports\SalesDashboard\Data\sales.csv
3. Create a Calendar calculated table:
   ADDCOLUMNS(CALENDARAUTO(), "MonthName", FORMAT([Date], "MMM YYYY"), ...)
4. Create a relationship from sales[OrderDate] (Many) to Calendar[Date] (One)
5. Mark Calendar as the date table
6. Create measures: Total Revenue, Order Count, Avg Unit Price
7. Full model refresh
8. ExportToTmdlFolder → C:\Reports\SalesDashboard\SalesDashboard.SemanticModel\definition
```

Step 8 is essential — without it, all model changes exist only in Power BI Desktop's memory and will be lost when the file is next opened.

**Step 3 — Close Power BI Desktop.**

Mandatory. SimBI's writes to `.Report/` are silently ignored by a running Power BI Desktop instance — it serves its cached in-memory report until a fresh open.

**Step 4 — Generate the report with SimBI:**
```
Power BI Desktop is now closed.

Use SimBI to build a sales dashboard:
1. Call parse_schema with the path C:\Reports\SalesDashboard\SalesDashboard.SemanticModel\definition.
2. Call get_vocabulary to inspect annotation guidelines.
3. Generate annotated mockup HTML using the schema and layout classes (db-page, db-grid, db-card, db-chart-area).
4. Call validate_mockup_html to lint the HTML.
5. Call emit_report with pbip_path = C:\Reports\SalesDashboard\SalesDashboard.pbip.
```

**Step 5 — Open the .pbip fresh in Power BI Desktop.**

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
├── dax/               DAX linter (advisory checks on measure expressions)
└── pbir/              Phase 3: DOM extractor, visual JSON templates, PBIR writer + theme resolver
```

## Supported visual types

SimBI emits **28 Power BI visual types**. The most common six are below; for the full list including data-role contracts and PBIR visualType strings, see [docs/chart-catalog.md](docs/chart-catalog.md) and the implementation-status overlay in [docs/simbi-visual-roadmap.md](docs/simbi-visual-roadmap.md).

| Annotation | Power BI visual | Required fields |
|---|---|---|
| `card` | Card | `data-pbi-measure` |
| `columnChart` | Column chart (stacks when `data-pbi-series` is present) | `data-pbi-axis`, `data-pbi-values`, optional `data-pbi-series` |
| `barChart` | Bar chart (stacks when `data-pbi-series` is present) | `data-pbi-axis`, `data-pbi-values`, optional `data-pbi-series` |
| `lineChart` | Line chart | `data-pbi-axis`, `data-pbi-values`, optional `data-pbi-series` |
| `slicer` | Button slicer | `data-pbi-field` |
| `table` | Table | `data-pbi-columns` (comma-separated — each token is either a bare measure name or a `Table[Column]` ref) |

Also supported: `multiRowCard`, `kpi`, `gauge`, `clusteredColumnChart`, `clusteredBarChart`, `hundredPercentStackedColumnChart`, `hundredPercentStackedBarChart`, `dotPlot`, `areaChart`, `comboChart`, `pieChart`, `donutChart`, `treemap`, `funnelChart`, `histogram`, `scatterChart`, `bubbleChart`, `waterfallChart`, `ribbonChart`, `map`, `filledMap`, `shapeMap`.

## License

[MIT](LICENSE) © Nick Lombardi
