from pathlib import Path

from simbi_mcp.types import FieldParameter

from simbi_mcp.pbir.extractor import VisualNode
from simbi_mcp.pbir.field_param import build_field_param_tmdl
from simbi_mcp.pbir.semantic_patcher import patch_field_parameters
from simbi_mcp.pbir.templates import build_visual_json


def test_field_parameter_construction() -> None:
    fp = FieldParameter(
        name="Indicator",
        measures=["Real GDP", "CPI Inflation", "Current Account", "Fiscal Balance"],
    )
    assert fp.name == "Indicator"
    assert fp.measures[0] == "Real GDP"
    assert len(fp.measures) == 4


def test_build_field_param_tmdl_qualifies_nameof_by_table() -> None:
    fp = FieldParameter(name="Indicator", measures=["Real GDP", "CPI Inflation"])
    tmdl = build_field_param_tmdl(fp, {"Real GDP": "WEO_Data", "CPI Inflation": "WEO_Data"})
    assert "NAMEOF('WEO_Data'[Real GDP])" in tmdl
    assert "NAMEOF('WEO_Data'[CPI Inflation])" in tmdl
    assert "NAMEOF([Real GDP])" not in tmdl  # not the bare form


def test_build_field_param_tmdl_bare_fallback_when_no_mapping() -> None:
    fp = FieldParameter(name="Indicator", measures=["Real GDP"])
    tmdl = build_field_param_tmdl(fp)  # no mapping
    assert "NAMEOF([Real GDP])" in tmdl


def test_build_field_param_tmdl_has_three_columns_and_metadata() -> None:
    fp = FieldParameter(name="Indicator", measures=["Real GDP", "CPI Inflation"])
    tmdl = build_field_param_tmdl(fp)
    assert "table Indicator" in tmdl
    assert "NAMEOF([Real GDP])" in tmdl
    assert "NAMEOF([CPI Inflation])" in tmdl
    assert tmdl.index("Real GDP") < tmdl.index("CPI Inflation")
    assert "column Indicator\n" in tmdl
    assert "column 'Indicator Fields'" in tmdl
    assert "column 'Indicator Order'" in tmdl
    assert 'extendedProperty ParameterMetadata' in tmdl
    assert '"version": 3' in tmdl and '"kind": 2' in tmdl
    assert "sourceColumn: [Value1]" in tmdl
    assert "sourceColumn: [Value2]" in tmdl
    assert "sourceColumn: [Value3]" in tmdl
    assert "relatedColumnDetails" in tmdl
    assert "groupByColumn: 'Indicator Fields'" in tmdl
    assert "annotation SummarizationSetBy = Automatic" in tmdl
    assert "annotation PBI_Id =" in tmdl
    assert "partition Indicator = calculated" in tmdl


def test_build_field_param_tmdl_unique_lineage_tags() -> None:
    fp = FieldParameter(name="Indicator", measures=["Real GDP"])
    tmdl = build_field_param_tmdl(fp)
    import re
    tags = re.findall(r"lineageTag: ([0-9a-f-]{36})", tmdl)
    assert len(tags) == len(set(tags)) >= 4


def test_build_field_param_tmdl_quotes_multiword_name() -> None:
    # Same header-quoting rule as tables/columns: a multi-word field-param
    # name must be quoted in `table`/`column`/`partition` headers or Power BI
    # Desktop fails to parse it ("invalid token" after the object name).
    fp = FieldParameter(name="Key Indicator", measures=["Real GDP"])
    tmdl = build_field_param_tmdl(fp)
    assert "table 'Key Indicator'" in tmdl
    assert "table Key Indicator\n" not in tmdl
    assert "column 'Key Indicator'\n" in tmdl
    assert "column Key Indicator\n" not in tmdl
    assert "partition 'Key Indicator' = calculated" in tmdl
    assert "partition Key Indicator = calculated" not in tmdl
    # The already-space-bearing '<n> Fields'/'<n> Order' columns still work.
    assert "column 'Key Indicator Fields'" in tmdl
    assert "column 'Key Indicator Order'" in tmdl


