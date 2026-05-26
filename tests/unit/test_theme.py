"""Tests for the theme resolution pipeline (Microsoft base → SimBI defaults → user override)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from simbi_mcp.pbir.theme import (
    InvalidThemeError,
    deep_merge,
    resolve_theme,
)


# ---------- deep_merge ----------


def test_deep_merge_overlays_scalar() -> None:
    assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}


def test_deep_merge_adds_new_key() -> None:
    assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_deep_merge_recurses_into_nested_dicts() -> None:
    base = {"visualStyles": {"barChart": {"*": {"gridlines": False}}}}
    overlay = {"visualStyles": {"barChart": {"*": {"fontSize": 12}}}}
    assert deep_merge(base, overlay) == {
        "visualStyles": {"barChart": {"*": {"gridlines": False, "fontSize": 12}}}
    }


def test_deep_merge_overlay_replaces_lists() -> None:
    # Lists are theme-meaningful (dataColors order matters) — overlay wins entirely.
    base = {"dataColors": ["#111", "#222", "#333"]}
    overlay = {"dataColors": ["#aaa", "#bbb"]}
    assert deep_merge(base, overlay) == {"dataColors": ["#aaa", "#bbb"]}


def test_deep_merge_overlay_overrides_dict_with_scalar() -> None:
    # Type mismatch: overlay wins; base value is discarded.
    base = {"foreground": {"r": 0, "g": 0, "b": 0}}
    overlay = {"foreground": "#000000"}
    assert deep_merge(base, overlay) == {"foreground": "#000000"}


def test_deep_merge_does_not_mutate_inputs() -> None:
    base = {"a": {"b": 1}}
    overlay = {"a": {"c": 2}}
    deep_merge(base, overlay)
    assert base == {"a": {"b": 1}}
    assert overlay == {"a": {"c": 2}}


# ---------- resolve_theme ----------


def test_resolve_theme_no_user_override_uses_simbi_default() -> None:
    theme = resolve_theme(user_theme_path=None)
    assert theme["name"]
    assert "dataColors" in theme
    # SimBI opinion: visualStyles must be present (Microsoft base alone doesn't push gridline-off, etc.)
    assert "visualStyles" in theme
    assert theme["visualStyles"]  # non-empty


def test_resolve_theme_preserves_microsoft_color_science() -> None:
    theme = resolve_theme(user_theme_path=None)
    # Microsoft CY25SU10 leads with #118DFF — assert SimBI defaults didn't blow it away
    assert theme["dataColors"][0].upper() == "#118DFF"
    assert theme["good"] and theme["bad"]


def test_resolve_theme_user_dataColors_wins(tmp_path: Path) -> None:
    user = tmp_path / "brand.json"
    user.write_text(json.dumps({"dataColors": ["#FF0000", "#00FF00"]}))
    theme = resolve_theme(user_theme_path=user)
    assert theme["dataColors"] == ["#FF0000", "#00FF00"]
    # SimBI visualStyles preserved
    assert "visualStyles" in theme and theme["visualStyles"]


def test_resolve_theme_user_visualStyles_merge_into_simbi_defaults(tmp_path: Path) -> None:
    user = tmp_path / "brand.json"
    user.write_text(json.dumps({
        "visualStyles": {"barChart": {"*": {"customMarker": "user-value"}}}
    }))
    theme = resolve_theme(user_theme_path=user)
    bar_style = theme["visualStyles"]["barChart"]["*"]
    # User addition is present
    assert bar_style.get("customMarker") == "user-value"
    # SimBI's opinionated keys (whichever) are still there alongside it
    assert len(bar_style) >= 2


def test_resolve_theme_missing_user_file_raises(tmp_path: Path) -> None:
    with pytest.raises(InvalidThemeError, match="not found"):
        resolve_theme(user_theme_path=tmp_path / "does-not-exist.json")


def test_resolve_theme_invalid_json_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{ this is not json")
    with pytest.raises(InvalidThemeError, match="parse"):
        resolve_theme(user_theme_path=bad)


def test_resolve_theme_non_dict_top_level_raises(tmp_path: Path) -> None:
    arr = tmp_path / "arr.json"
    arr.write_text("[1, 2, 3]")
    with pytest.raises(InvalidThemeError, match="object"):
        resolve_theme(user_theme_path=arr)


def test_resolve_theme_user_can_override_name(tmp_path: Path) -> None:
    user = tmp_path / "brand.json"
    user.write_text(json.dumps({"name": "AcmeBrand"}))
    theme = resolve_theme(user_theme_path=user)
    assert theme["name"] == "AcmeBrand"
