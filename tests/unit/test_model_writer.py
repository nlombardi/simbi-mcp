"""Unit tests for model_writer — full Path-1 semantic-model authoring."""
from __future__ import annotations

from pathlib import Path

import pytest

from simbi_mcp.pbir.model_writer import (
    _apply_table_renames,
    _auto_heal_measure_partitions,
    _detect_space_indentation,
    _reindent_stray_members,
    _reserved_renames,
    _split_model_blocks,
    write_semantic_model,
)
from simbi_mcp.pbir.semantic_patcher import _sync_pbi_query_order


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

    def test_multiword_table_name_ref_is_quoted(self, tmp_path):
        # Reproduces the real-world failure: a table named "Economic Data"
        # (quoted in the agent-authored header, per TMDL's own requirement)
        # must ALSO get a quoted `ref table 'Economic Data'` line in
        # model.tmdl -- an unquoted ref line fails with "InvalidObjectHeader:
        # the object name is followed by an invalid token".
        sm = _scaffold_semantic_model(tmp_path)
        tmdl = (
            "table 'Economic Data'\n"
            "\tlineageTag: 11111111-1111-4111-8111-111111111111\n\n"
            "\tcolumn Value\n\t\tdataType: double\n"
            "\t\tlineageTag: 22222222-2222-4222-8222-222222222222\n\n"
            "\tpartition 'Economic Data' = m\n\t\tmode: import\n\t\tsource = let x = 1 in x\n\n"
            "\tmeasure 'GDP Value' = SUM('Economic Data'[Value])\n"
        )
        write_semantic_model(sm, tmdl)

        model_content = (sm / "definition" / "model.tmdl").read_text(encoding="utf-8")
        assert "ref table 'Economic Data'" in model_content
        assert "ref table Economic Data\n" not in model_content

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

    def test_stray_member_with_nested_annotation_keeps_annotation_nested(self) -> None:
        # `annotation` is itself a recognized member keyword, but here it's a
        # NESTED property of the stray column (matching how Power BI commonly
        # writes `annotation SummarizationSetBy = Automatic` under a column),
        # not a sibling table-level member. It must shift WITH the column, not
        # get left behind at the column's old (pre-shift) depth.
        tmdl = (
            "table T\n\tlineageTag: x\n\n"
            "column Stray\n"
            "\tdataType: string\n"
            "\tannotation SummarizationSetBy = Automatic\n"
            "\tlineageTag: y\n"
        )
        blocks = _split_model_blocks(tmdl)
        t = next(b for b in blocks if b.name == "T")
        out = _reindent_stray_members(t.text)
        lines = out.split("\n")
        for line in lines[1:]:
            if line.strip():
                assert line.startswith("\t"), f"still at column 0: {line!r}"
        assert "\t\tannotation SummarizationSetBy = Automatic" in out
        assert "\t\tlineageTag: y" in out  # the line AFTER annotation also stays shifted


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

    def test_whitespace_only_blank_line_is_not_flagged(self) -> None:
        # A line containing only spaces is blank, not space-indented content.
        tmdl = "table WEO\n\tlineageTag: x\n   \n\tcolumn Y\n\t\tdataType: string\n"
        blocks = _split_model_blocks(tmdl)
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