def test_patch_field_parameters_creates_tmdl_and_ref(tmp_path: Path) -> None:
    tables = tmp_path / "definition" / "tables"
    tables.mkdir(parents=True)
    model = tmp_path / "definition" / "model.tmdl"
    model.write_text("model Model\n", encoding="utf-8")

    fp = FieldParameter(name="Indicator", measures=["Real GDP", "CPI Inflation"])
    patch_field_parameters([fp], tmp_path)

    tmdl = (tables / "Indicator.tmdl").read_text(encoding="utf-8")
    assert "NAMEOF([Real GDP])" in tmdl
    assert "ref table Indicator" in model.read_text(encoding="utf-8")


def test_patch_field_parameters_quotes_multiword_ref(tmp_path: Path) -> None:
    tables = tmp_path / "definition" / "tables"
    tables.mkdir(parents=True)
    model = tmp_path / "definition" / "model.tmdl"
    model.write_text("model Model\n", encoding="utf-8")

    fp = FieldParameter(name="Key Indicator", measures=["Real GDP"])
    patch_field_parameters([fp], tmp_path)

    assert "ref table 'Key Indicator'" in model.read_text(encoding="utf-8")


def test_patch_field_parameters_idempotent(tmp_path: Path) -> None:
    tables = tmp_path / "definition" / "tables"
    tables.mkdir(parents=True)
    model = tmp_path / "definition" / "model.tmdl"
    model.write_text("model Model\n", encoding="utf-8")
    fp = FieldParameter(name="Indicator", measures=["Real GDP"])
    patch_field_parameters([fp], tmp_path)
    patch_field_parameters([fp], tmp_path)
    assert model.read_text(encoding="utf-8").count("ref table Indicator") == 1


def test_patch_field_parameters_overwrites_stale_table(tmp_path: Path) -> None:
    # A re-emit must regenerate the SimBI-owned table so a corrected definition
    # (e.g. table-qualified NAMEOF) replaces a stale one, not get skipped.
    tables = tmp_path / "definition" / "tables"
    tables.mkdir(parents=True)
    (tmp_path / "definition" / "model.tmdl").write_text("model Model\n", encoding="utf-8")
    fp = FieldParameter(name="Indicator", measures=["GDP Growth"])

    # First emit with NO mapping -> bare NAMEOF
    patch_field_parameters([fp], tmp_path)
    assert "NAMEOF([GDP Growth])" in (tables / "Indicator.tmdl").read_text(encoding="utf-8")

    # Re-emit WITH mapping -> must overwrite to the qualified form
    patch_field_parameters([fp], tmp_path, {"GDP Growth": "WEO_Data"})
    text = (tables / "Indicator.tmdl").read_text(encoding="utf-8")
    assert "NAMEOF('WEO_Data'[GDP Growth])" in text
    assert "NAMEOF([GDP Growth])" not in text


def test_chart_field_param_y_has_measure_and_fieldparameters(schema):
    from simbi_mcp.pbir.extractor import VisualNode
    node = VisualNode(x=0, y=0, width=400, height=300, attrs={
        "data-pbi": "clusteredColumnChart", "data-pbi-axis": "sales[Region]",
        "data-pbi-values-param": "Indicator", "data-pbi-series": "sales[Region]"})
    # schema fixture has measures "Total Revenue", "Order Count" on table "sales"
    fps = {"Indicator": ["Total Revenue", "Order Count"]}
    result = build_visual_json(node, z_order=0, schema=schema, field_params=fps)
    y = result["visual"]["query"]["queryState"]["Y"]
    # default measure projection
    assert y["projections"][0]["field"]["Measure"]["Property"] == "Total Revenue"
    assert y["projections"][0]["displayName"] == "Total Revenue"
    # fieldParameters array referencing Indicator[Indicator]
    fp = y["fieldParameters"][0]
    assert fp["parameterExpr"]["Column"]["Property"] == "Indicator"
    assert fp["parameterExpr"]["Column"]["Expression"]["SourceRef"]["Entity"] == "Indicator"
    assert fp["index"] == 0 and fp["length"] == 1


