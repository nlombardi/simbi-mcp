"""Unit tests for semantic_patcher — ref table registration and measure insertion."""
from pathlib import Path

import pytest

from simbi_mcp.pbir.reserved_names import sanitize_schema
from simbi_mcp.pbir.semantic_patcher import (
    _build_minimal_tmdl,
    _new_guid,
    patch_semantic_model_measures,
)
from simbi_mcp.types import ModelMeasure, ModelSchema, ModelTable, ModelColumn, ModelRelationship


def _make_schema(
    table_name: str,
    measure_name: str,
    expr: str = "SUM(T[Value])",
    columns: list[ModelColumn] | None = None,
) -> ModelSchema:
    return ModelSchema(
        tables=[ModelTable(name=table_name, columns=columns or [])],
        measures=[ModelMeasure(name=measure_name, table=table_name, expression=expr, return_type="number")],
        relationships=[],
    )


def _scaffold_semantic_model(tmp_path: Path, existing_refs: list[str] | None = None) -> Path:
    """Create a minimal SemanticModel folder with a model.tmdl."""
    definition = tmp_path / "definition"
    (definition / "tables").mkdir(parents=True)
    refs = "\n".join(f"ref table {r}" for r in (existing_refs or []))
    model_tmdl = (
        "model Model\n"
        "\tculture: en-US\n"
        "\n"
        f"{refs}\n"
        "\n"
        "ref cultureInfo en-US\n"
    )
    (definition / "model.tmdl").write_text(model_tmdl, encoding="utf-8")
    return tmp_path


