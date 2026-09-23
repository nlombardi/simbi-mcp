"""Bookmark JSON builders and author-id -> emitted-guid resolution.

Structure verified against Power BI-generated bookmark samples in
resources/PowerBI_Files/Microsoft/.../bookmarks/*.bookmark.json.
"""
from __future__ import annotations

import uuid
from typing import Any

from simbi_mcp.types import Bookmark

_BOOKMARK_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report"
    "/definition/bookmark/1.4.0/schema.json"
)


def resolve_targets(bookmark: Bookmark, id_to_guid: dict[str, str]) -> Bookmark:
    """Return a copy of `bookmark` with author ids replaced by emitted guids.

    Raises ValueError naming the first id that has no emitted visual — a
    dangling reference would silently break the bookmark in Power BI Desktop.
    """
    def m(ids: list[str]) -> list[str]:
        out = []
        for i in ids:
            if i not in id_to_guid:
                raise ValueError(
                    f"Bookmark {bookmark.name!r} references unknown visual id {i!r}. "
                    f"Known ids: {sorted(id_to_guid)}"
                )
            out.append(id_to_guid[i])
        return out
    return bookmark.model_copy(update={
        "target": m(bookmark.target),
        "visible": m(bookmark.visible),
        "hidden": m(bookmark.hidden),
    })


def build_bookmark_json(
    bookmark: Bookmark, page_guid: str, visual_types: dict[str, str]
) -> dict[str, Any]:
    """Build a .bookmark.json dict. `bookmark` must already hold guids
    (call resolve_targets first). `visual_types` maps guid -> PBIR visualType."""
    name_id = "Bookmark" + uuid.uuid4().hex
    containers: dict[str, Any] = {}
    for guid in bookmark.hidden:
        sv: dict[str, Any] = {"visualType": visual_types.get(guid, ""), "objects": {}, "display": {"mode": "hidden"}}
        containers[guid] = {"singleVisual": sv}
    for guid in bookmark.visible:
        sv = {"visualType": visual_types.get(guid, ""), "objects": {}}
        containers[guid] = {"singleVisual": sv}

    target_guids: list[str] = []
    seen: set[str] = set()
    for g in list(bookmark.target) + list(bookmark.visible) + list(bookmark.hidden):
        if g not in seen:
            seen.add(g)
            target_guids.append(g)

    options: dict[str, Any] = {}
    if target_guids:
        options["applyOnlyToTargetVisuals"] = True
        options["targetVisualNames"] = target_guids
    if "currentPage" not in bookmark.captures:
        options["suppressActiveSection"] = True
    if "data" not in bookmark.captures:
        options["suppressData"] = True

    return {
        "$schema": _BOOKMARK_SCHEMA,
        "displayName": bookmark.name,
        "name": name_id,
        "options": options,
        "explorationState": {
            "version": "1.3",
            "activeSection": page_guid,
            "sections": {page_guid: {"visualContainers": containers}},
        },
    }
