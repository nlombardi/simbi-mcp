"""Unit tests for reserved_names — guarding against AS reserved table names.

Power BI's Tabular engine rejects any table literally named "Measures"
(it collides with the implicit MDX Measures dimension). SimBI must rename
such tables consistently across the schema so the report's visual.json
bindings and the SemanticModel TMDL agree.
"""
import pytest

from simbi_mcp.pbir.reserved_names import safe_table_name, sanitize_schema
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
