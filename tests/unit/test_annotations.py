"""Tests for annotation spec constants."""
from simbi_mcp.mockup.annotations import (
    ANNOTATION_SPEC_TEXT,
    CSS_CLASS_CATALOG,
    VISUAL_ATTRS,
    VisualType,
)


def test_visual_type_values() -> None:
    assert VisualType.CARD.value == "card"
    assert VisualType.COLUMN_CHART.value == "columnChart"
    assert VisualType.LINE_CHART.value == "lineChart"
    assert VisualType.SLICER.value == "slicer"
    assert VisualType.TABLE.value == "table"
    assert VisualType.CLUSTERED_COLUMN_CHART.value == "clusteredColumnChart"
    assert VisualType.CLUSTERED_BAR_CHART.value == "clusteredBarChart"
    assert VisualType.HUNDRED_PERCENT_STACKED_BAR_CHART.value == "hundredPercentStackedBarChart"
    assert VisualType.HUNDRED_PERCENT_STACKED_COLUMN_CHART.value == "hundredPercentStackedColumnChart"
    assert VisualType.AREA_CHART.value == "areaChart"
    assert VisualType.PIE_CHART.value == "pieChart"
    assert VisualType.DONUT_CHART.value == "donutChart"


def test_visual_attrs_has_all_types() -> None:
    for vt in VisualType:
        assert vt in VISUAL_ATTRS, f"Missing VISUAL_ATTRS entry for {vt}"
        assert "required" in VISUAL_ATTRS[vt]
        assert "optional" in VISUAL_ATTRS[vt]


def test_card_requires_measure() -> None:
    assert "data-pbi-measure" in VISUAL_ATTRS[VisualType.CARD]["required"]


def test_column_chart_requires_axis_and_values() -> None:
    required = VISUAL_ATTRS[VisualType.COLUMN_CHART]["required"]
    assert "data-pbi-axis" in required
    assert "data-pbi-values" in required


def test_column_chart_series_is_optional() -> None:
    attrs = VISUAL_ATTRS[VisualType.COLUMN_CHART]
    assert "data-pbi-series" in attrs["optional"]
    assert "data-pbi-series" not in attrs["required"]


def test_bar_chart_series_is_optional() -> None:
    attrs = VISUAL_ATTRS[VisualType.BAR_CHART]
    assert "data-pbi-series" in attrs["optional"]
    assert "data-pbi-series" not in attrs["required"]


def test_clustered_column_chart_requires_axis_values_and_series() -> None:
    required = VISUAL_ATTRS[VisualType.CLUSTERED_COLUMN_CHART]["required"]
    assert "data-pbi-axis" in required
    assert "data-pbi-values" in required
    assert "data-pbi-series" in required


def test_clustered_bar_chart_requires_axis_values_and_series() -> None:
    required = VISUAL_ATTRS[VisualType.CLUSTERED_BAR_CHART]["required"]
    assert "data-pbi-axis" in required
    assert "data-pbi-values" in required
    assert "data-pbi-series" in required


def test_hundred_percent_stacked_bar_chart_requires_axis_values_and_series() -> None:
    required = VISUAL_ATTRS[VisualType.HUNDRED_PERCENT_STACKED_BAR_CHART]["required"]
    assert "data-pbi-axis" in required
    assert "data-pbi-values" in required
    assert "data-pbi-series" in required


def test_hundred_percent_stacked_column_chart_requires_axis_values_and_series() -> None:
    required = VISUAL_ATTRS[VisualType.HUNDRED_PERCENT_STACKED_COLUMN_CHART]["required"]
    assert "data-pbi-axis" in required
    assert "data-pbi-values" in required
    assert "data-pbi-series" in required


def test_area_chart_requires_axis_and_values() -> None:
    required = VISUAL_ATTRS[VisualType.AREA_CHART]["required"]
    assert "data-pbi-axis" in required
    assert "data-pbi-values" in required


def test_pie_chart_requires_axis_and_values() -> None:
    required = VISUAL_ATTRS[VisualType.PIE_CHART]["required"]
    assert "data-pbi-axis" in required
    assert "data-pbi-values" in required


def test_donut_chart_requires_axis_and_values() -> None:
    required = VISUAL_ATTRS[VisualType.DONUT_CHART]["required"]
    assert "data-pbi-axis" in required
    assert "data-pbi-values" in required


def test_line_chart_series_is_optional() -> None:
    attrs = VISUAL_ATTRS[VisualType.LINE_CHART]
    assert "data-pbi-series" in attrs["optional"]
    assert "data-pbi-series" not in attrs["required"]


def test_area_chart_series_is_optional() -> None:
    attrs = VISUAL_ATTRS[VisualType.AREA_CHART]
    assert "data-pbi-series" in attrs["optional"]
    assert "data-pbi-series" not in attrs["required"]


def test_slicer_requires_field() -> None:
    assert "data-pbi-field" in VISUAL_ATTRS[VisualType.SLICER]["required"]


def test_annotation_spec_text_mentions_all_types() -> None:
    for vt in VisualType:
        assert vt.value in ANNOTATION_SPEC_TEXT, f"Missing {vt.value} in ANNOTATION_SPEC_TEXT"


def test_css_class_catalog_mentions_core_classes() -> None:
    for cls in ("db-page", "db-grid", "db-card", "db-chart-area", "db-slicer-items"):
        assert cls in CSS_CLASS_CATALOG, f"Missing {cls} in CSS_CLASS_CATALOG"


from simbi_mcp.mockup.annotations import EXAMPLES, UNIVERSAL_ATTRS


def test_visual_attrs_values_are_described_dicts() -> None:
    for vtype, spec in VISUAL_ATTRS.items():
        assert isinstance(spec["required"], dict), f"{vtype}: required must be a dict"
        assert isinstance(spec["optional"], dict), f"{vtype}: optional must be a dict"
        assert isinstance(spec["note"], str), f"{vtype}: note must be a str"
        for attr, desc in {**spec["required"], **spec["optional"]}.items():
            assert attr.startswith("data-pbi-"), f"{vtype}: bad attr name {attr}"
            assert desc.strip(), f"{vtype}: {attr} has an empty description"


def test_universal_attrs_not_duplicated_per_type() -> None:
    assert set(UNIVERSAL_ATTRS) == {"data-pbi-id", "data-pbi-hidden"}
    for vtype, spec in VISUAL_ATTRS.items():
        if vtype is VisualType.BOOKMARK:
            continue  # bookmark's data-pbi-hidden is an id list, deliberately shadows
        for attr in UNIVERSAL_ATTRS:
            assert attr not in spec["required"], f"{vtype} duplicates universal {attr}"
            assert attr not in spec["optional"], f"{vtype} duplicates universal {attr}"


def test_bar_column_notes_present() -> None:
    assert "HORIZONTAL" in VISUAL_ATTRS[VisualType.BAR_CHART]["note"]
    assert "columnChart" in VISUAL_ATTRS[VisualType.BAR_CHART]["note"]
    assert "VERTICAL" in VISUAL_ATTRS[VisualType.COLUMN_CHART]["note"]


def test_every_type_has_an_example() -> None:
    assert set(EXAMPLES) == set(VisualType)


def test_chart_examples_show_data_pbi_id() -> None:
    assert "data-pbi-id" in EXAMPLES[VisualType.LINE_CHART]
    assert "data-pbi-id" in EXAMPLES[VisualType.BAR_CHART]
