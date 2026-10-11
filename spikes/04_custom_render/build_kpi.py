"""Spike 04b (THROWAWAY): 'KPI Trend' page — where can an SVG measure sit next to a KPI?

  A/B  cardVisual (new card): Total Revenue + sparkline in the card's image area
       (A = %23-encoded colours, B = plain '#')
  C    cardVisual: Total Revenue + trend arrow in the image area
  D/E  image visual bound to the sparkline measure (D = %23, E = '#')
  F/G  fallback: classic card + table directly underneath holding sparkline + arrow

Bindings follow data-goblin/power-bi-agentic-development pbir-format examples
(cardVisual `image.imageUrl`, image `image.sourceType='imageData'` + `sourceField`).

Run:  python spikes/04_custom_render/build_kpi.py
"""
from __future__ import annotations

import json
from pathlib import Path

from build import ROOT, col, container, lit, lit_bool, meas, title_obj  # noqa: F401

PAGE = "d1f6a5b4c3e2d1f0a9b8"
ENTITY = "sales_small"


def measure_expr(p: str) -> dict:
    return {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": ENTITY}}, "Property": p}}}


def new_card(title: str, image_measure: str) -> dict:
    return {
        "visualType": "cardVisual",
        "query": {"queryState": {"Data": {"projections": [meas("Total Revenue")]}}},
        "objects": {
            "image": [
                {"properties": {"show": lit_bool(True)}},
                {
                    "properties": {
                        "imageType": lit("imageUrl"),
                        "imageUrl": measure_expr(image_measure),
                        "position": lit("Bottom"),
                        "padding": {"expr": {"Literal": {"Value": "0L"}}},
                    },
                    "selector": {"id": "default"},
                },
            ]
        },
        "visualContainerObjects": title_obj(title),
        "drillFilterOtherVisuals": True,
    }


def image_visual(title: str, image_measure: str) -> dict:
    return {
        "visualType": "image",
        "objects": {
            "image": [{
                "properties": {
                    "sourceType": lit("imageData"),
                    "sourceField": measure_expr(image_measure),
                    "transparency": {"expr": {"Literal": {"Value": "0D"}}},
                    "effects": lit_bool(False),
                }
            }]
        },
        "visualContainerObjects": title_obj(title),
        "drillFilterOtherVisuals": True,
    }


def main() -> None:
    page_dir = ROOT / "pages" / PAGE
    vis_dir = page_dir / "visuals"
    vis_dir.mkdir(parents=True, exist_ok=True)
    (page_dir / "page.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
        "name": PAGE,
        "displayName": "KPI Trend",
        "displayOption": "FitToPage",
        "height": 720,
        "width": 1280,
    }, indent=2), encoding="utf-8")

    classic = {
        "visualType": "card",
        "query": {"queryState": {"Values": {"projections": [meas("Total Revenue")]}}},
        "visualContainerObjects": title_obj("F: classic card"),
        "drillFilterOtherVisuals": True,
    }
    under_table = {
        "visualType": "tableEx",
        "query": {"queryState": {"Values": {"projections": [
            meas("Revenue Sparkline"),
            meas("Revenue Trend Arrow"),
        ]}}},
        "visualContainerObjects": title_obj("G: table under card (fallback)"),
        "drillFilterOtherVisuals": True,
    }

    specs = [
        # name, x, y, w, h, visual
        ("e0a1b2c3d4e5f6a7b8c9", 24, 24, 400, 220, new_card("A: new card + sparkline (%23)", "Revenue Sparkline")),
        ("e1a1b2c3d4e5f6a7b8c9", 440, 24, 400, 220, new_card("B: new card + sparkline (#)", "Revenue Sparkline Hex")),
        ("e2a1b2c3d4e5f6a7b8c9", 856, 24, 400, 220, new_card("C: new card + trend arrow", "Revenue Trend Arrow")),
        ("e3a1b2c3d4e5f6a7b8c9", 24, 260, 400, 140, image_visual("D: image visual (%23)", "Revenue Sparkline")),
        ("e4a1b2c3d4e5f6a7b8c9", 440, 260, 400, 140, image_visual("E: image visual (#)", "Revenue Sparkline Hex")),
        ("e5a1b2c3d4e5f6a7b8c9", 24, 420, 400, 140, classic),
        ("e6a1b2c3d4e5f6a7b8c9", 24, 564, 400, 132, under_table),
    ]
    for z, (name, x, y, w, h, visual) in enumerate(specs):
        d = vis_dir / name
        d.mkdir(exist_ok=True)
        (d / "visual.json").write_text(
            json.dumps(container(name, x, y, w, h, z * 1000, visual), indent=2), encoding="utf-8"
        )

    pages_path = ROOT / "pages" / "pages.json"
    pages = json.loads(pages_path.read_text(encoding="utf-8"))
    if PAGE not in pages["pageOrder"]:
        pages["pageOrder"].append(PAGE)
    pages["activePageName"] = PAGE
    pages_path.write_text(json.dumps(pages, indent=2), encoding="utf-8")
    print(f"Wrote page {PAGE} with {len(specs)} visuals.")


if __name__ == "__main__":
    main()
