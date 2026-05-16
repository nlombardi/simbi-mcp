"""Playwright DOM extraction smoke test.

Renders reference.html at a fixed viewport and extracts bounding boxes +
data-pbi-* annotations for every [data-pbi] element.
"""
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

VIEWPORT = {"width": 1280, "height": 800}


async def main() -> None:
    here = Path(__file__).parent
    html_path = here / "reference.html"
    assert html_path.exists()

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        context = await browser.new_context(viewport=VIEWPORT)
        page = await context.new_page()
        await page.goto(html_path.as_uri())
        await page.wait_for_load_state("networkidle")

        # Take a screenshot for visual fidelity check
        await page.screenshot(path=str(here / "check.png"))

        # Extract every [data-pbi] node's rect + data-pbi-* attributes
        nodes = await page.evaluate(
            """
            () => {
              const els = document.querySelectorAll('[data-pbi]');
              return Array.from(els).map(el => {
                const r = el.getBoundingClientRect();
                const data = {};
                for (const a of el.attributes) {
                  if (a.name.startsWith('data-pbi')) data[a.name] = a.value;
                }
                return {
                  x: r.x, y: r.y, width: r.width, height: r.height,
                  data: data,
                };
              });
            }
            """
        )

        print(json.dumps(nodes, indent=2))
        assert len(nodes) == 4, f"Expected 4 nodes, got {len(nodes)}"
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
