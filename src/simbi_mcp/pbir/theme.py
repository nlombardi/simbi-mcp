"""Theme resolution for PBIR emission.

Three-tier theme pipeline:

    1. Microsoft CY25SU10 — colour science, semantic palette, text classes
    2. SimBI opinionated defaults (SimBIDefault.json) — visualStyles overrides
       that enforce the dashboard-design-playbook: hide gridlines, no visual
       borders, lean cards, consistent label typography
    3. User-supplied theme JSON (optional) — partial overrides that deep-merge
       onto the SimBI baseline. Users override what they care about (brand
       colours, custom textClasses) without re-authoring the visualStyles.

The resolved theme is a single dict written to disk by writer.py. Users
typically need only a `dataColors` array to brand a report — everything
else is inherited.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

_STATIC_DIR = Path(__file__).parent / "static"


class InvalidThemeError(ValueError):
    """Raised when a user-supplied theme path is missing, unparseable, or wrong shape."""


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict where overlay wins, recursing into nested dicts.

    Lists are replaced wholesale by the overlay (order is theme-meaningful —
    e.g. dataColors ordering controls categorical series colour assignment).
    Scalar / list / dict type mismatches are resolved by overlay wins.
    Inputs are not mutated.
    """
    out: dict[str, Any] = deepcopy(base)
    for key, overlay_value in overlay.items():
        base_value = out.get(key)
        if isinstance(base_value, dict) and isinstance(overlay_value, dict):
            out[key] = deep_merge(base_value, overlay_value)
        else:
            out[key] = deepcopy(overlay_value)
    return out


def resolve_theme(user_theme_path: Path | None) -> dict[str, Any]:
    """Build the final theme dict by layering: Microsoft → SimBI → user.

    `user_theme_path` may be None (use SimBI default) or a path to a JSON
    file containing any partial theme — `dataColors`, `textClasses`,
    `visualStyles`, etc. The user theme is deep-merged onto SimBI's baseline
    so corp branding (typically just `dataColors`) does not erase SimBI's
    opinionated `visualStyles`.
    """
    base = _load_static_theme("CY25SU10.json")
    simbi = _load_static_theme("SimBIDefault.json")
    resolved = deep_merge(base, simbi)
    if user_theme_path is not None:
        user = _load_user_theme(user_theme_path)
        resolved = deep_merge(resolved, user)
    return resolved


def _load_static_theme(filename: str) -> dict[str, Any]:
    path = _STATIC_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


def _load_user_theme(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise InvalidThemeError(
            f"User theme file not found: {path}. Pass a valid JSON path or omit "
            f"theme_path to use SimBI's default theme."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InvalidThemeError(
            f"Could not parse user theme {path}: {exc.msg} at line {exc.lineno}."
        ) from exc
    if not isinstance(data, dict):
        raise InvalidThemeError(
            f"User theme {path} must be a JSON object at the top level, got "
            f"{type(data).__name__}. A PBIR theme is keyed by field names like "
            f"'dataColors', 'textClasses', 'visualStyles'."
        )
    return data


def build_theme_schema_text() -> str:
    """Render the theme JSON schema from SimBI's actual resolved default.

    Generated from the real CY25SU10.json/SimBIDefault.json files (via
    resolve_theme) rather than hand-written, so the palette, textClasses, and
    the list of visual types SimBI already opinionates on can never drift from
    what emit_report actually applies.
    """
    theme = resolve_theme(user_theme_path=None)
    lines: list[str] = [
        "THEME SCHEMA",
        "============",
        "emit_report's optional theme_path is a partial PBIR theme JSON file.",
        "Resolution order (each tier deep-merges ONTO the previous one):",
        "  1. Microsoft CY25SU10 — colour science, semantic palette, text classes",
        "  2. SimBI opinionated defaults — visualStyles enforcing the dashboard",
        "     design playbook (hidden gridlines, lean cards, no visual borders,",
        "     consistent typography)",
        "  3. Your theme_path file (optional) — deep-merged on top; you only",
        "     need to override what you care about (typically just dataColors)",
        "     without erasing SimBI's visualStyles opinions.",
        "",
        "TOP-LEVEL KEYS",
        "==============",
        f'  dataColors      ordered hex list, categorical series colours. Current default '
        f"starts {theme['dataColors'][0]!r}, {len(theme['dataColors'])} colours total. "
        "First entries are also referenced by shape fill (ThemeDataColor ColorId 0).",
        f"  good / neutral / bad   semantic single colours ({theme['good']!r} / "
        f"{theme['neutral']!r} / {theme['bad']!r}). RESERVED — never reassign these to "
        "categorical data (see DESIGN PRINCIPLES > COLOUR).",
        f"  textClasses     typography per role: {', '.join(sorted(theme['textClasses']))}.",
        "  visualStyles    per-visualType nested property objects — the biggest lever.",
        "",
        "VISUAL TYPES SIMBI ALREADY STYLES",
        "==================================",
        "SimBI's own default already sets visualStyles for these PBIR visual types",
        "(overriding one deep-merges onto SimBI's existing object for that type —",
        "it does not replace it):",
    ]
    for vtype in theme["visualStyles"]:
        if vtype == "*":
            continue
        lines.append(f"  {vtype}")
    lines += [
        "",
        "PER-VISUAL OVERRIDE BOUNDARY",
        "=============================",
        "This theme sets the REPORT-WIDE baseline. A single visual's explicit",
        "data-pbi-fill / data-pbi-stroke attributes, or its element's own computed",
        "CSS (background-color, border, border-radius, box-shadow — see",
        "get_vocabulary's STYLING CONTRACT section), override the theme for THAT",
        "one visual only. Use the theme for report-wide branding; use per-element",
        "styling in the mockup HTML for one-off exceptions.",
    ]
    return "\n".join(lines)
