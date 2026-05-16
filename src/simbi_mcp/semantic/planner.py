"""Measure planner — turns user intent + dataset profile into MeasurePlans."""
from __future__ import annotations

import json
import re
from typing import Any, cast

from simbi_mcp.types import DatasetProfile, MeasurePlan

_MODEL = "claude-opus-4-7"
_MAX_TOKENS = 2048

_SYSTEM_PROMPT = """You design Power BI measures.

Given a user's dashboard intent and a dataset profile, produce a JSON list of
DAX measures that will support the requested analysis. Stay grounded in the
provided columns — never invent a column name. Prefer a small, well-chosen set
(3-7 measures) over an exhaustive enumeration.

Respond with strict JSON of the form:
{
  "measures": [
    {
      "name": "<measure name, title case>",
      "expression": "<valid DAX>",
      "return_type": "currency|number|percentage|integer",
      "rationale": "<one sentence on why this measure>"
    }
  ]
}

Do not wrap the JSON in markdown fences. Do not add prose before or after.
"""

_COLUMN_REF = re.compile(r"\[([^\]]+)\]")


def plan_measures(
    *,
    prompt: str,
    profile: DatasetProfile,
    client: Any,
) -> list[MeasurePlan]:
    """Ask Claude for measure plans; validate against the profile.

    `client` is an Anthropic client (or a mock with the same interface).
    """
    user_message = _build_user_message(prompt, profile)
    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    text = _extract_text(response)
    parsed = _parse_json(text)
    plans = [MeasurePlan(**m) for m in parsed.get("measures", [])]
    _validate_columns(plans, profile)
    return plans


def _build_user_message(prompt: str, profile: DatasetProfile) -> str:
    column_lines = []
    for c in profile.columns:
        samples = ", ".join(repr(v) for v in c.sample_values[:3])
        column_lines.append(
            f"  - {c.name} ({c.dtype}, role={c.role.value}, "
            f"distinct={c.distinct_count}, samples=[{samples}])"
        )
    return (
        f"USER INTENT:\n{prompt}\n\n"
        f"DATASET PROFILE:\n"
        f"  table: '{profile.table_name}'\n"
        f"  rows: {profile.row_count}\n"
        f"  columns:\n" + "\n".join(column_lines)
    )


def _extract_text(response: Any) -> str:
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return str(block.text)
    raise ValueError("No text block in response")


def _parse_json(text: str) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(text))
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse planner JSON: {e}") from e


def _validate_columns(plans: list[MeasurePlan], profile: DatasetProfile) -> None:
    valid_columns = {c.name for c in profile.columns}
    for plan in plans:
        refs = _COLUMN_REF.findall(plan.expression)
        for ref in refs:
            if ref not in valid_columns:
                raise ValueError(
                    f"Measure {plan.name!r} references unknown column {ref!r}. "
                    f"Available: {sorted(valid_columns)}"
                )
