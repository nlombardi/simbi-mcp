# SimBI Chart Catalog

> Power BI's ~30 core visuals, organized by analytical intent. Every entry is a mini-spec: it tells you when to pick the chart AND what SimBI would need to emit it. For implementation status see [simbi-visual-roadmap.md](simbi-visual-roadmap.md). For dashboard composition see [dashboard-design-playbook.md](dashboard-design-playbook.md).

## How to read an entry

```
### <Visual name>
**Intent:** comparison / trend / part-to-whole / etc.
**When to use:** specific data shape and reader question
**When NOT to use:** common misuse and alternative
**Data shape:** e.g. 1 categorical + 1 measure
**PBIR visualType:** `microsoft-internal-name`
**Data roles required:** `Role1`, `Role2`, ...
**Proposed SimBI annotation:**
  data-pbi="<type>"
  data-pbi-<attr>="..."
**Implementation notes:** reuse of existing template, new emitter needed, etc.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#anchor) · [design notes](dashboard-design-playbook.md#anchor)
```

## 1. Single-value & KPI

### Card
**Intent:** Single-value KPI
**When to use:** Showing one headline number (revenue, count, ratio). Pair with a trend chart for context.
**When NOT to use:** When the value only makes sense relative to a target — use KPI instead.
**Data shape:** 1 measure
**PBIR visualType:** `card`
**Data roles required:** `Values`
**Proposed SimBI annotation:**
  data-pbi="card"
  data-pbi-measure="<Measure Name>"
**Implementation notes:** Already supported — see `VisualType.CARD` in `src/simbi_mcp/mockup/annotations.py`.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#card) · [design notes](dashboard-design-playbook.md#kpi-strip)

### Multi-row Card
**Intent:** Multi-measure summary panel
**When to use:** Displaying several headline KPIs side-by-side (or stacked) without a category axis — typically used in a KPI strip at the top of a dashboard.
**When NOT to use:** When measures have different units that would confuse readers when juxtaposed; split into individual Cards instead. Also avoid when a comparison across a dimension is needed — use a table or bar chart.
**Data shape:** 2+ measures, no category axis
**PBIR visualType:** `multiRowCard`
**Data roles required:** `Fields`
**Proposed SimBI annotation:**
  data-pbi="multiRowCard"
  data-pbi-measures="<Measure1>, <Measure2>, ..."
**Implementation notes:** Not yet supported. New emitter entry needed in `src/simbi_mcp/pbir/templates.py`. Annotation parser must split `data-pbi-measures` on commas and map each to a PBIR `fields` role binding. Consider reusing Card template structure with iteration.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#multi-row-card) · [design notes](dashboard-design-playbook.md#kpi-strip)

### KPI
**Intent:** Actual-vs-target progress with trend direction
**When to use:** When a measure must be evaluated against a goal (e.g. sales vs. quota) and the reader needs to see whether the trend is improving or declining. Ideal for operational dashboards where targets are first-class data.
**When NOT to use:** When no target exists — use Card instead. Avoid when the audience needs the exact underlying number rather than a status signal; a Card or table is clearer.
**Data shape:** 1 indicator measure + 1 target measure + 1 date/trend axis
**PBIR visualType:** `kpi`
**Data roles required:** `Indicator`, `TrendAxis`, `TargetGoals`
**Proposed SimBI annotation:**
  data-pbi="kpi"
  data-pbi-measure="<Indicator Measure>"
  data-pbi-target="<Target Measure>"
  data-pbi-trend="<Date Field>"
**Implementation notes:** Not yet supported. Requires a new emitter template and three new annotation attributes (`data-pbi-target`, `data-pbi-trend` in addition to the existing `data-pbi-measure` pattern). The PBIR format for KPI includes a `sparkline` sub-config — confirmed visualType `kpi` from Microsoft Sales Forecast PBIR sample.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#kpi) · [design notes](dashboard-design-playbook.md#kpi-strip)

### Gauge
**Intent:** Progress toward a bounded target on a radial scale
**When to use:** When a single measure has a well-defined minimum, maximum, and target, and the reader needs an at-a-glance sense of "how full is the tank" (e.g. capacity utilisation, NPS, completion rate).
**When NOT to use:** When the min/max range is not meaningful or not well understood by the audience — the arc will mislead. For simple target comparison, use KPI. Avoid on dense dashboards where the large visual footprint is hard to justify.
**Data shape:** 1 value measure + optional min, max, and target measures
**PBIR visualType:** `gauge`
**Data roles required:** `Value`, `MinValue`, `MaxValue`, `TargetValue`
**Proposed SimBI annotation:**
  data-pbi="gauge"
  data-pbi-measure="<Value Measure>"
  data-pbi-min="<Min Measure or literal>"
  data-pbi-max="<Max Measure or literal>"
  data-pbi-target="<Target Measure>"
**Implementation notes:** Not yet supported. Requires a new emitter template. Min/max can be static literals or measure references — the annotation parser must handle both. The PBIR gauge visual encodes needle position via `value` and the arc via `minValue`/`maxValue` sub-properties.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#gauge) · [design notes](dashboard-design-playbook.md#kpi-strip)

## 2. Comparison across categories

### Bar Chart
**Intent:** Comparison of a measure across categories (horizontal)
**When to use:** Comparing a single measure across a categorical dimension (e.g. revenue by region). Prefer horizontal bars when category labels are long or when there are more than ~7 categories, as labels read left-to-right naturally.
**When NOT to use:** When the order of categories is time-based — use a Line or Column chart instead. Avoid when showing part-to-whole — use a stacked bar or pie/treemap.
**Data shape:** 1 categorical dimension + 1 measure
**PBIR visualType:** `barChart`
**Data roles required:** `Category`, `Y`
**Proposed SimBI annotation:**
  data-pbi="barChart"
  data-pbi-axis="<Category Field>"
  data-pbi-values="<Measure Name>"