class TestOrphanTablePruningAndCleanup:
    def test_prunes_orphan_tables_and_local_date_tables(self, tmp_path: Path) -> None:
        sm = _scaffold_semantic_model(tmp_path)
        tables_dir = sm / "definition" / "tables"
        (tables_dir / "Countries.tmdl").write_text("table Countries\n\tlineageTag: 11111111-1111-4111-8111-111111111111\n", encoding="utf-8")
        (tables_dir / "LocalDateTable_12345678.tmdl").write_text("table LocalDateTable_12345678\n\tlineageTag: 22222222-2222-4222-8222-222222222222\n", encoding="utf-8")
        (tables_dir / "DateTableTemplate_abc123.tmdl").write_text("table DateTableTemplate_abc123\n\tlineageTag: 33333333-3333-4333-8333-333333333333\n", encoding="utf-8")

        tmdl = (
            "table WEO_Data\n"
            "\tlineageTag: 44444444-4444-4444-8444-444444444444\n\n"
            "\tcolumn Year\n\t\tdataType: int64\n"
            "\t\tlineageTag: 55555555-5555-4555-8555-555555555555\n"
            "\t\tsummarizeBy: none\n\t\tsourceColumn: Year\n\n"
            "\tpartition WEO_Data = m\n\t\tmode: import\n\t\tsource = let x = 1 in x\n"
        )
        write_semantic_model(sm, tmdl)

        assert (tables_dir / "WEO_Data.tmdl").exists()
        assert (tables_dir / "DateTableTemplate_abc123.tmdl").exists()
        assert not (tables_dir / "Countries.tmdl").exists()
        assert not (tables_dir / "LocalDateTable_12345678.tmdl").exists()

    def test_syncs_model_tmdl_refs(self, tmp_path: Path) -> None:
        sm = _scaffold_semantic_model(tmp_path)
        tables_dir = sm / "definition" / "tables"
        (tables_dir / "DateTableTemplate_abc123.tmdl").write_text("table DateTableTemplate_abc123\n\tlineageTag: 33333333-3333-4333-8333-333333333333\n", encoding="utf-8")
        model_tmdl = sm / "definition" / "model.tmdl"
        model_tmdl.write_text(
            "model Model\n\tculture: en-US\n\n"
            "ref table DateTableTemplate_abc123\n"
            "ref table Countries\n\n"
            "ref cultureInfo en-US\n",
            encoding="utf-8",
        )

        tmdl = (
            "table WEO_Data\n"
            "\tlineageTag: 44444444-4444-4444-8444-444444444444\n\n"
            "\tcolumn Year\n\t\tdataType: int64\n"
            "\t\tlineageTag: 55555555-5555-4555-8555-555555555555\n"
            "\t\tsummarizeBy: none\n\t\tsourceColumn: Year\n\n"
            "\tpartition WEO_Data = m\n\t\tmode: import\n\t\tsource = let x = 1 in x\n"
        )
        write_semantic_model(sm, tmdl)

        content = model_tmdl.read_text(encoding="utf-8")
        assert "ref table Countries" not in content
        assert "ref table WEO_Data" in content
        assert "ref table DateTableTemplate_abc123" in content

    def test_clears_relationships_when_none_supplied(self, tmp_path: Path) -> None:
        sm = _scaffold_semantic_model(tmp_path)
        rel_file = sm / "definition" / "relationships.tmdl"
        rel_file.write_text("relationship old-guid\n\tfromColumn: A.X\n\ttoColumn: B.Y\n", encoding="utf-8")

        tmdl = (
            "table WEO_Data\n"
            "\tlineageTag: 44444444-4444-4444-8444-444444444444\n\n"
            "\tcolumn Year\n\t\tdataType: int64\n"
            "\t\tlineageTag: 55555555-5555-4555-8555-555555555555\n"
            "\t\tsummarizeBy: none\n\t\tsourceColumn: Year\n\n"
            "\tpartition WEO_Data = m\n\t\tmode: import\n\t\tsource = let x = 1 in x\n"
        )
        write_semantic_model(sm, tmdl)

        assert rel_file.exists()
        assert rel_file.read_text(encoding="utf-8").strip() == ""

    def test_strips_dangling_variation_referencing_absent_relationship(self, tmp_path: Path) -> None:
        sm = _scaffold_semantic_model(tmp_path)
        tmdl = (
            "table Countries\n"
            "\tlineageTag: 11111111-1111-4111-8111-111111111111\n\n"
            "\tcolumn COUNTRY_UPDATE_DATE\n"
            "\t\tdataType: dateTime\n"
            "\t\tformatString: Long Date\n"
            "\t\tlineageTag: 22222222-2222-4222-8222-222222222222\n"
            "\t\tsummarizeBy: none\n"
            "\t\tsourceColumn: COUNTRY_UPDATE_DATE\n\n"
            "\t\tvariation Variation\n"
            "\t\t\tisDefault\n"
            "\t\t\trelationship: 0c85f157-fa62-4bc9-9364-b69fbe939e03\n"
            "\t\t\tdefaultHierarchy: LocalDateTable_eb17baf9-e61f-4097-b2ee-f6f92aee7ede.'Date Hierarchy'\n\n"
            "\t\tannotation SummarizationSetBy = Automatic\n\n"
            "\tpartition Countries = m\n"
            "\t\tmode: import\n"
            "\t\tsource = let x = 1 in x\n"
        )
        write_semantic_model(sm, tmdl)

        body = (sm / "definition" / "tables" / "Countries.tmdl").read_text(encoding="utf-8")
        assert "variation Variation" not in body
        assert "0c85f157-fa62-4bc9-9364-b69fbe939e03" not in body
        assert "column COUNTRY_UPDATE_DATE" in body
        assert "annotation SummarizationSetBy = Automatic" in body

    def test_preserves_valid_variation_referencing_defined_relationship(self, tmp_path: Path) -> None:
        sm = _scaffold_semantic_model(tmp_path)
        rel_guid = "9b64ea26-5cd0-4d51-a968-3e42ea2d603a"
        tmdl = (
            "table Orders\n"
            "\tlineageTag: 11111111-1111-4111-8111-111111111111\n\n"
            "\tcolumn OrderDate\n"
            "\t\tdataType: dateTime\n"
            "\t\tlineageTag: 22222222-2222-4222-8222-222222222222\n"
            "\t\tsummarizeBy: none\n"
            "\t\tsourceColumn: OrderDate\n\n"
            "\t\tvariation Variation\n"
            "\t\t\tisDefault\n"
            f"\t\t\trelationship: {rel_guid}\n\n"
            "\tpartition Orders = m\n"
            "\t\tmode: import\n"
            "\t\tsource = let x = 1 in x\n\n"
            f"relationship {rel_guid}\n"
            "\tfromColumn: Orders.OrderDate\n"
            "\ttoColumn: Orders.OrderDate\n"
        )
        write_semantic_model(sm, tmdl)

        body = (sm / "definition" / "tables" / "Orders.tmdl").read_text(encoding="utf-8")
        assert "variation Variation" in body
        assert rel_guid in body

    def test_cleans_diagram_layout_nodes(self, tmp_path: Path) -> None:
        import json
        sm = _scaffold_semantic_model(tmp_path)
        layout = {
            "version": "1.1.0",
            "diagrams": [
                {
                    "ordinal": 0,
                    "nodes": [
                        {"nodeIndex": "Countries", "nodeLineageTag": "tag-1"},
                        {"nodeIndex": "WEO_Data", "nodeLineageTag": "tag-2"},
                    ],
                }
            ],
        }
        (sm / "diagramLayout.json").write_text(json.dumps(layout), encoding="utf-8")

        tmdl = (
            "table WEO_Data\n"
            "\tlineageTag: 44444444-4444-4444-8444-444444444444\n\n"
            "\tcolumn Year\n\t\tdataType: int64\n"
            "\t\tlineageTag: 55555555-5555-4555-8555-555555555555\n"
            "\t\tsummarizeBy: none\n\t\tsourceColumn: Year\n\n"
            "\tpartition WEO_Data = m\n\t\tmode: import\n\t\tsource = let x = 1 in x\n"
        )
        write_semantic_model(sm, tmdl)

        updated = json.loads((sm / "diagramLayout.json").read_text(encoding="utf-8"))
        node_indices = [n["nodeIndex"] for n in updated["diagrams"][0]["nodes"]]
        assert "Countries" not in node_indices
        assert "WEO_Data" in node_indices