def test_chart_values_param_without_definition_raises(schema):
    from simbi_mcp.pbir.extractor import VisualNode
    node = VisualNode(x=0, y=0, width=400, height=300, attrs={
        "data-pbi": "clusteredColumnChart", "data-pbi-axis": "sales[Region]",
        "data-pbi-values-param": "Missing", "data-pbi-series": "sales[Region]"})
    import pytest
    with pytest.raises(ValueError, match="Missing"):
        build_visual_json(node, z_order=0, schema=schema, field_params={})


def test_field_param_emits_bound_slicer(schema):
    node = VisualNode(
        x=0, y=0, width=400, height=44,
        attrs={
            "data-pbi": "field-param",
            "data-pbi-param-name": "Indicator",
            "data-pbi-measures": "Real GDP, CPI Inflation",
            "data-pbi-style": "tabs",
        },
    )
    result = build_visual_json(node, z_order=0, schema=schema)
    assert result["visual"]["visualType"] == "slicer"
    proj = result["visual"]["query"]["queryState"]["Values"]["projections"][0]
    assert proj["field"]["Column"]["Property"] == "Indicator"
    assert proj["field"]["Column"]["Expression"]["SourceRef"]["Entity"] == "Indicator"
    # single-select slicer with a categorical filter
    assert result["filterConfig"]["filters"][0]["type"] == "Categorical"


from simbi_mcp.mockup.validator import validate_mockup, ValidationError
import pytest


def test_validator_allows_values_param_without_values(schema):
    # A clustered chart that uses data-pbi-values-param must NOT require data-pbi-values.
    html = (
        '<div data-pbi="clusteredColumnChart" data-pbi-axis="sales[Region]" '
        'data-pbi-values-param="Indicator" data-pbi-series="sales[Region]"></div>'
    )
    validate_mockup(html, schema)  # must not raise


def test_collect_field_params_from_nodes():
    from simbi_mcp.pbir.emitter import collect_field_params
    from simbi_mcp.pbir.extractor import VisualNode
    nodes = [
        VisualNode(x=0, y=0, width=1, height=1, attrs={
            "data-pbi": "field-param",
            "data-pbi-param-name": "Indicator",
            "data-pbi-measures": "Real GDP, CPI Inflation",
        }),
        VisualNode(x=0, y=0, width=1, height=1, attrs={
            "data-pbi": "card", "data-pbi-measure": "Total Revenue",
        }),
    ]
    fps = collect_field_params(nodes)
    assert len(fps) == 1
    assert fps[0].name == "Indicator"
    assert fps[0].measures == ["Real GDP", "CPI Inflation"]


def test_resolve_semantic_model_dir_is_report_relative(tmp_path):
    from simbi_mcp.pbir.emitter import _resolve_semantic_model_dir
    out = tmp_path / "Macro_Dash"
    got = _resolve_semantic_model_dir(out, "MacroDashboard", None)
    # Must resolve INSIDE Macro_Dash (sibling of the .Report folder), not above it.
    assert got == (out / "MacroDashboard.SemanticModel").resolve()


def test_resolve_semantic_model_dir_honors_explicit_rel(tmp_path):
    from simbi_mcp.pbir.emitter import _resolve_semantic_model_dir
    out = tmp_path / "proj"
    got = _resolve_semantic_model_dir(out, "Rep", "../Custom.SemanticModel")
    assert got == (out / "Custom.SemanticModel").resolve()


def test_validator_accepts_field_param_node(schema):
    html = (
        '<div data-pbi="field-param" data-pbi-param-name="Indicator" '
        'data-pbi-measures="Total Revenue, Order Count"></div>'
    )
    validate_mockup(html, schema)  # must not raise


def test_field_param_slicer_header_off(schema):
    from simbi_mcp.pbir.extractor import VisualNode
    node = VisualNode(x=0, y=0, width=400, height=44, attrs={
        "data-pbi": "field-param", "data-pbi-param-name": "Indicator",
        "data-pbi-measures": "Total Revenue, Order Count"})
    r = build_visual_json(node, z_order=0, schema=schema)
    assert r["visual"]["objects"]["header"][0]["properties"]["show"] == {"expr": {"Literal": {"Value": "false"}}}