**Implementation notes:** Already supported — see `VisualType.BAR_CHART` in `src/simbi_mcp/mockup/annotations.py`. Emitter maps `data-pbi-axis` → `Category` role and `data-pbi-values` → `Y` role.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#bar-chart) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Column Chart
**Intent:** Comparison of a measure across categories (vertical)
**When to use:** Comparing a single measure across a categorical or short time-based dimension (e.g. sales by month, units by product). Vertical orientation works well when labels are short and there are fewer than ~8 categories.
**When NOT to use:** When category labels are long — use a Bar chart instead. For continuous time series with many points, prefer a Line chart.
**Data shape:** 1 categorical dimension + 1 measure
**PBIR visualType:** `columnChart`
**Data roles required:** `Category`, `Y`
**Proposed SimBI annotation:**
  data-pbi="columnChart"
  data-pbi-axis="<Category Field>"
  data-pbi-values="<Measure Name>"
**Implementation notes:** Already supported — see `VisualType.COLUMN_CHART` in `src/simbi_mcp/mockup/annotations.py`. Emitter maps `data-pbi-axis` → `Category` role and `data-pbi-values` → `Y` role.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#column-chart) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Clustered Bar Chart
**Intent:** Side-by-side comparison of multiple measures or a measure broken by a series, across categories (horizontal)
**When to use:** When comparing two or more sub-groups within each category (e.g. revenue vs. cost by region, or sales by product broken by year). Horizontal layout suits long category labels.
**When NOT to use:** When series count exceeds ~4 — the clusters become too dense to read; consider a small-multiple layout or a table instead. For a single measure without a series, use Bar chart.
**Data shape:** 1 categorical dimension + 1 measure + 1 series dimension
**PBIR visualType:** `clusteredBarChart`
**Data roles required:** `Category`, `Y`, `Series`
**Proposed SimBI annotation:**
  data-pbi="clusteredBarChart"
  data-pbi-axis="<Category Field>"
  data-pbi-values="<Measure Name>"
  data-pbi-series="<Series Field>"
**Implementation notes:** Not yet supported. Shares the same PBIR template structure as `barChart` with an additional `Series` role binding. Confirmed `clusteredBarChart` visualType from PBIR samples. Annotation parser can extend the existing Bar chart path.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#clustered-bar-chart) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Clustered Column Chart
**Intent:** Side-by-side comparison of multiple measures or a measure broken by a series, across categories (vertical)
**When to use:** Same analytical need as Clustered Bar but with short category labels and fewer than ~8 categories. Effective for budget-vs-actual by department or multi-year comparison by product.
**When NOT to use:** When category labels are long or cluster count makes columns too narrow — use Clustered Bar instead. For more than ~4 series, consider small multiples or a table.
**Data shape:** 1 categorical dimension + 1 measure + 1 series dimension
**PBIR visualType:** `clusteredColumnChart`
**Data roles required:** `Category`, `Y`, `Series`
**Proposed SimBI annotation:**
  data-pbi="clusteredColumnChart"
  data-pbi-axis="<Category Field>"
  data-pbi-values="<Measure Name>"
  data-pbi-series="<Series Field>"
**Implementation notes:** Not yet supported. Shares the same PBIR template structure as `columnChart` with an additional `Series` role binding. Confirmed `clusteredColumnChart` visualType from PBIR samples (Visual Vocabulary report). Annotation parser can extend the existing Column chart path.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#clustered-column-chart) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Dot Plot
**Intent:** Precise value comparison across categories emphasising exact position over bar magnitude
**When to use:** When the exact value of each category matters more than the visual length of a bar (e.g. KPI scores, survey ratings, percentage completion per team). Effective when values cluster in a narrow range where bar lengths would be nearly identical and hard to distinguish.
**When NOT to use:** When the audience needs to compare magnitudes intuitively — bars convey "how much bigger" more immediately. Avoid when there are too many categories (>20) as dots become hard to scan.
**Data shape:** 1 categorical dimension + 1 measure
**PBIR visualType:** Not confirmed in samples — may not be a native PBI visual (verify in Desktop)
**Data roles required:** `Category`, `X`
**Proposed SimBI annotation:**
  data-pbi="dotPlot"
  data-pbi-axis="<Category Field>"
  data-pbi-values="<Measure Name>"
**Implementation notes:** Not yet supported. Verify PBIR visualType string against a sample — Power BI may implement this as a scatter chart variant. New emitter template required; no existing SimBI template to reuse directly.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#dot-plot) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

## 3. Trend over time

### Line Chart
**Intent:** Trend of one or more measures over a continuous time axis
**When to use:** Showing how a measure changes over time (e.g. daily active users, monthly revenue). Add a series dimension to compare multiple lines (e.g. revenue by region over time).
**When NOT to use:** When the x-axis is categorical rather than temporal or ordered — use a Bar or Column chart. Avoid when individual point values matter more than the trend shape — use a column chart with data labels.
**Data shape:** 1 date/time dimension + 1 measure + optional series dimension
**PBIR visualType:** `lineChart`
**Data roles required:** `Category`, `Y`, `Series` (Series optional)
**Proposed SimBI annotation:**
  data-pbi="lineChart"
  data-pbi-axis="<Date Field>"
  data-pbi-values="<Measure Name>"
  data-pbi-series="<Series Field>"  <!-- optional -->
**Implementation notes:** Already supported — see `VisualType.LINE_CHART` in `src/simbi_mcp/mockup/annotations.py`. `data-pbi-series` is already declared as optional in the annotation schema. Emitter maps axis → `Category`, values → `Y`, series → `Series`.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#line-chart) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Area Chart
**Intent:** Trend with visual emphasis on cumulative volume beneath the line
**When to use:** When the filled area below the line carries meaning — e.g. showing total volume over time (cumulative revenue, bandwidth consumption). The fill reinforces "magnitude" rather than just "direction."
**When NOT to use:** When comparing multiple series — overlapping fills obscure each other; use a Line chart with distinct colours instead. Avoid for sparse or irregular time series where the fill creates misleading implied continuity.
**Data shape:** 1 date/time dimension + 1 measure + optional series dimension
**PBIR visualType:** `areaChart`
**Data roles required:** `Category`, `Y`, `Series` (Series optional)
**Proposed SimBI annotation:**
  data-pbi="areaChart"
  data-pbi-axis="<Date Field>"
  data-pbi-values="<Measure Name>"
  data-pbi-series="<Series Field>"  <!-- optional -->
