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

import json
import re
from dataclasses import dataclass
from pathlib import Path

from simbi_mcp.dax.linter import LintSeverity, lint_measures
from simbi_mcp.pbir.reserved_names import safe_table_name
from simbi_mcp.pbir.semantic_patcher import (
    _register_ref_tables,
    _sanitize_tmdl,
    _sync_pbi_query_order,
    _sync_ref_tables,
)

# Lint rules whose violation makes Power BI Desktop REFUSE to load the model
# (a crash on open). These are fatal for authoring; DAX-correctness rules
# (unknown-ref etc.) stay advisory because a referenced table may live in a file
# this call doesn't carry.
_FATAL_LINT_RULES = frozenset(
    {
        "table-missing-partition",
        "invalid-partition-mode",
        "invalid-partition-source",
        "calc-table-missing-sourcecolumn",
        "invalid-lineage-tag",
        "sequential-relationship-guid",
        "invalid-relationship-guid",
        "missing-variation-relationship",
    }
)

# Block starts are top-level (column 0) constructs; members are indented.
_BLOCK_START_RE = re.compile(r"^(?P<kind>table|relationship) (?P<rest>.+?)\s*$")
_TABLE_NAME_RE = re.compile(r"^(?:'(?P<q>.+?)'|(?P<u>\S+))")

# Keywords that start a table member (one tab under `table <name>`). Used to
# detect agent-authored members left at the wrong indentation depth.
_MEMBER_KEYWORD_RE = re.compile(
    r"^[ \t]*(measure|column|partition|hierarchy|variation|calculationGroup|"
    r"extendedProperty|changedProperty|annotation)\b"
)


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


def _detect_space_indentation(text: str) -> int | None:
    """Return the 1-based line number of the first space-indented line in a
    table block's body, or None if every line uses tabs (or is blank).

    TMDL requires literal TAB characters for indentation. Power BI Desktop's
    parser rejects space-indented lines outright — "Invalid indentation was
    detected" — even when the spacing is internally consistent (e.g. a
    uniform 2-space convention). Guessing the intended nesting depth from a
    space count is unsafe, so this is a hard-fail signal, not something to
    auto-repair.

    The first line (the `table <name>` header, always column 0) is skipped —
    it is legitimately unindented and must not be mistaken for the defect.
    """
    lines = text.split("\n")
    for i, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        if line[:1] == " ":
            return i
    return None


def _reindent_stray_members(text: str) -> str:
    """Re-indent table members left at column 0 instead of nested under the table.

    A common agent-authoring mistake: writing measures (or occasionally
    columns) as a trailing section after the table's other members, flush
    with the `table <name>` header's own left margin instead of one tab
    under it. Power BI Desktop rejects this with "Invalid indentation was
    detected" since the member no longer reads as belonging to the table.

    Detects each member header line (measure/column/partition/...) that
    starts at column 0, and shifts it — and every following line up to the
    next column-0 line — one tab deeper. The shift state is keyed on column-0
    only, NOT on every keyword match: a keyword like `annotation` commonly
    appears as a NESTED property of a column/measure (e.g. `annotation
    SummarizationSetBy = Automatic`), at whatever depth the stray member's own
    body sits at, and must keep shifting with it rather than being mistaken
    for a fresh, already-correct sibling. Already-correctly-indented members
    (and everything nested under them, which never reaches column 0) are left
    untouched, so this is safe to apply unconditionally; a fully-correct
    block round-trips unchanged.
    """
    lines = text.split("\n")
    if not lines:
        return text
    out = [lines[0]]  # `table <name>` header — always column 0, never touched
    shifting = False
    for line in lines[1:]:
        if line.strip():
            indent_len = len(line) - len(line.lstrip("\t"))
            if indent_len == 0:
                # Only column 0 marks a fresh (potentially stray) member —
                # anything deeper is either already-correct content or the
                # nested body of whatever member we're currently shifting.
                shifting = bool(_MEMBER_KEYWORD_RE.match(line))
        if shifting and line.strip():
            line = "\t" + line
        out.append(line)
    return "\n".join(out)


