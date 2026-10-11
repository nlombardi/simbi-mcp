"""Spike 04 (THROWAWAY): hand-emit a 'Custom Render' page into the copied fixture.

Adds one page with:
  1. tableEx — Category | Total Revenue | Revenue Sparkline (SVG) | Revenue Share Bar (SVG)
  2. Deneb bar chart (Vega-Lite) — Category x Total Revenue
  3. Deneb box plot (Vega-Lite) — Revenue distribution by Region (row-level)
and registers Deneb in report.json `publicCustomVisuals`.

Run:  python spikes/04_custom_render/build.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent / "SalesDashboard.Report" / "definition"
ENTITY = "sales_small"
DENEB = "deneb7E15AEF80B9E4D4F8E12924291ECE89A"
PAGE = "c0570e4a11b5c4d0e8a1"
VISUAL_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report"
    "/definition/visualContainer/2.3.0/schema.json"
)


def col(p: str) -> dict:
    return {
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": ENTITY}}, "Property": p}},
        "queryRef": f"{ENTITY}.{p}",
        "nativeQueryRef": p,
    }


def meas(p: str) -> dict:
    return {
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": ENTITY}}, "Property": p}},
        "queryRef": f"{ENTITY}.{p}",
        "nativeQueryRef": p,
    }


def lit(value: str) -> dict:
    """PBIR string literal: single-quoted, embedded single quotes doubled."""
    return {"expr": {"Literal": {"Value": "'" + value.replace("'", "''") + "'"}}}


def lit_bool(value: bool) -> dict:
    return {"expr": {"Literal": {"Value": "true" if value else "false"}}}


def container(name: str, x: float, y: float, w: float, h: float, z: int, visual: dict) -> dict:
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": visual,
    }


DENEB_CONFIG = {"autosize": {"type": "fit", "contains": "padding"}}


def deneb(projections: list[dict], spec: dict) -> dict:
    return {
        "visualType": DENEB,
        "query": {"queryState": {"dataset": {"projections": projections}}},
        "objects": {
            "vega": [{
                "properties": {
                    "provider": lit("vegaLite"),
                    "renderMode": lit("svg"),
                    "jsonSpec": lit(json.dumps(spec, indent=2)),
                    "jsonConfig": lit(json.dumps(DENEB_CONFIG, indent=2)),
                    "enableTooltips": lit_bool(True),
                    "enableSelection": lit_bool(True),
                    "enableHighlight": lit_bool(True),
                }
            }]
        },
        "drillFilterOtherVisuals": True,
    }


BAR_SPEC = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "data": {"name": "dataset"},
    "width": "container",
    "height": "container",
    "mark": {"type": "bar", "tooltip": True, "cornerRadiusEnd": 3},
    "encoding": {
        "y": {"field": "Category", "type": "nominal", "sort": "-x", "title": None},
        "x": {"field": "Total Revenue", "type": "quantitative", "title": "Total Revenue"},
        "color": {"value": "#118DFF"},
    },
}

BOX_SPEC = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "data": {"name": "dataset"},
    "width": "container",
    "height": "container",
    "mark": {"type": "boxplot", "extent": 1.5, "tooltip": True},
    "encoding": {
        "x": {"field": "Region", "type": "nominal", "title": None},
        "y": {"field": "Revenue", "type": "quantitative", "title": "Order Revenue"},
        "color": {"field": "Region", "type": "nominal", "legend": None},
    },
}


def title_obj(text: str) -> dict:
    return {"title": [{"properties": {"show": lit_bool(True), "text": lit(text)}}]}


def main() -> None:
    page_dir = ROOT / "pages" / PAGE
    vis_dir = page_dir / "visuals"
    vis_dir.mkdir(parents=True, exist_ok=True)

    (page_dir / "page.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
        "name": PAGE,
        "displayName": "Custom Render",
        "displayOption": "FitToPage",
        "height": 720,
        "width": 1280,
    }, indent=2), encoding="utf-8")

    table = {
        "visualType": "tableEx",
        "query": {"queryState": {"Values": {"projections": [
            col("Category"),
            meas("Total Revenue"),
            meas("Revenue Sparkline"),
            meas("Revenue Share Bar"),
            meas("Revenue Trend Arrow"),
            meas("Revenue vs Avg Badge"),
        ]}}},
        "objects": {},
        "visualContainerObjects": title_obj("SVG measures in a native table"),
        "drillFilterOtherVisuals": True,
    }

    bar = deneb([col("Category"), meas("Total Revenue")], BAR_SPEC)
    bar["visualContainerObjects"] = title_obj("Deneb: bar (Vega-Lite)")

    box = deneb([col("Region"), col("OrderID"), col("Revenue")], BOX_SPEC)
    box["visualContainerObjects"] = title_obj("Deneb: box plot (Vega-Lite)")

    visuals = {
        "a1b2c3d4e5f60718293a": container("a1b2c3d4e5f60718293a", 24, 24, 1232, 300, 0, table),
        "b2c3d4e5f60718293a4b": container("b2c3d4e5f60718293a4b", 24, 340, 600, 356, 1000, bar),
        "c3d4e5f60718293a4b5c": container("c3d4e5f60718293a4b5c", 656, 340, 600, 356, 2000, box),
    }
    for name, v in visuals.items():
        d = vis_dir / name
        d.mkdir(exist_ok=True)
        (d / "visual.json").write_text(json.dumps(v, indent=2), encoding="utf-8")

    pages_path = ROOT / "pages" / "pages.json"
    pages = json.loads(pages_path.read_text(encoding="utf-8"))
    if PAGE not in pages["pageOrder"]:
        pages["pageOrder"].append(PAGE)
    pages["activePageName"] = PAGE
    pages_path.write_text(json.dumps(pages, indent=2), encoding="utf-8")

    report_path = ROOT / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["publicCustomVisuals"] = [DENEB]
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote page {PAGE} with {len(visuals)} visuals; Deneb registered.")


if __name__ == "__main__":
    main()
