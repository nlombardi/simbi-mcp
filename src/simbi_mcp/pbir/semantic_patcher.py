"""Semantic model patcher — writes missing measures into SemanticModel TMDL files.

This is the Path 1 fix. When a user creates a blank .pbip in Power BI Desktop
(no data connected, no measures defined), the SemanticModel TMDL contains the
right table structure but no measures. SimBI's visual.json files reference those
measures, so Power BI Desktop shows broken visuals.

This module patches the existing TMDL by appending any measures from the schema
that are not already present — it never removes or modifies existing content.
Path 2 (where the MS Power BI MCP already wrote the measures) is unaffected
because those measures will already be in the file and are skipped.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from simbi_mcp.types import ModelColumn, ModelMeasure, ModelSchema, ModelTable


def patch_semantic_model_measures(schema: ModelSchema, semantic_model_dir: Path) -> None:
    """Write missing measures into SemanticModel TMDL files.

    For each table in `schema` that has measures:
    - If a .tmdl file already exists for that table: appends any measures not
      yet present, inserting them just before the first `partition` or
      `annotation` block (TMDL conventional order).
    - If no .tmdl file exists yet (truly blank .pbip): creates a minimal TMDL
      with the table's columns and measures (no M partition — user connects
      data via Power BI Desktop's Transform Data).

    Safe to call repeatedly — idempotent per measure name.
    """
    tables_dir = semantic_model_dir / "definition" / "tables"

    # Build a lookup: table name → measures for that table
    measures_by_table: dict[str, list[ModelMeasure]] = {}
    for measure in schema.measures:
        measures_by_table.setdefault(measure.table, []).append(measure)

    if not measures_by_table:
        return  # no measures to write

    # Build a lookup: table name → ModelTable (for column definitions)
    table_by_name: dict[str, ModelTable] = {t.name: t for t in schema.tables}

    for table_name, measures in measures_by_table.items():
        tmdl_path = tables_dir / f"{table_name}.tmdl"

        if tmdl_path.exists():
            existing = tmdl_path.read_text(encoding="utf-8")
            new_measures = [
                m for m in measures
                if f"measure '{m.name}'" not in existing
                and f'measure "{m.name}"' not in existing
            ]
            if not new_measures:
                continue  # all measures already present — leave file untouched
            patched = _insert_measures(existing, new_measures)
            tmdl_path.write_text(patched, encoding="utf-8")
        else:
            # Create a minimal TMDL — columns + measures, no partition
            tables_dir.mkdir(parents=True, exist_ok=True)
            model_table = table_by_name.get(table_name)
            content = _build_minimal_tmdl(
                table_name=table_name,
                columns=model_table.columns if model_table else [],
                measures=measures,
            )
            tmdl_path.write_text(content, encoding="utf-8")


# ── TMDL text helpers ──────────────────────────────────────────────────────────

def _insert_measures(existing: str, measures: list[ModelMeasure]) -> str:
    """Splice measure blocks into existing TMDL before the first partition block.

    Uses the `partition` keyword as the insertion anchor because it is always a
    top-level table member (one tab of indentation), unlike `annotation` which
    can appear nested inside column blocks at two tabs.  If no partition exists
    the measures are appended at the end of the file.
    """
    additions = "\n".join(_measure_block(m) for m in measures)
    lines = existing.splitlines()
    insert_at = len(lines)
    for i, line in enumerate(lines):
        # Match only top-level partition lines (single leading tab, not two)
        if line.startswith("\tpartition "):
            insert_at = i
            break
    new_lines = lines[:insert_at] + ["", additions, ""] + lines[insert_at:]
    return "\n".join(new_lines).rstrip() + "\n"


def _build_minimal_tmdl(
    table_name: str,
    columns: list[ModelColumn],
    measures: list[ModelMeasure],
) -> str:
    """Build a complete table TMDL with columns and measures but no data partition."""
    parts: list[str] = [
        f"table {table_name}",
        f"\tlineageTag: {_new_guid()}",
        "",
    ]
    for m in measures:
        parts.append(_measure_block(m))
        parts.append("")
    for col in columns:
        parts += [
            f"\tcolumn {col.name}",
            f"\t\tdataType: {col.data_type}",
            f"\t\tlineageTag: {_new_guid()}",
            f"\t\tsummarizeBy: none",
            f"\t\tsourceColumn: {col.name}",
            "",
        ]
    return "\n".join(parts)


def _measure_block(m: ModelMeasure) -> str:
    lines = [f"\tmeasure '{m.name}' = {m.expression}"]
    fmt = _format_string(m.return_type)
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    lines.append(f"\t\tlineageTag: {_new_guid()}")
    return "\n".join(lines)


def _format_string(return_type: str) -> str:
    mapping = {
        "currency": r"\$#,0.00",
        "integer": "#,0",
        "percentage": "0.00%",
        "number": "#,0.00",
    }
    return mapping.get(return_type, "")


def _new_guid() -> str:
    return uuid.uuid4().hex[:20]