**Implementation notes:** Not yet supported. Confirmed `areaChart` visualType from PBIR samples. PBIR shares structural similarity with `lineChart` — reuse Line chart template as a starting point and add fill-area render mode.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#area-chart) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Stacked Area Chart
**Intent:** Part-to-whole trend — how the composition of a total changes over time
**When to use:** When you want to show both the overall trend of a total and how each sub-category contributes to it (e.g. revenue by product line over time). Ideal when the total itself is meaningful and the audience cares about share shifts.
**When NOT to use:** When individual series values matter more than the cumulative stack — use a Line chart with multiple series. Avoid when categories do not sum to a meaningful total (e.g. they are independent KPIs).
**Data shape:** 1 date/time dimension + 1 measure + 1 series dimension (required for stacking)
**PBIR visualType:** `stackedAreaChart`
**Data roles required:** `Category`, `Y`, `Series`
**Proposed SimBI annotation:**
  data-pbi="stackedAreaChart"
  data-pbi-axis="<Date Field>"
  data-pbi-values="<Measure Name>"
  data-pbi-series="<Series Field>"
**Implementation notes:** Not yet supported. Likely a variant of the Area chart PBIR template with a stacking property set. Verify visualType string. The series dimension is required (not optional) for stacking — the annotation parser should enforce this.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#stacked-area-chart) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Combo Chart (Line + Column)
**Intent:** Dual-measure trend comparison with two different visual encodings on a shared time axis
**When to use:** When two related measures have different scales or units and you want to show them together (e.g. revenue as columns + gross margin % as a line). The secondary axis accommodates the scale difference. Useful for comparing a volume metric with a rate metric.
**When NOT to use:** When the two measures are on the same scale — use a Line chart with two series instead (dual axes add cognitive load). Avoid when the audience is unfamiliar with dual-axis charts, as misreading the y-axis scales is a common error.
**Data shape:** 1 date/time dimension + 1 column measure + 1 line measure
**PBIR visualType:** `lineClusteredColumnComboChart` (clustered column variant) or `lineStackedColumnComboChart` (stacked column variant)
**Data roles required:** `Category`, `ColumnValues`, `LineValues`
**Proposed SimBI annotation:**
  data-pbi="comboChart"
  data-pbi-axis="<Date Field>"
  data-pbi-column-values="<Column Measure>"
  data-pbi-line-values="<Line Measure>"
**Implementation notes:** Not yet supported. The Combo chart in Power BI is a distinct visual (not a layered Line + Column) — verify the PBIR visualType string. Two new annotation attributes are proposed (`data-pbi-column-values` and `data-pbi-line-values`) to distinguish the two measure roles. A new emitter template is required; it cannot reuse the Line or Column chart templates directly.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#combo-chart-line--column) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

## 4. Part-to-whole

### Pie Chart
**Intent:** Part-to-whole proportions for a small number of categories
**When to use:** Showing how a small set of categories (≤5) share a whole (e.g. revenue by region as a percentage of total). Most effective when one or two slices dominate and the contrast is immediately obvious.
**When NOT to use:** More than 5 slices — switch to a bar chart. Avoid when precise comparison between similarly-sized slices matters; angle differences are hard to judge — use a bar chart instead.
**Data shape:** 1 categorical dimension + 1 measure
**PBIR visualType:** `pieChart`
**Data roles required:** `Category`, `Y`
**Proposed SimBI annotation:**
  data-pbi="pieChart"
  data-pbi-axis="<Category Field>"
  data-pbi-values="<Measure Name>"
**Implementation notes:** Not yet supported. Confirmed `pieChart` visualType from PBIR samples. New emitter template required; the emitter will map `data-pbi-axis` → `Category` role and `data-pbi-values` → `Y` role.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#pie-chart) · [design notes](dashboard-design-playbook.md#stacking)

### Donut Chart
**Intent:** Part-to-whole proportions with a central label space for a summary value
**When to use:** Same analytical need as a Pie chart, but the central hole provides space for a total or headline KPI label. Use when the summary value reinforces the slices (e.g. total revenue in the centre, slices showing regional share).
**When NOT to use:** More than 5 slices — switch to a bar chart. Avoid when the central space is left empty with no summary label — a Pie chart is simpler. Do not use when readers need to compare slice sizes precisely; use a bar chart.
**Data shape:** 1 categorical dimension + 1 measure
**PBIR visualType:** `donutChart`
**Data roles required:** `Category`, `Y`
**Proposed SimBI annotation:**
  data-pbi="donutChart"
  data-pbi-axis="<Category Field>"
  data-pbi-values="<Measure Name>"
**Implementation notes:** Not yet supported. Confirmed `donutChart` visualType from PBIR samples (Supply Chain Dashboard + Visual Vocabulary). Uses a distinct visualType from `pieChart` — not a property flag. Emitter can reuse the Pie chart template structure; the queryState shape is the same (Category + Y).
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#donut-chart) · [design notes](dashboard-design-playbook.md#stacking)

### Treemap
**Intent:** Hierarchical part-to-whole proportions using nested rectangles sized by measure
**When to use:** When comparing proportional sizes across many categories (or two levels of hierarchy) and the reader's question is "which category dominates?" — e.g. spend by department and sub-category. Works well when there are too many slices for a pie chart.
**When NOT to use:** When precise comparison of similar-sized categories is required — area differences are hard to judge; use a bar chart. Avoid for more than two hierarchy levels, as deeply nested rectangles become unreadable.
**Data shape:** 1–2 categorical dimensions (Group + optional Details) + 1 measure
**PBIR visualType:** `treemap`
**Data roles required:** `Group`, `Details` (optional), `Values`
**Proposed SimBI annotation:**
  data-pbi="treemap"
  data-pbi-group="<Primary Category Field>"
  data-pbi-details="<Secondary Category Field>"  <!-- optional -->
  data-pbi-values="<Measure Name>"
**Implementation notes:** Not yet supported. Confirmed `treemap` visualType from PBIR samples. New emitter template required. Two annotation attributes (`data-pbi-group`, `data-pbi-values`) are required; `data-pbi-details` is optional for a second hierarchy level.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#treemap) · [design notes](dashboard-design-playbook.md#stacking)

