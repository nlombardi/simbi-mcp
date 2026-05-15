"""Shared pytest fixtures."""
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sales_small_csv(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "datasets" / "sales_small.csv"
    assert path.exists(), f"Missing fixture: {path}"
    return path
