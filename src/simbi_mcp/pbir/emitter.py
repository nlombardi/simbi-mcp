"""PBIR emitter — top-level async orchestrator for Phase 3.

Writes html + dashboard.css to a temp dir, renders in Chrome to extract
visual bounding boxes, builds PBIR JSON from annotations + schema, then
writes the complete Report folder structure.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from simbi_mcp.pbir.extractor import extract_visuals
from simbi_mcp.pbir.templates import build_visual_json
from simbi_mcp.pbir.theme import resolve_theme
from simbi_mcp.pbir.writer import write_report
from simbi_mcp.types import ModelSchema

_DASHBOARD_CSS = Path(__file__).parent.parent / "mockup" / "dashboard.css"


async def emit_pbir(
    *,
    html: str,
    schema: ModelSchema,
    report_name: str,
    output_dir: Path,
    semantic_model_rel_path: str | None = None,
    theme_path: Path | None = None,
) -> Path:
    """Render html in system Chrome, extract annotations, write the .Report folder.

    The .pbip and .SemanticModel are produced by Power BI Desktop / Power BI MCP
    and are NEVER touched by SimBI — SimBI only contributes the .Report folder.

    `theme_path` is an optional path to a partial PBIR theme JSON. When omitted,
    SimBI emits its opinionated default theme (Microsoft CY25SU10 colour science
    + SimBI's visualStyles for gridline-off, lean cards, consistent typography).
    A user theme deep-merges onto that default, so corp branding (typically just
    `dataColors`) does not erase SimBI's visualStyles opinions.

    Creates:
      output_dir/<report_name>.Report/        (PBIR report folder)

    Returns the path to the .Report folder that was written.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        html_file = tmp_path / "mockup.html"
        html_file.write_text(html, encoding="utf-8")
        shutil.copy(_DASHBOARD_CSS, tmp_path / "dashboard.css")

        nodes = await extract_visuals(html_file)

    visuals = [
        build_visual_json(node, z_order=i * 1000, schema=schema)
        for i, node in enumerate(nodes)
    ]

    theme = resolve_theme(user_theme_path=theme_path)

    return write_report(
        visuals=visuals,
        report_name=report_name,
        output_dir=output_dir,
        semantic_model_rel_path=semantic_model_rel_path,
        theme=theme,
    )