### Stacked Bar Chart
**Intent:** Part-to-whole composition across categories (horizontal) — how sub-groups make up each category total
**When to use:** When comparing both the total and the sub-group contributions for each category (e.g. headcount by department, broken down by role). Horizontal orientation suits long category labels or many categories.
**When NOT to use:** When absolute sub-group values matter more than their share of the whole — use a Clustered Bar chart. Avoid when there are more than ~5 stack segments, as colours become hard to distinguish.
**Data shape:** 1 categorical dimension + 1 measure + 1 series dimension
**PBIR visualType:** `barChart` (same as plain Bar Chart — stacking is controlled by the `Series` role binding, not a distinct visualType)
**Data roles required:** `Category`, `Y`, `Series`
**Proposed SimBI annotation:**
  data-pbi="stackedBarChart"
  data-pbi-axis="<Category Field>"
  data-pbi-values="<Measure Name>"
  data-pbi-series="<Series Field>"
**Implementation notes:** Not yet supported. Confirmed from "18 Bar Charts" PBIR sample: "STACKED BAR CHART" uses `visualType: "barChart"` with a `Series` projection — there is no distinct `stackedBarChart` type in PBIR. The emitter reuses the `barChart` template and adds a `Series` role binding. The SimBI annotation token `stackedBarChart` exists only to communicate intent; the emitter maps it to `barChart` in PBIR.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#stacked-bar-chart) · [design notes](dashboard-design-playbook.md#stacking)

### Stacked Column Chart
**Intent:** Part-to-whole composition across categories (vertical) — how sub-groups make up each category total
**When to use:** Same analytical need as Stacked Bar but with short category labels and fewer than ~8 categories. Effective for quarterly revenue by product line, or monthly headcount by team.
**When NOT to use:** When category labels are long — use Stacked Bar instead. Avoid when there are more than ~5 stack segments. For comparing absolute sub-group values, use Clustered Column.
**Data shape:** 1 categorical dimension + 1 measure + 1 series dimension
**PBIR visualType:** `columnChart` (same as plain Column Chart — stacking is controlled by the `Series` role binding, not a distinct visualType; consistent with the confirmed `barChart` / stacked bar pattern)
**Data roles required:** `Category`, `Y`, `Series`
**Proposed SimBI annotation:**
  data-pbi="stackedColumnChart"
  data-pbi-axis="<Category Field>"
  data-pbi-values="<Measure Name>"
  data-pbi-series="<Series Field>"
**Implementation notes:** Not yet supported. By direct analogy with the confirmed stacked bar behavior (visualType `barChart` + Series binding), stacked column uses `columnChart` + Series binding — no separate PBIR type. The emitter reuses the `columnChart` template and adds a `Series` role. The SimBI token `stackedColumnChart` maps to `columnChart` in PBIR. Verify against a stacked column PBIR sample to confirm before implementing.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#stacked-column-chart) · [design notes](dashboard-design-playbook.md#stacking)

### 100% Stacked Bar Chart
**Intent:** Relative composition across categories (horizontal) — each bar normalized to 100% to show share only, not absolute totals
**When to use:** When the reader's question is purely "what proportion does each sub-group represent?" across categories (e.g. survey response distribution by team). Removes absolute-size distraction — all bars are the same length.
**When NOT to use:** When absolute values or totals matter — normalization hides them; use a Stacked Bar chart. Avoid when a category has only one or two sub-groups where a simple bar or table would be clearer.
**Data shape:** 1 categorical dimension + 1 measure + 1 series dimension
**PBIR visualType:** `hundredPercentStackedBarChart`
**Data roles required:** `Category`, `Y`, `Series`
**Proposed SimBI annotation:**
  data-pbi="hundredPercentStackedBarChart"
  data-pbi-axis="<Category Field>"
  data-pbi-values="<Measure Name>"
  data-pbi-series="<Series Field>"
**Implementation notes:** Not yet supported. Confirmed `hundredPercentStackedBarChart` visualType from PBIR samples (18 Bar Charts + Supply Chain Dashboard). Unlike plain stacked bar (which reuses `barChart`), the 100% variant uses a distinct visualType. Data roles are identical to Stacked Bar. New emitter branch required; queryState structure is the same as `barChart` + Series.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#100-stacked-bar-chart) · [design notes](dashboard-design-playbook.md#stacking)

### 100% Stacked Column Chart
**Intent:** Relative composition across categories (vertical) — each column normalized to 100% to show share only, not absolute totals
**When to use:** Same analytical need as 100% Stacked Bar but with short category labels and fewer than ~8 categories. Useful for showing survey or response-type distributions across time periods or groups.
**When NOT to use:** When absolute totals matter — use Stacked Column instead. When category labels are long — use 100% Stacked Bar. Avoid when sub-group count exceeds ~5 segments.
**Data shape:** 1 categorical dimension + 1 measure + 1 series dimension
**PBIR visualType:** `hundredPercentStackedColumnChart`
**Data roles required:** `Category`, `Y`, `Series`
**Proposed SimBI annotation:**
  data-pbi="hundredPercentStackedColumnChart"
  data-pbi-axis="<Category Field>"
  data-pbi-values="<Measure Name>"
  data-pbi-series="<Series Field>"
**Implementation notes:** Not yet supported. Confirmed `hundredPercentStackedColumnChart` visualType from PBIR samples (Supply Chain Dashboard + Visual Vocabulary). Uses a distinct visualType (not a flag on `columnChart`). New emitter branch required; queryState structure mirrors `columnChart` + Series binding.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#100-stacked-column-chart) · [design notes](dashboard-design-playbook.md#stacking)

### Funnel Chart
**Intent:** Sequential stage progression showing drop-off or conversion at each step
**When to use:** When a process has ordered stages and the reader needs to see volume at each step and where the biggest drop-offs occur (e.g. sales pipeline: leads → qualified → proposal → closed). The narrowing shape makes conversion loss visually immediate.
**When NOT to use:** When stages are not sequential or do not have a natural ordering — use a Bar chart. Avoid when all stages have similar volumes with no meaningful drop-off, as the funnel shape implies a conversion story that isn't there.
**Data shape:** 1 categorical dimension (ordered stages) + 1 measure
**PBIR visualType:** `funnel`
**Data roles required:** `Group`, `Values`
**Proposed SimBI annotation:**
  data-pbi="funnelChart"
  data-pbi-axis="<Stage Field>"
  data-pbi-values="<Measure Name>"
