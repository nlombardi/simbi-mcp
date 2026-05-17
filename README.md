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

Renders an annotated HTML mockup in Chrome, extracts visual bounding boxes, and writes a complete Power BI `.pbip` Report folder.

```
Input:  html: str, schema_json: str, report_name: str, output_dir: str
Output: absolute path to <report_name>.Report folder
Needs:  system Chrome
```

## End-to-end usage

### Standalone (no MS Power BI MCP needed)

SimBI is self-contained. Just describe your data and ask Claude to build the report:

```
Build me a sales dashboard for this CSV:
  columns: Region, OrderDate, Revenue, Units, Category
  measures needed: Total Revenue (SUM), Order Count (COUNTROWS), Avg Unit Price
Save it to C:/Reports as "SalesDashboard"
```

Claude will:
1. Read `simbi://annotation-vocabulary` to learn the annotation spec
2. Call `parse_schema(tmdl)` with TMDL you or Claude describes from the CSV schema
3. Generate the annotated HTML mockup
4. Call `emit_report(...)`, which writes three sibling artifacts:
   - `C:/Reports/SalesDashboard.pbip` ← **open this in Power BI Desktop**
   - `C:/Reports/SalesDashboard.Report/` (PBIR layout)
   - `C:/Reports/SalesDashboard.SemanticModel/` (BIM stub — no data, correct structure)

The report opens in Power BI Desktop with the correct visual layout. The BIM stub defines tables and measures so PBI Desktop accepts the file; visuals show empty until you load real data.

### With the Microsoft Power BI MCP (real data)

When both MCPs are configured, Claude can build a semantic model with actual loaded data:

```
Build me a sales dashboard from revenue.csv, save to C:/Reports as "SalesDashboard"
```

Claude will:
1. Use the MS Power BI MCP to load `revenue.csv`, create DAX measures, and export TMDL
2. In Power BI Desktop: **File → Save As → Power BI Project** to `C:/Reports/SalesDashboard` — this writes the real `C:/Reports/SalesDashboard.SemanticModel/` with actual data
3. Read `simbi://annotation-vocabulary`
4. Call `parse_schema(tmdl)` → schema JSON
5. Generate the annotated HTML mockup
6. Call `emit_report("SalesDashboard", "C:/Reports", ...)` — writes `.pbip` + `.Report/`, and **skips the SemanticModel stub** because the real one already exists

Result: a fully data-connected report you can open and refresh in Power BI Desktop.

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
