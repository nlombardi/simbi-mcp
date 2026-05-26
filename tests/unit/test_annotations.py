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
