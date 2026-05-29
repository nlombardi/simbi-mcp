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


# ── Structural TMDL lint rules ────────────────────────────────────────────────

_VALID_TMDL_WITH_RELATIONSHIP = """\
table Sales
\tlineageTag: a1b2c3d4-e5f6-4a5b-8c9d-ef0123456789
\tcolumn Region
\t\tdataType: string
\t\tlineageTag: b2c3d4e5-f6a7-4b5c-9d0e-f01234567890
\t\tsummarizeBy: none
\t\tsourceColumn: Region

relationship f7a3c2b1-9d4e-4f1a-b2c3-d4e5f6a7b8c9
\tfromColumn: Sales.Region
\ttoColumn: Dim.Key
"""

_SEQUENTIAL_GUID_TMDL = """\
table Sales
\tlineageTag: a1b2c3d4-e5f6-4a5b-8c9d-ef0123456789
\tcolumn Region
\t\tdataType: string
\t\tlineageTag: b2c3d4e5-f6a7-4b5c-9d0e-f01234567890
\t\tsummarizeBy: none
\t\tsourceColumn: Region

relationship a1b2c3d4-e5f6-7890-abcd-ef1234567890
\tfromColumn: Sales.Region
\ttoColumn: Dim.Key
"""

_INVALID_GUID_TMDL = """\
table Sales
\tlineageTag: a1b2c3d4-e5f6-4a5b-8c9d-ef0123456789
\tcolumn Region
\t\tdataType: string
\t\tlineageTag: b2c3d4e5-f6a7-4b5c-9d0e-f01234567890
\t\tsummarizeBy: none
\t\tsourceColumn: Region

relationship not-a-uuid
\tfromColumn: Sales.Region
\ttoColumn: Dim.Key
"""

_TRUNCATED_LINEAGE_TAG_TMDL = """\
table Sales
\tlineageTag: a1b2c3d4e5f6a7b8c9d0
\tcolumn Region
\t\tdataType: string
\t\tlineageTag: b2c3d4e5f6a7b8c9d0e1
\t\tsummarizeBy: none
\t\tsourceColumn: Region
"""

_CALC_TABLE_MISSING_SOURCE_COL = """\
table Years
\tlineageTag: a1b2c3d4-e5f6-4a5b-8c9d-ef0123456789

\tcolumn Year
\t\tdataType: int64
\t\tlineageTag: b2c3d4e5-f6a7-4b5c-9d0e-f01234567890
\t\tsummarizeBy: none

\tpartition Years = calculated
\t\tmode: import
\t\tsource = SELECTCOLUMNS(GENERATESERIES(1980, 2031, 1), "Year", [Value])
"""

_CALC_TABLE_WITH_SOURCE_COL = """\
table Years
\tlineageTag: a1b2c3d4-e5f6-4a5b-8c9d-ef0123456789

\tcolumn Year
\t\tdataType: int64
\t\tlineageTag: b2c3d4e5-f6a7-4b5c-9d0e-f01234567890
\t\tsummarizeBy: none
\t\tsourceColumn: Year

\tpartition Years = calculated
\t\tmode: import
\t\tsource = SELECTCOLUMNS(GENERATESERIES(1980, 2031, 1), "Year", [Value])
"""


class TestRelationshipGuids:
    def test_valid_random_guid_is_clean(self) -> None:
        findings = lint_measures(_VALID_TMDL_WITH_RELATIONSHIP)
        guid_findings = [f for f in findings if "guid" in f.rule]
        assert guid_findings == []

    def test_sequential_guid_is_error(self) -> None:
        findings = lint_measures(_SEQUENTIAL_GUID_TMDL)
        rules = [f.rule for f in findings]
        assert "sequential-relationship-guid" in rules

    def test_non_uuid_relationship_id_is_error(self) -> None:
        findings = lint_measures(_INVALID_GUID_TMDL)
        rules = [f.rule for f in findings]
        assert "invalid-relationship-guid" in rules

    def test_error_severity_on_bad_guid(self) -> None:
        findings = lint_measures(_SEQUENTIAL_GUID_TMDL)
        bad = [f for f in findings if "guid" in f.rule]
        assert all(f.severity == LintSeverity.ERROR for f in bad)


class TestLineageTags:
    def test_full_uuid_lineage_tags_are_clean(self) -> None:
        findings = lint_measures(_VALID_TMDL_WITH_RELATIONSHIP)
        tag_findings = [f for f in findings if f.rule == "invalid-lineage-tag"]
        assert tag_findings == []

    def test_truncated_hex_lineage_tag_is_error(self) -> None:
        findings = lint_measures(_TRUNCATED_LINEAGE_TAG_TMDL)
        rules = [f.rule for f in findings]
        assert "invalid-lineage-tag" in rules

    def test_truncated_tag_error_severity(self) -> None:
        findings = lint_measures(_TRUNCATED_LINEAGE_TAG_TMDL)
        bad = [f for f in findings if f.rule == "invalid-lineage-tag"]
        assert all(f.severity == LintSeverity.ERROR for f in bad)


class TestCalcTableSourceColumn:
    def test_calc_table_missing_source_column_is_error(self) -> None:
        findings = lint_measures(_CALC_TABLE_MISSING_SOURCE_COL)
        rules = [f.rule for f in findings]
        assert "calc-table-missing-sourcecolumn" in rules

    def test_calc_table_with_source_column_is_clean(self) -> None:
        findings = lint_measures(_CALC_TABLE_WITH_SOURCE_COL)
        rules = [f.rule for f in findings]
        assert "calc-table-missing-sourcecolumn" not in rules

    def test_m_partition_table_without_source_column_is_clean(self) -> None:
        # M-partition tables don't require sourceColumn in the linter
        tmdl = _tmdl("SUM(Sales[Revenue])")
        findings = lint_measures(tmdl)
        rules = [f.rule for f in findings]
        assert "calc-table-missing-sourcecolumn" not in rules

    def test_error_names_table_and_column(self) -> None:
        findings = lint_measures(_CALC_TABLE_MISSING_SOURCE_COL)
        bad = [f for f in findings if f.rule == "calc-table-missing-sourcecolumn"]
        assert bad
        assert "Years" in bad[0].message
        assert "Year" in bad[0].message
