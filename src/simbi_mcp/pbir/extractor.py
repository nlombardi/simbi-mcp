"""DOM extraction: renders HTML in headless Chrome, returns annotated VisualNode list.

Requires system Chrome (channel="chrome"). The caller must place dashboard.css
in the same directory as the HTML file before calling extract_visuals.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from simbi_mcp.mockup.annotations import VisualType

_VIEWPORT = {"width": 1280, "height": 720}

_JS_EXTRACT = """
() => {
  const els = document.querySelectorAll('[data-pbi]');
  return Array.from(els).map(el => {
    const r = el.getBoundingClientRect();
    const data = {};
    for (const a of el.attributes) {
      if (a.name.startsWith('data-pbi')) data[a.name] = a.value;
    }
    return {
      x: r.x + window.scrollX,
      y: r.y + window.scrollY,
      width: r.width,
      height: r.height,
      data: data,
    };
  });
}
"""


@dataclass(frozen=True)
class VisualNode:
    x: float
    y: float
    width: float
    height: float
    attrs: dict[str, str]

    @property
    def visual_type(self) -> VisualType:
        raw = self.attrs.get("data-pbi", "")
        try:
            return VisualType(raw)
        except ValueError:
            raise ValueError(
                f"VisualNode has invalid data-pbi value {raw!r}. "
                f"Valid types: {[v.value for v in VisualType]}"
            ) from None


async def extract_visuals(html_path: Path) -> list[VisualNode]:
    """Render html_path in system Chrome and extract [data-pbi] bounding boxes.

    dashboard.css must be in html_path.parent before this is called.
    Raises RuntimeError if no data-pbi elements are found.
    """
    from playwright.async_api import async_playwright  # type: ignore[import-not-found]

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        async with browser:
            context = await browser.new_context(viewport=_VIEWPORT)
            page = await context.new_page()
            await page.goto(html_path.as_uri())
            await page.wait_for_load_state("networkidle")
            raw: list[dict[str, Any]] = await page.evaluate(_JS_EXTRACT)

    if not raw:
        raise RuntimeError(f"No [data-pbi] elements found in {html_path}")

    return _parse_js_nodes(raw)


def _parse_js_nodes(raw: list[dict[str, Any]]) -> list[VisualNode]:
    return [
        VisualNode(
            x=float(node["x"]),
            y=float(node["y"]),
            width=float(node["width"]),
            height=float(node["height"]),
            attrs={k: str(v) for k, v in node["data"].items()},
        )
        for node in raw
    ]
