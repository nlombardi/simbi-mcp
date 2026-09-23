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

import re
from pathlib import Path

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


# ── On-disk SemanticModel normalization ─────────────────────────────────────────
#
# The .SemanticModel is frequently authored by the Power BI MCP / Power BI
# Desktop / Tabular Editor, NOT by SimBI — and any of those can write a table
# literally named "Measures" (the conventional disconnected measures table).
# Those measures never pass through SimBI's ModelSchema, so sanitize_schema()
# above cannot reach them. SimBI is the last tool to touch the .pbip before the
# user opens it, so it normalizes the on-disk model here using the SAME
# safe_table_name() rule — guaranteeing the model and the report (which SimBI
# emits from the sanitized schema) agree on every table name.

_TABLE_HEADER_RE = re.compile(r"^table\s+(['\"]?)(?P<name>.+?)\1[ \t]*$", re.MULTILINE)


def reserved_table_renames(semantic_model_dir: Path) -> dict[str, str]:
    """Scan the on-disk model and return {old_name: new_name} for reserved tables."""
    tables_dir = semantic_model_dir / "definition" / "tables"
    if not tables_dir.is_dir():
        return {}
    renames: dict[str, str] = {}
    for tmdl_path in sorted(tables_dir.glob("*.tmdl")):
        match = _TABLE_HEADER_RE.search(tmdl_path.read_text(encoding="utf-8"))
        if not match:
            continue
        old = match.group("name")
        new = safe_table_name(old)
        if new != old:
            renames[old] = new
    return renames


def sanitize_semantic_model_dir(semantic_model_dir: Path) -> dict[str, str]:
    """Rename every reserved-named table in an on-disk SemanticModel, in place.

    For each table whose name is reserved (e.g. "Measures"):
      - rewrites the `table` header and the same-named `partition` header,
      - renames the .tmdl file to match the new table name,
      - updates `model.tmdl`: the `ref table` line and any quoted occurrence in
        annotations such as PBI_QueryOrder.

    Returns the {old: new} rename map (empty when nothing was reserved) so the
    caller can keep other artifacts in sync if needed. Idempotent: a second call
    finds no reserved names and does nothing.
    """
    renames = reserved_table_renames(semantic_model_dir)
    if not renames:
        return {}

    tables_dir = semantic_model_dir / "definition" / "tables"
    for tmdl_path in sorted(tables_dir.glob("*.tmdl")):
        text = tmdl_path.read_text(encoding="utf-8")
        match = _TABLE_HEADER_RE.search(text)
        if not match:
            continue
        old = match.group("name")
        new = renames.get(old)
        if new is None:
            continue
        # Rewrite the table header and the partition that shares the table name.
        text = _TABLE_HEADER_RE.sub(
            lambda mm: f"table {new}" if mm.group("name") == old else mm.group(0),
            text,
            count=1,
        )
        text = re.sub(
            rf"^(?P<indent>[ \t]*partition[ \t]+)(['\"]?){re.escape(old)}\2(?P<rest>[ \t]*=)",
            rf"\g<indent>{new}\g<rest>",
            text,
            flags=re.MULTILINE,
        )
        tmdl_path.write_text(text, encoding="utf-8")
        target = tmdl_path.with_name(f"{new}.tmdl")
        if target != tmdl_path:
            tmdl_path.replace(target)

    _apply_renames_to_model_tmdl(semantic_model_dir / "definition" / "model.tmdl", renames)
    return renames


def _apply_renames_to_model_tmdl(model_tmdl: Path, renames: dict[str, str]) -> None:
    """Update `ref table` lines and quoted annotation references in model.tmdl."""
    if not model_tmdl.exists():
        return
    text = model_tmdl.read_text(encoding="utf-8")
    for old, new in renames.items():
        text = re.sub(
            rf"^(?P<kw>ref[ \t]+table[ \t]+)(['\"]?){re.escape(old)}\2[ \t]*$",
            rf"\g<kw>{new}",
            text,
            flags=re.MULTILINE,
        )
        # Quoted occurrences in annotations (e.g. PBI_QueryOrder = [...,"Measures"]).
        text = text.replace(f'"{old}"', f'"{new}"')
    model_tmdl.write_text(text, encoding="utf-8")
