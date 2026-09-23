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
        f"    partition {table} = m\n"
        f"        mode: import\n"
        f"        source = let x = 1 in x\n"
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
        "    partition Sales = m\n"
        "        mode: import\n"
        "        source = let x = 1 in x\n"
        "table Inventory\n"
        "    column Stock\n"
        "        dataType: int64\n"
        "    partition Inventory = m\n"
        "        mode: import\n"
        "        source = let x = 1 in x\n"
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
        "    partition Sales = m\n"
        "        mode: import\n"
        "        source = let x = 1 in x\n"
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


_DAX_SOURCE_TYPE_TMDL = """\
table Years
\tlineageTag: a1b2c3d4-e5f6-4a5b-8c9d-ef0123456789

\tpartition Years = dax
\t\tsource = SELECTCOLUMNS(GENERATESERIES(1980, 2031, 1), "Year", [Value])
"""


class TestInvalidPartitionSource:
    def test_dax_source_type_is_error(self) -> None:
        findings = lint_measures(_DAX_SOURCE_TYPE_TMDL)
        rules = [f.rule for f in findings]
        assert "invalid-partition-source" in rules

    def test_dax_source_type_error_severity(self) -> None:
        findings = lint_measures(_DAX_SOURCE_TYPE_TMDL)
        bad = [f for f in findings if f.rule == "invalid-partition-source"]
        assert bad and all(f.severity == LintSeverity.ERROR for f in bad)

    def test_calculated_source_type_is_clean(self) -> None:
        findings = lint_measures(_CALC_TABLE_WITH_SOURCE_COL)
        rules = [f.rule for f in findings]
        assert "invalid-partition-source" not in rules


_INVALID_MODE_TMDL = """\
table Years
\tlineageTag: a1b2c3d4-e5f6-4a5b-8c9d-ef0123456789

\tpartition Years = calculated
\t\tmode: calculated
\t\tsource = SELECTCOLUMNS(GENERATESERIES(1980, 2031, 1), "Year", [Value])
"""


class TestInvalidPartitionMode:
    def test_mode_calculated_is_error(self) -> None:
        findings = lint_measures(_INVALID_MODE_TMDL)
        rules = [f.rule for f in findings]
        assert "invalid-partition-mode" in rules

    def test_mode_message_recommends_import_not_dax(self) -> None:
        findings = [
            f for f in lint_measures(_INVALID_MODE_TMDL)
            if f.rule == "invalid-partition-mode"
        ]
        assert findings
        msg = findings[0].message.lower()
        assert "import" in msg
        assert "= dax" not in msg

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


class TestMissingVariationRelationship:
    def test_missing_variation_relationship_is_error(self) -> None:
        tmdl = (
            "table T\n\tlineageTag: 11111111-1111-4111-8111-111111111111\n\n"
            "\tcolumn Date\n\t\tdataType: dateTime\n"
            "\t\tvariation Variation\n\t\t\trelationship: 0c85f157-fa62-4bc9-9364-b69fbe939e03\n"
        )
        findings = lint_measures(tmdl)
        rules = [f.rule for f in findings]
        assert "missing-variation-relationship" in rules
        bad = next(f for f in findings if f.rule == "missing-variation-relationship")
        assert bad.severity == LintSeverity.ERROR
        assert "0c85f157-fa62-4bc9-9364-b69fbe939e03" in bad.message

    def test_defined_variation_relationship_is_clean(self) -> None:
        rel_guid = "0c85f157-fa62-4bc9-9364-b69fbe939e03"
        tmdl = (
            "table T\n\tlineageTag: 11111111-1111-4111-8111-111111111111\n\n"
            "\tcolumn Date\n\t\tdataType: dateTime\n"
            f"\t\tvariation Variation\n\t\t\trelationship: {rel_guid}\n\n"
            f"relationship {rel_guid}\n\tfromColumn: T.Date\n\ttoColumn: T.Date\n"
        )
        findings = lint_measures(tmdl)
        assert not any(f.rule == "missing-variation-relationship" for f in findings)


class TestTablePartitions:
    def test_missing_partition_is_error(self) -> None:
        tmdl = (
            "table Sales\n"
            "\tlineageTag: a1b2c3d4-e5f6-4a5b-8c9d-ef0123456789\n"
            "\tcolumn Region\n"
            "\t\tdataType: string\n"
        )
        findings = lint_measures(tmdl)
        rules = [f.rule for f in findings]
        assert "table-missing-partition" in rules
        bad = next(f for f in findings if f.rule == "table-missing-partition")
        assert bad.severity == LintSeverity.ERROR
        assert "Sales" in bad.message
        assert "partition Sales = calculated" in bad.message

    def test_table_with_m_partition_is_clean(self) -> None:
        tmdl = (
            "table Sales\n"
            "\tlineageTag: a1b2c3d4-e5f6-4a5b-8c9d-ef0123456789\n"
            "\tcolumn Region\n"
            "\t\tdataType: string\n"
            "\tpartition Sales = m\n"
            "\t\tmode: import\n"
            "\t\tsource = let x = 1 in x\n"
        )
        findings = lint_measures(tmdl)
        assert not any(f.rule == "table-missing-partition" for f in findings)

    def test_table_with_calculated_partition_is_clean(self) -> None:
        tmdl = (
            "table _Measures\n"
            "\tlineageTag: a1b2c3d4-e5f6-4a5b-8c9d-ef0123456789\n"
            "\tmeasure 'M1' = 1\n"
            "\tpartition _Measures = calculated\n"
            "\t\tmode: import\n"
            "\t\tsource = {BLANK()}\n"
        )
        findings = lint_measures(tmdl)
        assert not any(f.rule == "table-missing-partition" for f in findings)

