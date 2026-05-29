"""Advisory linter for DAX measures and TMDL structure.

Not a validator — a clean lint does NOT mean the DAX is semantically correct.
The linter catches a deliberately-narrow set of mechanical mistakes that produce
confusing Power BI Desktop load errors. Rules:

    error    unknown table/column reference inside a measure expression
    error    relationship GUID is not a valid random UUID (sequential/patterned
             GUIDs cause "invalid column ID" or similar AS engine errors)
    error    calculated table column missing sourceColumn property (required by
             Power BI Desktop's TMDL serializer even for calculated tables)
    error    lineageTag is not a full UUID (truncated hex is silently misread)
    warning  SEARCH() called without a 4th argument (errors on no-match)
    warning  aggregation of a year-literal column (likely wide-format mistake)

Rules are scoped to be high-precision: false positives train agents to ignore
the linter, which is worse than missing some true positives. Semantic checks
("is this the right aggregation?", "is this DAX answering the user's question?")
are explicitly out of scope.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from simbi_mcp.semantic.schema_reader import parse_tmdl_schema
from simbi_mcp.types import ModelSchema


class LintSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class LintFinding:
    severity: LintSeverity
    measure: str
    rule: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.measure} ({self.rule}): {self.message}"


_STRING_LITERAL_RE = re.compile(r'"[^"]*"')
_REF_RE = re.compile(r"(?P<tbl>'[^']+'|[A-Za-z_][\w]*)\[(?P<col>[^\]]+)\]")
_SEARCH_CALL_RE = re.compile(r"\bSEARCH\s*\(", re.IGNORECASE)
_AGG_FUNCS = ("SUM", "AVERAGE", "MIN", "MAX", "MEDIAN", "STDEV.S", "STDEV.P", "VAR.S", "VAR.P")
_AGG_YEAR_RE = re.compile(
    r"\b(" + "|".join(re.escape(f) for f in _AGG_FUNCS) + r")\s*\(\s*"
    r"(?:'[^']+'|[A-Za-z_]\w*)\[(?:'?(\d{4})'?)\]",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"^\d{4}$")

# Structural TMDL patterns
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
# Sequential/patterned GUIDs: segments that are purely ascending hex sequences
# like a1b2c3d4-e5f6-7890-... — heuristic: ≥3 segments are monotonically ordered bytes
_SEQUENTIAL_GUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_RELATIONSHIP_GUID_RE = re.compile(r"^relationship\s+(\S+)\s*$", re.MULTILINE)
_LINEAGE_TAG_RE = re.compile(r"lineageTag:\s*(\S+)")
_CALC_TABLE_RE = re.compile(r"partition\s+\S+\s*=\s*calculated", re.IGNORECASE)
_TABLE_BLOCK_RE = re.compile(r"^table\s+(\S+)", re.MULTILINE)
_COLUMN_BLOCK_RE = re.compile(r"^\t(column\s+\S.*)", re.MULTILINE)
_SOURCE_COL_RE = re.compile(r"\bsourceColumn\s*:", re.IGNORECASE)


def lint_measures(tmdl: str) -> list[LintFinding]:
    """Run advisory lint rules on TMDL structure and every measure expression.

    Returns findings in source order. Empty list means no rules triggered —
    NOT that the DAX is correct.
    """
    schema = parse_tmdl_schema(tmdl)
    findings: list[LintFinding] = []

    # Structural checks (TMDL-level, not per-measure)
    findings.extend(_check_relationship_guids(tmdl))
    findings.extend(_check_lineage_tags(tmdl))
    findings.extend(_check_calc_table_source_columns(tmdl))

    # DAX expression checks (per-measure)
    for measure in schema.measures:
        expr_no_strings = _STRING_LITERAL_RE.sub('""', measure.expression)
        findings.extend(_check_unknown_refs(measure.name, expr_no_strings, schema))
        findings.extend(_check_search_arity(measure.name, expr_no_strings))
        findings.extend(_check_year_literal_aggregation(measure.name, expr_no_strings))
    return findings


_HEX_ALPHABET = "0123456789abcdef"
# Any 6+ consecutive characters of the hex alphabet appearing in the flat GUID digits
# is a strong indicator of a hand-crafted sequential pattern.
_SEQUENTIAL_SUBSTRINGS = frozenset(
    _HEX_ALPHABET[i:i+6] for i in range(len(_HEX_ALPHABET) - 5)
)


def _is_sequential_guid(guid: str) -> bool:
    """Return True if a valid UUID looks hand-crafted or sequential.

    LLM-fabricated GUIDs typically contain runs of the hex alphabet —
    e.g. a1b2c3d4 (alternating), c4d5e6f7 (offset), 01234567 (direct).
    This checks for any 6+ consecutive hex digits that form a substring of
    '0123456789abcdef' — a pattern essentially impossible in a random UUID.
    """
    flat = guid.replace("-", "").lower()
    return any(sub in flat for sub in _SEQUENTIAL_SUBSTRINGS)


def _check_relationship_guids(tmdl: str) -> list[LintFinding]:
    findings: list[LintFinding] = []
    for match in _RELATIONSHIP_GUID_RE.finditer(tmdl):
        guid = match.group(1)
        if not _UUID_RE.match(guid):
            findings.append(LintFinding(
                severity=LintSeverity.ERROR,
                measure="(relationship)",
                rule="invalid-relationship-guid",
                message=(
                    f"Relationship GUID {guid!r} is not a valid UUID. "
                    f"Use uuid.uuid4() or an online UUID generator. "
                    f"Power BI Desktop rejects non-UUID relationship identifiers."
                ),
            ))
        elif _is_sequential_guid(guid):
            findings.append(LintFinding(
                severity=LintSeverity.ERROR,
                measure="(relationship)",
                rule="sequential-relationship-guid",
                message=(
                    f"Relationship GUID {guid!r} appears hand-crafted or sequential "
                    f"(ascending byte pattern detected). Power BI Desktop's Analysis "
                    f"Services engine uses GUIDs as column binding keys — fabricated "
                    f"GUIDs cause 'invalid column ID' crashes on open. "
                    f"Generate a real random UUID."
                ),
            ))
    return findings


def _check_lineage_tags(tmdl: str) -> list[LintFinding]:
    findings: list[LintFinding] = []
    for match in _LINEAGE_TAG_RE.finditer(tmdl):
        tag = match.group(1).strip()
        if not _UUID_RE.match(tag):
            findings.append(LintFinding(
                severity=LintSeverity.ERROR,
                measure="(structure)",
                rule="invalid-lineage-tag",
                message=(
                    f"lineageTag {tag!r} is not a full UUID "
                    f"(xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx). "
                    f"Truncated hex tags cause silent misreads. "
                    f"Generate real random UUIDs for all lineageTag values."
                ),
            ))
    return findings


def _check_calc_table_source_columns(tmdl: str) -> list[LintFinding]:
    """Check that every column in a calculated table has sourceColumn defined.

    Power BI Desktop's TMDL serializer requires sourceColumn on calculated table
    columns even though logically there is no physical source — the property maps
    to the output column name from the DAX expression. Omitting it causes
    PFE_TM_METADATA_CALCTABLE_COLUMN_MISSING_SOURCECOLUMN on open.
    """
    findings: list[LintFinding] = []

    # Split TMDL into per-table blocks
    table_positions = [(m.start(), m.group(1)) for m in _TABLE_BLOCK_RE.finditer(tmdl)]
    for i, (start, table_name) in enumerate(table_positions):
        end = table_positions[i + 1][0] if i + 1 < len(table_positions) else len(tmdl)
        block = tmdl[start:end]

        if not _CALC_TABLE_RE.search(block):
            continue  # not a calculated table — sourceColumn is optional

        # Find column sub-blocks within this table block
        col_positions = list(_COLUMN_BLOCK_RE.finditer(block))
        for j, col_match in enumerate(col_positions):
            col_start = col_match.start()
            col_end = col_positions[j + 1].start() if j + 1 < len(col_positions) else len(block)
            col_name = col_match.group(1).split("=", 1)[0].replace("column", "").strip().strip("'")
            col_block = block[col_start:col_end]

            if not _SOURCE_COL_RE.search(col_block):
                findings.append(LintFinding(
                    severity=LintSeverity.ERROR,
                    measure="(structure)",
                    rule="calc-table-missing-sourcecolumn",
                    message=(
                        f"Column {col_name!r} in calculated table {table_name!r} "
                        f"is missing 'sourceColumn: {col_name}'. Power BI Desktop "
                        f"requires this property even on calculated tables — it maps "
                        f"to the DAX output column name. Add: "
                        f"sourceColumn: {col_name}"
                    ),
                ))
    return findings


def _check_unknown_refs(
    measure_name: str, expr: str, schema: ModelSchema
) -> list[LintFinding]:
    findings: list[LintFinding] = []
    known_tables = {t.name: {c.name for c in t.columns} for t in schema.tables}
    for match in _REF_RE.finditer(expr):
        table = match.group("tbl").strip("'")
        col = match.group("col").strip().strip("'")
        if table not in known_tables:
            findings.append(
                LintFinding(
                    severity=LintSeverity.ERROR,
                    measure=measure_name,
                    rule="unknown-table",
                    message=(
                        f"Reference to {table}[{col}] but table {table!r} is "
                        f"not defined in the TMDL. Known tables: "
                        f"{sorted(known_tables) or '(none)'}."
                    ),
                )
            )
            continue
        if col not in known_tables[table]:
            findings.append(
                LintFinding(
                    severity=LintSeverity.ERROR,
                    measure=measure_name,
                    rule="unknown-column",
                    message=(
                        f"Reference to {table}[{col}] but column {col!r} is not "
                        f"defined on table {table!r}. Known columns: "
                        f"{sorted(known_tables[table]) or '(none)'}."
                    ),
                )
            )
    return findings


def _check_search_arity(measure_name: str, expr: str) -> list[LintFinding]:
    findings: list[LintFinding] = []
    for match in _SEARCH_CALL_RE.finditer(expr):
        args = _extract_call_args(expr, match.end() - 1)
        if args is None:
            continue
        if len(args) < 4:
            findings.append(
                LintFinding(
                    severity=LintSeverity.WARNING,
                    measure=measure_name,
                    rule="search-arity",
                    message=(
                        "SEARCH() raises a runtime error when the substring is "
                        "not found. Pass a 4th argument (e.g. "
                        "SEARCH(find, within, 1, BLANK())) or switch to "
                        "CONTAINSSTRING(within, find), which returns FALSE on "
                        "no-match."
                    ),
                )
            )
    return findings


def _check_year_literal_aggregation(measure_name: str, expr: str) -> list[LintFinding]:
    findings: list[LintFinding] = []
    for match in _AGG_YEAR_RE.finditer(expr):
        fn, year = match.group(1), match.group(2)
        findings.append(
            LintFinding(
                severity=LintSeverity.WARNING,
                measure=measure_name,
                rule="year-literal-aggregation",
                message=(
                    f"{fn.upper()}() is being applied to a year-literal column "
                    f"[{year}]. This usually indicates a wide-format source "
                    f"(one column per period). Consider unpivoting to a long "
                    f"format with Year and Value columns, then aggregating "
                    f"Value with a FILTER on Year. If [{year}] is a legitimate "
                    f"snapshot column, ignore this warning."
                ),
            )
        )
    return findings


def _extract_call_args(expr: str, open_paren_idx: int) -> list[str] | None:
    """Return the top-level comma-separated args of a call starting at `(`.

    Returns None if the parentheses are unbalanced. Quoted strings already
    stripped by the caller, so commas inside literals are not a concern.
    """
    depth = 0
    args: list[str] = []
    current = []
    i = open_paren_idx
    if expr[i] != "(":
        return None
    i += 1
    while i < len(expr):
        ch = expr[i]
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            if depth == 0:
                args.append("".join(current).strip())
                return args
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1
    return None
