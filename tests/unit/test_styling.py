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
