"""Shared Pydantic models for the SimBI semantic layer.

These types form the contract between schema_reader.py (produces ModelSchema)
and downstream phases (consume ModelSchema as input).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelColumn(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    data_type: str = "string"


class ModelTable(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    columns: list[ModelColumn]


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


class FieldParameter(BaseModel):
    """A field parameter: a calc table that swaps which measure a chart shows."""

    model_config = ConfigDict(frozen=True)

    name: str            # parameter + table name, e.g. "Indicator"
    measures: list[str]  # measure names to swap between, display order preserved


class Bookmark(BaseModel):
    """A page-state bookmark: captured aspects + which visuals it targets.

    captures: subset of {"visibility", "data", "display", "currentPage"}.
    target: visual ids the bookmark applies to; [] means all visuals.
    visible/hidden: visual ids shown/hidden (used when captures includes "visibility").
    """

    model_config = ConfigDict(frozen=True)

    name: str
    captures: set[str] = Field(default_factory=set)
    target: list[str] = Field(default_factory=list)
    visible: list[str] = Field(default_factory=list)
    hidden: list[str] = Field(default_factory=list)


class ColumnProfile(BaseModel):
    """One column's stats from analyze_data_source, before TMDL authoring."""

    model_config = ConfigDict(frozen=True)

    name: str
    polars_dtype: str
    tmdl_type: str
    null_count: int
    null_pct: float
    distinct_count: int
    sample_values: list[str] = Field(default_factory=list)
    min: str | None = None
    max: str | None = None
    hints: list[str] = Field(default_factory=list)


class TableProfile(BaseModel):
    """One table's (sheet or CSV) profile from analyze_data_source."""

    model_config = ConfigDict(frozen=True)

    table_name: str
    row_count: int
    columns: list[ColumnProfile]
    hints: list[str] = Field(default_factory=list)


class DataSourceProfile(BaseModel):
    """Full analyze_data_source result: one or more tables from one file."""

    model_config = ConfigDict(frozen=True)

    source_path: str
    tables: list[TableProfile]
