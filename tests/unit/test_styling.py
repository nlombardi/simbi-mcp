"""Unit tests for CSS value parsing in pbir/styling.py — pure functions, no browser."""
from __future__ import annotations

from simbi_mcp.pbir.styling import (
    ShadowLayer,
    parse_css_color,
    parse_px,
    parse_shadow_layer,
    split_shadow_layers,
)


def test_parse_rgb() -> None:
    assert parse_css_color("rgb(241, 245, 249)") == ("#F1F5F9", 1.0)


def test_parse_rgba() -> None:
    hex_, alpha = parse_css_color("rgba(0, 0, 0, 0.1)")
    assert hex_ == "#000000"
    assert abs(alpha - 0.1) < 1e-9


def test_parse_transparent() -> None:
    assert parse_css_color("rgba(0, 0, 0, 0)") == ("#000000", 0.0)


def test_parse_hex_forms() -> None:
    assert parse_css_color("#1e3a8a") == ("#1E3A8A", 1.0)
    assert parse_css_color("#abc") == ("#AABBCC", 1.0)


def test_parse_garbage_returns_none() -> None:
    assert parse_css_color("linear-gradient(#fff, #000)") is None
    assert parse_css_color("") is None


def test_parse_px() -> None:
    assert parse_px("12px") == 12.0
    assert parse_px("0px") == 0.0
    assert parse_px("") == 0.0
    assert parse_px("auto") == 0.0


def test_split_shadow_layers_respects_parens() -> None:
    css = "rgba(0, 0, 0, 0.1) 0px 1px 3px 0px, rgba(0, 0, 0, 0.06) 0px 1px 2px 0px"
    layers = split_shadow_layers(css)
    assert len(layers) == 2
    assert "0.1" in layers[0] and "0.06" in layers[1]


def test_parse_shadow_layer() -> None:
    layer = parse_shadow_layer("rgba(0, 0, 0, 0.1) 0px 1px 3px 0px")
    assert layer == ShadowLayer(color_hex="#000000", alpha=0.1, x=0.0, y=1.0, blur=3.0, spread=0.0)


def test_parse_shadow_layer_no_spread() -> None:
    layer = parse_shadow_layer("rgb(30, 58, 138) 2px 4px 6px")
    assert layer is not None
    assert (layer.x, layer.y, layer.blur, layer.spread) == (2.0, 4.0, 6.0, 0.0)


def test_parse_shadow_layer_inset_returns_none() -> None:
    assert parse_shadow_layer("rgba(0, 0, 0, 0.1) 0px 1px 3px 0px inset") is None


def test_parse_px_malformed_numeral_returns_zero() -> None:
    assert parse_px("1.2.3px") == 0.0
    assert parse_px("..px") == 0.0
    assert parse_px("-.px") == 0.0


def test_parse_css_color_malformed_alpha_returns_none() -> None:
    assert parse_css_color("rgba(0, 0, 0, 1.2.3)") is None


def test_parse_shadow_layer_malformed_length_returns_none() -> None:
    # Malformed first token causes findall to extract fewer than 2 required lengths
    assert parse_shadow_layer("rgba(0, 0, 0, 0.1) 1.2.3px") is None


def test_parse_shadow_layer_negative_offset_and_spread() -> None:
    layer = parse_shadow_layer("rgba(0, 0, 0, 0.2) 0px 4px 6px -1px")
    assert layer is not None
    assert (layer.x, layer.y, layer.blur, layer.spread) == (0.0, 4.0, 6.0, -1.0)


import math

from simbi_mcp.pbir.styling import (
    container_objects_from_styles,
    literal,
    page_background_card,
    shape_objects_from_styles,
    solid,
)

_DB_CARD_STYLES = {
    "backgroundColor": "rgb(255, 255, 255)",
    "borderWidth": "0px",
    "borderStyle": "none",
    "borderColor": "rgb(0, 0, 0)",
    "borderRadius": "12px",
    "boxShadow": "rgba(0, 0, 0, 0.1) 0px 1px 3px 0px, rgba(0, 0, 0, 0.06) 0px 1px 2px 0px",
}


