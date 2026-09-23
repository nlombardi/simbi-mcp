"""End-to-end composition test for the view-toggle pattern.

Exercises the full primitive stack — stacked charts with stable ids, visibility
bookmarks, and buttons — through the same building blocks emit_pbir uses, without
launching a browser.
"""
from __future__ import annotations

from simbi_mcp.pbir.bookmarks import build_bookmark_json, resolve_targets
from simbi_mcp.pbir.emitter import collect_bookmarks, resolve_button_actions
from simbi_mcp.pbir.extractor import VisualNode
from simbi_mcp.pbir.templates import build_visual_json


# Three charts stacked at the same x/y, each with a stable id.
_POS = dict(x=48, y=216, width=1184, height=462)


def _chart(pbi_type: str, vid: str) -> VisualNode:
    return VisualNode(**_POS, attrs={
        "data-pbi": pbi_type,
        "data-pbi-axis": "sales[Region]",
        "data-pbi-values": "Total Revenue",
        "data-pbi-id": vid,
        **({"data-pbi-series": "sales[Region]"} if pbi_type == "clusteredColumnChart" else {}),
    })


def _bookmark_node(name: str, visible: str, hidden: str) -> VisualNode:
    return VisualNode(x=0, y=0, width=1, height=1, attrs={
        "data-pbi": "bookmark", "data-pbi-name": name,
        "data-pbi-captures": "visibility",
        "data-pbi-visible": visible, "data-pbi-hidden": hidden,
    })


def _button_node(text: str, bookmark: str) -> VisualNode:
    return VisualNode(x=0, y=0, width=100, height=36, attrs={
        "data-pbi": "button", "data-pbi-action": "bookmark",
        "data-pbi-bookmark": bookmark, "data-pbi-text": text,
    })


def test_view_toggle_composition(schema):
    chart_nodes = [
        _chart("clusteredColumnChart", "chartBar"),
        _chart("lineChart", "chartLine"),
        _chart("table", "chartTable"),
    ]
    # table needs columns, not axis/values — adjust that one node
    chart_nodes[2] = VisualNode(**_POS, attrs={
        "data-pbi": "table", "data-pbi-columns": "sales[Region],Total Revenue",
        "data-pbi-id": "chartTable",
    })
    bookmark_nodes = [
        _bookmark_node("View: Bar", "chartBar", "chartLine, chartTable"),
        _bookmark_node("View: Line", "chartLine", "chartBar, chartTable"),
        _bookmark_node("View: Table", "chartTable", "chartBar, chartLine"),
    ]
    button_nodes = [
        _button_node("Bar", "View: Bar"),
        _button_node("Line", "View: Line"),
        _button_node("Table", "View: Table"),
    ]
    all_nodes = chart_nodes + bookmark_nodes + button_nodes

    # Mirror emit_pbir: bookmark nodes are NOT built as visuals.
    visual_nodes = [n for n in all_nodes if n.attrs.get("data-pbi") != "bookmark"]
    visuals = [build_visual_json(n, z_order=i * 1000, schema=schema) for i, n in enumerate(visual_nodes)]

    # (a) all three charts emit at the same x/y
    chart_positions = [
        (v["position"]["x"], v["position"]["y"])
        for v in visuals
        if v.get("simbiId", "").startswith("chart")
    ]
    assert len(chart_positions) == 3
    assert len(set(chart_positions)) == 1  # stacked

    # Build bookmarks like emit_pbir does
    bookmarks_meta = collect_bookmarks(all_nodes)
    assert len(bookmarks_meta) == 3
    page_guid = "pageGuidTest"
    id_to_guid = {v["simbiId"]: v["name"] for v in visuals if "simbiId" in v}
    visual_types = {v["name"]: v["visual"]["visualType"] for v in visuals}

    bookmark_dicts = []
    name_to_guid = {}
    for bm in bookmarks_meta:
        resolved = resolve_targets(bm, id_to_guid)
        bj = build_bookmark_json(resolved, page_guid, visual_types)
        name_to_guid[bm.name] = bj["name"]
        bookmark_dicts.append(bj)

    # (b) three bookmark dicts produced
    assert len(bookmark_dicts) == 3

    # (c) each bookmark shows exactly one chart visible, two hidden
    for bj in bookmark_dicts:
        vcs = bj["explorationState"]["sections"][page_guid]["visualContainers"]
        hidden = [g for g, c in vcs.items() if c["singleVisual"].get("display", {}).get("mode") == "hidden"]
        visible = [g for g, c in vcs.items() if "display" not in c["singleVisual"]]
        assert len(visible) == 1
        assert len(hidden) == 2

    # (d) each button resolves to a distinct bookmark guid via visualContainerObjects.visualLink
    resolve_button_actions(visuals, name_to_guid)
    button_links = []
    for v in visuals:
        vco = v["visual"].get("visualContainerObjects", {})
        if "visualLink" in vco:
            button_links.append(vco["visualLink"][0]["properties"]["bookmark"]["expr"]["Literal"]["Value"])
    assert len(button_links) == 3
    assert len(set(button_links)) == 3  # three distinct bookmark ids
