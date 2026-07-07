"""CSS → PBIR styling translation (pure functions, no I/O, no Playwright).

Parses the computed-style strings captured by pbir/extractor.py and builds the
PBIR JSON fragments templates.py / writer.py embed. Literal formats verified
against real Power BI samples in resources/PowerBI_Files/.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

_RGB_RE = re.compile(
    r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(-?\d+(?:\.\d+)?)\s*)?\)"
)
_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_PX_RE = re.compile(r"^(-?\d+(?:\.\d+)?)px$")
_PX_TOKEN_RE = re.compile(r"(-?\d+(?:\.\d+)?)px")


def parse_css_color(value: str) -> tuple[str, float] | None:
    """Parse rgb()/rgba()/#RGB/#RRGGBB into ("#RRGGBB", alpha). None if unparseable."""
    value = value.strip()
    m = _RGB_RE.match(value)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        alpha = float(m.group(4)) if m.group(4) is not None else 1.0
        return f"#{r:02X}{g:02X}{b:02X}", alpha
    m = _HEX_RE.match(value)
    if m:
        digits = m.group(1)
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        return f"#{digits.upper()}", 1.0
    return None


def parse_px(value: str) -> float:
    m = _PX_RE.match(value.strip())
    return float(m.group(1)) if m else 0.0


def split_shadow_layers(value: str) -> list[str]:
    """Split a computed box-shadow on commas outside parentheses."""
    layers: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in value:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            layers.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        layers.append(tail)
    return layers


@dataclass(frozen=True)
class ShadowLayer:
    color_hex: str
    alpha: float
    x: float
    y: float
    blur: float
    spread: float


def parse_shadow_layer(layer: str) -> ShadowLayer | None:
    """Parse one computed box-shadow layer: 'rgba(0, 0, 0, 0.1) 0px 1px 3px 0px'."""
    if "inset" in layer:
        return None
    color_match = _RGB_RE.search(layer)
    if color_match is None:
        return None
    parsed = parse_css_color(color_match.group(0))
    if parsed is None:
        return None
    color_hex, alpha = parsed
    lengths = [float(v) for v in _PX_TOKEN_RE.findall(layer)]
    if len(lengths) < 2:
        return None
    x, y = lengths[0], lengths[1]
    blur = lengths[2] if len(lengths) > 2 else 0.0
    spread = lengths[3] if len(lengths) > 3 else 0.0
    return ShadowLayer(color_hex=color_hex, alpha=alpha, x=x, y=y, blur=blur, spread=spread)


def literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def solid(hex_: str) -> dict:
    return {"solid": {"color": literal(f"'{hex_}'")}}


def _transparency(alpha: float) -> str:
    return f"{round((1 - alpha) * 100)}D"


