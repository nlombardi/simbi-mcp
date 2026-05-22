# SimBI MCP — End-to-End Walkthroughs

Two copy-paste walkthroughs you can run directly in Claude with SimBI MCP configured.

Both use the sample dataset at `tests/fixtures/datasets/sales_small.csv` (50 rows: OrderID, OrderDate, Region, Product, Category, UnitsSold, UnitPrice, Revenue).

**Before starting:** make sure the SimBI MCP server is running and connected to your Claude session. Verify with a quick `list tools` — you should see `parse_schema` and `emit_report`.

---

## Path 1 — SimBI only (no Microsoft Power BI MCP needed)

SimBI parses the TMDL you provide, generates the report layout, and writes a SemanticModel stub alongside it. The stub has the right table/column/measure structure but no loaded data — visuals open in Power BI Desktop but show empty until you connect a data source.

### Step 1 — Pick an output folder

Create (or note) the folder where you want the report written, for example:

```
C:\Reports\SalesDashboard\
```

### Step 2 — Paste this prompt into Claude

Replace `C:\Reports\SalesDashboard` with your actual output folder path.

---

> Call `parse_schema` with the TMDL below, then generate an annotated HTML dashboard mockup from the resulting schema, then call `emit_report` to write the project.
>
> Use `report_name = "SalesDashboard"` and `output_dir = "C:\Reports\SalesDashboard"`.
>
> The dashboard should show:
> - Three KPI cards: Total Revenue, Order Count, Avg Unit Price
> - A slicer on Category
> - A column chart: Total Revenue by Region
> - A line chart: Total Revenue over OrderDate
>
> TMDL:
> ```
> /// Exported by Microsoft Power BI MCP (ExportTMDL)
> model Model
> 	culture: en-US
>
> ref table sales
>
> table sales
> 	lineageTag: a1b2c3d4-e5f6-7890-abcd-ef1234567890
>
> 	/// Row count for this table
> 	measure 'Order Count' = COUNTROWS(sales)
> 		formatString: #,0
> 		lineageTag: b2c3d4e5-f6a7-8901-bcde-f12345678901
>
> 	/// Sum of all revenue
> 	measure 'Total Revenue' = SUM(sales[Revenue])
> 		formatString: \$#,0.00
> 		lineageTag: c3d4e5f6-a7b8-9012-cdef-123456789012
>
> 	/// Average selling price per unit
> 	measure 'Avg Unit Price' = DIVIDE(SUM(sales[Revenue]), SUM(sales[UnitsSold]))
> 		formatString: \$#,0.00
> 		lineageTag: d4e5f6a7-b8c9-0123-defa-234567890123
>
> 	column OrderID
> 		dataType: int64
> 		lineageTag: e5f6a7b8-c9d0-1234-efab-345678901234
> 		summarizeBy: none
> 		sourceColumn: OrderID
>
> 	column OrderDate
> 		dataType: dateTime
> 		lineageTag: f6a7b8c9-d0e1-2345-fabc-456789012345
> 		summarizeBy: none
> 		sourceColumn: OrderDate
>
> 	column Region
> 		dataType: string
> 		lineageTag: a7b8c9d0-e1f2-3456-abcd-567890123456
> 		summarizeBy: none
> 		sourceColumn: Region
>
> 	column Product
> 		dataType: string
> 		lineageTag: b8c9d0e1-f2a3-4567-bcde-678901234567
> 		summarizeBy: none
> 		sourceColumn: Product
>
> 	column Category
> 		dataType: string
> 		lineageTag: c9d0e1f2-a3b4-5678-cdef-789012345678
> 		summarizeBy: none
> 		sourceColumn: Category
>
> 	column UnitsSold
> 		dataType: int64
> 		lineageTag: d0e1f2a3-b4c5-6789-defa-890123456789
> 		summarizeBy: sum
> 		sourceColumn: UnitsSold
>
> 	column UnitPrice
> 		dataType: double
> 		lineageTag: e1f2a3b4-c5d6-7890-efab-901234567890
> 		summarizeBy: none
> 		sourceColumn: UnitPrice
>
> 	column Revenue
> 		dataType: double
> 		lineageTag: f2a3b4c5-d6e7-8901-fabc-012345678901
> 		summarizeBy: sum
> 		sourceColumn: Revenue
>
> 	partition sales = m
> 		mode: import
> 		source =
> 				let
> 				    Source = Csv.Document(
> 				        File.Contents("C:\Data\sales_small.csv"),
> 				        [Delimiter=",", Columns=8, Encoding=65001, QuoteStyle=QuoteStyle.None]
> 				    ),
> 				    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
> 				    ChangedTypes = Table.TransformColumnTypes(PromotedHeaders, {
> 				        {"OrderID", Int64.Type}, {"OrderDate", type datetime},
> 				        {"Region", type text}, {"Product", type text},
> 				        {"Category", type text}, {"UnitsSold", Int64.Type},
> 				        {"UnitPrice", type number}, {"Revenue", type number}
> 				    })
> 				in
> 				    ChangedTypes
> ```

