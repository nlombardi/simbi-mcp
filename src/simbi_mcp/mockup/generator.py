"""HTML mockup generator — converts user prompt + ModelSchema to annotated HTML.

Calls Claude with a structured prompt that includes:
  - The data-pbi annotation vocabulary (from annotations.py)
  - The available CSS class catalog (from annotations.py)
  - The full ModelSchema (measure names, table/column names)
  - The user's dashboard intent

Claude responds with JSON {"html": "<the full HTML page>"}.
The HTML is then validated against the schema before being returned.
"""
from __future__ import annotations

import json
from typing import Any

from simbi_mcp.mockup.annotations import ANNOTATION_SPEC_TEXT, CSS_CLASS_CATALOG
from simbi_mcp.mockup.validator import validate_mockup
from simbi_mcp.types import ModelSchema

_MODEL = "claude-opus-4-7"
_MAX_TOKENS = 4096

_SYSTEM_PROMPT = f"""\
You generate annotated HTML mockups for Power BI dashboards.

Your output is compiled directly into Power BI report files. Every visual you
place must use the annotation vocabulary exactly as specified — do not invent
attribute names or values.

{ANNOTATION_SPEC_TEXT}

{CSS_CLASS_CATALOG}

DESIGN RULES
============
These rules apply to every dashboard you generate. They are not suggestions.

SIZING
- Title text elements (data-pbi-role="title"): minimum height 40px, font content
  is 16pt bold. A height of 32px or below clips the descenders — always use 40px+.
- Label text elements (data-pbi-role="label"): height 24px is standard; 20px is
  the minimum. These are uppercase 9pt labels above slicers and filters.
- Dropdowns and field-param slicers: standard height 40px. Width must match the
  content — a four-item indicator selector does not need more than 240px. Never
  exceed 300px for a compact header dropdown. Default to 200–240px unless the
  option labels are unusually long (>20 chars).
- Between-style slicers: height 56px minimum (accommodates the slider track).
- Buttons: height 40px. Group related buttons flush together with equal widths
  so they form a visible button bar; 100–120px per button is typical.
- Chart area: fill the remaining canvas height after header, filter rail, and
  title. On a 720px page with a 64px header, 88px filter rail, and 40px title +
  8px gap: chart top ≈ 200px, chart height ≈ 500px (adjust proportionally).

LAYOUT
- Header band: 64px tall. Dark brand color. Brand title left (24px from edge),
  indicator/measure selector top-right (right-aligned to 1256px, standard 240px
  wide dropdown).
- Filter rail: 88px tall, sits directly below the header. White or very light
  background. Filters start at left edge (24px); view-toggle buttons are always
  placed at the RIGHT of the filter rail (right-align to ~1256px) with equal
  widths and tight grouping. Never scatter filters across the page.
- Chart title: sits between filter rail bottom and chart top, 8–12px gap from
  rail. Full text should be in the same color as the brand (#003087 or equivalent).

DYNAMIC CHART TITLES
- When a field-param (measure switcher) controls the chart, the chart title
  should update to reflect the selected measure. Do this by:
  1. Creating a string-returning DAX measure in the model (e.g. "Chart Title Label")
     that uses SELECTEDVALUE to return the display name of the selected indicator.
  2. On the title text element, add data-pbi-title-measure="Chart Title Label".
  3. Keep data-pbi-text set to the default indicator label for the HTML preview.
  - Only use data-pbi-title-measure when the schema contains such a string measure.
    If no suitable measure exists, use a static data-pbi-text title instead —
    do not invent a measure name not present in the schema.

FIELD PARAMETER STYLE
- Default field-param style is "dropdown", not "tabs". Tabs become unreadable
  with more than 3 options. Use "tabs" only for 2–3 options with short labels.
- A field-param dropdown in the header should have style="dropdown" and a width
  of 200–240px. Place it top-right of the header with a label above it.

OUTPUT FORMAT
=============
Respond with a single JSON object and nothing else:
  {{"html": "<complete HTML page as a string>"}}

The HTML page must:
- Have <html>, <head>, <body> tags
- Include <link rel="stylesheet" href="dashboard.css" /> in <head>
- Use class="db-page" on the outermost container
- Use class="db-grid" for the visual grid
- Fit within 1280x720 pixels
- Contain between 3 and 8 data-pbi visuals
- Use ONLY classes from the CSS catalog above
- Contain realistic placeholder values (e.g. "$1.2M", "847", "Q4 2025")

Never wrap the JSON in markdown fences. Do not add prose before or after.
"""


def generate_mockup(
    *,
    prompt: str,
    schema: ModelSchema,
    client: Any,
) -> str:
    """Call Claude to generate an annotated HTML mockup, then validate it.

    Returns the raw HTML string.
    Raises ValidationError if Claude references measures/columns not in schema.
    Raises ValueError if Claude's response cannot be parsed.
    """
    user_message = _build_user_message(prompt, schema)
    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    html = _extract_html(response)
    validate_mockup(html, schema)
    return html


def _build_user_message(prompt: str, schema: ModelSchema) -> str:
    measure_lines = "\n".join(
        f"  - {m.name} (return_type: {m.return_type}, table: {m.table})"
        for m in schema.measures
    )
    table_lines = "\n".join(
        f"  - {t.name}: columns [{', '.join(c.name for c in t.columns)}]"
        for t in schema.tables
    )
    return (
        f"DASHBOARD INTENT:\n{prompt}\n\n"
        f"SEMANTIC MODEL:\n"
        f"  Measures:\n{measure_lines}\n\n"
        f"  Tables:\n{table_lines}\n\n"
        "Generate a dashboard HTML mockup that addresses the intent above using "
        "only the measures and columns listed. Do not reference any name not in this list."
    )


def _extract_html(response: Any) -> str:
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text = str(block.text)
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse generator JSON: {e}") from e
            if "html" not in parsed:
                raise ValueError(
                    f"Generator response missing 'html' key. Keys found: {list(parsed.keys())}"
                )
            return str(parsed["html"])
    raise ValueError("No text block in generator response")
