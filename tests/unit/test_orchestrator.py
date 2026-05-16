"""Tests for the semantic-layer orchestrator."""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from simbi_mcp.semantic.orchestrator import create_semantic_model
from simbi_mcp.types import ModelSchema


@pytest.fixture
def fake_anthropic() -> MagicMock:
    """Anthropic client that returns one canned measure plan."""
    import json
    client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock(type="text", text=json.dumps({
        "measures": [{
            "name": "Total Revenue",
            "expression": "SUM(sales_small[Revenue])",
            "return_type": "currency",
            "rationale": "for the test",
        }],
    }))]
    client.messages.create.return_value = response
    return client


@pytest.fixture
def fake_pbi_client() -> AsyncMock:
    """PbiClient stub with canned TMDL schema response."""
    client = AsyncMock()
    client.create_table.return_value = None
    client.refresh_table.return_value = None
    client.create_measures.return_value = None
    client.get_raw_schema.return_value = (
        "table sales_small\n"
        "\tmeasure 'Total Revenue' = SUM(sales_small[Revenue])\n"
        "\t\tformatString: \\$#,0.00;(\\$#,0.00)\n"
        "\tcolumn Revenue\n"
        "\t\tdataType: double\n"
        "\tcolumn Region\n"
        "\t\tdataType: string\n"
    )
    return client


async def test_orchestrator_returns_model_schema(
    sales_small_csv: Path,
    fake_anthropic: MagicMock,
    fake_pbi_client: AsyncMock,
) -> None:
    schema = await create_semantic_model(
        prompt="Show revenue by region",
        dataset_path=sales_small_csv,
        anthropic_client=fake_anthropic,
        pbi_client=fake_pbi_client,
    )

    assert isinstance(schema, ModelSchema)
    assert schema.has_measure("Total Revenue")


async def test_orchestrator_calls_create_table_before_create_measures(
    sales_small_csv: Path,
    fake_anthropic: MagicMock,
    fake_pbi_client: AsyncMock,
) -> None:
    await create_semantic_model(
        prompt="x",
        dataset_path=sales_small_csv,
        anthropic_client=fake_anthropic,
        pbi_client=fake_pbi_client,
    )

    fake_pbi_client.create_table.assert_awaited_once()
    fake_pbi_client.create_measures.assert_awaited_once()
    # Verify ordering via method_calls list
    method_names = [call[0] for call in fake_pbi_client.method_calls]
    assert method_names.index("create_table") < method_names.index("create_measures")


async def test_orchestrator_calls_refresh_between_create_and_measures(
    sales_small_csv: Path,
    fake_anthropic: MagicMock,
    fake_pbi_client: AsyncMock,
) -> None:
    await create_semantic_model(
        prompt="x",
        dataset_path=sales_small_csv,
        anthropic_client=fake_anthropic,
        pbi_client=fake_pbi_client,
    )

    method_names = [call[0] for call in fake_pbi_client.method_calls]
    create_idx = method_names.index("create_table")
    refresh_idx = method_names.index("refresh_table")
    measures_idx = method_names.index("create_measures")
    assert create_idx < refresh_idx < measures_idx


async def test_orchestrator_propagates_create_table_failure(
    sales_small_csv: Path,
    fake_anthropic: MagicMock,
    fake_pbi_client: AsyncMock,
) -> None:
    fake_pbi_client.create_table.side_effect = RuntimeError("table create failed")

    with pytest.raises(RuntimeError, match="table create failed"):
        await create_semantic_model(
            prompt="x",
            dataset_path=sales_small_csv,
            anthropic_client=fake_anthropic,
            pbi_client=fake_pbi_client,
        )


async def test_orchestrator_passes_all_measures_to_create_measures(
    sales_small_csv: Path,
    fake_anthropic: MagicMock,
    fake_pbi_client: AsyncMock,
) -> None:
    await create_semantic_model(
        prompt="x",
        dataset_path=sales_small_csv,
        anthropic_client=fake_anthropic,
        pbi_client=fake_pbi_client,
    )

    call_kwargs = fake_pbi_client.create_measures.call_args.kwargs
    assert call_kwargs["table_name"] == "sales_small"
    assert len(call_kwargs["measures"]) == 1
    assert call_kwargs["measures"][0].name == "Total Revenue"