---

### What Claude should do

1. Call `parse_schema` with the TMDL above
2. Generate annotated HTML in-context (6 `data-pbi` elements)
3. Call `emit_report` — it will return the path to `SalesDashboard.pbip`

### Expected output

```
C:\Reports\SalesDashboard\
  SalesDashboard.pbip                   ← open this in Power BI Desktop
  SalesDashboard.Report\                ← PBIR layout (6 visual.json files)
  SalesDashboard.SemanticModel\         ← stub: correct types, no loaded data
    definition.pbism
    model.bim
```

### What to check

- Open `SalesDashboard.pbip` in Power BI Desktop — the layout should render with 6 visuals
- Visuals will be empty (no data) — this is expected for Path 1
- No DAX type errors — the stub now writes `double` for Revenue, `dateTime` for OrderDate, etc.
- In Power BI Desktop: **Home → Transform data** to connect `sales_small.csv` as the data source, then refresh

---

## Path 2 — Microsoft Power BI MCP + SimBI

The MS Power BI MCP creates and populates the real semantic model (tables, measures, relationships, loaded data). SimBI then generates the report layout into the same project folder. The result is a fully data-connected report that shows live data immediately on open.

> **Critical ordering rule:** Power BI Desktop must be **open** while the MCP builds the model, then **closed** before SimBI emits the report. Violating this order is the most common cause of missing visuals.

### Step 1 — Open the .pbip file in Power BI Desktop

Create a new Power BI project (File → New, then File → Save As with "Power BI Project" format) and save it to your output folder, for example:

```
C:\Reports\SalesDashboard\SalesDashboard.pbip
```

Leave Power BI Desktop **open** for the next two steps.

### Step 2 — Build the semantic model with the MS Power BI MCP

Paste this prompt into Claude (requires the Microsoft Power BI MCP configured alongside SimBI):

---

> The Power BI file `C:\Reports\SalesDashboard\SalesDashboard.pbip` is open in Power BI Desktop.
>
> Use the Power BI MCP to:
> 1. Connect to the running Power BI Desktop instance
> 2. Refresh data to load `C:\Reports\SalesDashboard\Data\sales_small.csv`
> 3. Create a `Calendar` calculated table: `ADDCOLUMNS(CALENDARAUTO(), "Year", YEAR([Date]), "MonthNo", MONTH([Date]), "MonthName", FORMAT([Date], "MMM YYYY"), "Quarter", "Q" & QUARTER([Date]) & " " & YEAR([Date]))`
> 4. Create a relationship from `sales_small[OrderDate]` (Many) to `Calendar[Date]` (One), active
> 5. Mark `Calendar` as the date table on column `Date`
> 6. Create these measures in the `sales_small` table:
>    - `Total Revenue = SUM(sales_small[Revenue])`  format: `\$#,0.00`
>    - `Order Count = COUNTROWS(sales_small)`  format: `#,0`
>    - `Avg Unit Price = DIVIDE(SUM(sales_small[Revenue]), SUM(sales_small[UnitsSold]))`  format: `\$#,0.00`
> 7. Run a full model refresh
> 8. ExportToTmdlFolder → `C:\Reports\SalesDashboard\SalesDashboard.SemanticModel\definition`