**Implementation notes:** Not yet supported. Confirmed `funnel` visualType from PBIR samples (Supply Chain Dashboard). New emitter template required. Stage ordering is critical — the annotation parser or emitter must preserve the source data order (or allow an explicit order attribute).
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#funnel-chart) · [design notes](dashboard-design-playbook.md#stacking)

## 5. Distribution

### Histogram
**Intent:** Frequency distribution of a continuous measure — how many values fall in each bin
**When to use:** When the reader's question is "how is this measure distributed?" (e.g. order value distribution, response time distribution). Bins reveal skew, outliers, and concentration that summary statistics alone hide.
**When NOT to use:** When the axis is categorical rather than continuous — use a Bar chart. Avoid when the dataset is too small for binning to be meaningful (fewer than ~30 data points); a dot plot or table is more honest.
**Data shape:** 1 continuous measure (binned on the axis)
**PBIR visualType:** `barChart` (no distinct histogram type — binning is an axis config on a standard bar chart)
**Data roles required:** `X` (binned measure), `Y` (count or frequency measure)
**Proposed SimBI annotation:**
  data-pbi="histogram"
  data-pbi-values="<Continuous Measure>"
  data-pbi-bins="<Bin Count or Bin Width>"  <!-- optional -->
**Implementation notes:** Power BI native histogram is achieved with a bar chart + axis binning — no separate visualType. Reuses `barChart` emitter; the binning is a PBIR axis config, not a new visual. The SimBI annotation `data-pbi="histogram"` acts as a shorthand that the emitter translates to a binned barChart. The `data-pbi-bins` attribute should drive the PBIR axis `binCount` or `binWidth` property (TBD — verify property names against PBIR sample). Verify the exact PBIR axis binning config before implementing.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#histogram) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Box Plot
**Intent:** Distribution summary showing median, quartiles, and outliers for one or more groups
**When to use:** When comparing the spread and central tendency of a continuous measure across groups (e.g. salary distribution by department, response time by region). Shows more distributional detail than a bar chart mean while remaining compact.
**When NOT to use:** When the audience is unfamiliar with box plot conventions (whiskers, IQR) — the visual requires explanation and may mislead a general audience. For a simple comparison of averages, a bar chart is more accessible.
**Data shape:** 1 continuous measure + optional 1 categorical dimension (grouping)
**PBIR visualType:** AppSource custom visual — no native PBIR `visualType` string
**Data roles required:** `Sampling` (measure), `Category` (optional grouping)
**Proposed SimBI annotation:**
  data-pbi="boxPlot"
  data-pbi-values="<Continuous Measure>"
  data-pbi-axis="<Grouping Field>"  <!-- optional -->
**Implementation notes:** AppSource only — out-of-scope for SimBI. Document for reader awareness; will be marked ⚪ in the roadmap. Power BI's built-in visual library does not include a native box plot; it requires an AppSource custom visual. SimBI cannot emit AppSource visuals. If a future SimBI version targets custom visuals, revisit this entry.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#box-plot) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

## 6. Correlation

### Scatter Chart
**Intent:** Relationship between two continuous measures across individual data points
**When to use:** When the reader's question is "is there a relationship between X and Y?" (e.g. does ad spend correlate with revenue by market? do larger orders take longer to fulfil?). Each point represents one entity; position on both axes encodes its two measures.
**When NOT to use:** When one axis is categorical rather than continuous — use a Bar or Column chart. Avoid when there are fewer than ~10 data points, as scatter patterns are meaningless at small N. For time-based relationships, use a Line chart.
**Data shape:** 1 continuous measure (X axis) + 1 continuous measure (Y axis) + optional 1 categorical dimension (Details/labels)
**PBIR visualType:** `scatterChart`
**Data roles required:** `X`, `Y`, `Details` (optional)
**Proposed SimBI annotation:**
  data-pbi="scatterChart"
  data-pbi-x="<X-Axis Measure>"
  data-pbi-y="<Y-Axis Measure>"
  data-pbi-details="<Label or Group Field>"  <!-- optional -->
**Implementation notes:** Not yet supported. Confirmed `scatterChart` visualType from PBIR samples. New emitter template required. Two new annotation attributes are proposed (`data-pbi-x`, `data-pbi-y`) distinct from the existing `data-pbi-axis`/`data-pbi-values` pattern to reflect the symmetric nature of scatter axes. `data-pbi-details` drives the `Details` role, which labels individual points.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#scatter-chart) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Bubble Chart
**Intent:** Relationship between two continuous measures with a third measure encoded as bubble size
**When to use:** When the reader's question extends a scatter analysis with a third dimension — e.g. "which markets have high spend and high revenue, and how large are they?" The bubble size adds a third quantitative variable without adding a third axis.
**When NOT to use:** When the size dimension is not meaningful or not understood by the audience — use a Scatter chart instead. Avoid when bubbles overlap heavily (many data points) making size comparisons impossible.
**Data shape:** 1 continuous measure (X) + 1 continuous measure (Y) + 1 measure (size) + optional 1 categorical dimension (Details)
**PBIR visualType:** `scatterChart` (same as Scatter — bubble size is a `Size` data role binding, not a distinct visualType)
**Data roles required:** `X`, `Y`, `Size`, `Details` (optional)
**Proposed SimBI annotation:**
  data-pbi="bubbleChart"
  data-pbi-x="<X-Axis Measure>"
  data-pbi-y="<Y-Axis Measure>"
  data-pbi-size="<Size Measure>"
  data-pbi-details="<Label or Group Field>"  <!-- optional -->
**Implementation notes:** Not yet supported. Confirmed: Bubble Chart uses the same `scatterChart` visualType as Scatter Chart — the `Size` data role binding is what differentiates it in PBIR. The emitter can extend the Scatter chart template by binding `data-pbi-size` to the `Size` data role.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#bubble-chart) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

## 7. Ranking & flow

