"""Unit tests for semantic_patcher — ref table registration and measure insertion."""
from pathlib import Path

import pytest

from simbi_mcp.pbir.semantic_patcher import patch_semantic_model_measures
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