---

After this step the SemanticModel definition folder on disk matches the live model in memory.

### Step 3 — Close Power BI Desktop

**Close Power BI Desktop completely** before continuing. Power BI Desktop caches the Report in memory while the file is open — any files SimBI writes to the `.Report` folder while the file is open will be silently ignored on reload. A fresh open is the only way to pick up SimBI's output.

### Step 4 — Generate the report with SimBI

Paste this prompt into Claude:

---

> The Power BI Desktop file at `C:\Reports\SalesDashboard\SalesDashboard.pbip` is now closed.
>
> Use SimBI to build a sales dashboard:
> 1. Call `parse_schema` with the folder `C:\Reports\SalesDashboard\SalesDashboard.SemanticModel\definition`
> 2. Generate annotated HTML using the schema. Use `dashboard.css` layout classes (`db-page`, `db-grid`, `db-card`, `db-chart-area`) so every visual has real CSS dimensions — zero-size elements are rejected.
>    The dashboard should show:
>    - Three KPI cards: Total Revenue, Order Count, Avg Unit Price
>    - Slicers on Region and Category
>    - Column chart: Total Revenue by Region
>    - Bar chart: Total Revenue by Product
>    - Line chart: Total Revenue over Calendar[MonthName] with Category series
>    - Table: Total Revenue, Order Count, Avg Unit Price
> 3. Call `validate_mockup_html` to lint the HTML
> 4. Call `emit_report` with `pbip_path = "C:\Reports\SalesDashboard\SalesDashboard.pbip"`

---

### Step 5 — Open the .pbip fresh

Open `SalesDashboard.pbip` in Power BI Desktop. Because both the SemanticModel and Report folders were written to disk while the file was closed, Power BI Desktop reads everything cold and all visuals appear with live data immediately.

### Expected output

```
C:\Reports\SalesDashboard\
  SalesDashboard.pbip
  SalesDashboard.Report\
    definition\
      pages\<guid>\visuals\   ← 9 visual.json files
  SalesDashboard.SemanticModel\
    definition\
      tables\
        Calendar.tmdl         ← calculated date table
        sales_small.tmdl      ← measures + partition
      relationships.tmdl      ← active Calendar relationship
```

### What to check

- All 9 visuals visible on Page 1 with live data
- Cards show correct totals ($56,163.05 revenue, 50 orders)
- Slicers filter the charts and table
- Line chart X axis shows month labels (Jan 2025, Feb 2025 …)

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No [data-pbi] elements found` | Claude generated HTML without `data-pbi` attributes | Ask Claude to retry; the annotation vocabulary is in the server instructions |
| `N visuals have zero width/height` | HTML elements have no CSS dimensions | Add `db-card` / `db-chart-area` classes; don't use bare unstyled `<div>`s |
| Visuals missing / blank page after reload | `emit_report` ran while Power BI Desktop was open | Close PBI Desktop, re-run `emit_report`, open fresh |
| `Unknown measure` validation error | Claude used a measure name not in the schema | Check measure names in schema match HTML (`Total Revenue`, `Order Count`, `Avg Unit Price`) |
| Measures and relationships missing on open | TMDL not synced to disk before closing | Re-run ExportToTmdlFolder → SemanticModel/definition, then close and reopen |
| Visuals are empty (Path 1) | Stub has no loaded data | Expected — connect data source in Power BI Desktop |
| `AVERAGE cannot work with values of type String` | Stale stub from before the dataType fix | Delete the old `SalesDashboard.SemanticModel\` folder and re-run `emit_report` |