def container_objects_from_styles(
    styles: dict[str, str],
) -> tuple[dict, list[str], list[str]]:
    """Map computed CSS to visualContainerObjects background/border/dropShadow.

    Returns (fragment, honored-notes, warnings). Emits nothing for defaults
    (transparent background, no border, no shadow) to keep visual.json lean.
    """
    out: dict = {}
    honored: list[str] = []
    warnings: list[str] = []

    bg = parse_css_color(styles.get("backgroundColor", ""))
    bg_hex: str | None = None
    if bg is not None and bg[1] > 0:
        bg_hex, bg_alpha = bg
        out["background"] = [{
            "properties": {
                "show": literal("true"),
                "color": solid(bg_hex),
                "transparency": literal(_transparency(bg_alpha)),
            }
        }]
        honored.append(f"background {bg_hex}")

    width = parse_px(styles.get("borderWidth", ""))
    border_style = styles.get("borderStyle", "none").strip().lower()
    border_color = parse_css_color(styles.get("borderColor", ""))
    radius = parse_px(styles.get("borderRadius", ""))
    has_border = (
        border_style not in ("", "none", "hidden")
        and width > 0
        and border_color is not None
        and border_color[1] > 0
    )
    if has_border or radius > 0:
        props: dict = {"show": literal("true")}
        if has_border:
            assert border_color is not None
            props["color"] = solid(border_color[0])
            props["width"] = literal(f"{max(1, round(width))}D")
            honored.append(f"border {border_color[0]}")
        else:
            # Power BI only rounds corners when the border is on. Emit a 1px
            # border matching the background so corners round invisibly.
            props["color"] = solid(bg_hex or "#FFFFFF")
            props["width"] = literal("1D")
        if radius > 0:
            props["radius"] = literal(f"{round(radius)}D")
            honored.append(f"radius {round(radius)}")
        out["border"] = [{"properties": props}]

    shadow_css = styles.get("boxShadow", "").strip()
    if shadow_css and shadow_css != "none":
        layers = split_shadow_layers(shadow_css)
        layer = parse_shadow_layer(layers[0]) if layers else None
        if layer is None:
            warnings.append(f"box-shadow {shadow_css!r} could not be parsed; skipped")
        else:
            angle = round(math.degrees(math.atan2(layer.y, layer.x))) % 360
            out["dropShadow"] = [{
                "properties": {
                    "show": literal("true"),
                    "color": solid(layer.color_hex),
                    "preset": literal("'Custom'"),
                    "angle": literal(f"{angle}D"),
                    "shadowDistance": literal(f"{round(math.hypot(layer.x, layer.y))}D"),
                    "shadowBlur": literal(f"{round(layer.blur)}D"),
                    "shadowSpread": literal(f"{round(layer.spread)}D"),
                    "transparency": literal(_transparency(layer.alpha)),
                }
            }]
            honored.append("dropShadow")
            if len(layers) > 1:
                warnings.append(
                    f"box-shadow has {len(layers)} layers; only the first transfers"
                )
    return out, honored, warnings


def shape_objects_from_styles(
    styles: dict[str, str], attrs: dict[str, str]
) -> tuple[dict, list[str], list[str]]:
    """Map CSS/attrs to shape GEOMETRY objects (fill/outline/roundEdge).

    data-pbi-fill / data-pbi-stroke beat computed CSS. Structure verified
    against resources/PowerBI_Files/Card with Context (fill + outline with
    selector id=default, roundEdge L-suffixed).
    """
    out: dict = {}
    honored: list[str] = []
    warnings: list[str] = []

    fill_source = attrs.get("data-pbi-fill", "").strip() or styles.get("backgroundColor", "")
    fill = parse_css_color(fill_source)
    if fill_source and fill is None:
        warnings.append(f"shape fill {fill_source!r} could not be parsed; skipped")
    elif fill is not None and fill[1] > 0:
        out["fill"] = [{
            "properties": {"fillColor": solid(fill[0])},
            "selector": {"id": "default"},
        }]
        honored.append(f"fill {fill[0]}")

    border_style = styles.get("borderStyle", "none").strip().lower()
    css_stroke_visible = (
        border_style not in ("", "none", "hidden")
        and parse_px(styles.get("borderWidth", "")) > 0
    )
    stroke_source = attrs.get("data-pbi-stroke", "").strip() or (
        styles.get("borderColor", "") if css_stroke_visible else ""
    )
    stroke = parse_css_color(stroke_source)
    if stroke_source and stroke is None:
        warnings.append(f"shape stroke {stroke_source!r} could not be parsed; skipped")
    elif stroke is not None and stroke[1] > 0:
        out["outline"] = [
            {"properties": {"show": literal("true")}},
            {"properties": {"lineColor": solid(stroke[0])}, "selector": {"id": "default"}},
        ]
        honored.append(f"stroke {stroke[0]}")

    radius = parse_px(styles.get("borderRadius", ""))
    if radius > 0:
        out["shape"] = [{"properties": {"roundEdge": literal(f"{round(radius)}L")}}]
        honored.append(f"roundEdge {round(radius)}")
    return out, honored, warnings


def page_background_card(css_color: str) -> list[dict] | None:
    """Build a page.json objects.background card from a CSS color, or None."""
    parsed = parse_css_color(css_color)
    if parsed is None or parsed[1] == 0:
        return None
    hex_, alpha = parsed
    return [{
        "properties": {
            "color": solid(hex_),
            "transparency": literal(_transparency(alpha)),
        }
    }]
