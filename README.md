# SimBI MCP

An MCP server that generates Power BI dashboards from natural language. Point it at a CSV and describe the dashboard you want — it produces a `.pbip` Report folder that Power BI Desktop can open directly.

## How it works

SimBI chains three phases into two MCP tools and one resource:

```
User prompt + CSV
      │
      ▼  [MS Power BI MCP]
  Semantic model  ──→  TMDL string
      │
      ▼  parse_schema
  ModelSchema JSON
      │
      ▼  [Claude reads simbi://annotation-vocabulary and generates HTML in-context]
  Annotated HTML mockup  (data-pbi-* annotations)
      │
      ▼  emit_report
  .pbip Report folder  (Playwright renders HTML → extracts bounding boxes → writes PBIR files)
```

Claude orchestrates between the Microsoft Power BI MCP (to create the semantic model) and SimBI (to generate the report). SimBI handles phases 2 and 3; the MS MCP handles phase 1. Claude generates the HTML mockup itself using the annotation vocabulary exposed as an MCP resource — no nested API calls.

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

### Full flow (CSV → Power BI report)

With both SimBI and the Microsoft Power BI MCP configured, just ask Claude:

```
Build me a sales dashboard from revenue.csv
```

Claude will:
1. Use the MS Power BI MCP to load the CSV, create DAX measures, and export TMDL
2. Read `simbi://annotation-vocabulary` to learn the annotation spec and CSS catalog
3. Call `parse_schema(tmdl)` to get a structured schema
4. Generate the annotated HTML mockup itself using the schema and vocabulary
5. Call `emit_report(html, schema_json, "SalesDashboard", "C:/Reports")`

Open the resulting `C:/Reports/SalesDashboard.Report` folder in Power BI Desktop.

### If you already have TMDL

Skip the MS MCP step by pasting your TMDL directly:

```
Here's my TMDL: <paste>
Generate a sales dashboard and save it to C:/Reports as "SalesDashboard"
```

Claude reads the vocabulary, parses the schema, writes the HTML, and emits the report.

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
