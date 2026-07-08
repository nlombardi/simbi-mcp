"""Unit tests for model_writer — full Path-1 semantic-model authoring."""
from __future__ import annotations

from pathlib import Path

import pytest

from simbi_mcp.pbir.model_writer import (
    _apply_table_renames,
    _detect_space_indentation,
    _reindent_stray_members,
    _reserved_renames,
    _split_model_blocks,
    write_semantic_model,
)


_FULL_MODEL_TMDL = """\
table WEO_Long
\tlineageTag: 11111111-1111-4111-8111-111111111111

\tcolumn Year
\t\tdataType: int64
\t\tlineageTag: 22222222-2222-4222-8222-222222222222
\t\tsummarizeBy: none
\t\tsourceColumn: Year

\tpartition WEO_Long = m
\t\tmode: import
\t\tsource =
\t\t\tlet Source = Excel.Workbook(File.Contents("x.xlsx")) in Source

table Year
\tlineageTag: 33333333-3333-4333-8333-333333333333

\tcolumn Year
\t\tdataType: int64
\t\tlineageTag: 44444444-4444-4444-8444-444444444444
\t\tsummarizeBy: none
\t\tsourceColumn: Year

\tpartition Year = calculated
\t\tmode: import
\t\tsource = GENERATESERIES(1980, 2031, 1)

relationship abcdef12-3456-4789-abcd-ef0123456789
\tfromColumn: WEO_Long.Year
\ttoColumn: Year.Year
"""


class TestSplitModelBlocks:
    def test_splits_tables_and_relationship(self) -> None:
        blocks = _split_model_blocks(_FULL_MODEL_TMDL)
        kinds = [(b.kind, b.name) for b in blocks]
        assert kinds == [
            ("table", "WEO_Long"),
            ("table", "Year"),
            ("relationship", "abcdef12-3456-4789-abcd-ef0123456789"),
        ]

    def test_table_block_retains_partition(self) -> None:
        blocks = _split_model_blocks(_FULL_MODEL_TMDL)
        weo = next(b for b in blocks if b.name == "WEO_Long")
        assert "partition WEO_Long = m" in weo.text
        assert "Table.Contents" not in weo.text  # sanity: no cross-block bleed

    def test_quoted_table_name(self) -> None:
        blocks = _split_model_blocks("table 'My Table'\n\tlineageTag: x\n")
        assert blocks[0].kind == "table"
        assert blocks[0].name == "My Table"


class TestReservedRenames:
    def test_detects_reserved_table(self) -> None:
        blocks = _split_model_blocks("table Measures\n\tlineageTag: x\n")
        assert _reserved_renames(blocks) == {"Measures": "_Measures"}

    def test_no_renames_when_clean(self) -> None:
        blocks = _split_model_blocks(_FULL_MODEL_TMDL)
        assert _reserved_renames(blocks) == {}


_RESERVED_MODEL_TMDL = """\
table Measures
\tlineageTag: 55555555-5555-4555-8555-555555555555

\tmeasure 'Real GDP' = CALCULATE(SUM(WEO_Long[Value]), Measures[x]) + SUM(Measures[Value])

\tpartition Measures = calculated
\t\tmode: import
\t\tsource = {BLANK()}

relationship aaaaaaaa-1111-4111-8111-111111111111
\tfromColumn: Measures.Key
\ttoColumn: WEO_Long.Key
"""


class TestApplyTableRenames:
    def test_rewrites_table_and_partition_header(self) -> None:
        blocks = _split_model_blocks(_RESERVED_MODEL_TMDL)
        renames = {"Measures": "_Measures"}
        out = _apply_table_renames(blocks, renames)
        table = next(b for b in out if b.kind == "table")
        assert table.name == "_Measures"
        assert "table _Measures" in table.text
        assert "partition _Measures = calculated" in table.text
        assert "table Measures\n" not in table.text

    def test_rewrites_dax_column_refs(self) -> None:
        blocks = _split_model_blocks(_RESERVED_MODEL_TMDL)
        out = _apply_table_renames(blocks, {"Measures": "_Measures"})
        table = next(b for b in out if b.kind == "table")
        # Bracketed DAX refs Measures[x] / Measures[Value] must be rewritten.
        assert "_Measures[x]" in table.text
        assert "_Measures[Value]" in table.text
        # The other table's ref must be untouched.
        assert "WEO_Long[Value]" in table.text

    def test_rewrites_relationship_endpoints(self) -> None:
        blocks = _split_model_blocks(_RESERVED_MODEL_TMDL)
        out = _apply_table_renames(blocks, {"Measures": "_Measures"})
        rel = next(b for b in out if b.kind == "relationship")
        assert "fromColumn: _Measures.Key" in rel.text
        assert "toColumn: WEO_Long.Key" in rel.text


