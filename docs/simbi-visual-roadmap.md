# SimBI Visual Roadmap

> Implementation status overlay on top of [chart-catalog.md](chart-catalog.md). Per-chart prose lives in the catalog — this file is the status table only.

## Status legend
- ✅ **Supported** — annotation defined in `src/simbi_mcp/mockup/annotations.py`, emitter template exists, validator covers it
- 🟡 **Planned (next)** — chosen for the next implementation pass; design known
- 🔵 **Planned (later)** — wanted, but not prioritized
- ⚪ **Out-of-scope** — won't implement (AppSource, R/Python, service-side AI)

## Status table

| Visual | Status | Catalog § | Annotation needed? | Emitter work | Notes |
|--------|--------|-----------|--------------------|--------------|-------|
| [Card](chart-catalog.md#card) | ✅ | 1. Single-value & KPI | Done | Done | `data-pbi-measure` only |
| [Multi-row Card](chart-catalog.md#multi-row-card) | ✅ | 1. Single-value & KPI | Done | Done | `data-pbi-measures` (comma-separated) |
| [KPI](chart-catalog.md#kpi) | ✅ | 1. Single-value & KPI | Done | Done | `data-pbi-measure` + `data-pbi-target` + `data-pbi-trend`; PBIR `kpi` |
| [Gauge](chart-catalog.md#gauge) | ✅ | 1. Single-value & KPI | Done | Done | `data-pbi-measure` + optional min/max/target (measure refs only) |
| [Bar Chart](chart-catalog.md#bar-chart) | ✅ | 2. Comparison across categories | Done | Done | `data-pbi-axis` + `data-pbi-values` |
| [Column Chart](chart-catalog.md#column-chart) | ✅ | 2. Comparison across categories | Done | Done | `data-pbi-axis` + `data-pbi-values` |
| [Clustered Bar Chart](chart-catalog.md#clustered-bar-chart) | ✅ | 2. Comparison across categories | Done | Done | PBIR `clusteredBarChart`; series binding only |
| [Clustered Column Chart](chart-catalog.md#clustered-column-chart) | ✅ | 2. Comparison across categories | Done | Done | PBIR `clusteredColumnChart`; series binding only |
| [Dot Plot](chart-catalog.md#dot-plot) | ✅ | 2. Comparison across categories | Done | Done | PBIR visualType `dotPlot` (verify against sample if rendering fails) |
| [Line Chart](chart-catalog.md#line-chart) | ✅ | 3. Trend over time | Done | Done | `data-pbi-axis` + `data-pbi-values`; optional `data-pbi-series` |
| [Area Chart](chart-catalog.md#area-chart) | ✅ | 3. Trend over time | Done | Done | PBIR `areaChart`; reuses Line emitter, change render mode |
| [Stacked Area Chart](chart-catalog.md#stacked-area-chart) | ✅ | 3. Trend over time | Done | Done | areaChart + optional `data-pbi-series` (no new visual needed) |
| [Combo Chart (Line + Column)](chart-catalog.md#combo-chart-line--column) | ✅ | 3. Trend over time | Done | Done | PBIR `lineClusteredColumnComboChart`; `data-pbi-column-values` + `data-pbi-line-values` |
| [Pie Chart](chart-catalog.md#pie-chart) | ✅ | 4. Part-to-whole | Done | Done | New emitter; share-of-whole context required |
| [Donut Chart](chart-catalog.md#donut-chart) | ✅ | 4. Part-to-whole | Done | Done | PBIR `donutChart` (distinct from pieChart); shares queryState shape |
| [Treemap](chart-catalog.md#treemap) | ✅ | 4. Part-to-whole | Done | Done | `data-pbi-group` + `data-pbi-values` + optional `data-pbi-details` |
| [Stacked Bar Chart](chart-catalog.md#stacked-bar-chart) | ✅ | 4. Part-to-whole | Done | Done | PBIR `barChart` + Series (no distinct stacked type); reuses bar emitter |
| [Stacked Column Chart](chart-catalog.md#stacked-column-chart) | ✅ | 4. Part-to-whole | Done | Done | PBIR `columnChart` + Series (no distinct stacked type); reuses column emitter |
| [100% Stacked Bar Chart](chart-catalog.md#100-stacked-bar-chart) | ✅ | 4. Part-to-whole | Done | Done | PBIR `hundredPercentStackedBarChart` (distinct type, confirmed) |
| [100% Stacked Column Chart](chart-catalog.md#100-stacked-column-chart) | ✅ | 4. Part-to-whole | Done | Done | PBIR `hundredPercentStackedColumnChart` (distinct type, confirmed) |
| [Funnel Chart](chart-catalog.md#funnel-chart) | ✅ | 4. Part-to-whole | Done | Done | Annotation `funnelChart` → PBIR `funnel`; ordered category required |
| [Histogram](chart-catalog.md#histogram) | ✅ | 5. Distribution | Done | Done | PBIR `barChart` + `binCount` axis property (verify name against PBIR sample) |
| [Box Plot](chart-catalog.md#box-plot) | ⚪ | 5. Distribution | n/a | n/a | AppSource only; not in core PBI visuals |
| [Scatter Chart](chart-catalog.md#scatter-chart) | ✅ | 6. Correlation | Done | Done | `data-pbi-x` + `data-pbi-y` (both measures) + optional `data-pbi-details` |
| [Bubble Chart](chart-catalog.md#bubble-chart) | ✅ | 6. Correlation | Done | Done | Shares PBIR `scatterChart`; adds `data-pbi-size` |
| [Waterfall Chart](chart-catalog.md#waterfall-chart) | ✅ | 7. Ranking & flow | Done | Done | PBIR `waterfallChart`; optional `data-pbi-breakdown` |
| [Ribbon Chart](chart-catalog.md#ribbon-chart) | ✅ | 7. Ranking & flow | Done | Done | PBIR `ribbonChart`; same axis/values/series triplet as clustered chart |
| [Decomposition Tree](chart-catalog.md#decomposition-tree) | ⚪ | 7. Ranking & flow | n/a | n/a | Requires PBI service AI; no offline equivalent |
| [Map](chart-catalog.md#map) | ✅ | 8. Geographic | Done | Done | PBIR `map`; relies on tenant Bing-Maps enablement at render time |
| [Filled Map](chart-catalog.md#filled-map) | ✅ | 8. Geographic | Done | Done | PBIR `filledMap`; same Bing dependency as Map |
| [Azure Map](chart-catalog.md#azure-map) | ⚪ | 8. Geographic | n/a | n/a | Requires Azure Maps subscription |
| [Shape Map](chart-catalog.md#shape-map) | ✅ | 8. Geographic | Done | Done | PBIR `shapeMap`; optional `data-pbi-topojson` emits placeholder objects entry |
| [Table](chart-catalog.md#table) | ✅ | 9. Tabular | Done | Done | `data-pbi-columns` (mixed measures + column refs); PBIR `tableEx` |
| [Matrix](chart-catalog.md#matrix) | 🟡 | 9. Tabular | new: `data-pbi-rows`, `data-pbi-columns`, `data-pbi-values` | Medium | PBIR `pivotTable` (confirmed); three new annotation attributes |
| [Key Influencers](chart-catalog.md#key-influencers) | ⚪ | 10. AI-driven | n/a | n/a | Requires PBI service AI; no offline equivalent |
| [Q&A Visual](chart-catalog.md#qa-visual) | ⚪ | 10. AI-driven | n/a | n/a | Requires PBI service AI; no offline equivalent |
| [Smart Narrative](chart-catalog.md#smart-narrative) | ⚪ | 10. AI-driven | n/a | n/a | Requires PBI service AI; no offline equivalent |
| [Slicer](chart-catalog.md#slicer) | ✅ | 11. Filtering | Done | Done | List mode; PBIR emits `advancedSlicerVisual` |

## How a visual gets to 🟡

A visual is promoted to planned-next when two conditions both hold:
1. **Annotation reuse is high** — it can extend an existing `data-pbi-*` shape with one or two new attributes, rather than introducing an entirely new visual contract.
2. **It fills a common dashboard need** — it appears in the majority of business dashboards (stacked columns, KPIs with targets, matrix tables) rather than serving niche analyses.

Visuals that meet only (1) stay planned-later until a dashboard need surfaces. Visuals that meet only (2) stay planned-later until the emitter has enough shared infrastructure to make the new contract cheap.
