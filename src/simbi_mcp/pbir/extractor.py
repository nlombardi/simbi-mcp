"""DOM extraction: renders HTML in headless Chrome, returns annotated VisualNode list.

Requires system Chrome (channel="chrome"). The caller must place dashboard.css
in the same directory as the HTML file before calling extract_visuals.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.async_api import ViewportSize

from simbi_mcp.mockup.annotations import VisualType

_VIEWPORT: ViewportSize = {"width": 1280, "height": 720}

_JS_EXTRACT = """
() => {
  const pageContainers = document.querySelectorAll('[data-pbi-page]');
  const groups = pageContainers.length > 0
    ? Array.from(pageContainers).map((el, i) => ({
        el, index: i, name: el.getAttribute('data-pbi-page') || ('Page ' + (i + 1))
      }))
    : [{ el: document.documentElement, index: 0, name: 'Page 1' }];

  const result = [];
  for (const { el: pageEl, index: pageIdx, name: pageName } of groups) {
    const pageRect = pageEl.getBoundingClientRect();
    for (const el of pageEl.querySelectorAll('[data-pbi]')) {
      const r = el.getBoundingClientRect();
      const data = {};
      for (const a of el.attributes) {
        if (a.name.startsWith('data-pbi')) data[a.name] = a.value;
      }
      result.push({
        x: r.x - pageRect.x,
        y: r.y - pageRect.y,
        width: r.width,
        height: r.height,
        data,
        page_index: pageIdx,
        page_name: pageName,
      });
    }
  }
  return result;
}
"""


@dataclass(frozen=True)
class VisualNode:
    x: float
    y: float
    width: float
    height: float
    attrs: dict[str, str]
    page_index: int = 0
    page_name: str = "Page 1"

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
    from playwright.async_api import async_playwright

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

    nodes = _parse_js_nodes(raw)

    zero_size = [n for n in nodes if n.width == 0 and n.height == 0]
    if zero_size:
        types = [n.attrs.get("data-pbi", "?") for n in zero_size]
        raise RuntimeError(
            f"{len(zero_size)} of {len(nodes)} data-pbi element(s) have zero "
            f"width/height after rendering ({types}). Power BI Desktop will "
            f"silently discard zero-size visuals.\n\n"
            f"Fix: wrap each visual element in a container that gives it "
            f"explicit dimensions. Use the dashboard.css classes — for example:\n"
            f'  <div class="db-card" data-pbi="card" data-pbi-measure="Total Revenue">\n'
            f'    <span class="db-label">Total Revenue</span>\n'
            f"  </div>\n\n"
            f"Every visual must have a non-zero bounding box in the rendered HTML."
        )

    return nodes


def _parse_js_nodes(raw: list[dict[str, Any]]) -> list[VisualNode]:
    return [
        VisualNode(
            x=float(node["x"]),
            y=float(node["y"]),
            width=float(node["width"]),
            height=float(node["height"]),
            attrs={k: str(v) for k, v in node["data"].items()},
            page_index=int(node.get("page_index", 0)),
            page_name=str(node.get("page_name", "Page 1")),
        )
        for node in raw
    ]
