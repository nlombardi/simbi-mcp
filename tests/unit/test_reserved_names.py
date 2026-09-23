"""Unit tests for reserved_names — guarding against AS reserved table names.

Power BI's Tabular engine rejects any table literally named "Measures"
(it collides with the implicit MDX Measures dimension). SimBI must rename
such tables consistently across the schema so the report's visual.json
bindings and the SemanticModel TMDL agree.
"""
import pytest

from simbi_mcp.pbir.reserved_names import (
    reserved_table_renames,
    safe_table_name,
    sanitize_schema,
    sanitize_semantic_model_dir,
)
from simbi_mcp.types import (
    ModelColumn,
    ModelMeasure,
    ModelRelationship,
    ModelSchema,
    ModelTable,
)


class TestSafeTableName:
    @pytest.mark.parametrize("reserved", ["Measures", "measures", "MEASURES", " Measures "])
    def test_reserved_name_is_prefixed(self, reserved):
        assert safe_table_name(reserved) == f"_{reserved}"

    @pytest.mark.parametrize("ok", ["Sales", "_Measures", "Key Measures", "MeasuresTable"])
    def test_non_reserved_name_is_unchanged(self, ok):
        assert safe_table_name(ok) == ok


class TestSanitizeSchema:
    def test_renames_measures_table_in_table_defs(self):
        schema = ModelSchema(
            tables=[ModelTable(name="Measures", columns=[])],
            measures=[],
            relationships=[],
        )
        out = sanitize_schema(schema)
        assert [t.name for t in out.tables] == ["_Measures"]

    def test_renames_measure_host_table(self):
        schema = ModelSchema(
            tables=[ModelTable(name="Measures", columns=[])],
            measures=[
                ModelMeasure(name="Total Revenue", table="Measures",
                             expression="SUM(Sales[Amt])", return_type="currency"),
            ],
            relationships=[],
        )
        out = sanitize_schema(schema)
        assert out.measures[0].table == "_Measures"

    def test_renames_host_table_with_no_table_def(self):
        """A disconnected measures table often has no ModelTable entry — catch it."""
        schema = ModelSchema(
            tables=[ModelTable(name="Sales", columns=[ModelColumn(name="Amt")])],
            measures=[
                ModelMeasure(name="Total Revenue", table="Measures",
                             expression="SUM(Sales[Amt])", return_type="currency"),
            ],
            relationships=[],
        )
        out = sanitize_schema(schema)
        assert out.measures[0].table == "_Measures"

    def test_renames_relationship_endpoints(self):
        schema = ModelSchema(
            tables=[
                ModelTable(name="Measures", columns=[ModelColumn(name="Key")]),
                ModelTable(name="Sales", columns=[ModelColumn(name="Key")]),
            ],
            measures=[],
            relationships=[
                ModelRelationship(from_table="Sales", from_column="Key",
                                  to_table="Measures", to_column="Key"),
            ],
        )
        out = sanitize_schema(schema)
        assert out.relationships[0].to_table == "_Measures"
        assert out.relationships[0].from_table == "Sales"

    def test_no_reserved_names_returns_equivalent_schema(self):
        schema = ModelSchema(
            tables=[ModelTable(name="Sales", columns=[ModelColumn(name="Amt")])],
            measures=[
                ModelMeasure(name="Total Revenue", table="Sales",
                             expression="SUM(Sales[Amt])", return_type="currency"),
            ],
            relationships=[],
        )
        out = sanitize_schema(schema)
        assert out == schema

    def test_visual_and_tmdl_stay_consistent(self):
        """Both the host table on the measure and the table def get the same
        rewritten name, so visual.json (m.table) and TMDL agree."""
        schema = ModelSchema(
            tables=[ModelTable(name="Measures", columns=[])],
            measures=[
                ModelMeasure(name="KPI", table="Measures",
                             expression="1", return_type="number"),
            ],
            relationships=[],
        )
        out = sanitize_schema(schema)
        table_names = {t.name for t in out.tables}
        assert out.measures[0].table in table_names