class TestRegisterRefTables:
    def test_adds_ref_table_for_newly_created_file(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        schema = _make_schema("MacroData", "GDP Growth %")

        patch_semantic_model_measures(schema, sm)

        model_content = (sm / "definition" / "model.tmdl").read_text(encoding="utf-8")
        assert "ref table MacroData" in model_content

    def test_ref_table_inserted_before_ref_cultureInfo(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        schema = _make_schema("MacroData", "GDP Growth %")

        patch_semantic_model_measures(schema, sm)

        model_content = (sm / "definition" / "model.tmdl").read_text(encoding="utf-8")
        ref_pos = model_content.index("ref table MacroData")
        culture_pos = model_content.index("ref cultureInfo en-US")
        assert ref_pos < culture_pos

    def test_does_not_duplicate_existing_ref_table(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path, existing_refs=["MacroData"])
        # Pre-create the .tmdl so patcher takes the update path (not create path)
        tmdl_path = sm / "definition" / "tables" / "MacroData.tmdl"
        tmdl_path.write_text(
            "table MacroData\n\tlineageTag: abc\n",
            encoding="utf-8",
        )
        schema = _make_schema("MacroData", "GDP Growth %")

        patch_semantic_model_measures(schema, sm)

        model_content = (sm / "definition" / "model.tmdl").read_text(encoding="utf-8")
        assert model_content.count("ref table MacroData") == 1

    def test_idempotent_on_second_call(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        schema = _make_schema("MacroData", "GDP Growth %")

        patch_semantic_model_measures(schema, sm)
        patch_semantic_model_measures(schema, sm)

        model_content = (sm / "definition" / "model.tmdl").read_text(encoding="utf-8")
        assert model_content.count("ref table MacroData") == 1

    def test_ref_table_name_with_space_is_quoted(self, tmp_path):
        # TMDL's `ref table <name>` grammar takes exactly one token; a bare
        # multi-word name ("ref table Economic Data") fails to parse in Power
        # BI Desktop with "the object name is followed by an invalid token" —
        # the name must be quoted, matching how `table 'Name'` is quoted
        # elsewhere whenever it contains whitespace.
        sm = _scaffold_semantic_model(tmp_path)
        schema = _make_schema("Economic Data", "GDP Value")

        patch_semantic_model_measures(schema, sm)

        model_content = (sm / "definition" / "model.tmdl").read_text(encoding="utf-8")
        assert "ref table 'Economic Data'" in model_content
        assert "ref table Economic Data\n" not in model_content

    def test_idempotent_for_quoted_ref_table_name(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        schema = _make_schema("Economic Data", "GDP Value")

        patch_semantic_model_measures(schema, sm)
        patch_semantic_model_measures(schema, sm)

        model_content = (sm / "definition" / "model.tmdl").read_text(encoding="utf-8")
        assert model_content.count("ref table 'Economic Data'") == 1

    def test_new_table_header_with_space_is_quoted(self, tmp_path):
        # Same underlying defect as the ref-table bug: a bare `table Economic
        # Data` header (no existing .tmdl, so _build_minimal_tmdl creates it)
        # is exactly as unparseable as the unquoted ref line was.
        sm = _scaffold_semantic_model(tmp_path)
        schema = _make_schema(
            "Economic Data", "GDP Value",
            columns=[ModelColumn(name="Country Code", data_type="string")],
        )

        patch_semantic_model_measures(schema, sm)

        table_content = (sm / "definition" / "tables" / "Economic Data.tmdl").read_text(
            encoding="utf-8"
        )
        assert "table 'Economic Data'" in table_content
        assert "table Economic Data\n" not in table_content
        # Column headers need the same quoting when the name has a space...
        assert "column 'Country Code'" in table_content
        assert "column Country Code\n" not in table_content
        # ...but sourceColumn is a property VALUE, not an object header, and
        # real Power BI exports leave it unquoted even with spaces.
        assert "sourceColumn: Country Code" in table_content

    def test_multiple_new_tables_all_registered(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        schema = ModelSchema(
            tables=[
                ModelTable(name="MacroData", columns=[]),
                ModelTable(name="Years", columns=[]),
            ],
            measures=[
                ModelMeasure(name="GDP Growth %", table="MacroData", expression="AVERAGE(MacroData[Value])", return_type="number"),
                ModelMeasure(name="Year Count", table="Years", expression="COUNTROWS(Years)", return_type="integer"),
            ],
            relationships=[],
        )

        patch_semantic_model_measures(schema, sm)

        model_content = (sm / "definition" / "model.tmdl").read_text(encoding="utf-8")
        assert "ref table MacroData" in model_content
        assert "ref table Years" in model_content

    def test_no_ref_registration_when_file_already_existed(self, tmp_path):
        """File-update path (existing .tmdl) should not add duplicate ref."""
        sm = _scaffold_semantic_model(tmp_path, existing_refs=["MacroData"])
        tmdl_path = sm / "definition" / "tables" / "MacroData.tmdl"
        tmdl_path.write_text(
            "table MacroData\n\tlineageTag: abc\n\n\tpartition MacroData = m\n\t\tmode: import\n",
            encoding="utf-8",
        )
        schema = _make_schema("MacroData", "New Measure")

        patch_semantic_model_measures(schema, sm)

        model_content = (sm / "definition" / "model.tmdl").read_text(encoding="utf-8")
        assert model_content.count("ref table MacroData") == 1

    def test_graceful_when_model_tmdl_missing(self, tmp_path):
        """No crash if model.tmdl doesn't exist — just skip ref registration."""
        definition = tmp_path / "definition"
        (definition / "tables").mkdir(parents=True)
        # model.tmdl intentionally omitted
        schema = _make_schema("MacroData", "GDP Growth %")

        patch_semantic_model_measures(schema, tmp_path)  # must not raise

        tmdl_path = tmp_path / "definition" / "tables" / "MacroData.tmdl"
        assert tmdl_path.exists()


class TestNoDataConnectionWarning:
    """A blank-table fallback (_build_minimal_tmdl) creates columns/measures
    with NO partition — the table has no connection to any actual data source.
    This is silent and easy to miss (visuals render, just empty), and it's
    exactly the state a caller ends up in if they skip write_semantic_model
    and let emit_report create the table for them. The caller must be told."""

    def test_warns_when_creating_new_table(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        schema = _make_schema("Economic Data", "GDP Value")

        warnings = patch_semantic_model_measures(schema, sm)

        assert len(warnings) == 1
        assert "Economic Data" in warnings[0]
        assert "no data source" in warnings[0].lower() or "no data connected" in warnings[0].lower()
        assert "write_semantic_model" in warnings[0]

    def test_no_warning_when_table_already_exists(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        tmdl_path = sm / "definition" / "tables" / "MacroData.tmdl"
        tmdl_path.write_text(
            "table MacroData\n\tlineageTag: abc\n\n\tpartition MacroData = m\n\t\tmode: import\n",
            encoding="utf-8",
        )
        schema = _make_schema("MacroData", "GDP Growth %")

        warnings = patch_semantic_model_measures(schema, sm)

        assert warnings == []

    def test_no_warning_when_no_measures(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        schema = ModelSchema(tables=[], measures=[], relationships=[])

        warnings = patch_semantic_model_measures(schema, sm)

        assert warnings == []

    def test_one_warning_per_newly_created_table(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path)
        schema = ModelSchema(
            tables=[ModelTable(name="MacroData", columns=[]), ModelTable(name="Years", columns=[])],
            measures=[
                ModelMeasure(name="GDP", table="MacroData", expression="AVERAGE(MacroData[Value])", return_type="number"),
                ModelMeasure(name="Year Count", table="Years", expression="COUNTROWS(Years)", return_type="integer"),
            ],
            relationships=[],
        )

        warnings = patch_semantic_model_measures(schema, sm)

        assert len(warnings) == 2
        assert any("MacroData" in w for w in warnings)
        assert any("Years" in w for w in warnings)


class TestRepairCorruptedDaxPartition:
    """A previous session may have written `partition X = dax` (a fictional
    PartitionSourceType) and deleted the mode line, per a wrong lint message.
    The patcher must heal those files back to the valid `= calculated` +
    `mode: import` form on the next emit — even when no new measures are added."""

    def _corrupt_tmdl(self) -> str:
        return (
            "table KPI\n"
            "\tlineageTag: abc\n"
            "\n"
            "\tmeasure 'Total' = SUM(KPI[Value])\n"
            "\t\tlineageTag: def\n"
            "\n"
            "\tpartition KPI = dax\n"
            "\t\tsource = SELECTCOLUMNS(GENERATESERIES(1, 3, 1), \"Value\", [Value])\n"
        )

    def test_dax_source_rewritten_even_with_no_new_measures(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path, existing_refs=["KPI"])
        tmdl_path = sm / "definition" / "tables" / "KPI.tmdl"
        tmdl_path.write_text(self._corrupt_tmdl(), encoding="utf-8")
        # Measure already present → exercises the no-new-measures path.
        schema = _make_schema("KPI", "Total", expr="SUM(KPI[Value])")

        patch_semantic_model_measures(schema, sm)

        content = tmdl_path.read_text(encoding="utf-8")
        assert "= dax" not in content
        assert "partition KPI = calculated" in content
        assert "mode: import" in content

    def test_mode_calculated_rewritten_to_import(self, tmp_path):
        sm = _scaffold_semantic_model(tmp_path, existing_refs=["KPI"])
        tmdl_path = sm / "definition" / "tables" / "KPI.tmdl"
        tmdl_path.write_text(
            "table KPI\n"
            "\tlineageTag: abc\n"
            "\n"
            "\tpartition KPI = calculated\n"
            "\t\tmode: calculated\n"
            "\t\tsource = {1}\n",
            encoding="utf-8",
        )
        schema = _make_schema("KPI", "Total", expr="SUM(KPI[Value])")

        patch_semantic_model_measures(schema, sm)

        content = tmdl_path.read_text(encoding="utf-8")
        assert "mode: calculated" not in content
        assert "mode: import" in content


class TestReservedNames:
    def test_sanitized_schema_never_writes_reserved_measures_table(self, tmp_path):
        """End-to-end guard: a schema whose measures live in a "Measures" table
        must, after sanitize_schema, produce a "_Measures.tmdl" — never a
        "Measures.tmdl" that the AS engine would reject on open."""
        sm = _scaffold_semantic_model(tmp_path)
        raw = _make_schema("Measures", "Total Revenue", expr="SUM(Sales[Amt])")

        patch_semantic_model_measures(sanitize_schema(raw), sm)

        tables_dir = sm / "definition" / "tables"
        assert not (tables_dir / "Measures.tmdl").exists()
        assert (tables_dir / "_Measures.tmdl").exists()
        content = (tables_dir / "_Measures.tmdl").read_text(encoding="utf-8")
        assert content.startswith("table _Measures")
        model_content = (sm / "definition" / "model.tmdl").read_text(encoding="utf-8")
        assert "ref table _Measures" in model_content
        assert "ref table Measures\n" not in model_content


class TestBuildMinimalTmdlPartitions:
    def test_empty_columns_generates_calculated_partition(self) -> None:
        tmdl = _build_minimal_tmdl(
            table_name="_Measures",
            columns=[],
            measures=[ModelMeasure(name="Total", table="_Measures", expression="1", return_type="integer")],
        )
        assert "partition _Measures = calculated" in tmdl
        assert "mode: import" in tmdl
        assert "source = {BLANK()}" in tmdl

    def test_columns_generates_m_partition(self) -> None:
        tmdl = _build_minimal_tmdl(
            table_name="Sales",
            columns=[ModelColumn(name="Region", data_type="string"), ModelColumn(name="Amount", data_type="double")],
            measures=[],
        )
        assert "partition Sales = m" in tmdl
        assert "mode: import" in tmdl
        assert '#table({"Region", "Amount"}, {})' in tmdl

    def test_new_guid_produces_full_uuid(self) -> None:
        import re
        guid = _new_guid()
        assert len(guid) == 36
        assert re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", guid)

    def test_new_table_with_columns_syncs_pbi_query_order(self, tmp_path: Path) -> None:
        sm = _scaffold_semantic_model(tmp_path)
        schema = _make_schema(
            "Economic Data",
            "GDP",
            columns=[ModelColumn(name="Country", data_type="string")],
        )
        patch_semantic_model_measures(schema, sm)

        model_content = (sm / "definition" / "model.tmdl").read_text(encoding="utf-8")
        assert 'annotation PBI_QueryOrder = ["Economic Data"]' in model_content

