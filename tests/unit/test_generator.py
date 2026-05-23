"""Tests for the HTML mockup generator."""
import json
from unittest.mock import MagicMock

import pytest

from simbi_mcp.mockup.generator import generate_mockup
from simbi_mcp.mockup.validator import ValidationError
from simbi_mcp.types import (
    ModelColumn,
    ModelMeasure,
    ModelSchema,
    ModelTable,
)


@pytest.fixture
def schema() -> ModelSchema:
    return ModelSchema(
        tables=[
            ModelTable(name="sales", columns=[ModelColumn(name="Region"), ModelColumn(name="OrderDate")]),
        ],
        measures=[
            ModelMeasure(
                name="Total Revenue",
                table="sales",
                expression="SUM(sales[Revenue])",
                return_type="currency",
            ),
        ],
        relationships=[],
    )


def _fake_response(html: str) -> MagicMock:
    """Mimic Messages API response with JSON-wrapped HTML."""
    resp = MagicMock()
    resp.content = [
        MagicMock(type="text", text=json.dumps({"html": html}))
    ]
    return resp


_VALID_HTML = (
    '<html><head><link rel="stylesheet" href="dashboard.css"/></head>'
    '<body class="db-page"><div class="db-grid">'
    '<div data-pbi="card" data-pbi-measure="Total Revenue" class="db-card db-col-1">'
    '<div class="db-label">Revenue</div>'
    '<div class="db-value">$1.2M</div></div>'
    '</div></body></html>'
)


def test_generate_mockup_returns_html_string(schema: ModelSchema) -> None:
    client = MagicMock()
    client.messages.create.return_value = _fake_response(_VALID_HTML)

    result = generate_mockup(prompt="Show revenue", schema=schema, client=client)

    assert isinstance(result, str)
    assert "data-pbi" in result


def test_generate_mockup_calls_claude_with_schema_context(schema: ModelSchema) -> None:
    client = MagicMock()
    client.messages.create.return_value = _fake_response(_VALID_HTML)

    generate_mockup(prompt="Show revenue by region", schema=schema, client=client)

    kwargs = client.messages.create.call_args.kwargs
    user_content = kwargs["messages"][0]["content"]
    assert "Total Revenue" in user_content
    assert "sales" in user_content
    assert "Region" in user_content


def test_generate_mockup_includes_prompt_in_message(schema: ModelSchema) -> None:
    client = MagicMock()
    client.messages.create.return_value = _fake_response(_VALID_HTML)

    generate_mockup(prompt="I need a weekly KPI view", schema=schema, client=client)

    kwargs = client.messages.create.call_args.kwargs
    user_content = kwargs["messages"][0]["content"]
    assert "weekly KPI view" in user_content


def test_generate_mockup_raises_on_hallucinated_measure(schema: ModelSchema) -> None:
    bad_html = (
        '<html><body><div data-pbi="card" '
        'data-pbi-measure="Hallucinated KPI"></div></body></html>'
    )
    client = MagicMock()
    client.messages.create.return_value = _fake_response(bad_html)

    with pytest.raises(ValidationError, match="Hallucinated KPI"):
        generate_mockup(prompt="x", schema=schema, client=client)


def test_generate_mockup_raises_on_malformed_json(schema: ModelSchema) -> None:
    resp = MagicMock()
    resp.content = [MagicMock(type="text", text="not json")]
    client = MagicMock()
    client.messages.create.return_value = resp

    with pytest.raises(ValueError, match="parse"):
        generate_mockup(prompt="x", schema=schema, client=client)


def test_generate_mockup_raises_when_html_key_missing(schema: ModelSchema) -> None:
    resp = MagicMock()
    resp.content = [MagicMock(type="text", text=json.dumps({"wrong_key": "..."}))]
    client = MagicMock()
    client.messages.create.return_value = resp

    with pytest.raises(ValueError, match="html"):
        generate_mockup(prompt="x", schema=schema, client=client)


def test_system_prompt_contains_annotation_spec(schema: ModelSchema) -> None:
    client = MagicMock()
    client.messages.create.return_value = _fake_response(_VALID_HTML)

    generate_mockup(prompt="x", schema=schema, client=client)

    kwargs = client.messages.create.call_args.kwargs
    system = kwargs["system"]
    assert "data-pbi" in system
    assert "card" in system
    assert "columnChart" in system
    assert "db-page" in system
