import pytest

from simbi_mcp.pbir.bookmarks import build_bookmark_json, resolve_targets
from simbi_mcp.types import Bookmark


def test_resolve_targets_maps_ids_to_guids():
    id_to_guid = {"chartBar": "guidBar", "chartLine": "guidLine"}
    b = Bookmark(name="V", captures={"visibility"}, target=["chartBar", "chartLine"],
                 visible=["chartBar"], hidden=["chartLine"])
    resolved = resolve_targets(b, id_to_guid)
    assert resolved.visible == ["guidBar"]
    assert resolved.hidden == ["guidLine"]
    assert resolved.target == ["guidBar", "guidLine"]


def test_resolve_targets_unknown_id_raises():
    b = Bookmark(name="V", captures={"visibility"}, visible=["ghost"])
    with pytest.raises(ValueError, match="ghost"):
        resolve_targets(b, {})


def test_build_bookmark_json_visibility():
    # bookmark already has GUIDs (post-resolve); visual_types maps guid->pbi visualType
    b = Bookmark(name="View: Bar", captures={"visibility"},
                 target=["guidBar", "guidLine"], visible=["guidBar"], hidden=["guidLine"])
    visual_types = {"guidBar": "clusteredColumnChart", "guidLine": "lineChart"}
    j = build_bookmark_json(b, page_guid="page1", visual_types=visual_types)
    assert j["displayName"] == "View: Bar"
    assert j["name"].startswith("Bookmark")
    assert j["options"]["targetVisualNames"] == ["guidBar", "guidLine"]
    assert j["options"]["suppressData"] is True          # data not captured
    assert j["options"]["suppressActiveSection"] is True  # currentPage not captured
    vcs = j["explorationState"]["sections"]["page1"]["visualContainers"]
    assert vcs["guidLine"]["singleVisual"]["display"] == {"mode": "hidden"}
    assert "display" not in vcs["guidBar"]["singleVisual"]
    assert vcs["guidBar"]["singleVisual"]["visualType"] == "clusteredColumnChart"
    assert j["explorationState"]["activeSection"] == "page1"


def test_bookmark_construction():
    b = Bookmark(
        name="View: Bar",
        captures={"visibility"},
        target=["chartBar", "chartLine"],
        visible=["chartBar"],
        hidden=["chartLine"],
    )
    assert b.name == "View: Bar"
    assert "visibility" in b.captures
    assert b.target == ["chartBar", "chartLine"]
    assert b.visible == ["chartBar"]
    assert b.hidden == ["chartLine"]


def test_bookmark_defaults():
    b = Bookmark(name="Empty")
    assert b.captures == set()
    assert b.target == []
    assert b.visible == []
    assert b.hidden == []


def test_collect_bookmarks_from_nodes():
    from simbi_mcp.pbir.emitter import collect_bookmarks
    from simbi_mcp.pbir.extractor import VisualNode
    nodes = [VisualNode(x=0, y=0, width=1, height=1, attrs={
        "data-pbi": "bookmark", "data-pbi-name": "View: Bar",
        "data-pbi-captures": "visibility",
        "data-pbi-visible": "chartBar", "data-pbi-hidden": "chartLine, chartTable",
    })]
    bms = collect_bookmarks(nodes)
    assert len(bms) == 1
    assert bms[0].name == "View: Bar"
    assert bms[0].captures == {"visibility"}
    assert bms[0].visible == ["chartBar"]
    assert bms[0].hidden == ["chartLine", "chartTable"]


def test_resolve_button_actions_rewrites_visuallink():
    from simbi_mcp.pbir.emitter import resolve_button_actions
    visuals = [{
        "name": "btnGuid",
        "simbiButtonAction": {"type": "bookmark", "bookmark": "View: Bar"},
        "visual": {"visualType": "actionButton"},
    }]
    name_to_guid = {"View: Bar": "Bookmarkabc123"}
    resolve_button_actions(visuals, name_to_guid)
    assert "simbiButtonAction" not in visuals[0]
    vlink = visuals[0]["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]
    assert vlink["bookmark"]["expr"]["Literal"]["Value"] == "'Bookmarkabc123'"
    assert vlink["type"]["expr"]["Literal"]["Value"] == "'Bookmark'"


def test_resolve_button_actions_nonbookmark_left_clean():
    from simbi_mcp.pbir.emitter import resolve_button_actions
    visuals = [{"name": "b", "simbiButtonAction": {"type": "blank"}, "visual": {"visualType": "actionButton"}}]
    resolve_button_actions(visuals, {})
    # non-bookmark actions: simbiButtonAction removed, no visualLink added
    assert "simbiButtonAction" not in visuals[0]
    assert "visualContainerObjects" not in visuals[0]["visual"]
