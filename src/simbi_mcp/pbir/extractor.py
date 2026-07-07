"""DOM extraction: renders HTML in headless Chrome, returns annotated VisualNode list.

Requires system Chrome (channel="chrome"). The caller must place dashboard.css
in the same directory as the HTML file before calling extract_visuals.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
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
        el, index: i, name: el.getAttribute('data-pbi-page') || ('Page ' + (i + 1)),
        background: getComputedStyle(el).backgroundColor
      }))
    : [{ el: document.documentElement, index: 0, name: 'Page 1', background: '' }];

  const result = [];
  for (const { el: pageEl, index: pageIdx, name: pageName, background } of groups) {
    const pageRect = pageEl.getBoundingClientRect();
    for (const el of pageEl.querySelectorAll('[data-pbi]')) {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      const data = {};
      for (const a of el.attributes) {
        if (a.name.startsWith('data-pbi') || a.name === 'style') data[a.name] = a.value;
      }
      result.push({
        x: r.x - pageRect.x,
        y: r.y - pageRect.y,
        width: r.width,
        height: r.height,
        data,
        styles: {
          backgroundColor: cs.backgroundColor,
          borderWidth: cs.borderTopWidth,
          borderStyle: cs.borderTopStyle,
          borderColor: cs.borderTopColor,
          borderRadius: cs.borderTopLeftRadius,
          boxShadow: cs.boxShadow,
        },
        page_background: background,
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
    styles: dict[str, str] = field(default_factory=dict)
    page_background: str = ""

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


@dataclass
class ExtractResult:
    nodes: list[VisualNode]
    previews: list[Path]
    warnings: list[str]


def _safe_filename(name: str) -> str:
    return re.sub(r'[^\w\- ]', "_", name)


async def extract_visuals(
    html_path: Path, screenshot_dir: Path | None = None
) -> ExtractResult:
    """Render html_path in system Chrome; extract [data-pbi] geometry + computed
    styles. When screenshot_dir is given, also write one PNG per data-pbi-page
    container (or the full page when none) — best-effort, never fatal.

    dashboard.css must be in html_path.parent before this is called.
    Raises RuntimeError if no data-pbi elements are found.
    """
    from playwright.async_api import async_playwright

    previews: list[Path] = []
    warnings: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        async with browser:
            context = await browser.new_context(viewport=_VIEWPORT)
            page = await context.new_page()
            await page.goto(html_path.as_uri())
            await page.wait_for_load_state("networkidle")
            raw: list[dict[str, Any]] = await page.evaluate(_JS_EXTRACT)

            if screenshot_dir is not None:
                try:
                    screenshot_dir.mkdir(parents=True, exist_ok=True)
                    containers = page.locator("[data-pbi-page]")
                    count = await containers.count()
                    if count == 0:
                        dest = screenshot_dir / "Page 1.png"
                        await page.screenshot(path=str(dest))
                        previews.append(dest)
                    else:
                        for i in range(count):
                            el = containers.nth(i)
                            name = await el.get_attribute("data-pbi-page") or f"Page {i + 1}"
                            dest = screenshot_dir / f"{_safe_filename(name)}.png"
                            await el.screenshot(path=str(dest))
                            previews.append(dest)
                except Exception as exc:  # preview is best-effort by design
                    warnings.append(f"preview screenshot failed: {exc}")

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

    return ExtractResult(nodes=nodes, previews=previews, warnings=warnings)


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
            styles={k: str(v) for k, v in node.get("styles", {}).items()},
            page_background=str(node.get("page_background", "")),
        )
        for node in raw
    ]