_VARIATION_HEADER_RE = re.compile(r"^(?P<indent>[ \t]*)variation\b")
_RELATIONSHIP_PROP_RE = re.compile(r"^[ \t]*relationship:\s*(?P<guid>\S+)")


def _strip_dangling_variations(text: str, defined_rel_ids: set[str]) -> str:
    """Remove variation blocks whose target relationship is not defined in the model.

    Power BI Desktop auto-generates `variation Variation` on date columns pointing
    to `LocalDateTable_<guid>` via a relationship in `relationships.tmdl`. If TMDL
    is copied or authored with a variation whose relationship is absent, Power BI
    Desktop crashes on open with:
    "Property Relationship of object 'variation Variation in column ...' refers to an object which cannot be found".

    Stripping dangling variations leaves the column intact as a standard column
    without broken relationship links.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _VARIATION_HEADER_RE.match(line)
        if m:
            indent_len = len(m.group("indent").expandtabs(4))
            block_lines = [line]
            rel_guid: str | None = None
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if not next_line.strip():
                    k = j + 1
                    deeper = False
                    while k < len(lines):
                        if lines[k].strip():
                            k_indent = len(lines[k]) - len(lines[k].lstrip("\t "))
                            k_exp = len(lines[k][:k_indent].expandtabs(4))
                            if k_exp > indent_len:
                                deeper = True
                            break
                        k += 1
                    if deeper:
                        block_lines.append(next_line)
                        j += 1
                        continue
                    else:
                        break
                next_indent = len(next_line) - len(next_line.lstrip("\t "))
                next_exp = len(next_line[:next_indent].expandtabs(4))
                if next_exp > indent_len:
                    rel_m = _RELATIONSHIP_PROP_RE.match(next_line)
                    if rel_m:
                        rel_guid = rel_m.group("guid").strip("'\"")
                    block_lines.append(next_line)
                    j += 1
                else:
                    break

            if rel_guid is not None and rel_guid in defined_rel_ids:
                out.extend(block_lines)
            i = j
        else:
            out.append(line)
            i += 1
    return "".join(out)


def _clean_diagram_layout(semantic_model_dir: Path, surviving_tables: set[str]) -> None:
    """Prune deleted table nodes from diagramLayout.json if present."""
    layout_file = semantic_model_dir / "diagramLayout.json"
    if not layout_file.exists():
        return
    try:
        data = json.loads(layout_file.read_text(encoding="utf-8"))
        diagrams = data.get("diagrams", [])
        changed = False
        for d in diagrams:
            nodes = d.get("nodes", [])
            filtered = [n for n in nodes if n.get("nodeIndex") in surviving_tables]
            if len(filtered) != len(nodes):
                d["nodes"] = filtered
                changed = True
        if changed:
            layout_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


_PARTITION_KEYWORD_RE = re.compile(r"^[ \t]*partition\b", re.MULTILINE)
_COLUMN_KEYWORD_RE = re.compile(r"^[ \t]*column\b", re.MULTILINE)


def _auto_heal_measure_partitions(text: str, table_name: str) -> str:
    """Auto-inject a calculated partition for measure-only tables missing one.

    When an agent authors a dedicated measures table (like `_Measures`), it
    frequently omits the partition block because the table has no physical data.
    However, Tabular Object Model (TOM) requires every table to have a partition.
    Omitting it causes Power BI Desktop to throw:
    'Model validation failed. A composite model cannot be used with entity based query sources'.

    If a table block contains NO partition and NO columns (only measures and
    properties), this auto-heals it with:
        partition <name> = calculated
            mode: import
            source = {BLANK()}

    If the table block has columns, it is not a pure measures container; we do
    not guess its data source, letting `table-missing-partition` reject it.
    """
    if _PARTITION_KEYWORD_RE.search(text):
        return text
    if _COLUMN_KEYWORD_RE.search(text):
        return text  # Has columns; do not auto-heal, let fatal lint rule catch it

    safe_name = _quote_name(table_name)
    partition_block = (
        f"\n\tpartition {safe_name} = calculated\n"
        f"\t\tmode: import\n"
        f"\t\tsource = {{BLANK()}}\n"
    )
    return text.rstrip() + "\n" + partition_block


def write_semantic_model(semantic_model_dir: Path, tmdl: str) -> dict[str, str]:
    """Persist a full agent-authored model TMDL to disk, normalized.

    Splits the TMDL into table/relationship blocks, rewrites reserved table names
    everywhere they appear, repairs partitions, re-indents members left at the
    wrong depth, strips dangling variation blocks, and refuses to write (raising
    ValueError) if any load-crash lint rule fires OR any line uses space instead
    of tab indentation. On success writes each table to ``tables/<name>.tmdl``,
    prunes orphan tables, writes ``relationships.tmdl``, and synchronizes
    ``model.tmdl``.

    Returns the ``{old: new}`` reserved-name rename map (empty when none).
    """
    blocks = _split_model_blocks(tmdl)
    renames = _reserved_renames(blocks)
    blocks = _apply_table_renames(blocks, renames)

    # Fail loudly BEFORE any repair or write: space-indentation can't be
    # safely auto-corrected (we don't know the author's intended depth-per-
    # level), so this must be a hard error, not a silent guess.
    for b in blocks:
        if b.kind != "table":
            continue
        bad_line = _detect_space_indentation(b.text)
        if bad_line is not None:
            raise ValueError(
                f"Table {b.name!r} uses space indentation on line {bad_line} "
                f"of its block, not tabs. TMDL requires literal TAB characters "
                f"for every nesting level: table members (measure/column/"
                f"partition/...) one tab under 'table {b.name}', their own "
                f"properties one tab deeper still. Power BI Desktop rejects "
                f"space-indented TMDL with 'Invalid indentation was detected' "
                f"even when the spacing is internally consistent. Rewrite this "
                f"table's members using tabs and call write_semantic_model again."
            )

    rel_blocks = [b for b in blocks if b.kind == "relationship"]
    defined_rel_ids = {b.name for b in rel_blocks}

    table_blocks = [
        ModelBlock(
            b.kind,
            b.name,
            _auto_heal_measure_partitions(
                _strip_dangling_variations(
                    _sanitize_tmdl(_reindent_stray_members(b.text)),
                    defined_rel_ids,
                ),
                b.name,
            ),
        )
        for b in blocks
        if b.kind == "table"
    ]

    # Fail loudly BEFORE writing anything: a half-written model is worse than none.
    normalized = "\n\n".join(b.text.rstrip() for b in table_blocks + rel_blocks) + "\n"
    fatal = [
        f
        for f in lint_measures(normalized)
        if f.severity == LintSeverity.ERROR and f.rule in _FATAL_LINT_RULES
    ]
    if fatal:
        raise ValueError(
            "Refusing to write semantic model: load-blocking errors:\n"
            + "\n".join(str(f) for f in fatal)
        )

    definition = semantic_model_dir / "definition"
    tables_dir = definition / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    active_table_names = {b.name for b in table_blocks}

    # Prune orphan tables left over from prior model states or starter templates.
    # Power BI Desktop scans all .tmdl files in tables/ on startup regardless of model.tmdl;
    # orphaned tables with broken variations/partitions cause fatal deserialization errors.
    # DateTableTemplate_* is Power BI's internal template and is preserved.
    for table_file in tables_dir.glob("*.tmdl"):
        stem = table_file.stem
        if stem not in active_table_names and not stem.startswith("DateTableTemplate_"):
            table_file.unlink()

    for b in table_blocks:
        (tables_dir / f"{b.name}.tmdl").write_text(b.text, encoding="utf-8")

    rel_file = definition / "relationships.tmdl"
    if rel_blocks:
        rel_text = "\n\n".join(b.text.rstrip() for b in rel_blocks) + "\n"
        rel_file.write_text(rel_text, encoding="utf-8")
    elif rel_file.exists():
        rel_file.write_text("\n", encoding="utf-8")

    surviving_tables = {f.stem for f in tables_dir.glob("*.tmdl")}
    _sync_ref_tables(semantic_model_dir, surviving_tables)
    _sync_pbi_query_order(semantic_model_dir)
    _clean_diagram_layout(semantic_model_dir, surviving_tables)
    return renames
