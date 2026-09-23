"""Unit tests for _parse_js_nodes — no browser required."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from simbi_mcp.mockup.annotations import VisualType
from simbi_mcp.pbir.extractor import VisualNode, _parse_js_nodes


def test_parse_js_nodes_basic() -> None:
    raw = [
        {
            "x": 24,
            "y": 24,
            "width": 400,
            "height": 104,
            "data": {"data-pbi": "card", "data-pbi-measure": "Total Revenue"},
        }
    ]
    nodes = _parse_js_nodes(raw)
    assert len(nodes) == 1
    assert nodes[0].x == 24.0
    assert nodes[0].y == 24.0
    assert nodes[0].width == 400.0
    assert nodes[0].height == 104.0
    assert nodes[0].attrs["data-pbi-measure"] == "Total Revenue"


def test_parse_js_nodes_visual_type() -> None:
    raw = [{"x": 0, "y": 0, "width": 100, "height": 100, "data": {"data-pbi": "columnChart"}}]
    nodes = _parse_js_nodes(raw)
    assert nodes[0].visual_type == VisualType.COLUMN_CHART


def test_parse_js_nodes_multiple() -> None:
    raw = [
        {
            "x": 24,
            "y": 24,
            "width": 400,
            "height": 104,
            "data": {"data-pbi": "card", "data-pbi-measure": "M1"},
        },
        {
            "x": 440,
            "y": 24,
            "width": 400,
            "height": 104,
            "data": {"data-pbi": "card", "data-pbi-measure": "M2"},
        },
    ]
    nodes = _parse_js_nodes(raw)
    assert len(nodes) == 2
    assert nodes[0].attrs["data-pbi-measure"] == "M1"
    assert nodes[1].attrs["data-pbi-measure"] == "M2"


def test_parse_js_nodes_float_coords() -> None:
    raw = [{"x": 24.5, "y": 100.7, "width": 400.0, "height": 200.3, "data": {"data-pbi": "card"}}]
    nodes = _parse_js_nodes(raw)
    assert nodes[0].x == 24.5
    assert nodes[0].y == 100.7


def test_parse_js_nodes_all_attrs_preserved() -> None:
    raw = [
        {
            "x": 0,
            "y": 0,
            "width": 100,
            "height": 100,
            "data": {
                "data-pbi": "columnChart",
                "data-pbi-axis": "sales[Region]",
                "data-pbi-values": "Total Revenue",
            },
        }
    ]
    nodes = _parse_js_nodes(raw)
    assert nodes[0].attrs["data-pbi-axis"] == "sales[Region]"
    assert nodes[0].attrs["data-pbi-values"] == "Total Revenue"


def test_visual_node_is_frozen() -> None:
    node = VisualNode(x=0, y=0, width=100, height=100, attrs={"data-pbi": "card"})
    with pytest.raises(FrozenInstanceError):
        node.x = 99  # type: ignore[misc]


def test_parse_js_nodes_invalid_visual_type_raises_on_access() -> None:
    # decompositionTree is permanently out-of-scope (AI service-only per roadmap),
    # so it stays a safe "definitely unknown" placeholder.
    raw = [{"x": 0, "y": 0, "width": 100, "height": 100, "data": {"data-pbi": "decompositionTree"}}]
    nodes = _parse_js_nodes(raw)
    with pytest.raises(ValueError, match="decompositionTree"):
        _ = nodes[0].visual_type


from simbi_mcp.pbir.extractor import ExtractResult, _safe_filename


def test_parse_js_nodes_carries_styles() -> None:
    raw = [{
        "x": 0, "y": 0, "width": 100, "height": 100,
        "data": {"data-pbi": "card", "data-pbi-measure": "M"},
        "styles": {"backgroundColor": "rgb(255, 255, 255)", "boxShadow": "none"},
        "page_background": "rgb(241, 245, 249)",
    }]
    nodes = _parse_js_nodes(raw)
    assert nodes[0].styles["backgroundColor"] == "rgb(255, 255, 255)"
    assert nodes[0].page_background == "rgb(241, 245, 249)"


def test_parse_js_nodes_defaults_without_styles() -> None:
    raw = [{"x": 0, "y": 0, "width": 100, "height": 100, "data": {"data-pbi": "card"}}]
    nodes = _parse_js_nodes(raw)
    assert nodes[0].styles == {}
    assert nodes[0].page_background == ""


def test_safe_filename() -> None:
    assert _safe_filename("Overview") == "Overview"
    # NOTE: brief's expected literal ("P_a_g_e __1_", 12 chars) is unreachable from
    # an 11-char input via a 1-char-in/1-char-out regex substitution; corrected to
    # match the verbatim `re.sub(r'[^\w\- ]', "_", name)` implementation's actual output.
    assert _safe_filename('P/a:g*e "1"') == "P_a_g_e _1_"


def test_extract_result_shape() -> None:
    r = ExtractResult(nodes=[], previews=[], warnings=[])
    assert r.nodes == [] and r.previews == [] and r.warnings == []


def test_js_extract_scopes_page_containers() -> None:
    from simbi_mcp.pbir.extractor import _JS_EXTRACT
    assert "[data-pbi-page]:not([data-pbi])" in _JS_EXTRACT
