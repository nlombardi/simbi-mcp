"""PBIR emitter — top-level async orchestrator for Phase 3.

Writes html + dashboard.css to a temp dir, renders in Chrome to extract
visual bounding boxes, builds PBIR JSON from annotations + schema, then
writes the complete Report folder structure.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from simbi_mcp.pbir.bookmarks import build_bookmark_json, resolve_targets
from simbi_mcp.pbir.extractor import VisualNode, extract_visuals
from simbi_mcp.pbir.semantic_patcher import patch_field_parameters
from simbi_mcp.pbir.styling import page_background_card
from simbi_mcp.pbir.templates import build_visual_json
from simbi_mcp.pbir.theme import resolve_theme
from simbi_mcp.pbir.writer import PageSpec, _new_guid, write_report
from simbi_mcp.types import Bookmark, FieldParameter, ModelSchema

_DASHBOARD_CSS = Path(__file__).parent.parent / "mockup" / "dashboard.css"


def _resolve_semantic_model_dir(output_dir: Path, report_name: str, semantic_model_rel_path: str | None) -> Path:
    """Resolve the SemanticModel dir the same way Power BI resolves definition.pbir's
    byPath: relative to the .Report folder (output_dir/<name>.Report), not output_dir."""
    rel = semantic_model_rel_path or f"../{report_name}.SemanticModel"
    return (output_dir / f"{report_name}.Report" / rel).resolve()


def collect_field_params(nodes: list[VisualNode]) -> list[FieldParameter]:
    """Extract FieldParameter definitions from field-param annotation nodes."""
    params: list[FieldParameter] = []
    for node in nodes:
        if node.attrs.get("data-pbi") == "field-param":
            name = node.attrs["data-pbi-param-name"]
            measures = [
                m.strip()
                for m in node.attrs["data-pbi-measures"].split(",")
                if m.strip()
            ]
            params.append(FieldParameter(name=name, measures=measures))
    return params


def _split(attr: str) -> list[str]:
    return [s.strip() for s in attr.split(",") if s.strip()]


def collect_bookmarks(nodes: list[VisualNode]) -> list[Bookmark]:
    """Extract Bookmark definitions from data-pbi="bookmark" annotation nodes."""
    out: list[Bookmark] = []
    for node in nodes:
        if node.attrs.get("data-pbi") == "bookmark":
            a = node.attrs
            out.append(Bookmark(
                name=a["data-pbi-name"],
                captures=set(_split(a.get("data-pbi-captures", ""))),
                target=_split(a.get("data-pbi-target", "")) if a.get("data-pbi-target", "all") != "all" else [],
                visible=_split(a.get("data-pbi-visible", "")),
                hidden=_split(a.get("data-pbi-hidden", "")),
            ))
    return out


def resolve_button_actions(visuals: list[dict], bookmark_name_to_guid: dict[str, str]) -> None:
    """Rewrite each visual's stashed simbiButtonAction into a real visualLink.

    Mutates visuals in place. Bookmark actions become a visualContainerObjects.visualLink
    referencing the bookmark's generated name id. Non-bookmark actions are simply
    de-stashed (the button still renders; navigation wiring is out of scope here).
    """
    for v in visuals:
        action = v.pop("simbiButtonAction", None)
        if not action:
            continue
        if action.get("type") == "bookmark":
            bm_name = action.get("bookmark", "")
            guid = bookmark_name_to_guid.get(bm_name)
            if guid is None:
                raise ValueError(
                    f"Button references unknown bookmark {bm_name!r}. "
                    f"Known bookmarks: {sorted(bookmark_name_to_guid)}"
                )
            v["visual"].setdefault("visualContainerObjects", {})["visualLink"] = [
                {"properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "type": {"expr": {"Literal": {"Value": "'Bookmark'"}}},
                    "bookmark": {"expr": {"Literal": {"Value": f"'{guid}'"}}},
                }}
            ]


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

        extract_result = await extract_visuals(html_file)
    nodes = extract_result.nodes

    # Bookmark nodes are metadata, not rendered visuals — exclude them from
    # build_visual_json. Field-param nodes DO render a slicer, so keep those.
    visual_nodes = [n for n in nodes if n.attrs.get("data-pbi") != "bookmark"]
    field_params_map = {fp.name: fp.measures for fp in collect_field_params(nodes)}

    # Group visual nodes by page. Nodes from single-page HTML all have page_index=0.
    page_groups: dict[int, tuple[str, str, list]] = {}
    for node in visual_nodes:
        idx = node.page_index
        if idx not in page_groups:
            page_groups[idx] = (node.page_name, node.page_background, [])
        page_groups[idx][2].append(node)

    theme = resolve_theme(user_theme_path=theme_path)

    field_params = collect_field_params(nodes)
    if field_params:
        semantic_model_dir = _resolve_semantic_model_dir(output_dir, report_name, semantic_model_rel_path)
        measure_tables = {m.name: m.table for m in schema.measures}
        patch_field_parameters(field_params, semantic_model_dir, measure_tables)

    # Build PageSpec list — one entry per page group, in page_index order.
    page_specs: list[PageSpec] = []
    all_visuals: list[dict] = []
    for idx in sorted(page_groups):
        page_name, page_bg, group_nodes = page_groups[idx]
        page_visuals = [
            build_visual_json(node, z_order=i * 1000, schema=schema, field_params=field_params_map)
            for i, node in enumerate(group_nodes)
        ]
        all_visuals.extend(page_visuals)
        page_specs.append(PageSpec(
            visuals=page_visuals,
            display_name=page_name,
            background=page_background_card(page_bg),
        ))

    # Bookmarks reference the first page's GUID (multi-page bookmark scoping
    # is not yet supported — bookmarks always anchor to page 0).
    bookmarks_meta = collect_bookmarks(nodes)
    bookmark_dicts: list[dict] | None = None
    if bookmarks_meta:
        page_guid = _new_guid()
        page_specs[0].guid = page_guid
        id_to_guid = {v["simbiId"]: v["name"] for v in all_visuals if "simbiId" in v}
        visual_types = {v["name"]: v["visual"]["visualType"] for v in all_visuals}
        bookmark_dicts = []
        name_to_guid: dict[str, str] = {}
        for bm in bookmarks_meta:
            resolved = resolve_targets(bm, id_to_guid)
            bj = build_bookmark_json(resolved, page_guid, visual_types)
            name_to_guid[bm.name] = bj["name"]
            bookmark_dicts.append(bj)
        resolve_button_actions(all_visuals, name_to_guid)

    return write_report(
        pages=page_specs,
        report_name=report_name,
        output_dir=output_dir,
        semantic_model_rel_path=semantic_model_rel_path,
        theme=theme,
        bookmarks=bookmark_dicts,
    )
