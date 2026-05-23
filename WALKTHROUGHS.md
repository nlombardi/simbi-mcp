# SimBI MCP — End-to-End Walkthroughs

Two copy-paste walkthroughs you can run directly in Claude with SimBI MCP configured.

Both use the sample dataset at `tests/fixtures/datasets/sales_small.csv` (50 rows: OrderID, OrderDate, Region, Product, Category, UnitsSold, UnitPrice, Revenue).

**Before starting:** make sure the SimBI MCP server is running and connected to your Claude session. Verify with a quick `list tools` — you should see `parse_schema` and `emit_report`.

---

## Path 1 — SimBI only (no Microsoft Power BI MCP needed)

Claude writes the TMDL itself from your CSV description, parses it into a schema, generates the report layout, and automatically patches the measures into the SemanticModel TMDL. Visuals open in Power BI Desktop immediately — connect your CSV via **Home → Transform data** to load live data.

### Step 1 — Create a blank .pbip in Power BI Desktop

1. Open Power BI Desktop
2. **File → New** (start from a blank report)
3. **File → Save As** — choose **"Power BI Project (.pbip)"** format and save to your target folder, e.g.:

   ```
   C:\Reports\SalesDashboard\SalesDashboard.pbip
   ```

4. **Close Power BI Desktop completely** before continuing. SimBI writes the `.Report/` folder while the file is closed — any writes made while the file is open are silently discarded on reload.

### Step 2 — Paste this prompt into Claude

Replace the paths below with your actual `.pbip` path and CSV path.

---

> I have a CSV dataset at `C:\Reports\SalesDashboard\Data\sales_small.csv` with these columns:
> OrderID (int), OrderDate (date), Region (text), Product (text), Category (text),
> UnitsSold (int), UnitPrice (decimal), Revenue (decimal).
>
> I have already created a blank .pbip at `C:\Reports\SalesDashboard\SalesDashboard.pbip`
> and closed Power BI Desktop.
>
> Using SimBI (Path 1 — no Power BI MCP):
> 1. Write TMDL for a table named `sales` with the correct column dataTypes and these
>    measures (with DAX and formatStrings):
>    - `Total Revenue = SUM(sales[Revenue])`  format: `\$#,0.00`
>    - `Order Count = COUNTROWS(sales)`  format: `#,0`
>    - `Avg Unit Price = DIVIDE(SUM(sales[Revenue]), SUM(sales[UnitsSold]))`  format: `\$#,0.00`
>    Include a partition block pointing at `C:\Reports\SalesDashboard\Data\sales_small.csv`.
>    Do NOT call the Power BI MCP — write the TMDL as inline text yourself.
> 2. Call `parse_schema` with that TMDL.
> 3. Generate annotated HTML using the schema and `dashboard.css` layout classes
>    (`db-page`, `db-grid`, `db-card`, `db-chart-area`) so every visual has real CSS
>    dimensions. The dashboard should show:
>    - Three KPI cards: Total Revenue, Order Count, Avg Unit Price
>    - A slicer on Category
>    - A column chart: Total Revenue by Region
>    - A line chart: Total Revenue over OrderDate
> 4. Call `validate_mockup_html` to lint the HTML.
> 5. Call `emit_report` with `pbip_path = "C:\Reports\SalesDashboard\SalesDashboard.pbip"`.

---

### What Claude should do

1. Write TMDL inline (no MCP calls) — columns, measures, partition pointing at the CSV
2. Call `parse_schema` with that inline TMDL
3. Generate annotated HTML with 6 `data-pbi` elements
4. Call `validate_mockup_html`
5. Call `emit_report` — which writes the `.Report/` folder **and** patches the measures into the SemanticModel TMDL automatically

### Expected output

```
C:\Reports\SalesDashboard\
  SalesDashboard.pbip                       ← you created this; SimBI left it untouched
  SalesDashboard.Report\                    ← PBIR layout (6 visual.json files)
    definition\
      pages\<guid>\visuals\
  SalesDashboard.SemanticModel\             ← created by PBI Desktop; measures patched in
    definition\
      tables\
        sales.tmdl                          ← measures appended by SimBI
```

### What to check

- Open `SalesDashboard.pbip` fresh in Power BI Desktop — the layout should render with 6 visuals
- Measures appear in the Fields pane (Total Revenue, Order Count, Avg Unit Price)
- Visuals will be empty until data is connected — this is expected for Path 1
- In Power BI Desktop: **Home → Transform data** to connect `sales_small.csv`, then refresh

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
| Measures and relationships missing on open (Path 2) | TMDL not synced to disk before closing | Re-run ExportToTmdlFolder → SemanticModel/definition, then close and reopen |
| Visuals are empty (Path 1) | No data connected yet | Expected — use **Home → Transform data** to connect the CSV, then refresh |
| Measures missing from Fields pane (Path 1) | `emit_report` was called before the `.pbip` existed | Create the blank `.pbip` in Power BI Desktop first, then re-run `emit_report` |
| Claude calls Power BI MCP instead of writing TMDL | Claude chose Path 2 by mistake | Restart the conversation; tell Claude explicitly "use SimBI Path 1, no Power BI MCP" |
| `AVERAGE cannot work with values of type String` | Stale SemanticModel from before the dataType fix | Delete the old `SalesDashboard.SemanticModel\` folder and re-run `emit_report` |