def test_container_background_emitted() -> None:
    vco, honored, _ = container_objects_from_styles({"backgroundColor": "rgb(255, 255, 255)"})
    props = vco["background"][0]["properties"]
    assert props["color"] == solid("#FFFFFF")
    assert props["show"] == literal("true")
    assert props["transparency"] == literal("0D")
    assert any("background" in h for h in honored)


def test_transparent_background_skipped() -> None:
    vco, honored, warnings = container_objects_from_styles({"backgroundColor": "rgba(0, 0, 0, 0)"})
    assert vco == {} and honored == [] and warnings == []


def test_visible_border_emitted() -> None:
    vco, _, _ = container_objects_from_styles({
        "borderWidth": "2px", "borderStyle": "solid",
        "borderColor": "rgb(30, 58, 138)", "borderRadius": "0px",
    })
    props = vco["border"][0]["properties"]
    assert props["show"] == literal("true")
    assert props["color"] == solid("#1E3A8A")
    assert props["width"] == literal("2D")
    assert "radius" not in props


def test_radius_without_border_uses_background_matching_border() -> None:
    vco, _, _ = container_objects_from_styles(_DB_CARD_STYLES)
    props = vco["border"][0]["properties"]
    assert props["show"] == literal("true")
    assert props["radius"] == literal("12D")
    assert props["width"] == literal("1D")
    assert props["color"] == solid("#FFFFFF")  # matches the background


def test_dropshadow_from_db_card() -> None:
    vco, honored, warnings = container_objects_from_styles(_DB_CARD_STYLES)
    props = vco["dropShadow"][0]["properties"]
    assert props["preset"] == literal("'Custom'")
    assert props["angle"] == literal("90D")          # atan2(1, 0) = 90° = downward
    assert props["shadowDistance"] == literal("1D")  # hypot(0, 1)
    assert props["shadowBlur"] == literal("3D")
    assert props["shadowSpread"] == literal("0D")
    assert props["transparency"] == literal("90D")   # alpha 0.1
    assert any("dropShadow" in h for h in honored)
    assert any("layers" in w for w in warnings)      # 2nd layer dropped


def test_shape_fill_from_css_background() -> None:
    objs, honored, _ = shape_objects_from_styles(
        {"backgroundColor": "rgb(30, 58, 138)"}, attrs={}
    )
    card = objs["fill"][0]
    assert card["properties"]["fillColor"] == solid("#1E3A8A")
    assert card["selector"] == {"id": "default"}
    assert any("fill" in h for h in honored)


def test_shape_fill_attr_beats_css() -> None:
    objs, _, _ = shape_objects_from_styles(
        {"backgroundColor": "rgb(255, 0, 0)"}, attrs={"data-pbi-fill": "#1E3A8A"}
    )
    assert objs["fill"][0]["properties"]["fillColor"] == solid("#1E3A8A")


def test_shape_outline_no_round_edge() -> None:
    objs, _, _ = shape_objects_from_styles(
        {
            "borderWidth": "1px", "borderStyle": "solid",
            "borderColor": "rgb(212, 214, 218)", "borderRadius": "8px",
        },
        attrs={},
    )
    assert objs["outline"][0]["properties"]["show"] == literal("true")
    assert objs["outline"][1]["properties"]["lineColor"] == solid("#D4D6DA")
    assert objs["outline"][1]["selector"] == {"id": "default"}
    assert "shape" not in objs


def test_shape_no_styles_emits_nothing() -> None:
    objs, honored, warnings = shape_objects_from_styles(
        {"backgroundColor": "rgba(0, 0, 0, 0)", "borderStyle": "none"}, attrs={}
    )
    assert objs == {} and honored == [] and warnings == []


def test_page_background_card() -> None:
    cards = page_background_card("rgb(241, 245, 249)")
    assert cards is not None
    assert cards[0]["properties"]["color"] == solid("#F1F5F9")
    assert cards[0]["properties"]["transparency"] == literal("0D")


def test_page_background_transparent_is_none() -> None:
    assert page_background_card("rgba(0, 0, 0, 0)") is None
    assert page_background_card("") is None
