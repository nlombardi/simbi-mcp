"""Tests for the Microsoft Power BI MCP client wrapper."""
from unittest.mock import AsyncMock

import pytest

from simbi_mcp.semantic.pbi_client import PbiClient
from simbi_mcp.types import (
    ColumnProfile,
    ColumnRole,
    DatasetProfile,
    MeasurePlan,
)


@pytest.fixture
def profile() -> DatasetProfile:
    return DatasetProfile(
        source_path="Q:/dev/sales.csv",
        table_name="sales",
        row_count=10,
        columns=[
            ColumnProfile(
                name="OrderID", dtype="Int64", role=ColumnRole.ID,
                null_count=0, distinct_count=10, sample_values=[1001],
            ),
            ColumnProfile(
                name="OrderDate", dtype="Date", role=ColumnRole.DATE,
                null_count=0, distinct_count=10, sample_values=["2025-01-01"],
            ),
            ColumnProfile(
                name="Region", dtype="String", role=ColumnRole.DIMENSION,
                null_count=0, distinct_count=4, sample_values=["North"],
            ),
            ColumnProfile(
                name="Revenue", dtype="Float64", role=ColumnRole.MEASURE,
                null_count=0, distinct_count=10, sample_values=[1.0],
            ),
        ],
    )


@pytest.fixture
def measures() -> list[MeasurePlan]:
    return [
        MeasurePlan(
            name="Total Revenue",
            expression="SUM(sales[Revenue])",
            return_type="currency",
            rationale="total",
        ),
        MeasurePlan(
            name="Order Count",
            expression="COUNTROWS(sales)",
            return_type="integer",
            rationale="count",
        ),
    ]


async def test_create_table_calls_table_operations(profile: DatasetProfile) -> None:
    session = AsyncMock()
    session.call_tool.return_value = AsyncMock(content=[{"success": True}])

    client = PbiClient(session=session)
    await client.create_table(profile)

    session.call_tool.assert_awaited_once()
    tool_name = session.call_tool.call_args.args[0]
    assert tool_name == "table_operations"
    args = session.call_tool.call_args.kwargs["arguments"]
    assert args["operation"] == "Create"
    assert args["definitions"][0]["Name"] == "sales"
    # Columns must be present and contain all 4 columns
    assert len(args["definitions"][0]["Columns"]) == 4
    # MExpression must reference the CSV path
    assert "sales.csv" in args["definitions"][0]["MExpression"]


async def test_create_table_maps_roles_to_summarize_by(profile: DatasetProfile) -> None:
    session = AsyncMock()
    session.call_tool.return_value = AsyncMock(content=[{"success": True}])

    client = PbiClient(session=session)
    await client.create_table(profile)

    cols = {
        c["Name"]: c
        for c in session.call_tool.call_args.kwargs["arguments"]["definitions"][0]["Columns"]
    }
    assert cols["OrderID"]["SummarizeBy"] == "None"
    assert cols["OrderDate"]["SummarizeBy"] == "None"
    assert cols["Region"]["SummarizeBy"] == "None"
    assert cols["Revenue"]["SummarizeBy"] == "Sum"


async def test_refresh_table_calls_table_operations(profile: DatasetProfile) -> None:
    session = AsyncMock()
    session.call_tool.return_value = AsyncMock(content=[{"success": True}])

    client = PbiClient(session=session)
    await client.refresh_table("sales")

    session.call_tool.assert_awaited_once()
    tool_name = session.call_tool.call_args.args[0]
    assert tool_name == "table_operations"
    args = session.call_tool.call_args.kwargs["arguments"]
    assert args["operation"] == "RefreshWithXMLA"


async def test_create_measures_batches_all_in_one_call(
    measures: list[MeasurePlan],
) -> None:
    session = AsyncMock()
    session.call_tool.return_value = AsyncMock(content=[{"success": True}])

    client = PbiClient(session=session)
    await client.create_measures(table_name="sales", measures=measures)

    session.call_tool.assert_awaited_once()
    tool_name = session.call_tool.call_args.args[0]
    assert tool_name == "measure_operations"
    args = session.call_tool.call_args.kwargs["arguments"]
    assert args["operation"] == "Create"
    assert len(args["definitions"]) == 2
    assert args["definitions"][0]["Name"] == "Total Revenue"
    assert args["definitions"][0]["TableName"] == "sales"
    assert args["definitions"][1]["Name"] == "Order Count"


async def test_create_measures_maps_return_type_to_format_string(
    measures: list[MeasurePlan],
) -> None:
    session = AsyncMock()
    session.call_tool.return_value = AsyncMock(content=[{"success": True}])

    client = PbiClient(session=session)
    await client.create_measures(table_name="sales", measures=measures)

    defs = session.call_tool.call_args.kwargs["arguments"]["definitions"]
    currency_def = next(d for d in defs if d["Name"] == "Total Revenue")
    integer_def = next(d for d in defs if d["Name"] == "Order Count")
    assert "FormatString" in currency_def
    assert "FormatString" in integer_def
    assert "$" in currency_def["FormatString"]
    assert "$" not in integer_def["FormatString"]


async def test_get_raw_schema_calls_model_operations() -> None:
    session = AsyncMock()
    # Simulate the MCP returning a TMDL string in some response field
    tmdl_doc = "table sales\n    measure 'Total Revenue' = SUM(sales[Revenue])\n"
    session.call_tool.return_value = AsyncMock(
        content=[{"success": True, "tmdlDocument": tmdl_doc}]
    )

    client = PbiClient(session=session)
    tmdl = await client.get_raw_schema()

    session.call_tool.assert_awaited_once()
    tool_name = session.call_tool.call_args.args[0]
    assert tool_name == "model_operations"
    args = session.call_tool.call_args.kwargs["arguments"]
    assert args["operation"] == "ExportTMDL"
    assert isinstance(tmdl, str)
    assert "sales" in tmdl
