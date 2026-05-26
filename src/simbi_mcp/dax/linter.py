"""Advisory linter for DAX measures defined in TMDL text.

Not a validator — a clean lint does NOT mean the DAX is semantically correct.
The linter only catches a small, deliberately-narrow set of mechanical mistakes
that produce confusing runtime errors. Three rules:

    error    unknown table/column reference inside a measure expression
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


def lint_measures(tmdl: str) -> list[LintFinding]:
    """Run advisory lint rules on every measure in `tmdl`.

    Returns findings in source order. Empty list means no rules triggered —
    NOT that the DAX is correct.
    """
    schema = parse_tmdl_schema(tmdl)
    findings: list[LintFinding] = []
    for measure in schema.measures:
        expr_no_strings = _STRING_LITERAL_RE.sub('""', measure.expression)
        findings.extend(_check_unknown_refs(measure.name, expr_no_strings, schema))
        findings.extend(_check_search_arity(measure.name, expr_no_strings))
        findings.extend(_check_year_literal_aggregation(measure.name, expr_no_strings))
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
