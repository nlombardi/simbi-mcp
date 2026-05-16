"""Shared Pydantic models for the SimBI semantic layer.

These types form the contract between:
- profiler.py (produces DatasetProfile)
- planner.py (produces list[MeasurePlan])
- pbi_client.py / schema_reader.py (produce ModelSchema)
- downstream phases (consume ModelSchema as input)
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ColumnRole(StrEnum):
    """How a column should be used in dashboards."""

    MEASURE = "measure"      # numeric facts (sums, averages)
    DIMENSION = "dimension"  # categories (group-by, axis)
    DATE = "date"            # temporal axis
    ID = "id"                # identifiers (not for aggregation)


class ColumnProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    dtype: str
    role: ColumnRole
    null_count: int = Field(ge=0)
    distinct_count: int = Field(ge=0)
    sample_values: list[str | int | float | bool | None]


class DatasetProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_path: str
    table_name: str
    row_count: int = Field(ge=0)
    columns: list[ColumnProfile]


class MeasurePlan(BaseModel):
    """A measure the planner wants to create."""

    model_config = ConfigDict(frozen=True)

    name: str
    expression: str       # DAX expression
    return_type: str      # currency | number | percentage | integer
    rationale: str        # why the planner chose this


class ModelTable(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    columns: list[str]


class ModelMeasure(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    table: str
    expression: str
    return_type: str


class ModelRelationship(BaseModel):
    model_config = ConfigDict(frozen=True)

    from_table: str
    from_column: str
    to_table: str
    to_column: str


class ModelSchema(BaseModel):
    """Authoritative schema of a created semantic model.

    Downstream phases (HTML generator, PBIR emitter) consume this as their
    source of truth for what measures/columns exist.
    """

    model_config = ConfigDict(frozen=True)

    tables: list[ModelTable]
    measures: list[ModelMeasure]
    relationships: list[ModelRelationship]

    def has_measure(self, name: str) -> bool:
        return any(m.name == name for m in self.measures)

    def find_measure(self, name: str) -> ModelMeasure:
        for m in self.measures:
            if m.name == name:
                return m
        raise KeyError(f"No measure named {name!r}")
