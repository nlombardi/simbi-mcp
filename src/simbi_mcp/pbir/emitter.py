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
from simbi_mcp.pbir.writer import write_report, write_semantic_model_stub
from simbi_mcp.types import ModelSchema

_DASHBOARD_CSS = Path(__file__).parent.parent / "mockup" / "dashboard.css"


async def emit_pbir(
    *,
    html: str,
    schema: ModelSchema,
    report_name: str,
    output_dir: Path,
    semantic_model_rel_path: str | None = None,
) -> Path:
    """Render html in system Chrome, extract annotations, write complete .pbip project.

    Creates:
      output_dir/<report_name>.pbip           (project entry point — open this in PBI Desktop)
      output_dir/<report_name>.Report/        (PBIR report folder)
      output_dir/<report_name>.SemanticModel/ (minimal BIM model stub)

    Returns the path to the .pbip project file.
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

    write_report(
        visuals=visuals,
        report_name=report_name,
        output_dir=output_dir,
        semantic_model_rel_path=semantic_model_rel_path,
    )
    # Only generate the stub when no SemanticModel exists yet — preserves a real
    # model written by the MS Power BI MCP or saved from Power BI Desktop.
    if not (output_dir / f"{report_name}.SemanticModel").exists():
        write_semantic_model_stub(schema, report_name, output_dir)
    return output_dir / f"{report_name}.pbip"
