# Spike 04 — Custom render tier (SVG measures + Deneb)

**Question:** Can SimBI emit, from scratch, (a) a Deneb (Vega-Lite) custom visual with an
embedded spec and (b) an SVG `ImageUrl` measure rendered in a native table — and have
Power BI Desktop load and render both?

**Probe:** `tests/full/SalesDashboard` copied here; control page removed; `build.py`
(throwaway) emits one page "Custom Render" with three visuals. Open
`SalesDashboard.pbip` in Desktop. The 50 sample rows are inlined in the partition as an
M `#table`, so the model has no local file path and refreshes on any machine.

## Confirmed from source (pre-Desktop)

### Deneb identity — from `deneb-viz/deneb` `apps/deneb/pbiviz.json` + `capabilities.json`
| Item | Value |
|---|---|
| PBIR `visualType` | `deneb7E15AEF80B9E4D4F8E12924291ECE89A` (the visual GUID) |
| Data role | single role `dataset` (kind `GroupingOrMeasure`) → `queryState.dataset.projections` |
| Row window | categorical `dataReductionAlgorithm.window.count = 30000` |
| Spec storage | `objects.vega[0].properties.jsonSpec` (string literal) |
| Other `vega` props | `jsonConfig`, `provider` (`'vegaLite'` / `'vega'`), `renderMode` (`'svg'`/`'canvas'`), `enableTooltips`, `enableSelection`, `enableHighlight`, `selectionMode`, `selectionMaxDataPoints`, `enableContextMenu`, `tooltipDelay`, `logLevel`, `version` |
| Other objects | `developer.version`, `stateManagement.denebMetaVersion`, `dataLimit.override`, `editor.*`, `display.*` — not emitted; see Desktop re-save diff below |

Spec is stored as a PBIR string literal: `{"expr":{"Literal":{"Value":"'<json>'"}}}` —
single-quoted, so embedded `'` must be doubled. Vega-Lite specs reference fields by the
projection's display name (`nativeQueryRef`) and data by `{"name": "dataset"}`.

### Custom visual registration — from official report schema 3.0.0
`report.json` → `"publicCustomVisuals": ["deneb7E15AEF80B9E4D4F8E12924291ECE89A"]`
(AppSource visuals; org-store visuals use `organizationCustomVisuals` with metadata).

### SVG measures
TMDL measure with `dataCategory: ImageUrl`, returning
`data:image/svg+xml;utf8,<svg …>`. `#` must be `%23`, `%` must be `%25`.
Numbers formatted with `FORMAT(x, "0.0", "en-US")` so comma-decimal locales don't
corrupt SVG coordinates.

### Static validation
- All three new `visual.json` + `report.json` validate against the official Microsoft
  JSON schemas (visualContainer 2.3.0, report 3.0.0).
- `simbi_mcp.pbir.pbir_validator.validate_pbir_report` → `[]`.

## Desktop result (2026-10-10)

| Check | Result |
|---|---|
| Report opens without error | ✅ opened cleanly, refresh OK |
| Deneb recognised from `publicCustomVisuals` | ✅ (`report.json` untouched on save → registration form accepted as-is) |
| Table: SVG measures render as images | ✅ confirmed by user (sparkline, share bar, trend arrow, ± badge) |
| Deneb bar chart renders | ✅ |
| Deneb box plot renders (row-level) | ✅ |
| Cross-filter from Deneb bar → table | ✅ confirmed by user |

### Re-save diff (pre-open snapshot vs Desktop save)

**Untouched:** `report.json`, `pages.json`, `page.json`, both `jsonSpec` /
`jsonConfig` strings, all `vega` props we wrote, every DAX byte of both SVG measures.

**Rewritten (cosmetic):**
- `$schema` visualContainer `2.3.0` → `2.1.0` (Desktop writes its own version; ours was accepted).
- `position.tabOrder` dropped when `0`; empty `objects: {}` dropped.
- TMDL: measures moved above columns, blank line between measures, `dataCategory`
  moved after `lineageTag`. Semantics identical.

**Added by Deneb (all derived — generator need NOT emit):**
- `developer.version` = `'2.0.0.0'` (installed Deneb build)
- `vega.version` = `'6.4.3'` (bundled Vega version)
- `stateManagement`: `viewportHeight/Width` (from container size), `denebMetaVersion '2'`,
  `consolidateFieldParameters false`, and `supportFieldConfiguration` — a JSON string
  per projected field; measures get `highlight/format/formatted: true`, columns `false`.
  Recomputed from the projections on load.

### Learnings for the real emitter
- Minimal Deneb payload = `visualType` GUID + `dataset` projections + `vega.{provider,
  renderMode, jsonSpec, jsonConfig}` + `publicCustomVisuals`. Interactivity toggles optional.
- **Row-level (unaggregated) data:** project the numeric field as a *Column* plus a
  unique key (`OrderID`) — Deneb treats columns as group-by, so each order is one row.
  This is how the box plot (catalog ⚪ gap) works without any aggregation.
- SVG measures: `dataCategory: ImageUrl` in TMDL is sufficient; native `tableEx`
  renders them with no visual-side config.

## KPI placement test (`build_kpi.py`, page "KPI Trend")

Tested on **Power BI Desktop 2.148.878.0 (October 2025)** — saves visualContainer `2.1.0`.

| Visual | Binding | Result |
|---|---|---|
| A — `cardVisual` + sparkline (`%23`) | `objects.image[1].imageUrl` = measure, `imageType 'imageUrl'`, selector `{id: default}` | ✅ renders under the value |
| B — `cardVisual` + sparkline (`#`) | same | ✅ renders |
| C — `cardVisual` + trend arrow | same | ✅ renders |
| D — `image` visual (`%23`) | `image.sourceType 'imageData'` + `sourceField` = measure, no `query` | ❌ blank |
| E — `image` visual (`#`) | same | ❌ blank — config kept on save, so parsed but not rendered |
| F+G — classic card + table underneath | table `Values` | ✅ renders, but 20px default row height → scrollbars; needs `grid.imageHeight/Width` |

**Findings**
- **New card is the KPI-with-trend container.** No table workaround needed.
- **Encoding:** `%23` and `#` both render in table cells and the new card in Desktop →
  keep `%23` as the SimBI rule. The third-party claim that `%23` breaks colours may
  apply to the Service only — check once after publishing.
- **Image visual:** blank on Oct 2025 Desktop. Bindings came from examples saved with
  visualContainer `2.7.0`, so likely a newer-Desktop feature. ⏳ Retest D/E after the
  user updates Desktop.
- Desktop adds a `filterConfig` entry for the card's measure on save (derived, not needed).

## Verdict

**GO.** Both render paths work from hand-written PBIR/TMDL with no Desktop-only
state required, and Deneb selections cross-filter native visuals.
