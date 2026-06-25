"""Guard against Analysis Services reserved table names.

Power BI's Tabular engine rejects any table whose name is a reserved string —
most notably "Measures", which collides with the implicit MDX Measures
dimension. Loading a .pbip whose model contains such a table fails hard with:

    The name of the object 'Table' cannot be the reserved string 'Measures'.

Power BI Desktop's UI silently prevents this name, but TMDL written directly
to disk bypasses that guard — which is exactly SimBI's write path
(patch_semantic_model_measures / patch_field_parameters). So SimBI must
enforce the constraint itself.

We rewrite reserved names by prefixing an underscore — the universal Power BI
convention for a measures-holding table ("_Measures"). The rewrite is applied
to the ModelSchema as a whole so that every downstream consumer agrees on the
new name: the report's visual.json bindings (templates._measure_proj reads
ModelMeasure.table) AND the SemanticModel TMDL (patch_semantic_model_measures
writes a file named after ModelMeasure.table). Renaming in only one place would
silently break every visual that references the measure.
"""
from __future__ import annotations

from simbi_mcp.types import ModelSchema

# Lowercased table names rejected by the AS Tabular engine.
RESERVED_TABLE_NAMES = frozenset({"measures"})


def safe_table_name(name: str) -> str:
    """Return a non-reserved version of `name`, prefixing '_' if reserved.

    Comparison is case-insensitive and ignores surrounding whitespace, matching
    how the AS engine normalizes object names.
    """
    if name.strip().lower() in RESERVED_TABLE_NAMES:
        return f"_{name}"
    return name


def sanitize_schema(schema: ModelSchema) -> ModelSchema:
    """Rewrite reserved table names everywhere they appear in the schema.

    Renames are applied consistently to table definitions, every measure's host
    table, and both endpoints of every relationship, so the report and the
    semantic model stay in agreement. A disconnected measures table frequently
    has no ModelTable entry (only measures point at it), so host tables are
    collected from the measures as well.

    Returns the original schema unchanged when nothing is reserved.
    """
    rename: dict[str, str] = {}
    for t in schema.tables:
        safe = safe_table_name(t.name)
        if safe != t.name:
            rename[t.name] = safe
    for m in schema.measures:
        safe = safe_table_name(m.table)
        if safe != m.table:
            rename.setdefault(m.table, safe)

    if not rename:
        return schema

    return schema.model_copy(
        update={
            "tables": [
                t.model_copy(update={"name": rename.get(t.name, t.name)})
                for t in schema.tables
            ],
            "measures": [
                m.model_copy(update={"table": rename.get(m.table, m.table)})
                for m in schema.measures
            ],
            "relationships": [
                r.model_copy(
                    update={
                        "from_table": rename.get(r.from_table, r.from_table),
                        "to_table": rename.get(r.to_table, r.to_table),
                    }
                )
                for r in schema.relationships
            ],
        }
    )
