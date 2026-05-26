"""Tests for the advisory DAX linter."""
from __future__ import annotations

import pytest

from simbi_mcp.dax.linter import LintFinding, LintSeverity, lint_measures


def _tmdl(measure_expr: str, *, table: str = "Sales", extra_cols: str = "") -> str:
    """Wrap a single measure expression in a minimal valid TMDL document."""
    cols = "\n    column Region\n        dataType: string\n    column Revenue\n        dataType: double"
    if extra_cols:
        cols += "\n" + extra_cols
    return (
        f"table {table}\n"
        f"    measure 'Test' = {measure_expr}\n"
        f"        formatString: #,0\n"
        f"{cols}\n"
    )


def test_clean_measure_returns_no_findings() -> None:
    tmdl = _tmdl("SUM(Sales[Revenue])")
    assert lint_measures(tmdl) == []


def test_search_without_fourth_arg_is_warning() -> None:
    tmdl = _tmdl('CALCULATE(SUM(Sales[Revenue]), FILTER(Sales, SEARCH("foo", Sales[Region]) > 0))')
    findings = lint_measures(tmdl)
    assert len(findings) == 1
    assert findings[0].severity == LintSeverity.WARNING
    assert "SEARCH" in findings[0].message
    assert findings[0].measure == "Test"


def test_search_with_fourth_arg_is_clean() -> None:
    tmdl = _tmdl('CALCULATE(SUM(Sales[Revenue]), FILTER(Sales, SEARCH("foo", Sales[Region], 1, 0) > 0))')
    assert lint_measures(tmdl) == []


def test_containsstring_is_clean() -> None:
    tmdl = _tmdl('CALCULATE(SUM(Sales[Revenue]), FILTER(Sales, CONTAINSSTRING(Sales[Region], "foo")))')
    assert lint_measures(tmdl) == []


def test_year_literal_aggregation_is_warning() -> None:
    extra = "    column '2026'\n        dataType: double"
    tmdl = _tmdl("AVERAGE(Sales[2026])", extra_cols=extra)
    findings = lint_measures(tmdl)
    warns = [f for f in findings if f.severity == LintSeverity.WARNING]
    assert any("year-literal" in f.message.lower() or "wide" in f.message.lower() for f in warns)


def test_year_literal_in_filter_is_clean() -> None:
    extra = "    column Year\n        dataType: int64"
    tmdl = _tmdl("CALCULATE(SUM(Sales[Revenue]), FILTER(Sales, Sales[Year] = 2026))", extra_cols=extra)
    assert lint_measures(tmdl) == []


def test_unknown_column_reference_is_error() -> None:
    tmdl = _tmdl("SUM(Sales[NonExistentColumn])")
    findings = lint_measures(tmdl)
    errors = [f for f in findings if f.severity == LintSeverity.ERROR]
    assert len(errors) == 1
    assert "NonExistentColumn" in errors[0].message


def test_unknown_table_reference_is_error() -> None:
    tmdl = _tmdl("SUM(GhostTable[Revenue])")
    findings = lint_measures(tmdl)
    errors = [f for f in findings if f.severity == LintSeverity.ERROR]
    assert any("GhostTable" in f.message for f in errors)


def test_reference_to_other_table_column_is_clean() -> None:
    tmdl = (
        "table Sales\n"
        "    measure 'Cross' = SUM(Inventory[Stock])\n"
        "        formatString: #,0\n"
        "    column Region\n"
        "        dataType: string\n"
        "table Inventory\n"
        "    column Stock\n"
        "        dataType: int64\n"
    )
    assert lint_measures(tmdl) == []


def test_multiple_measures_findings_are_attributed() -> None:
    tmdl = (
        "table Sales\n"
        '    measure \'A\' = SUM(Sales[Ghost])\n'
        "        formatString: #,0\n"
        '    measure \'B\' = SEARCH("x", Sales[Region])\n'
        "        formatString: #,0\n"
        "    column Region\n"
        "        dataType: string\n"
    )
    findings = lint_measures(tmdl)
    measures_with_findings = {f.measure for f in findings}
    assert measures_with_findings == {"A", "B"}


def test_lint_does_not_flag_quoted_string_contents() -> None:
    tmdl = _tmdl('CALCULATE(SUM(Sales[Revenue]), Sales[Region] = "GhostTable[Ghost]")')
    findings = lint_measures(tmdl)
    errors = [f for f in findings if f.severity == LintSeverity.ERROR]
    assert errors == []


def test_finding_renders_as_string() -> None:
    tmdl = _tmdl("SUM(Sales[Ghost])")
    findings = lint_measures(tmdl)
    rendered = str(findings[0])
    assert "ERROR" in rendered
    assert "Test" in rendered
    assert "Ghost" in rendered