# A faithful copy of a Power BI MCP-authored disconnected measures table —
# the exact shape that triggers the "reserved string 'Measures'" load failure.
_MEASURES_TMDL = """table Measures
\tlineageTag: 04065887-101d-4df0-9b24-5d5b2c5b632b
\tisHidden

\tcolumn Dummy
\t\tdataType: string
\t\tlineageTag: 6fa77135-c653-490c-9239-958337004bcf
\t\tsummarizeBy: none
\t\tisHidden
\t\tsourceColumn: Dummy

\tmeasure 'Real GDP' = CALCULATE(SUM(WEO_Long[Value]), WEO_Long[INDICATOR.ID] = "NGDP_RPCH")
\t\tlineageTag: d2f27143-f93e-42ed-b4cf-fad799e8c238
\t\tformatString: #,##0.0

\tpartition Measures = calculated
\t\tmode: import
\t\tsource = DATATABLE("Dummy", STRING, {{""}})
"""

_MODEL_TMDL = """model Model
\tculture: en-US

annotation PBI_QueryOrder = ["Countries","WEO_Long","Year","Measures"]

ref table Countries
ref table WEO_Long
ref table Year
ref table Measures

ref cultureInfo en-US
"""


def _scaffold_model_with_measures_table(tmp_path):
    tables = tmp_path / "definition" / "tables"
    tables.mkdir(parents=True)
    (tables / "Measures.tmdl").write_text(_MEASURES_TMDL, encoding="utf-8")
    (tables / "WEO_Long.tmdl").write_text("table WEO_Long\n\tlineageTag: x\n", encoding="utf-8")
    (tmp_path / "definition" / "model.tmdl").write_text(_MODEL_TMDL, encoding="utf-8")
    return tmp_path


class TestSanitizeSemanticModelDir:
    def test_detects_reserved_table(self, tmp_path):
        sm = _scaffold_model_with_measures_table(tmp_path)
        assert reserved_table_renames(sm) == {"Measures": "_Measures"}

    def test_renames_file_and_header(self, tmp_path):
        sm = _scaffold_model_with_measures_table(tmp_path)
        sanitize_semantic_model_dir(sm)
        tables = sm / "definition" / "tables"
        assert not (tables / "Measures.tmdl").exists()
        content = (tables / "_Measures.tmdl").read_text(encoding="utf-8")
        assert content.startswith("table _Measures")
        assert "partition _Measures = calculated" in content
        # Measure expressions referencing other tables are untouched.
        assert "SUM(WEO_Long[Value])" in content

    def test_updates_model_tmdl_refs_and_annotations(self, tmp_path):
        sm = _scaffold_model_with_measures_table(tmp_path)
        sanitize_semantic_model_dir(sm)
        model = (sm / "definition" / "model.tmdl").read_text(encoding="utf-8")
        assert "ref table _Measures" in model
        assert "ref table Measures\n" not in model
        assert '"_Measures"' in model
        assert '"Measures"' not in model
        # Other tables are left alone.
        assert "ref table WEO_Long" in model

    def test_idempotent(self, tmp_path):
        sm = _scaffold_model_with_measures_table(tmp_path)
        sanitize_semantic_model_dir(sm)
        assert sanitize_semantic_model_dir(sm) == {}

    def test_no_reserved_tables_is_noop(self, tmp_path):
        tables = tmp_path / "definition" / "tables"
        tables.mkdir(parents=True)
        (tables / "Sales.tmdl").write_text("table Sales\n\tlineageTag: x\n", encoding="utf-8")
        (tmp_path / "definition" / "model.tmdl").write_text(
            "model Model\n\nref table Sales\n", encoding="utf-8"
        )
        assert sanitize_semantic_model_dir(tmp_path) == {}
        assert (tables / "Sales.tmdl").exists()

    def test_missing_tables_dir_is_safe(self, tmp_path):
        assert sanitize_semantic_model_dir(tmp_path) == {}
