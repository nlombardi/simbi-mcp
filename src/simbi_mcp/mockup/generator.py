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