class TestAutoHealMeasurePartitions:
    def test_auto_heals_measure_only_table(self, tmp_path: Path) -> None:
        sm = _scaffold_semantic_model(tmp_path)
        tmdl = (
            "table WEO_Data\n"
            "\tlineageTag: 44444444-4444-4444-8444-444444444444\n\n"
            "\tcolumn Year\n\t\tdataType: int64\n"
            "\t\tlineageTag: 55555555-5555-4555-8555-555555555555\n"
            "\t\tsummarizeBy: none\n\t\tsourceColumn: Year\n\n"
            "\tpartition WEO_Data = m\n\t\tmode: import\n\t\tsource = let x = 1 in x\n\n"
            "table _Measures\n"
            "\tlineageTag: 66666666-6666-4666-8666-666666666666\n\n"
            "\tmeasure 'Total Growth' = AVERAGE(WEO_Data[Year])\n"
            "\t\tformatString: 0.00%\n"
            "\t\tlineageTag: 77777777-7777-4777-8777-777777777777\n"
        )
        write_semantic_model(sm, tmdl)

        measures_tmdl = (sm / "definition" / "tables" / "_Measures.tmdl").read_text(encoding="utf-8")
        assert "partition _Measures = calculated" in measures_tmdl
        assert "mode: import" in measures_tmdl
        assert "source = {BLANK()}" in measures_tmdl

    def test_rejects_column_table_missing_partition(self, tmp_path: Path) -> None:
        sm = _scaffold_semantic_model(tmp_path)
        tmdl = (
            "table RawData\n"
            "\tlineageTag: 44444444-4444-4444-8444-444444444444\n\n"
            "\tcolumn Value\n\t\tdataType: double\n"
            "\t\tlineageTag: 55555555-5555-4555-8555-555555555555\n"
            "\t\tsummarizeBy: sum\n\t\tsourceColumn: Value\n"
        )
        with pytest.raises(ValueError, match="table-missing-partition"):
            write_semantic_model(sm, tmdl)
        assert not (sm / "definition" / "tables" / "RawData.tmdl").exists()

    def test_unit_auto_heal_preserves_existing_partition(self) -> None:
        raw = (
            "table MyCalc\n"
            "\tcolumn Val\n\t\tdataType: int64\n"
            "\tpartition MyCalc = calculated\n\t\tmode: import\n\t\tsource = {1}\n"
        )
        assert _auto_heal_measure_partitions(raw, "MyCalc") == raw


