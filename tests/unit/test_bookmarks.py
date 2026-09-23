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


def test_build_bookmark_json_infers_targets_from_visible_hidden():
    # When target is not explicitly set, targetVisualNames is inferred from visible + hidden
    b = Bookmark(name="Toggle", captures={"visibility"}, visible=["guidA"], hidden=["guidB"])
    j = build_bookmark_json(b, page_guid="p1", visual_types={})
    assert j["options"]["applyOnlyToTargetVisuals"] is True
    assert j["options"]["targetVisualNames"] == ["guidA", "guidB"]


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
    }, page_name="Overview")]
    bms = collect_bookmarks(nodes)
    assert len(bms) == 1
    assert bms[0].name == "View: Bar"
    assert bms[0].captures == {"visibility"}
    assert bms[0].visible == ["chartBar"]
    assert bms[0].hidden == ["chartLine", "chartTable"]
    assert bms[0].page_name == "Overview"


def test_resolve_button_actions_rewrites_action_objects() -> None:
    from simbi_mcp.pbir.emitter import resolve_button_actions
    visuals: list[dict[str, Any]] = [{
        "name": "btnGuid",
        "simbiButtonAction": {"type": "bookmark", "bookmark": "View: Bar"},
        "visual": {"visualType": "actionButton"},
    }]
    name_to_guid = {"View: Bar": "Bookmarkabc123"}
    resolve_button_actions(visuals, name_to_guid)
    assert "simbiButtonAction" not in visuals[0]
    vis: dict[str, Any] = visuals[0]["visual"]
    action = vis["visualContainerObjects"]["visualLink"][0]["properties"]
    assert action["bookmark"]["expr"]["Literal"]["Value"] == "'Bookmarkabc123'"
    assert action["type"]["expr"]["Literal"]["Value"] == "'Bookmark'"
    assert action["show"]["expr"]["Literal"]["Value"] == "true"
    assert "action" not in vis.get("objects", {})


def test_resolve_button_actions_navigation() -> None:
    from simbi_mcp.pbir.emitter import resolve_button_actions
    visuals: list[dict[str, Any]] = [{
        "name": "btnNav",
        "simbiButtonAction": {"type": "navigate", "page": "Page 2"},
        "visual": {"visualType": "actionButton"},
    }]
    page_to_guid = {"Page 2": "guidPage2"}
    resolve_button_actions(visuals, page_name_to_guid=page_to_guid)
    assert "simbiButtonAction" not in visuals[0]
    vis: dict[str, Any] = visuals[0]["visual"]
    action = vis["visualContainerObjects"]["visualLink"][0]["properties"]
    assert action["show"]["expr"]["Literal"]["Value"] == "true"
    assert action["type"]["expr"]["Literal"]["Value"] == "'PageNavigation'"
    assert action["navigationSection"]["expr"]["Literal"]["Value"] == "'guidPage2'"


def test_resolve_button_actions_reset() -> None:
    from simbi_mcp.pbir.emitter import resolve_button_actions
    visuals: list[dict[str, Any]] = [{
        "name": "btnReset",
        "simbiButtonAction": {"type": "reset"},
        "visual": {"visualType": "actionButton"},
    }]
    resolve_button_actions(visuals)
    assert "simbiButtonAction" not in visuals[0]
    vis: dict[str, Any] = visuals[0]["visual"]
    action = vis["visualContainerObjects"]["visualLink"][0]["properties"]
    assert action["show"]["expr"]["Literal"]["Value"] == "true"
    assert action["type"]["expr"]["Literal"]["Value"] == "'ClearAllSlicers'"


def test_resolve_button_actions_nonbookmark_left_clean() -> None:
    from simbi_mcp.pbir.emitter import resolve_button_actions
    visuals: list[dict[str, Any]] = [
        {"name": "b", "simbiButtonAction": {"type": "blank"}, "visual": {"visualType": "actionButton"}}
    ]
    resolve_button_actions(visuals, {})
    # non-bookmark actions: simbiButtonAction removed, no action added
    assert "simbiButtonAction" not in visuals[0]
    vis: dict[str, Any] = visuals[0]["visual"]
    assert "visualLink" not in vis.get("visualContainerObjects", {})
    assert "action" not in vis.get("objects", {})


def test_multipage_bookmark_parent_page_scoping() -> None:
    from simbi_mcp.pbir.emitter import collect_bookmarks, build_bookmark_json, resolve_targets
    from simbi_mcp.pbir.extractor import VisualNode

    nodes = [
        VisualNode(x=0, y=0, width=10, height=10, attrs={"data-pbi": "bookmark", "data-pbi-name": "BM Page 1", "data-pbi-visible": "v1"}, page_name="Page 1"),
        VisualNode(x=0, y=0, width=10, height=10, attrs={"data-pbi": "bookmark", "data-pbi-name": "BM Page 2", "data-pbi-visible": "v2"}, page_name="Page 2"),
    ]
    bms = collect_bookmarks(nodes)
    id_to_guid = {"v1": "guid1", "v2": "guid2"}
    page_name_to_guid = {"Page 1": "guidP1", "Page 2": "guidP2"}
    visual_types = {"guid1": "card", "guid2": "lineChart"}

    bm1_resolved = resolve_targets(bms[0], id_to_guid)
    bj1 = build_bookmark_json(bm1_resolved, page_name_to_guid[bms[0].page_name], visual_types)
    assert bj1["explorationState"]["activeSection"] == "guidP1"
    assert "guidP1" in bj1["explorationState"]["sections"]

    bm2_resolved = resolve_targets(bms[1], id_to_guid)
    bj2 = build_bookmark_json(bm2_resolved, page_name_to_guid[bms[1].page_name], visual_types)
    assert bj2["explorationState"]["activeSection"] == "guidP2"
    assert "guidP2" in bj2["explorationState"]["sections"]
