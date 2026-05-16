"""Tests for the dataset profiler."""
from pathlib import Path

import pytest

from simbi_mcp.semantic.profiler import profile_dataset
from simbi_mcp.types import ColumnRole


def test_profile_sales_small_returns_one_row_per_column(sales_small_csv: Path) -> None:
    profile = profile_dataset(sales_small_csv)
    assert profile.table_name == "sales_small"
    assert profile.row_count >= 10
    column_names = {c.name for c in profile.columns}
    assert column_names == {
        "OrderID", "OrderDate", "Region", "Product",
        "Category", "UnitsSold", "UnitPrice", "Revenue",
    }


def test_revenue_classified_as_measure(sales_small_csv: Path) -> None:
    profile = profile_dataset(sales_small_csv)
    revenue = next(c for c in profile.columns if c.name == "Revenue")
    assert revenue.role is ColumnRole.MEASURE


def test_region_classified_as_dimension(sales_small_csv: Path) -> None:
    profile = profile_dataset(sales_small_csv)
    region = next(c for c in profile.columns if c.name == "Region")
    assert region.role is ColumnRole.DIMENSION


def test_order_date_classified_as_date(sales_small_csv: Path) -> None:
    profile = profile_dataset(sales_small_csv)
    order_date = next(c for c in profile.columns if c.name == "OrderDate")
    assert order_date.role is ColumnRole.DATE


def test_order_id_classified_as_id(sales_small_csv: Path) -> None:
    profile = profile_dataset(sales_small_csv)
    order_id = next(c for c in profile.columns if c.name == "OrderID")
    assert order_id.role is ColumnRole.ID


def test_sample_values_are_truncated(sales_small_csv: Path) -> None:
    profile = profile_dataset(sales_small_csv)
    for c in profile.columns:
        assert len(c.sample_values) <= 5


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        profile_dataset(tmp_path / "nope.csv")