### Waterfall Chart
**Intent:** From→to delta decomposed as a sum of contributions — showing how individual positive and negative changes explain a net variance
**When to use:** When the reader's question is "how did we get from value A to value B?" (e.g. budget-vs-actual variance decomposed by cost driver, monthly revenue bridge from last month to this month). Each bar represents one contribution; running total bars show the cumulative position.
**When NOT to use:** When the reader needs to compare absolute values across categories — use a Bar chart. Avoid when there are more than ~10 contributing items, as the visual becomes cluttered. Do not use for showing composition at a point in time — use a Stacked Bar or Treemap.
**Data shape:** 1 categorical dimension (ordered categories/stages) + 1 measure (delta values) + optional 1 breakdown dimension
**PBIR visualType:** `waterfallChart`
**Data roles required:** `Category`, `Y`, `Breakdown` (optional)
**Proposed SimBI annotation:**
  data-pbi="waterfallChart"
  data-pbi-axis="<Category or Stage Field>"
  data-pbi-values="<Delta Measure>"
  data-pbi-breakdown="<Breakdown Field>"  <!-- optional -->
**Implementation notes:** Not yet supported. Confirmed `waterfallChart` visualType from PBIR samples (Supply Chain Dashboard). New emitter template required. The waterfall visual in Power BI auto-calculates running totals from delta values. The optional `Breakdown` role adds a sub-group dimension to each waterfall bar.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#waterfall-chart) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Ribbon Chart
**Intent:** Category rank changes over time — stacked columns where ribbon connectors between periods show how category positions shift
**When to use:** When the reader's question is "how have the relative rankings of categories changed over time?" (e.g. product sales rank by quarter, market share rank by month). The crossing ribbons make rank inversions immediately visible in a way a standard line chart cannot.
**When NOT to use:** When absolute values matter more than rank order — use a Stacked Column chart. Avoid when there are more than ~6 categories, as overlapping ribbons become unreadable. Do not use when time periods are not evenly spaced or when there is only one time period.
**Data shape:** 1 date/time dimension + 1 measure + 1 categorical series dimension (the ranked categories)
**PBIR visualType:** `ribbonChart`
**Data roles required:** `Category`, `Y`, `Series`
**Proposed SimBI annotation:**
  data-pbi="ribbonChart"
  data-pbi-axis="<Date or Period Field>"
  data-pbi-values="<Measure Name>"
  data-pbi-series="<Ranked Category Field>"
**Implementation notes:** Not yet supported. Confirmed `ribbonChart` visualType from PBIR samples (Supply Chain Dashboard + Visual Vocabulary). New emitter template required. The `Series` role determines which categories are ranked and connected by ribbons across time periods.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#ribbon-chart) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Decomposition Tree
**Intent:** AI-assisted hierarchical drill-down to explain what drives a measure
**When to use:** When the reader wants to interactively decompose a measure (e.g. total sales) by successively splitting on the dimension that explains the most variance at each level. Useful for exploratory root-cause analysis where the analyst does not know in advance which dimensions to drill into.
**When NOT to use:** When the hierarchy of dimensions is already known and fixed — use a matrix or a series of bar charts instead. Do not use when a static, reproducible breakdown is required; the AI-driven split is non-deterministic. Avoid on embedded or exported reports where interactive drilling is not possible.
**Data shape:** 1 measure (the value being explained) + 2+ categorical dimensions (potential explanatory factors)
**PBIR visualType:** `decompositionTreeVisual`
**Data roles required:** `Analyze` (measure), `Explain By` (dimensions)
**Proposed SimBI annotation:**
  data-pbi="decompositionTree"
  data-pbi-values="<Measure to Analyze>"
  data-pbi-explain-by="<Dim1>, <Dim2>, ..."
**Implementation notes:** Requires Power BI service-side AI computation — out-of-scope for SimBI; will be marked ⚪ in the roadmap. SimBI cannot generate the trained model or invoke the service-side AI that selects which dimension to split at each level. Document for reader awareness. If Power BI ever exposes the decomposition logic in a static PBIR format (fixed splits), revisit this entry.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#decomposition-tree) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

## 8. Geographic

### Map
**Intent:** Bubble map sized by measure plotted at geographic coordinates or addresses
**When to use:** When the reader's question is "where is this concentrated?" and the data has a geographic dimension (city, address, lat/lon) plus a numeric measure (sales, incidents, headcount). Bubble size encodes magnitude at each location, allowing spatial hotspot detection.
**When NOT to use:** When geographic precision matters at sub-city level — use Azure Map or Shape Map. Avoid when you have more than ~200 points (bubbles overlap unreadably). Do not use when regional totals, not point locations, are what matters — use Filled Map instead.
**Data shape:** 1 location field (address, city, country) or lat + lon pair + 1 measure (bubble size) + optional 1 categorical dimension (legend color)
**PBIR visualType:** `map`
**Data roles required:** `Location`, `Latitude` (optional), `Longitude` (optional), `Size`, `Legend` (optional)
**Proposed SimBI annotation:**
  data-pbi="map"
  data-pbi-location="<Table>[<LocationColumn>]"
  data-pbi-size="<Size Measure>"
  data-pbi-legend="<Table>[<CategoryColumn>]"  <!-- optional -->
**Implementation notes:** Not yet supported. Confirmed `map` visualType from Microsoft PBIR samples. New emitter template needed. Requires Bing Maps geocoding — works for tenants where Bing Maps is enabled (now deprecated in some regions). When latitude/longitude columns are available, bind them to the `Latitude`/`Longitude` data roles to bypass geocoding.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#map) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Filled Map
**Intent:** Choropleth map coloring geographic regions by measure intensity
**When to use:** When the reader's question is "how does this metric differ by region?" and the data has a standard geographic dimension (country, state, province) with a continuous measure. Color saturation encodes the measure value for each region polygon, making regional patterns immediately visible.
**When NOT to use:** When exact point locations matter — use Map (bubbles). Avoid when regions have vastly different sizes and smaller high-value regions are visually swamped — consider a bar chart ranked by region instead. Do not use when comparing more than two measures simultaneously.
**Data shape:** 1 geographic dimension (country/state/region name) + 1 measure (fill color intensity)
**PBIR visualType:** `filledMap`
**Data roles required:** `Location`, `Color saturation`
**Proposed SimBI annotation:**
  data-pbi="filledMap"
  data-pbi-location="<Table>[<RegionColumn>]"
  data-pbi-color-saturation="<Measure Name>"
