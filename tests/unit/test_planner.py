"""Tests for the measure planner."""
import json
from unittest.mock import MagicMock

import pytest

from simbi_mcp.semantic.planner import plan_measures
from simbi_mcp.types import (
    ColumnProfile,
    ColumnRole,
    DatasetProfile,
    MeasurePlan,
)


@pytest.fixture
def sample_profile() -> DatasetProfile:
    return DatasetProfile(
        source_path="/tmp/sales.csv",
        table_name="sales",
        row_count=100,
        columns=[
            ColumnProfile(
                name="Revenue", dtype="Float64", role=ColumnRole.MEASURE,
                null_count=0, distinct_count=99, sample_values=[1.0, 2.0],
            ),
            ColumnProfile(
                name="Region", dtype="String", role=ColumnRole.DIMENSION,
                null_count=0, distinct_count=4, sample_values=["N", "S"],
            ),
        ],
    )


def _fake_anthropic_response(measures: list[dict]) -> MagicMock:
    """Mimic the Messages API response shape."""
    response = MagicMock()
    response.content = [MagicMock(type="text", text=json.dumps({"measures": measures}))]
    return response


def test_planner_returns_list_of_measure_plans(sample_profile: DatasetProfile) -> None:
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_anthropic_response([
        {
            "name": "Total Revenue",
            "expression": "SUM('sales'[Revenue])",
            "return_type": "currency",
            "rationale": "User asked for revenue overview",
        },
    ])

    plans = plan_measures(
        prompt="Show me revenue by region",
        profile=sample_profile,
        client=fake_client,
    )

    assert len(plans) == 1
    assert isinstance(plans[0], MeasurePlan)
    assert plans[0].name == "Total Revenue"
    assert plans[0].expression == "SUM('sales'[Revenue])"


def test_planner_rejects_measures_referencing_unknown_columns(
    sample_profile: DatasetProfile,
) -> None:
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_anthropic_response([
        {
            "name": "Bogus",
            "expression": "SUM('sales'[NonexistentColumn])",
            "return_type": "number",
            "rationale": "hallucinated",
        },
    ])

    with pytest.raises(ValueError, match="references unknown column"):
        plan_measures(
            prompt="anything",
            profile=sample_profile,
            client=fake_client,
        )


def test_planner_passes_profile_into_prompt(sample_profile: DatasetProfile) -> None:
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_anthropic_response([])

    plan_measures(prompt="x", profile=sample_profile, client=fake_client)

    call_kwargs = fake_client.messages.create.call_args.kwargs
    user_message = call_kwargs["messages"][0]["content"]
    assert "Revenue" in user_message
    assert "Region" in user_message
    assert "sales" in user_message


def test_planner_raises_on_malformed_json(sample_profile: DatasetProfile) -> None:
    fake_client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock(type="text", text="not json at all")]
    fake_client.messages.create.return_value = response

    with pytest.raises(ValueError, match="parse"):
        plan_measures(prompt="x", profile=sample_profile, client=fake_client)
