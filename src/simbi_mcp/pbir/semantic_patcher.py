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

import re
import uuid
from pathlib import Path

from simbi_mcp.pbir.field_param import build_field_param_tmdl
from simbi_mcp.types import (
    FieldParameter,
    ModelColumn,
    ModelMeasure,
    ModelSchema,
    ModelTable,
)


def patch_semantic_model_measures(schema: ModelSchema, semantic_model_dir: Path) -> None:
    """Write missing measures into SemanticModel TMDL files.

    For each table in `schema` that has measures:
    - If a .tmdl file already exists for that table: appends any measures not
      yet present, inserting them just before the first `partition` or
      `annotation` block (TMDL conventional order).
    - If no .tmdl file exists yet (truly blank .pbip): creates a minimal TMDL
      with the table's columns and measures (no M partition — user connects
      data via Power BI Desktop's Transform Data).

    After writing all table files, adds a `ref table <Name>` line to model.tmdl
    for every newly-created file. Without this, Power BI may load the same table
    via two paths simultaneously (ref resolution + directory scan) and throw a
    duplicate-definition error (TmdlObject.AddContentOf).

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

    newly_created: list[str] = []

    for table_name, measures in measures_by_table.items():
        tmdl_path = tables_dir / f"{table_name}.tmdl"

        if tmdl_path.exists():
            original = tmdl_path.read_text(encoding="utf-8")
            existing = _sanitize_tmdl(original)
            new_measures = [
                m for m in measures
                if f"measure '{m.name}'" not in existing
                and f'measure "{m.name}"' not in existing
            ]
            if new_measures:
                existing = _insert_measures(existing, new_measures)
            # Write back when measures were inserted OR sanitization repaired the
            # file. A corrupted partition (e.g. `= dax`) must heal even when all
            # measures are already present; an already-valid file is left as-is.
            if existing != original:
                tmdl_path.write_text(existing, encoding="utf-8")
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
            newly_created.append(table_name)

    if newly_created:
        _register_ref_tables(semantic_model_dir, newly_created)


def patch_field_parameters(
    field_params: list[FieldParameter],
    semantic_model_dir: Path,
    measure_tables: dict[str, str] | None = None,
) -> None:
    """Write each field-parameter calc table to TMDL and ref it in model.tmdl.

    The field-parameter table is SimBI-owned and fully regenerable, so it is
    OVERWRITTEN on every call — re-emitting must pick up a corrected definition
    (e.g. table-qualified NAMEOF refs) rather than keep a stale file. The
    `ref table` line is added idempotently via `_register_ref_tables`.
    """
    if not field_params:
        return
    tables_dir = semantic_model_dir / "definition" / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for fp in field_params:
        tmdl_path = tables_dir / f"{fp.name}.tmdl"
        tmdl_path.write_text(
            build_field_param_tmdl(fp, measure_tables), encoding="utf-8"
        )
        written.append(fp.name)

    _register_ref_tables(semantic_model_dir, written)


# ── TMDL text helpers ──────────────────────────────────────────────────────────

_INVALID_MODE_RE = re.compile(r"^([ \t]+mode:[ \t]+)calculated([ \t]*)$", re.MULTILINE)
_DAX_PARTITION_SOURCE_RE = re.compile(
    r"^([ \t]*partition[ \t]+.+?[ \t]*=[ \t]*)dax([ \t]*)$", re.MULTILINE
)
_CALC_PARTITION_HEADER_RE = re.compile(
    r"^(?P<indent>[ \t]*)partition[ \t]+.+?[ \t]*=[ \t]*calculated[ \t]*$"
)
_MODE_LINE_RE = re.compile(r"^[ \t]+mode:")


def _sanitize_tmdl(tmdl: str) -> str:
    """Repair partition properties that Power BI Desktop rejects on open.

    Two corruptions, both produced by acting on an earlier (wrong) lint message:

      - `= dax` is a fictional PartitionSourceType. The valid keyword for a
        DAX/calculated table is `calculated`; Power BI raises InvalidValueFormat
        ("Failed to convert the value 'dax' to ... PartitionSourceType") on open.
      - `mode: calculated` is not a valid ModeType (import, directQuery, dual).
        Calculated partitions use `mode: import`.

    Rewrites both to the valid form and guarantees every calculated partition
    carries a `mode: import` line — the known-good shape every fixture uses.
    """
    text = _DAX_PARTITION_SOURCE_RE.sub(r"\1calculated\2", tmdl)
    text = _INVALID_MODE_RE.sub(r"\1import\2", text)
    return _ensure_calculated_partition_mode(text)


def _ensure_calculated_partition_mode(tmdl: str) -> str:
    """Insert `mode: import` after any calculated partition header lacking one.

    The mode line is indented one tab deeper than its `partition` header. A
    header already followed by a `mode:` line is left untouched (idempotent).
    """
    lines = tmdl.split("\n")
    out: list[str] = []
    for idx, line in enumerate(lines):
        out.append(line)
        header = _CALC_PARTITION_HEADER_RE.match(line)
        if not header:
            continue
        nxt = lines[idx + 1] if idx + 1 < len(lines) else ""
        if _MODE_LINE_RE.match(nxt):
            continue
        out.append(f"{header.group('indent')}\tmode: import")
    return "\n".join(out)


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


def _quote_name(name: str) -> str:
    """Quote a TMDL object-header name only when it contains whitespace.

    `table X`/`column X`/`ref table X` headers take exactly one token — a
    multi-word name must be quoted ('Economic Data') or Power BI Desktop
    fails to parse it ("the object name is followed by an invalid token").
    Property VALUES like `sourceColumn:` are a different grammar position —
    verified against real Power BI exports, they stay unquoted even with
    spaces — so this must only be applied to header lines, not values.
    """
    return f"'{name}'" if re.search(r"\s", name) else name


def _build_minimal_tmdl(
    table_name: str,
    columns: list[ModelColumn],
    measures: list[ModelMeasure],
) -> str:
    """Build a complete table TMDL with columns and measures but no data partition."""
    parts: list[str] = [
        f"table {_quote_name(table_name)}",
        f"\tlineageTag: {_new_guid()}",
        "",
    ]
    for m in measures:
        parts.append(_measure_block(m))
        parts.append("")
    for col in columns:
        parts += [
            f"\tcolumn {_quote_name(col.name)}",
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


def _register_ref_tables(semantic_model_dir: Path, table_names: list[str]) -> None:
    """Add missing `ref table <Name>` lines to model.tmdl.

    Power BI Desktop uses model.tmdl as the canonical manifest of which tables
    belong to the model. A table .tmdl file that has no corresponding `ref table`
    line may be loaded via directory scan AND via ref resolution simultaneously,
    causing TmdlObject.AddContentOf to throw a duplicate-definition error on open.

    Inserts each missing `ref table` before the first `ref cultureInfo` line (or
    appends before the final newline if no such line exists), preserving file
    structure. Safe to call repeatedly — skips names that are already present.
    """
    model_tmdl = semantic_model_dir / "definition" / "model.tmdl"
    if not model_tmdl.exists():
        return

    existing = model_tmdl.read_text(encoding="utf-8")
    lines = existing.splitlines()

    to_add = [
        name for name in table_names
        if f"ref table {_quote_name(name)}" not in existing
    ]
    if not to_add:
        return

    ref_lines = [f"ref table {_quote_name(name)}" for name in to_add]

    # Insert before `ref cultureInfo` if present, otherwise before the last blank line.
    insert_at = len(lines)
    for i, line in enumerate(lines):
        if line.startswith("ref cultureInfo"):
            insert_at = i
            break

    new_lines = lines[:insert_at] + ref_lines + lines[insert_at:]
    model_tmdl.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _new_guid() -> str:
    return uuid.uuid4().hex[:20]