**Implementation notes:** Not yet supported. Confirmed `filledMap` visualType from Microsoft PBIR samples. New emitter template needed. Same Bing Maps geocoding dependency as the Map visual — works only for tenants where Bing Maps is enabled (now deprecated in some regions). Region names must match Bing Maps' expected strings (e.g., full country name, ISO codes not guaranteed).
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#filled-map) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Azure Map
**Intent:** Cloud-hosted map visual backed by Azure Maps service, offering higher fidelity and more styling options than Bing-based visuals
**When to use:** When the tenant has Azure Maps enabled and needs advanced map capabilities (custom tile layers, traffic, satellite imagery, better geocoding). Preferred over Map/Filled Map when Bing Maps is deprecated or unavailable in the tenant region.
**When NOT to use:** When the tenant does not have Azure Maps subscription configured — the visual renders blank. Do not use when a simple bubble or choropleth suffices; the additional setup cost is not justified for straightforward geographic summaries.
**Data shape:** 1 location field or lat/lon pair + 1 or more measures or categorical dimensions
**PBIR visualType:** `azureMap`
**Data roles required:** `Location`, `Latitude` (optional), `Longitude` (optional), `Size` (optional), `Color saturation` (optional)
**Proposed SimBI annotation:**
  data-pbi="azureMap"
  data-pbi-location="<Table>[<LocationColumn>]"
  data-pbi-size="<Size Measure>"  <!-- optional -->
**Implementation notes:** Confirmed `azureMap` visualType from PBIR samples. Requires Azure Maps subscription and tenant admin enablement; SimBI cannot configure subscription credentials — will be marked ⚪ in the roadmap. Even if the PBIR structure can be emitted, the visual will not render without a valid Azure Maps key configured at the tenant level.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#azure-map) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Shape Map
**Intent:** Choropleth map using custom TopoJSON shapes for non-standard or internal geographies (e.g. sales territories, floor plans, custom regions)
**When to use:** When standard Bing/Azure geocoding does not match your geographic units — for example, custom sales territories, facility floor plans, or administrative regions not recognised by Bing. The user supplies a TopoJSON file defining the region polygons.
**When NOT to use:** When standard country/state geography suffices — use Filled Map instead (simpler setup). Avoid when the audience needs a recognisable real-world map; custom shapes require users to have prior knowledge of the geography.
**Data shape:** 1 location field matching TopoJSON region keys + 1 measure (fill color intensity)
**PBIR visualType:** `shapeMap`
**Data roles required:** `Location`, `Color saturation`
**Proposed SimBI annotation:**
  data-pbi="shapeMap"
  data-pbi-location="<Table>[<RegionKeyColumn>]"
  data-pbi-color-saturation="<Measure Name>"
  data-pbi-topojson="<path-or-url>"  <!-- user-supplied TopoJSON -->
**Implementation notes:** Not yet supported. Requires user-supplied TopoJSON; SimBI would need a path/upload mechanism beyond current scope. The PBIR structure must reference the TopoJSON source — this introduces a file-dependency that SimBI's current emitter architecture does not handle. Verify PBIR visualType string against a sample before scheduling implementation.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#shape-map) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

## 9. Tabular

### Table
**Intent:** Flat row-by-row display of data with optional totals — the go-to visual when exact values matter more than visual patterns
**When to use:** When the reader's question requires precise numbers across multiple attributes simultaneously (e.g. "show me sales, cost, and margin for each product"). Best when the audience will read individual rows rather than scan for a trend. Appropriate when the dataset is small enough to scan (under ~50 rows without scrolling) or when export/drill-through is the primary use.
**When NOT to use:** When a trend, comparison, or composition can be shown more clearly with a chart — a table forces the reader to do the comparison mentally. Avoid when there are more than ~10 columns; horizontal scrolling destroys readability. Do not use when only one measure is needed — a Card or KPI visual communicates a single value more efficiently.
**Data shape:** 2+ fields (any mix of categorical dimensions and measures); no strict shape constraint
**PBIR visualType:** `tableEx`
**Data roles required:** `Values`
**Proposed SimBI annotation:**
  data-pbi="table"
  data-pbi-columns="<MeasureOrField1>, <Table>[<Column2>], ..."
**Implementation notes:** Already supported — see `VisualType.TABLE` in `src/simbi_mcp/mockup/annotations.py`. The `data-pbi-columns` attribute accepts a comma-separated list of tokens where each token is either a bare measure name or a `Table[Column]` reference. **Important:** the PBIR JSON SimBI emits uses `tableEx`, NOT `table` — the translation from the HTML annotation token `table` to the PBIR visualType `tableEx` happens in `_PBI_VISUAL_TYPE` in `src/simbi_mcp/pbir/templates.py`.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#table) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Matrix
**Intent:** Pivot table with row and column headers, values at intersections, and automatic subtotals — the tabular equivalent of a cross-tab analysis
**When to use:** When the reader's question is "what is metric X for each combination of dimension A and dimension B?" (e.g. sales by product category × region, with subtotals per category). The nested row/column header drill-down capability makes it powerful for hierarchical breakdowns.
**When NOT to use:** When only one dimension axis is needed — a Table is simpler. Avoid when the cross-product of rows × columns is large (many blank cells, poor performance). Do not use when visual comparison across categories is the goal — a bar chart communicates rank differences far more clearly than a matrix of numbers.
**Data shape:** 1+ categorical dimensions for rows + 1+ categorical dimensions for columns + 1+ measures for values
**PBIR visualType:** `pivotTable`
**Data roles required:** `Rows`, `Columns`, `Values`
**Proposed SimBI annotation:**
  data-pbi="matrix"
  data-pbi-rows="<Table>[<RowDim1>], <Table>[<RowDim2>]"
  data-pbi-columns="<Table>[<ColDim1>]"
  data-pbi-values="<Measure1>, <Measure2>"
