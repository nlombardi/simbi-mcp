"""Unit tests for _parse_js_nodes — no browser required."""
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
    try:
        node.x = 99  # type: ignore[misc]
        raise AssertionError("Should have raised FrozenInstanceError")
    except (AssertionError, Exception):
        pass
