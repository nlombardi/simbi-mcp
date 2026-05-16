# Playwright DOM Extraction Notes

## Viewport used
1280 x 800 (matches typical Power BI page default)

## Extraction approach
- `getBoundingClientRect()` from page.evaluate
- Filter to `[data-pbi]` elements
- Collect all `data-pbi-*` attributes

## Environment workaround: Tailwind CDN offline

**Kill criterion triggered on first run.** `storage.googleapis.com` and `cdn.tailwindcss.com`
are unreachable on this machine (DNS resolution fails). The original `reference.html` used
`<script src="https://cdn.tailwindcss.com">` — without it, the browser fell back to default
block-level layout: every element at x=0, full-width, stacked vertically.

**Fix:** replaced the CDN `<script>` tag with inline CSS equivalents for every Tailwind class
used in the HTML (`grid`, `grid-cols-3`, `gap-4`, `p-6`, `h-64`, etc.). This is a spike-only
workaround. Production code (Phase 3) should either:
1. Bundle Tailwind at build time (recommended), or
2. Use a local Tailwind CLI output instead of CDN

## Playwright browser

`chromium` could not be downloaded (same network restriction — `storage.googleapis.com` blocked).
Used `channel="chrome"` to launch the system Chrome installation at
`C:\Program Files\Google\Chrome\Application\chrome.exe` instead. This required changing
`p.chromium.launch()` to `p.chromium.launch(channel="chrome")` in `extract.py`.

## Coordinate fidelity
- Visual match with screenshot: **yes** — screenshot and extracted rects are in exact agreement
- Sub-pixel rounding observed: **none** — all values are integers; Tailwind uses integer px values
  (24px padding, 16px gap) so no fractional coords arise under this layout
- Quirks:
  - Card height=104: body padding (24) + card padding-top (24) + text-sm line-height (20) +
    text-3xl line-height (36) = 104. Matches exactly.
  - Bar chart height=256 from `h-64` (64 * 4px = 256px). Correct.
  - Bar chart y=144: body-padding (24) + card-height (104) + gap (16) = 144. Correct.
  - Column widths: (1280 - 2*24 body-padding - 2*16 gap) / 3 = (1280-48-32)/3 = 400px. Correct.
  - `getBoundingClientRect()` returns coords relative to the viewport top-left (not the document
    origin). For pages that fit within the viewport (no scroll), these are identical to document
    coords. For scrollable pages in Phase 3, will need to add `window.scrollX/Y` offset.

## Time to extract 4 elements
~2–3 seconds total wall-clock (browser launch dominates). The `evaluate()` call itself is
sub-millisecond. For large dashboards with 50–100 elements, extraction time stays negligible;
browser launch is the fixed cost.

## Extracted nodes (sample run)

```json
[
  {
    "x": 24,
    "y": 24,
    "width": 400,
    "height": 104,
    "data": {
      "data-pbi": "card",
      "data-pbi-measure": "Total Revenue"
    }
  },
  {
    "x": 440,
    "y": 24,
    "width": 400,
    "height": 104,
    "data": {
      "data-pbi": "card",
      "data-pbi-measure": "Order Count"
    }
  },
  {
    "x": 856,
    "y": 24,
    "width": 400,
    "height": 104,
    "data": {
      "data-pbi": "slicer",
      "data-pbi-field": "Date[Year]"
    }
  },
  {
    "x": 24,
    "y": 144,
    "width": 1232,
    "height": 256,
    "data": {
      "data-pbi": "barChart",
      "data-pbi-axis": "Product[Category]",
      "data-pbi-values": "Total Revenue"
    }
  }
]
```

## Verdict

Approach is viable. `getBoundingClientRect()` + `data-pbi-*` attribute collection gives
pixel-perfect bounding boxes that match the rendered screenshot. The mechanism is solid for
Phase 3 — the only Phase 3 requirement is to bundle CSS locally (no CDN dependency).