**Implementation notes:** Not yet supported. Confirmed `pivotTable` visualType from PBIR samples (Supply Chain Dashboard). New annotation attributes needed (`data-pbi-rows`, `data-pbi-columns`, `data-pbi-values` — three separate role buckets, unlike Table's single `data-pbi-columns`). The PBIR structure differs significantly from `tableEx` — it encodes row hierarchy, column hierarchy, and value bindings separately — so a new dedicated emitter template is required rather than extending the Table template.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#matrix) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

## 10. AI-driven

### Key Influencers
**Intent:** AI-driven ranked list of factors that statistically increase or decrease a target metric
**When to use:** When the reader's question is "what factors most strongly drive metric X up or down?" and the dataset has multiple candidate explanatory dimensions. The visual runs a logistic/linear regression in the PBI service and ranks influencers by effect size with confidence intervals.
**When NOT to use:** When a fixed, deterministic explanation is required — the AI-selected influencers change as data changes, making results non-reproducible in static reports. Avoid in embedded or exported contexts where the service-side inference cannot execute. Do not use when the relationship between variables is already understood — a scatter chart or bar chart with a known breakdown communicates a predetermined insight more clearly.
**Data shape:** 1 measure or binary categorical (the target to explain) + 2+ categorical/numeric dimensions (candidate explanatory factors)
**PBIR visualType:** `keyDriversVisual`
**Data roles required:** `Analyze`, `Explain By`
**Proposed SimBI annotation:**
  data-pbi="keyInfluencers"
  data-pbi-analyze="<Target Measure or Field>"
  data-pbi-explain-by="<Dim1>, <Dim2>, ..."
**Implementation notes:** Requires PBI service-side ML model training. SimBI emits only the report layer; the trained model and runtime inference live in the PBI service. ⚪ out-of-scope. Even emitting the PBIR skeleton would produce a visual that renders blank or errors without the service-side computation. Document for completeness; do not schedule for implementation.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#key-influencers) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Q&A Visual
**Intent:** Natural-language query box that lets report consumers ask questions in plain English and receive an automatically chosen chart or value in response
**When to use:** When the report audience includes non-technical consumers who want ad-hoc exploration without navigating a fixed layout. Effective in Power BI Service where the NL engine has been trained on the model's tables, columns, and synonyms.
**When NOT to use:** When the report is embedded, exported, or viewed offline — the NL engine requires a live PBI service connection. Avoid when precise, reproducible charts are needed; the Q&A response varies by phrasing. Do not use as a substitute for well-designed visuals for known questions.
**Data shape:** No fixed shape — the NL engine selects fields dynamically based on the question text
**PBIR visualType:** `qnaVisual`
**Data roles required:** N/A (driven by NL query at runtime)
**Proposed SimBI annotation:**
  data-pbi="qnaVisual"
  data-pbi-question="<Optional pre-seeded question text>"
**Implementation notes:** Requires PBI service-side NL inference and a configured Q&A synonyms/linguistic-schema. SimBI cannot generate this configuration. ⚪ out-of-scope. The linguistic schema and synonym tables are maintained in the Power BI dataset, not the report PBIR layer — SimBI has no access to or influence over them. A pre-seeded question can be embedded in PBIR but the response rendering is entirely service-side.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#q-a-visual) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

### Smart Narrative
**Intent:** Auto-generated text box that summarises key insights from data in natural language, updating dynamically as filters change
**When to use:** When the report needs an executive summary panel that describes the data in sentences rather than charts. Effective for audiences who prefer text over visuals, or as a companion to a complex visual to call out the headline findings.
**When NOT to use:** When a static, author-controlled text block is needed — use a standard Text Box visual instead. Avoid in embedded or exported contexts where the AI content generation cannot execute. Do not use when precise wording matters; the generated text is non-deterministic and may change unexpectedly.
**Data shape:** No fixed shape — the AI engine selects and summarises fields/measures it deems relevant
**PBIR visualType:** Not in samples — likely a service-rendered variant; not implementable without PBI service inference
**Data roles required:** N/A (AI-selected from the page/report context)
**Proposed SimBI annotation:**
  data-pbi="smartNarrative"
  <!-- No field bindings — content is fully AI-generated at runtime -->
**Implementation notes:** PBIR-level this is likely a `textbox` (TBD — verify against a PBIR sample) with AI-generated content tokens. The text generation happens in the PBI service. ⚪ out-of-scope for AI features. SimBI can potentially emit an empty textbox skeleton (a plain `textbox` PBIR visual), but cannot pre-fill the narrative — the AI-generated tokens are resolved only when the report is rendered by the PBI service. Do not schedule for implementation beyond the empty skeleton.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#smart-narrative) · [design notes](dashboard-design-playbook.md#choosing-the-right-chart)

## 11. Filtering

### Slicer
**Intent:** Interactive filter applied to other visuals on the page
**When to use:** When the audience needs to filter the dashboard by a dimension (region, date, product). Place at the top or in a left rail; never scatter slicers across the page.
**When NOT to use:** When the filter is fixed for the entire dashboard purpose — bake it into the underlying measures or page filter instead.
**Data shape:** 1 categorical field (or a date for range/between modes)
**PBIR visualType:** `advancedSlicerVisual`
**Data roles required:** `Field`
**Proposed SimBI annotation:**
  data-pbi="slicer"
  data-pbi-field="<Table>[<Column>]"

**Slicer modes (all share the annotation above):**
- **List** ✅ supported today. Renders as `db-pill` items. Default mode.
- **Dropdown** — compact for many options. PBIR difference: a `selection.singleSelect=false` config + `dropdown` display mode. TBD — verify.
- **Between** — two-handle range slider. For numeric or date fields. PBIR difference: `slicerRange.start`/`end` config.
- **Range** — single-handle "less than" or "greater than" slider. Similar PBIR shape to Between.
- **Hierarchy** — tree of nested categorical fields. Requires `data-pbi-fields` (plural) instead of `data-pbi-field`. Marked ⚪ in roadmap (complex).

**Implementation notes:** List mode is supported — see `VisualType.SLICER` in `src/simbi_mcp/mockup/annotations.py`. **Important:** the PBIR JSON SimBI emits uses `advancedSlicerVisual`, NOT `slicer` — translation in `_PBI_VISUAL_TYPE` in `src/simbi_mcp/pbir/templates.py`. The classic `slicer` PBIR visualType also exists but isn't what SimBI writes. Other modes require new emitter config; Hierarchy mode would need a new annotation attribute.
**Cross-refs:** [roadmap](simbi-visual-roadmap.md#slicer) · [design notes](dashboard-design-playbook.md#interactivity-patterns)