class TestSyncPbiQueryOrder:
    def test_prunes_stale_queries_and_adds_new_m_queries(self, tmp_path: Path) -> None:
        sm = _scaffold_semantic_model(tmp_path)
        tables_dir = sm / "definition" / "tables"
        (tables_dir / "MacroData.tmdl").write_text(
            "table MacroData\n\tpartition MacroData = m\n\t\tmode: import\n", encoding="utf-8"
        )
        (tables_dir / "_Measures.tmdl").write_text(
            "table _Measures\n\tpartition _Measures = calculated\n\t\tmode: import\n", encoding="utf-8"
        )

        model_tmdl = sm / "definition" / "model.tmdl"
        model_tmdl.write_text(
            'model Model\n\tculture: en-US\n\nannotation PBI_QueryOrder = ["DeletedQuery", "StaleTable"]\n\nref table MacroData\n',
            encoding="utf-8",
        )

        _sync_pbi_query_order(sm)

        content = model_tmdl.read_text(encoding="utf-8")
        assert 'annotation PBI_QueryOrder = ["MacroData"]' in content
        assert "DeletedQuery" not in content
        assert "_Measures" not in content

    def test_preserves_order_of_surviving_m_queries(self, tmp_path: Path) -> None:
        sm = _scaffold_semantic_model(tmp_path)
        tables_dir = sm / "definition" / "tables"
        (tables_dir / "TableB.tmdl").write_text(
            "table TableB\n\tpartition TableB = m\n\t\tmode: import\n", encoding="utf-8"
        )
        (tables_dir / "TableA.tmdl").write_text(
            "table TableA\n\tpartition TableA = m\n\t\tmode: import\n", encoding="utf-8"
        )
        (tables_dir / "TableC.tmdl").write_text(
            "table TableC\n\tpartition TableC = m\n\t\tmode: import\n", encoding="utf-8"
        )

        model_tmdl = sm / "definition" / "model.tmdl"
        model_tmdl.write_text(
            'model Model\n\tculture: en-US\n\nannotation PBI_QueryOrder = ["TableB", "OldDeleted", "TableA"]\n\nref table TableB\n',
            encoding="utf-8",
        )

        _sync_pbi_query_order(sm)

        content = model_tmdl.read_text(encoding="utf-8")
        assert 'annotation PBI_QueryOrder = ["TableB", "TableA", "TableC"]' in content

    def test_inserts_query_order_when_missing_and_m_tables_exist(self, tmp_path: Path) -> None:
        sm = _scaffold_semantic_model(tmp_path)
        tables_dir = sm / "definition" / "tables"
        (tables_dir / "Sales.tmdl").write_text(
            "table Sales\n\tpartition Sales = m\n\t\tmode: import\n", encoding="utf-8"
        )

        model_tmdl = sm / "definition" / "model.tmdl"
        model_tmdl.write_text(
            "model Model\n\tculture: en-US\n\nref table Sales\n\nref cultureInfo en-US\n",
            encoding="utf-8",
        )

        _sync_pbi_query_order(sm)

        content = model_tmdl.read_text(encoding="utf-8")
        assert 'annotation PBI_QueryOrder = ["Sales"]' in content

