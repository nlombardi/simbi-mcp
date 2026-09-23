"""Validator for emitted PBIR report folders.

Verifies strict Power BI Desktop compatibility rules:
1. All visual container position coordinates (x, y, width, height, z, tabOrder)
   must be 32-bit integers (never floats/decimals).
2. baseTheme in report.json must reference CY25SU10 and CY25SU10.json.
3. No legacy objects.section in report.json.
4. Button actions must reside in visualContainerObjects.visualLink (never visual.objects.action).
5. Standard shape objects must not contain unsupported properties (e.g. roundEdge).
6. Bookmarks in definition/bookmarks/*.bookmark.json must adhere to Fabric schema 1.4.0:
   - display.mode is strictly limited to ['maximize', 'spotlight', 'elevation', 'hidden'].
   - mode 'visible' is rejected (visible visuals must omit display).
   - Target visual GUIDs must exist in the report visuals.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class PBIRValidationError(ValueError):
    """Raised when an emitted PBIR report folder fails compatibility validation."""


def validate_pbir_report(report_dir: Path, raise_on_error: bool = True) -> list[str]:
    """Validate a .Report directory against Power BI Desktop PBIR rules.

    Returns a list of error strings. If raise_on_error is True and any error
    is found, raises PBIRValidationError.
    """
    errors: list[str] = []

    if not report_dir.is_dir():
        errors.append(f"Report directory does not exist: {report_dir}")
        if raise_on_error:
            raise PBIRValidationError("; ".join(errors))
        return errors

    # 1. Validate report.json
    report_json_path = report_dir / "definition" / "report.json"
    if not report_json_path.exists():
        errors.append("Missing definition/report.json")
    else:
        try:
            report_data = json.loads(report_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON in report.json: {exc.msg}")
            report_data = None

        if isinstance(report_data, dict):
            base_theme = (
                report_data.get("themeCollection", {})
                .get("baseTheme", {})
                .get("name")
            )
            if base_theme != "CY25SU10":
                errors.append(
                    f"report.json baseTheme.name must be 'CY25SU10', got {base_theme!r}"
                )

            # Check for obsolete objects.section
            objects = report_data.get("objects", {})
            if isinstance(objects, dict) and "section" in objects:
                errors.append(
                    "report.json contains legacy objects.section which conflicts with PBIR pages"
                )

            # Check resourcePackages
            packages = report_data.get("resourcePackages", [])
            has_cy25 = False
            for pkg in packages:
                for item in pkg.get("items", []):
                    if (
                        item.get("name") == "CY25SU10"
                        and item.get("path") == "BaseThemes/CY25SU10.json"
                    ):
                        has_cy25 = True
            if not has_cy25:
                errors.append(
                    "report.json resourcePackages does not declare BaseThemes/CY25SU10.json"
                )

    # 2. Validate BaseThemes/CY25SU10.json
    theme_file = report_dir / "StaticResources" / "SharedResources" / "BaseThemes" / "CY25SU10.json"
    if not theme_file.exists():
        errors.append("Missing StaticResources/SharedResources/BaseThemes/CY25SU10.json")
    else:
        try:
            theme_data = json.loads(theme_file.read_text(encoding="utf-8"))
            if not isinstance(theme_data, dict) or theme_data.get("name") != "CY25SU10":
                errors.append("BaseThemes/CY25SU10.json must have name 'CY25SU10'")
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON in BaseThemes/CY25SU10.json: {exc.msg}")

    # 3. Validate all visual.json files
    all_visual_guids: set[str] = set()
    pages_dir = report_dir / "definition" / "pages"
    if pages_dir.exists():
        for visual_file in pages_dir.glob("*/visuals/*/visual.json"):
            rel_path = visual_file.relative_to(report_dir).as_posix()
            try:
                raw_text = visual_file.read_text(encoding="utf-8")
                v_data: dict[str, Any] = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                errors.append(f"Invalid JSON in {rel_path}: {exc.msg}")
                continue

            v_name = v_data.get("name") or visual_file.parent.name
            all_visual_guids.add(v_name)

            # Check position coordinates
            position = v_data.get("position")
            if not isinstance(position, dict):
                errors.append(f"{rel_path}: missing or non-dict 'position' object")
            else:
                for coord in ("x", "y", "width", "height", "z", "tabOrder"):
                    if coord in position:
                        val = position[coord]
                        # Must be strictly int, not bool or float
                        if not isinstance(val, int) or isinstance(val, bool):
                            val_type = type(val).__name__
                            errors.append(
                                f"{rel_path}: position.{coord} must be an integer, "
                                f"got {val_type} ({val})"
                            )

            visual_inner = v_data.get("visual", {})
            if isinstance(visual_inner, dict):
                # Reject obsolete visual.objects.action (Power BI requires visualContainerObjects.visualLink)
                objs_inner = visual_inner.get("objects", {})
                if isinstance(objs_inner, dict) and "action" in objs_inner:
                    errors.append(
                        f"{rel_path}: invalid visual.objects.action; "
                        f"button actions must be in visualContainerObjects.visualLink"
                    )

                # Check for unsupported shape properties (e.g. roundEdge)
                objs = visual_inner.get("objects", {})
                if isinstance(objs, dict) and "shape" in objs:
                    shape_cards = objs.get("shape", [])
                    if isinstance(shape_cards, list):
                        for card in shape_cards:
                            props = card.get("properties", {})
                            if "roundEdge" in props:
                                errors.append(
                                    f"{rel_path}: unsupported property 'roundEdge' "
                                    f"in visual.objects.shape"
                                )

    # 4. Validate bookmarks
    bookmarks_dir = report_dir / "definition" / "bookmarks"
    if bookmarks_dir.exists():
        bm_meta = bookmarks_dir / "bookmarks.json"
        if not bm_meta.exists():
            errors.append("definition/bookmarks directory exists but bookmarks.json is missing")

        allowed_display_modes = {"maximize", "spotlight", "elevation", "hidden"}

        for bm_file in bookmarks_dir.glob("*.bookmark.json"):
            rel_bm = bm_file.relative_to(report_dir).as_posix()
            try:
                bm_data = json.loads(bm_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"Invalid JSON in {rel_bm}: {exc.msg}")
                continue

            if not isinstance(bm_data, dict):
                errors.append(f"{rel_bm}: root must be a JSON object")
                continue

            # Check targetVisualNames if present
            options = bm_data.get("options", {})
            if isinstance(options, dict):
                target_names = options.get("targetVisualNames", [])
                if isinstance(target_names, list):
                    for tg in target_names:
                        if all_visual_guids and tg not in all_visual_guids:
                            errors.append(
                                f"{rel_bm}: targetVisualNames references non-existent visual GUID {tg!r}"
                            )

            # Check explorationState sections and visualContainers
            exp_state = bm_data.get("explorationState", {})
            if isinstance(exp_state, dict):
                sections = exp_state.get("sections", {})
                if isinstance(sections, dict):
                    for _, sec_data in sections.items():
                        if isinstance(sec_data, dict):
                            vcs = sec_data.get("visualContainers", {})
                            if isinstance(vcs, dict):
                                for v_guid, v_container in vcs.items():
                                    if all_visual_guids and v_guid not in all_visual_guids:
                                        errors.append(
                                            f"{rel_bm}: visualContainers references non-existent visual GUID {v_guid!r}"
                                        )
                                    if isinstance(v_container, dict):
                                        sv = v_container.get("singleVisual", {})
                                        if isinstance(sv, dict):
                                            disp = sv.get("display")
                                            if isinstance(disp, dict):
                                                mode = disp.get("mode")
                                                if mode == "visible":
                                                    errors.append(
                                                        f"{rel_bm}: invalid display.mode='visible' on visual {v_guid!r}. "
                                                        f"Fabric schema 1.4.0 does not permit 'visible'; visible visuals must omit display entirely."
                                                    )
                                                elif mode not in allowed_display_modes:
                                                    errors.append(
                                                        f"{rel_bm}: invalid display.mode={mode!r} on visual {v_guid!r}. "
                                                        f"Must be one of {sorted(allowed_display_modes)} or omitted."
                                                    )

    if errors and raise_on_error:
        raise PBIRValidationError("; ".join(errors))

    return errors
