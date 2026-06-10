from simbi_mcp.mockup.annotations import VisualType
from simbi_mcp.pbir.templates import build_visual_json
from simbi_mcp.pbir.extractor import VisualNode


def test_shape_emits_modern_shape(schema):
    node = VisualNode(x=0, y=0, width=1280, height=64, attrs={
        "data-pbi": "shape", "data-pbi-shape": "rectangle"})
    r = build_visual_json(node, z_order=0, schema=schema)
    assert r["visual"]["visualType"] == "shape"
    assert "query" not in r["visual"]
    tile = r["visual"]["objects"]["shape"][0]["properties"]["tileShape"]
    assert tile == {"expr": {"Literal": {"Value": "'rectangle'"}}}


def test_text_emits_textbox_with_text(schema):
    node = VisualNode(x=0, y=0, width=400, height=40, attrs={
        "data-pbi": "text", "data-pbi-text": "GDP, % Change", "data-pbi-role": "title"})
    r = build_visual_json(node, z_order=0, schema=schema)
    assert r["visual"]["visualType"] == "textbox"
    assert "query" not in r["visual"]
    run = r["visual"]["objects"]["general"][0]["properties"]["paragraphs"][0]["textRuns"][0]
    assert run["value"] == "GDP, % Change"


def test_shape_default_is_rectangle(schema):
    node = VisualNode(x=0, y=0, width=10, height=10, attrs={"data-pbi": "shape"})
    r = build_visual_json(node, z_order=0, schema=schema)
    assert r["visual"]["objects"]["shape"][0]["properties"]["tileShape"]["expr"]["Literal"]["Value"] == "'rectangle'"


def test_button_emits_action_button(schema):
    node = VisualNode(x=0, y=0, width=120, height=36, attrs={
        "data-pbi": "button", "data-pbi-text": "Bar Chart",
        "data-pbi-action": "bookmark", "data-pbi-bookmark": "View: Bar"})
    r = build_visual_json(node, z_order=0, schema=schema)
    assert r["visual"]["visualType"] == "actionButton"
    assert "query" not in r["visual"]
    # button label
    text_objs = r["visual"]["objects"]["text"]
    label = next(p["properties"]["text"]["expr"]["Literal"]["Value"]
                 for p in text_objs if "text" in p.get("properties", {}))
    assert label == "'Bar Chart'"
    # action intent stashed for later bookmark-guid resolution; NOT yet a visualLink
    assert r["simbiButtonAction"] == {"type": "bookmark", "bookmark": "View: Bar"}
    assert "visualContainerObjects" not in r["visual"]


def test_button_blank_action(schema):
    node = VisualNode(x=0, y=0, width=80, height=30, attrs={
        "data-pbi": "button", "data-pbi-action": "blank", "data-pbi-text": "X"})
    r = build_visual_json(node, z_order=0, schema=schema)
    assert r["visual"]["visualType"] == "actionButton"
    assert r["simbiButtonAction"] == {"type": "blank"}


def test_theme_has_chrome_styles():
    import json
    from pathlib import Path
    from simbi_mcp.pbir import theme as theme_mod
    t = json.loads((Path(theme_mod.__file__).parent / "static" / "SimBIDefault.json").read_text(encoding="utf-8"))
    vs = t["visualStyles"]
    assert "actionButton" in vs
    assert "textbox" in vs
    assert "shape" in vs
    assert "basicShape" in vs


def test_text_title_role_sets_color(schema):
    node = VisualNode(x=0, y=0, width=400, height=40, attrs={
        "data-pbi": "text", "data-pbi-text": "GDP", "data-pbi-role": "title"})
    r = build_visual_json(node, z_order=0, schema=schema)
    run = r["visual"]["objects"]["general"][0]["properties"]["paragraphs"][0]["textRuns"][0]
    assert run["textStyle"]["color"] == "#003087"
    assert run["value"] == "GDP"


def test_text_no_role_has_no_textstyle(schema):
    node = VisualNode(x=0, y=0, width=400, height=40, attrs={
        "data-pbi": "text", "data-pbi-text": "Plain"})
    r = build_visual_json(node, z_order=0, schema=schema)
    run = r["visual"]["objects"]["general"][0]["properties"]["paragraphs"][0]["textRuns"][0]
    assert "textStyle" not in run


def test_text_color_override(schema):
    node = VisualNode(x=0, y=0, width=400, height=40, attrs={
        "data-pbi": "text", "data-pbi-text": "Title", "data-pbi-role": "title",
        "data-pbi-color": "#FFFFFF"})
    r = build_visual_json(node, z_order=0, schema=schema)
    run = r["visual"]["objects"]["general"][0]["properties"]["paragraphs"][0]["textRuns"][0]
    assert run["textStyle"]["color"] == "#FFFFFF"  # override beats role navy


def test_text_color_without_role(schema):
    node = VisualNode(x=0, y=0, width=400, height=40, attrs={
        "data-pbi": "text", "data-pbi-text": "X", "data-pbi-color": "#112233"})
    r = build_visual_json(node, z_order=0, schema=schema)
    run = r["visual"]["objects"]["general"][0]["properties"]["paragraphs"][0]["textRuns"][0]
    assert run["textStyle"]["color"] == "#112233"
