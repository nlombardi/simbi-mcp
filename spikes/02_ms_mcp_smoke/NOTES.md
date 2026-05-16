# Microsoft Power BI MCP — Smoke Test Notes

## Tool surface (all operation categories)

| Tool name | SimBI use |
|---|---|
| `database_operations` | Database-level ops |
| `trace_operations` | Query tracing / diagnostics |
| `named_expression_operations` | Named M expressions |
| `measure_operations` | **PRIMARY: create / read DAX measures** |
| `object_translation_operations` | Localized object names |
| `dax_query_operations` | Run DAX queries |
| `perspective_operations` | Perspectives |
| `column_operations` | Read / configure columns |
| `user_hierarchy_operations` | Drill-down hierarchies |
| `calculation_group_operations` | Calculation groups |
| `security_role_operations` | Row-level security |
| `table_operations` | **PRIMARY: create tables from CSV** |
| `calendar_operations` | Auto date tables |
| `relationship_operations` | **PRIMARY: relationships** |
| `model_operations` | **PRIMARY: read schema, export TMDL** |
| `culture_operations` | Locale |
| `function_operations` | Shared M functions |
| `query_group_operations` | Query organization |
| `transaction_operations` | Explicit multi-tool transactions (not needed for SimBI) |
| `connection_operations` | Data source connections |
| `partition_operations` | Table partitions |

---

## Verified argument schemas

### `table_operations` — Create a table from CSV

```json
{
  "operation": "Create",
  "definitions": [
    {
      "Name": "Sales",
      "Description": "optional",
      "Mode": "Import",
      "MExpression": "let\n    Source = Csv.Document(File.Contents(\"C:\\\\path\\\\to\\\\file.csv\"), [Delimiter=\",\", Columns=8, Encoding=1252, QuoteStyle=QuoteStyle.None]),\n    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),\n    ChangedTypes = Table.TransformColumnTypes(PromotedHeaders, {\n        {\"OrderID\", Int64.Type},\n        {\"OrderDate\", type date},\n        {\"Revenue\", type number}\n    })\nin\n    ChangedTypes",
      "Columns": [
        { "Name": "OrderID",    "DataType": "Int64",    "Ordinal": 0, "SummarizeBy": "None" },
        { "Name": "OrderDate",  "DataType": "DateTime", "Ordinal": 1, "SummarizeBy": "None", "FormatString": "Short Date" },
        { "Name": "Region",     "DataType": "String",   "Ordinal": 2, "SummarizeBy": "None" },
        { "Name": "UnitsSold",  "DataType": "Int64",    "Ordinal": 3, "SummarizeBy": "Sum"  },
        { "Name": "Revenue",    "DataType": "Double",   "Ordinal": 4, "SummarizeBy": "Sum", "FormatString": "\\$#,0.00;(\\$#,0.00)" }
      ]
    }
  ]
}
```

**Gotchas:**
- `Columns` is REQUIRED for M tables — the engine will not infer schema from the expression
- Do NOT set `IsKey: true` on Import tables — throws an error
- Backslashes in file path need double-escaping in the JSON string: `C:\\\\path\\\\to\\\\file.csv`
  (one level for Python string escaping → one more for JSON → four backslashes in source code)
- Valid `DataType` values: `String`, `Int64`, `Double`, `DateTime`, `Boolean`, `Decimal`

**DataType mapping from polars/ColumnRole:**

| ColumnRole | Polars dtype | PBI DataType | SummarizeBy |
|---|---|---|---|
| ID | Int64 | Int64 | None |
| DATE | Date / Datetime | DateTime | None |
| MEASURE (int) | Int64 | Int64 | Sum |
| MEASURE (float) | Float64 | Double | Sum |
| DIMENSION | String | String | None |

**M type mapping:**

| PBI DataType | M type expression |
|---|---|
| Int64 | `Int64.Type` |
| Double | `type number` |
| DateTime | `type date` |
| String | `type text` |

**After `table_operations.Create`, must call refresh before measures compute:**
```json
{ "operation": "RefreshWithXMLA", "definitions": [{ "Name": "Sales" }] }
```

---

