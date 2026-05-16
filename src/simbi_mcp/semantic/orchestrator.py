"""Semantic layer orchestrator — the public entry point of Phase 1.

Composes profiler + planner + pbi_client + schema_reader into one async
function: create_semantic_model(prompt, dataset_path) -> ModelSchema.

Call sequence (order matters):
  1. profile_dataset — synchronous, derives column types
  2. plan_measures — LLM call, needs profile
  3. pbi_client.create_table — registers schema with Power BI model
  4. pbi_client.refresh_table — loads data (must precede measure computation)
  5. pbi_client.create_measures — adds DAX measures in one batched call
  6. pbi_client.get_raw_schema — exports TMDL for schema readback
  7. parse_tmdl_schema — converts TMDL string to typed ModelSchema
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from simbi_mcp.semantic.pbi_client import PbiClient
from simbi_mcp.semantic.planner import plan_measures
from simbi_mcp.semantic.profiler import profile_dataset
from simbi_mcp.semantic.schema_reader import parse_tmdl_schema
from simbi_mcp.types import ModelSchema


async def create_semantic_model(
    *,
    prompt: str,
    dataset_path: Path,
    anthropic_client: Any,
    pbi_client: PbiClient,
) -> ModelSchema:
    """Profile dataset → plan measures → create model → return schema."""
    profile = profile_dataset(dataset_path)

    plans = plan_measures(
        prompt=prompt,
        profile=profile,
        client=anthropic_client,
    )

    await pbi_client.create_table(profile)
    await pbi_client.refresh_table(profile.table_name)
    await pbi_client.create_measures(
        table_name=profile.table_name,
        measures=plans,
    )

    tmdl = await pbi_client.get_raw_schema()
    return parse_tmdl_schema(tmdl)
