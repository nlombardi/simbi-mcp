"""Theme visualStyles must nest property cards under an inner '*' selector,
matching Power BI's PBIR theme format. Cards placed directly under a visual
type (without the inner '*') are silently ignored by Power BI Desktop.
"""
import json
from pathlib import Path

import pytest

from simbi_mcp.pbir import theme as theme_mod

_KNOWN_CARD_NAMES = {
    "background", "border", "visualHeader", "categoryAxis", "valueAxis",
    "legend", "labels", "title", "lineStyles", "grid", "columnHeaders",
    "values", "card", "dataLabels", "categoryLabels", "trendline",
    "indicator", "shape", "outline", "text", "fill",
}


def _theme():
    p = Path(theme_mod.__file__).parent / "static" / "SimBIDefault.json"
    return json.loads(p.read_text(encoding="utf-8"))


def test_every_visualstyle_entry_uses_inner_star():
    vs = _theme()["visualStyles"]
    for vtype, body in vs.items():
        assert isinstance(body, dict), f"{vtype} body must be a dict"
        # The ONLY allowed top-level selector keys are '*' (and rarely property
        # selectors). A correctly-formed entry has its cards under '*'.
        assert "*" in body, f"visualStyles[{vtype!r}] is missing the inner '*' selector"
        # No card names should appear at the WRONG level (directly under vtype).
        leaked = _KNOWN_CARD_NAMES & set(body.keys())
        assert not leaked, f"visualStyles[{vtype!r}] has cards {leaked} outside the inner '*' selector"


def test_inner_star_holds_cards_as_dict():
    vs = _theme()["visualStyles"]
    # For the universal '*' type, the inner '*' must be a dict of card-arrays.
    inner = vs["*"]["*"]
    assert isinstance(inner, dict), "visualStyles['*']['*'] must be a dict of card -> [props]"
    # known cards should now live here
    assert "categoryAxis" in inner
    assert "background" in inner


def test_theme_still_valid_json_and_has_datacolors():
    # SimBIDefault.json holds only the visualStyles overrides; the dataColors
    # palette comes from the Microsoft base theme and is merged in by
    # resolve_theme. Assert against the resolved theme so "palette intact" is
    # meaningful.
    t = _theme()
    assert "visualStyles" in t
    resolved = theme_mod.resolve_theme(None)
    assert resolved["dataColors"][0]  # palette intact