### `measure_operations` — Create measures (batched)

```json
{
  "operation": "Create",
  "definitions": [
    {
      "TableName": "Sales",
      "Name": "Total Revenue",
      "Expression": "SUM(Sales[Revenue])",
      "FormatString": "\\$#,0.00;(\\$#,0.00)",
      "Description": "optional"
    },
    {
      "TableName": "Sales",
      "Name": "Number of Orders",
      "Expression": "COUNTROWS(Sales)",
      "FormatString": "#,0"
    },
    {
      "TableName": "Sales",
      "Name": "Average Order Value",
      "Expression": "DIVIDE([Total Revenue], [Number of Orders])",
      "FormatString": "\\$#,0.00;(\\$#,0.00)"
    }
  ]
}
```

**Key points:**
- Batch all measures in one call (one MCP round-trip)
- Cross-measure references within the same batch work fine
- `FormatString` maps from `MeasurePlan.return_type`: see table below

**FormatString by return_type:**

| return_type | FormatString |
|---|---|
| currency | `\\$#,0.00;(\\$#,0.00)` |
| integer | `#,0` |
| percentage | `0.00%;-0.00%;0.00%` |
| number | `#,0.00` |

---

### `model_operations` — Export TMDL schema

```json
{
  "operation": "ExportTMDL",
  "tmdlExportOptions": { "maxReturnCharacters": -1 }
}
```

**Response:** `{"success": true, "tmdlDocument": "<TMDL string>"}` (shape inferred —
confirm actual key name from first real call; may be a different key or embedded differently).

**TMDL format example** (from Sales.tmdl):
```
table Sales
    measure 'Total Revenue' = SUM(Sales[Revenue])
        formatString: \$#,0.00;(\$#,0.00)
    column OrderID
        dataType: int64
        summarizeBy: none
    column Revenue
        dataType: double
        summarizeBy: sum
```

**Parsing approach for schema_reader.py:** line-by-line regex. Key patterns:
- Table: `^table (.+)$`
- Measure: `^\s+measure '(.+?)' = (.+)$`
- Column: `^\s+column (.+)$`
- DataType: `^\s+dataType: (.+)$` (within a column block)

Relationships would appear as a separate `relationship` block in the TMDL if any.

---

### `transaction_operations` — Not needed for SimBI

Each `table_operations` / `measure_operations` call auto-wraps in a transaction and
commits on success (controlled by `Options.UseTransaction` defaulting to `true`).

Only needed if you want atomic multi-tool batches:
```json
{ "operation": "Begin", "connectionName": "PBIDesktop-<model-name>-<port>" }
// → {"transactionId": "abc-123"}

{ "operation": "Commit", "transactionId": "abc-123" }
// or
{ "operation": "Rollback", "transactionId": "abc-123" }
```

---

## Correct call sequence for `create_semantic_model()`

```
table_operations.Create       → creates table definition + partition
table_operations.RefreshWithXMLA → loads data into the model (must precede queries)
measure_operations.Create     → creates all measures in one batched call
model_operations.ExportTMDL   → reads full model definition back as TMDL string
```

---

## Interface changes from original plan

The original plan assumed `ingest_dataset() → dataset_id` passed between calls.
The real API is **session-scoped stateless** — no IDs, sequential calls on same model.

Corrected `PbiClient` interface:
```python
async def create_table(self, profile: DatasetProfile) -> None
async def refresh_table(self, table_name: str) -> None
async def create_measures(self, *, table_name: str, measures: list[MeasurePlan]) -> None
async def get_raw_schema(self) -> str  # returns TMDL string
```

Corrected `orchestrator.create_semantic_model()` call sequence:
```python
profile = profile_dataset(dataset_path)
plans = plan_measures(prompt=prompt, profile=profile, client=anthropic_client)
await pbi_client.create_table(profile)
await pbi_client.refresh_table(profile.table_name)
await pbi_client.create_measures(table_name=profile.table_name, measures=plans)
tmdl = await pbi_client.get_raw_schema()
return parse_tmdl_schema(tmdl)
```

`schema_reader.py` parses TMDL string (not a JSON dict).
