"""CSS → PBIR styling translation (pure functions, no I/O, no Playwright).

Parses the computed-style strings captured by pbir/extractor.py and builds the
PBIR JSON fragments templates.py / writer.py embed. Literal formats verified
against real Power BI samples in resources/PowerBI_Files/.
"""
from __future__ import annotations

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