def _scaffold_semantic_model(tmp_path: Path) -> Path:
    definition = tmp_path / "definition"
    (definition / "tables").mkdir(parents=True)
    (definition / "model.tmdl").write_text(
        "model Model\n\tculture: en-US\n\nref cultureInfo en-US\n", encoding="utf-8"
    )
    return tmp_path


class TestWriteSemanticModel:
    def test_reserved_table_written_with_safe_name(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        renames = write_semantic_model(sm, _RESERVED_MODEL_TMDL)

        tables = sm / "definition" / "tables"
        assert renames == {"Measures": "_Measures"}
        assert (tables / "_Measures.tmdl").exists()
        assert not (tables / "Measures.tmdl").exists()
        body = (tables / "_Measures.tmdl").read_text(encoding="utf-8")
        assert "table _Measures" in body
        assert "_Measures[Value]" in body

    def test_relationships_and_refs_written(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        write_semantic_model(sm, _RESERVED_MODEL_TMDL)

        rels = (sm / "definition" / "relationships.tmdl").read_text(encoding="utf-8")
        assert "fromColumn: _Measures.Key" in rels
        model = (sm / "definition" / "model.tmdl").read_text(encoding="utf-8")
        assert "ref table _Measures" in model

    def test_repairs_dax_partition_source(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        tmdl = (
            "table Years\n"
            "\tlineageTag: 66666666-6666-4666-8666-666666666666\n"
            "\n"
            "\tcolumn Year\n"
            "\t\tdataType: int64\n"
            "\t\tlineageTag: 77777777-7777-4777-8777-777777777777\n"
            "\t\tsummarizeBy: none\n"
            "\t\tsourceColumn: Year\n"
            "\n"
            "\tpartition Years = dax\n"
            "\t\tsource = GENERATESERIES(1980, 2031, 1)\n"
        )
        write_semantic_model(sm, tmdl)

        body = (sm / "definition" / "tables" / "Years.tmdl").read_text(encoding="utf-8")
        assert "= dax" not in body
        assert "partition Years = calculated" in body
        assert "mode: import" in body

    def test_fails_loudly_on_structural_error(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        # Sequential relationship GUID is a hard lint ERROR.
        tmdl = (
            "table A\n\tlineageTag: 88888888-8888-4888-8888-888888888888\n"
            "\n\tcolumn K\n\t\tdataType: int64\n\t\tlineageTag: 99999999-9999-4999-8999-999999999999\n"
            "\t\tsummarizeBy: none\n\t\tsourceColumn: K\n"
            "\n\tpartition A = m\n\t\tmode: import\n\t\tsource = let x = 1 in x\n"
            "\nrelationship a1b2c3d4-e5f6-7890-abcd-ef1234567890\n"
            "\tfromColumn: A.K\n\ttoColumn: A.K\n"
        )
        with pytest.raises(ValueError):
            write_semantic_model(sm, tmdl)
        # Nothing partially written on failure.
        assert not (sm / "definition" / "tables" / "A.tmdl").exists()


# ---------- Indentation repair/validation (Power BI TMDL requires literal tabs) ----------

# Reproduces the reported failure: columns properly indented (1 tab), measures
# floating at column 0 (0 tabs) instead of nested under the table, with a
# multi-line DAX body left at its original (now too-shallow) depth.
_STRAY_MEASURES_TMDL = """\
table WEO
\tlineageTag: 81fd2903-8b6b-4b1e-b0e9-3e0d5c8a2c1f

\tcolumn "INDICATOR.ID"
\t\tdataType: string
\t\tlineageTag: c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f

\tcolumn Value
\t\tdataType: double
\t\tlineageTag: a7b8c9d0-e1f2-4a3b-5c6d-7e8f9a0b1c2d

\tpartition WEO = m
\t\tmode: import
\t\tsource =
\t\t\tlet x = 1 in x

measure "Real GDP" =
\tCALCULATE(
\t\tAVERAGE([Value]),
\t\tFILTER('WEO', 'WEO'[INDICATOR.ID] = "NGDP_RPCH")
\t)

measure "GDP Value" = SUM([Value])
"""


class TestReindentStrayMembers:
    def test_shifts_column_zero_measure_header_and_body(self) -> None:
        blocks = _split_model_blocks(_STRAY_MEASURES_TMDL)
        weo = next(b for b in blocks if b.name == "WEO")
        out = _reindent_stray_members(weo.text)
        assert '\tmeasure "Real GDP" =' in out
        assert '\n\t\tCALCULATE(' in out
        assert '\n\t\t\tAVERAGE([Value]),' in out
        assert '\n\t\t\tFILTER(' in out
        assert '\n\t\t)' in out
        # No non-blank line after the `table` header is left at column 0.
        lines = out.split("\n")
        for line in lines[1:]:
            if line.strip():
                assert line.startswith("\t"), f"still at column 0: {line!r}"

    def test_shifts_single_line_measure(self) -> None:
        blocks = _split_model_blocks(_STRAY_MEASURES_TMDL)
        weo = next(b for b in blocks if b.name == "WEO")
        out = _reindent_stray_members(weo.text)
        assert '\tmeasure "GDP Value" = SUM([Value])' in out

    def test_leaves_correctly_indented_content_untouched(self) -> None:
        blocks = _split_model_blocks(_FULL_MODEL_TMDL)
        weo_long = next(b for b in blocks if b.name == "WEO_Long")
        out = _reindent_stray_members(weo_long.text)
        assert out == weo_long.text  # fully idempotent — nothing was stray

    def test_table_header_line_never_shifted(self) -> None:
        blocks = _split_model_blocks(_STRAY_MEASURES_TMDL)
        weo = next(b for b in blocks if b.name == "WEO")
        out = _reindent_stray_members(weo.text)
        assert out.split("\n")[0] == "table WEO"

    def test_stray_column_is_also_reindented(self) -> None:
        tmdl = 'table T\n\tlineageTag: x\n\ncolumn Stray\n\tdataType: string\n\tlineageTag: y\n'
        blocks = _split_model_blocks(tmdl)
        t = next(b for b in blocks if b.name == "T")
        out = _reindent_stray_members(t.text)
        assert "\tcolumn Stray" in out
        assert "\t\tdataType: string" in out


class TestDetectSpaceIndentation:
    def test_finds_first_space_indented_line(self) -> None:
        tmdl = (
            'table WEO\n\tlineageTag: x\n\n'
            '  measure "Average Value" = AVERAGE([Value])\n'
        )
        blocks = _split_model_blocks(tmdl)
        weo = next(b for b in blocks if b.name == "WEO")
        assert _detect_space_indentation(weo.text) == 4

    def test_returns_none_when_clean(self) -> None:
        blocks = _split_model_blocks(_FULL_MODEL_TMDL)
        weo_long = next(b for b in blocks if b.name == "WEO_Long")
        assert _detect_space_indentation(weo_long.text) is None

    def test_table_header_column_zero_is_not_flagged(self) -> None:
        # The `table X` header line itself is legitimately at column 0 with no
        # leading space — must not be mistaken for space-indentation.
        blocks = _split_model_blocks("table WEO\n\tlineageTag: x\n")
        weo = next(b for b in blocks if b.name == "WEO")
        assert _detect_space_indentation(weo.text) is None


class TestWriteSemanticModelIndentation:
    def test_repairs_stray_measures_before_writing(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        write_semantic_model(sm, _STRAY_MEASURES_TMDL)

        body = (sm / "definition" / "tables" / "WEO.tmdl").read_text(encoding="utf-8")
        lines = body.split("\n")
        for line in lines[1:]:
            if line.strip():
                assert line.startswith("\t"), f"still at column 0 on disk: {line!r}"
        assert '\tmeasure "Real GDP" =' in body
        assert '\tmeasure "GDP Value" = SUM([Value])' in body

    def test_rejects_space_indentation_and_writes_nothing(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        tmdl = (
            "table WEO\n\tlineageTag: 11111111-1111-4111-8111-111111111111\n\n"
            "\tcolumn Value\n\t\tdataType: double\n"
            "\t\tlineageTag: 22222222-2222-4222-8222-222222222222\n\n"
            "\tpartition WEO = m\n\t\tmode: import\n\t\tsource = let x = 1 in x\n\n"
            '  measure "Average Value" = AVERAGE([Value])\n'
        )
        with pytest.raises(ValueError, match="(?i)tab"):
            write_semantic_model(sm, tmdl)
        assert not (sm / "definition" / "tables" / "WEO.tmdl").exists()
