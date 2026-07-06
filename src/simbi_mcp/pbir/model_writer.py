"""Path-1 semantic-model authoring: persist agent-written TMDL to disk, normalized.

SimBI's documented Path 1 lets the agent define the whole model as TMDL text and
have SimBI persist it — no live Power BI MCP connection required. Historically
only *measures* were persisted (patch_semantic_model_measures), so the agent had
to hand-write table/partition files directly to disk, bypassing every SimBI
guard. A reserved table name (e.g. "Measures") or an invalid partition written
that way crashes Power BI Desktop on open.

This module closes that gap: it takes the full model TMDL, normalizes it (reserved
table names rewritten EVERYWHERE they appear, partitions repaired), validates it,
then writes each table to its own .tmdl file, writes relationships.tmdl, and
registers every table in model.tmdl. Nothing reaches disk un-normalized.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from simbi_mcp.dax.linter import LintSeverity, lint_measures
from simbi_mcp.pbir.reserved_names import safe_table_name
from simbi_mcp.pbir.semantic_patcher import _register_ref_tables, _sanitize_tmdl

# Lint rules whose violation makes Power BI Desktop REFUSE to load the model
# (a crash on open). These are fatal for authoring; DAX-correctness rules
# (unknown-ref etc.) stay advisory because a referenced table may live in a file
# this call doesn't carry.
_FATAL_LINT_RULES = frozenset(
    {
        "invalid-partition-mode",
        "invalid-partition-source",
        "calc-table-missing-sourcecolumn",
        "invalid-lineage-tag",
        "sequential-relationship-guid",
        "invalid-relationship-guid",
    }
)

# Block starts are top-level (column 0) constructs; members are indented.
_BLOCK_START_RE = re.compile(r"^(?P<kind>table|relationship) (?P<rest>.+?)\s*$")
_TABLE_NAME_RE = re.compile(r"^(?:'(?P<q>.+?)'|(?P<u>\S+))")


@dataclass
class ModelBlock:
    kind: str  # "table" | "relationship"
    name: str  # table name (unquoted) or relationship id
    text: str  # the block's full TMDL text, including its header line


def _split_model_blocks(tmdl: str) -> list[ModelBlock]:
    """Split full-model TMDL into its top-level table and relationship blocks.

    A block begins at a column-0 `table <name>` or `relationship <id>` line and
    runs until the next such line (or EOF). Leading content before the first
    block (blank lines, stray model header) is ignored.
    """
    blocks: list[ModelBlock] = []
    current: ModelBlock | None = None
    buffer: list[str] = []

    def _flush() -> None:
        if current is not None:
            current.text = "\n".join(buffer).rstrip() + "\n"
            blocks.append(current)

    for line in tmdl.splitlines():
        start = _BLOCK_START_RE.match(line)
        if start:
            _flush()
            kind = start.group("kind")
            rest = start.group("rest")
            if kind == "table":
                m = _TABLE_NAME_RE.match(rest)
                name = (m.group("q") or m.group("u")) if m else rest
            else:
                name = rest.strip()
            current = ModelBlock(kind=kind, name=name, text="")
            buffer = [line]
        elif current is not None:
            buffer.append(line)
    _flush()
    return blocks


def _reserved_renames(blocks: list[ModelBlock]) -> dict[str, str]:
    """Return {old: new} for every table block whose name is reserved."""
    renames: dict[str, str] = {}
    for b in blocks:
        if b.kind != "table":
            continue
        safe = safe_table_name(b.name)
        if safe != b.name:
            renames[b.name] = safe
    return renames


def _quote_name(name: str) -> str:
    """Quote a TMDL object name only when it contains whitespace."""
    return f"'{name}'" if re.search(r"\s", name) else name


def _rewrite_refs(text: str, renames: dict[str, str]) -> str:
    """Rewrite every reference to a renamed table within a block's text.

    Covers: the `table`/`partition` header lines, bracketed DAX refs
    (`Old[Col]` / `'Old'[Col]`), and dotted refs (`Old.Col` / `'Old'.Col`, used
    by relationship endpoints and sortByColumn). A leading word character before
    the name blocks the match, so an already-prefixed `_Old` is never doubled and
    unrelated identifiers ending in the name are left alone.
    """
    for old, new in renames.items():
        esc = re.escape(old)
        new_q = _quote_name(new)
        # table header
        text = re.sub(
            rf"^(?P<i>[ \t]*table[ \t]+)(['\"]?){esc}\2[ \t]*$",
            rf"\g<i>{new_q}",
            text,
            flags=re.MULTILINE,
        )
        # partition header (name shares the table name, up to the `=`)
        text = re.sub(
            rf"^(?P<i>[ \t]*partition[ \t]+)(['\"]?){esc}\2(?P<r>[ \t]*=)",
            rf"\g<i>{new_q}\g<r>",
            text,
            flags=re.MULTILINE,
        )
        # bracketed DAX refs: Old[  and  'Old'[
        text = re.sub(rf"(?<![\w_]){esc}\[", f"{new}[", text)
        text = re.sub(rf"'{esc}'\[", f"'{new}'[", text)
        # dotted refs: Old.  and  'Old'.
        text = re.sub(rf"(?<![\w_]){esc}\.", f"{new}.", text)
        text = re.sub(rf"'{esc}'\.", f"'{new}'.", text)
    return text


def _apply_table_renames(
    blocks: list[ModelBlock], renames: dict[str, str]
) -> list[ModelBlock]:
    """Return blocks with reserved-table references rewritten everywhere."""
    if not renames:
        return blocks
    out: list[ModelBlock] = []
    for b in blocks:
        name = renames.get(b.name, b.name) if b.kind == "table" else b.name
        out.append(ModelBlock(kind=b.kind, name=name, text=_rewrite_refs(b.text, renames)))
    return out


def write_semantic_model(semantic_model_dir: Path, tmdl: str) -> dict[str, str]:
    """Persist a full agent-authored model TMDL to disk, normalized.

    Splits the TMDL into table/relationship blocks, rewrites reserved table names
    everywhere they appear, repairs partitions, and refuses to write (raising
    ValueError) if any load-crash lint rule fires. On success writes each table
    to ``tables/<name>.tmdl``, writes ``relationships.tmdl`` when relationships
    are supplied, and registers every table in ``model.tmdl``.

    Returns the ``{old: new}`` reserved-name rename map (empty when none).
    """
    blocks = _split_model_blocks(tmdl)
    renames = _reserved_renames(blocks)
    blocks = _apply_table_renames(blocks, renames)

    table_blocks = [
        ModelBlock(b.kind, b.name, _sanitize_tmdl(b.text))
        for b in blocks
        if b.kind == "table"
    ]
    rel_blocks = [b for b in blocks if b.kind == "relationship"]

    # Fail loudly BEFORE writing anything: a half-written model is worse than none.
    normalized = "\n\n".join(b.text.rstrip() for b in table_blocks + rel_blocks) + "\n"
    fatal = [
        f
        for f in lint_measures(normalized)
        if f.severity == LintSeverity.ERROR and f.rule in _FATAL_LINT_RULES
    ]
    if fatal:
        raise ValueError(
            "Refusing to write semantic model — load-blocking errors:\n"
            + "\n".join(str(f) for f in fatal)
        )

    definition = semantic_model_dir / "definition"
    tables_dir = definition / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    for b in table_blocks:
        (tables_dir / f"{b.name}.tmdl").write_text(b.text, encoding="utf-8")

    if rel_blocks:
        rel_text = "\n\n".join(b.text.rstrip() for b in rel_blocks) + "\n"
        (definition / "relationships.tmdl").write_text(rel_text, encoding="utf-8")

    _register_ref_tables(semantic_model_dir, [b.name for b in table_blocks])
    return renames
