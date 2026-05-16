# Microsoft Power BI MCP — Smoke Test Notes

## Tool surface (operation categories)

The MS Power BI MCP exposes these operation categories. Each entry below is a
distinct MCP tool name. Tool argument schemas need to be confirmed from the MCP's
tool definitions (see TODO below).

| Category | Likely purpose for SimBI |
|---|---|
| `database_operations` | Database-level ops (create/open a PBI dataset) |
| `trace_operations` | Query tracing / diagnostics |
| `named_expression_operations` | Named M expressions (reusable query steps) |
| `measure_operations` | **PRIMARY: create / read / update DAX measures** |
| `object_translation_operations` | Localized object names |
| `dax_query_operations` | Run DAX queries against the model |
| `perspective_operations` | Manage perspectives (field subsets) |
| `column_operations` | **Read / configure table columns** |
| `user_hierarchy_operations` | Define drill-down hierarchies |
| `calculation_group_operations` | Calculation groups (advanced measures) |
| `security_role_operations` | Row-level security |
| `table_operations` | **PRIMARY: create / ingest tables from CSV** |
| `calendar_operations` | Auto-generate date tables |
| `relationship_operations` | **PRIMARY: define table relationships** |
| `model_operations` | **PRIMARY: read model schema, commit changes** |
| `culture_operations` | Locale / formatting culture |
| `function_operations` | Shared M functions |
| `query_group_operations` | Query organization |
| `transaction_operations` | **PRIMARY: begin / commit model changes** |
| `connection_operations` | Data source connections |
| `partition_operations` | Table partitions (incremental refresh) |

## SimBI-critical operations (Phase 1)

Four tools needed for `create_semantic_model()`:

1. **`table_operations`** — ingest CSV as a table
2. **`measure_operations`** — create DAX measures
3. **`model_operations`** — read model schema back
4. **`transaction_operations`** — commit changes (may be required before reads)

## TODO: confirm argument schemas

The smoke script needs to be run with each critical tool to capture the actual
JSON argument shapes. Run the smoke script and document:

```python
# For each critical tool, call it and capture the request/response:
result = await session.call_tool("measure_operations", arguments={...})
```

Open questions:
- Does each tool take an `action` discriminator (e.g., `{"action": "create", ...}`)?
  Or are create/list/delete separate tools (e.g., `measure_operations_create`)?
- What is the exact argument shape for ingesting a CSV via `table_operations`?
- Does `model_operations` return a schema blob we can parse into `ModelSchema`?
- Is `transaction_operations` required before `measure_operations`? (XMLA typically
  requires `begin transaction` → operations → `commit`)

## Evidence that smoke succeeded

The SemanticModel TMDL in `spikes/01_pbir_reference/` shows 5 measures were
created (Total Revenue, Total Units Sold, Number of Orders, Average Order Value,
Average Unit Price), confirming the MCP successfully authored the model. The
annotation `PBI_ProTooling = ["MCP-PBIModeling","DevMode"]` in model.tmdl is
written by the MCP itself as a provenance marker.

## Sample schema response (to be filled)

[Paste actual `model_operations` response here after running smoke script]
