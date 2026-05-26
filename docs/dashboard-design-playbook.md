# Dashboard Design Playbook

> Companion guide for SimBI dashboard authors. For the full theory and worked examples, see [DataSense — Dashboard Design Best Practices](https://datasense.to/blog/dashboard-design-best-practices).

## 1. Page Layout & Hierarchy

Every SimBI report is emitted onto a **1280 × 720** canvas — the Power BI default confirmed in `spikes/01_pbir_reference/NOTES.md` ("Page coordinate system"). That is exactly 16:9, which maps cleanly to a widescreen laptop or meeting-room display. Design for that rectangle first; never assume the reader will scroll or resize.

SimBI's `db-grid` class divides the canvas into a three-column, variable-height grid. Span declarations control width (`db-col-1` = one third, `db-col-2` = two thirds, `db-col-3` = full width) and height (`db-row-1` = single row, `db-row-2` = double row). Every visual container should carry exactly one column class and one row class. A KPI strip of four cards across the top is four `db-col-1 db-row-1` `db-card` divs; the primary chart beneath them is typically `db-col-2 db-row-2` or `db-col-3 db-row-2` depending on how much supporting detail sits beside it.

Reading patterns matter because dashboard consumers are not reading — they are scanning. The **F-pattern** suits dense operational reports where the viewer's eye sweeps left-to-right across the top row, then drops and repeats in shorter strokes. Put your most critical KPIs in that top-left zone. The **Z-pattern** suits landing pages and executive summaries where the eye travels corner-to-corner; place a headline number top-left, a trend top-right, a call-to-action or filter bottom-left, and a summary bottom-right. Most SimBI dashboards are operational and lean toward F-pattern — but the choice belongs to the author, not the tool.

<a name="kpi-strip"></a>

The most reliable backbone for a SimBI page is **KPI strip → primary chart → supporting detail**. Lock a narrow top band (one `db-row-1`) for two to four headline cards using `db-label` and `db-value` — Revenue, Margin, Units, and one more if the model supports it. The primary chart owns the largest cell on the page (typically `db-col-2 db-row-2` or `db-col-3 db-row-2`) and answers the report's single most important question. Supporting detail — a slicer column, a breakdown table, a secondary chart — fills the remaining cells. If you cannot decide which chart is "primary," you have not decided what the dashboard is for.

Whitespace is not waste. The `db-card` class already adds padding and a shadow; do not pack cells so tightly that those shadows bleed together. A gap between the KPI strip and the primary chart signals a visual hierarchy that the reader absorbs in under a second. When a cell feels empty, the instinct is to fill it — resist: an intentional gap is cleaner than a chart that has nothing useful to say. For the full theory on visual hierarchy and spacing, see [DataSense — Dashboard Design Best Practices](https://datasense.to/blog/dashboard-design-best-practices).

## 2. Choosing the Right Chart

<a name="choosing-the-right-chart"></a>

### Decision tree

Start here when a chart type is not obvious. The tree maps the reader's analytical intent to a recommended visual:

```
What is the reader trying to do?

├── See ONE number
│     └── Card  (or KPI Card if there is a target to compare against)
│
├── COMPARE values across categories
│     ├── Ordered / short list          → Bar Chart (horizontal)
│     ├── Time on X axis                → Column Chart
│     └── Multiple series               → Clustered Column or Stacked Column
│
├── See a TREND over time
│     └── Line Chart  (Area Chart if cumulative magnitude matters)
│
├── See PART-TO-WHOLE
│     ├── ≤ 5 segments                  → Donut  (or Pie, with reservations)
│     └── > 5 segments                  → Bar Chart or Treemap
│
├── See DISTRIBUTION
│     └── Binned Bar Chart  (Power BI has no native histogram)
│
├── See CORRELATION
│     └── Scatter Chart  (Bubble Chart if a third measure adds context)
│
└── See FLOW or RANKING
      └── Waterfall, Ribbon, or Funnel
```

For full per-chart specifications — required fields, optional fields, and when to avoid each type — see [`chart-catalog.md`](chart-catalog.md).

### Before / after examples

**Pie chart with 12 slices.** A pie or donut with more than five segments turns into a color-legend guessing game. The reader cannot rank the slices accurately, and the smallest wedges become invisible. Fix: replace with a [Bar Chart](chart-catalog.md#bar-chart) sorted descending so the viewer reads ranking immediately, left to right, with no legend required.

**Dual-axis trend chart combining two incompatible measures.** Placing Revenue (millions) and Return Rate (percentage) on a shared time axis with two Y axes forces the reader to mentally context-switch on every data point; the crossing lines create a false impression of correlation. Fix: split into two [Line Charts](chart-catalog.md#line-chart) stacked vertically (small multiples), each with its own correctly-scaled axis, so the trends are readable independently.

**Raw table dump — 200 rows × 8 columns, no aggregation.** An unfiltered table is a data export, not a dashboard visual; it tells the reader nothing without scrolling and sorting by hand. Fix: replace with a [Matrix](chart-catalog.md#matrix) that groups by the key dimensions and adds subtotals, surfacing the structure the analyst already understands.

### A note on guidance vs. specification

The rules above are defaults informed by perception research and SimBI's canvas constraints, not laws. Context, audience, and brand can justify departures. When you want the authoritative lookup — accepted field types, emitter support, known limitations — use [`chart-catalog.md`](chart-catalog.md), not this section.

## 3. Color

### Palette by data type

Pick palette by data type, not by taste. **Categorical** palettes use distinct hues (eight maximum) to separate unordered groups — product lines, regions, sales reps — where no hue should imply rank; a Revenue-by-Region bar chart is a canonical case. **Sequential** palettes use a single hue from light to dark to encode magnitude across an ordered measure — heat-intensity on a matrix, spend concentration by territory — so the reader can read "more" as "darker" without a legend. **Diverging** palettes use two hues meeting at a neutral midpoint to show above/below-benchmark performance — variance-to-plan, NPS deltas — where both direction and magnitude carry meaning.

### Semantic color

Green means good. Red means bad. Grey means neutral or inactive. Reserve these associations and never reassign them — using red as a category color for, say, the APAC region will make every APAC bar look like an alert. Semantic color works because it is predictable; the moment you borrow it for decoration you destroy the signal.

### Accessibility

Meet WCAG AA: 4.5:1 contrast ratio minimum for all body text and label text against their background. Never encode information by color alone — every color distinction must be reinforced by shape, label, or position, because roughly 8% of men have some form of color-vision deficiency. In practice: label your lines directly instead of relying on a color legend, and use filled/outlined shapes alongside color to distinguish scatter series.

### SimBI palette

SimBI's mockup layer expresses color through CSS classes, not inline styles. `db-card` provides the white card with drop shadow that forms the baseline surface for every visual container. Slicer state is expressed through `db-pill` (unselected) and `db-pill active` (selected), giving a single accent color for the active filter without requiring any additional palette definition. The default is intentionally minimal: most dashboards need nothing beyond it. If you extend the palette — adding an accent for a new status indicator, for example — you must update both the `CSS_CLASS_CATALOG` string in `src/simbi_mcp/mockup/annotations.py` **and** the actual stylesheet. These two must stay in sync; one without the other will either produce undocumented classes that Claude will not emit or documented classes that render unstyled.

## 4. Typography & Density

**One typeface, three sizes maximum.** SimBI's class vocabulary encodes this directly: `db-label` is the small, muted label that sits above a metric (dimension name, column header, period qualifier); `db-value` is the large bold number that carries the KPI. Add a title size for section headers and stop there. More sizes do not create more hierarchy — they create more noise.

**Number formatting is not optional.** Right-align all numerics so decimal points and thousands-separators stack vertically; misaligned columns force the eye to re-anchor on every row. Hold precision constant within a column — do not mix integers and two-decimal values in the same field. Abbreviate at scale: 1.2M is faster to read than 1,234,567 and takes up a third of the space, but only abbreviate consistently (all values in the column, not just the large ones). Thousand-separator commas are non-negotiable — a bare seven-digit number is a parsing burden the reader should never have to carry.

**Ink-to-data ratio (Tufte).** Kill gridlines: the reader's eye will find the bar top without a horizontal rule behind it, and removing gridlines halves the visual noise on most charts. Remove redundant axis ticks that duplicate the label directly beside them — the tick adds nothing once the label is present. Strip decorative borders from card interiors; a border inside a `db-card` is a border inside a border. The default `db-card` style is already lean — resist customizations that add visual weight.

## 5. Interactivity Patterns

### Slicers

Place slicers in one of two locations: a top rail spanning the full canvas width, or a dedicated left-column rail occupying a single `db-col-1` cell. Never scatter them across the page — a slicer buried beside a chart, or wedged below a KPI card, disappears from the reader's mental model of what can be filtered. **A scattered slicer is a broken slicer.** When the reader cannot find the controls, they assume there are none and distrust the numbers.

Default state matters as much as placement. Avoid pre-filtering a dashboard to a specific region, period, or segment unless the dashboard is explicitly scoped — "Q3 North America Review" — and the scope is stated in the page title. A silent pre-filter is a trap: the reader sees partial data and believes it is complete. The "Select all" state is the correct default for any slicer on a general-purpose dashboard. Maintain it.

SimBI's slicer visuals use `db-pill` for unselected options and `db-pill active` for the selected state. The single accent color is deliberate — it registers as a control, not a data series. For the full slicer specification, see [chart-catalog.md#slicer](chart-catalog.md#slicer).

### Cross-filter vs Cross-highlight

**Cross-filter** is a strict drill: clicking a segment in one visual removes all other data from every other visual on the page — the selected slice is the only thing visible. Use cross-filter when the reader's intent is to focus entirely on that slice and comparisons to the rest of the data would be a distraction.

**Cross-highlight** is a comparison tool: clicking a segment in one visual dims the unselected portions of every other visual while keeping them visible, so the reader sees the selected slice in context against the whole. Use cross-highlight when seeing the proportion or relative size of the slice against the full dataset is the analytical point — for example, understanding how a single region contributes to a company-wide trend.

Power BI applies cross-highlight by default. Override to cross-filter intentionally, not by habit.

### Drillthrough, Bookmarks, and Tooltips

Drillthrough pages, bookmark navigation, and custom tooltip pages are powerful interactivity patterns that significantly improve the depth and focus of an analytical experience. They are **not yet emitted by SimBI** — the current emitter generates static visual layouts without wiring these behaviors. This is tracked future work; see [simbi-visual-roadmap.md](simbi-visual-roadmap.md) for tracked work. When designing dashboards today, plan layouts that stand alone without drillthrough; when SimBI adds support, retrofitting will be straightforward because the page-and-grid structure already maps cleanly to the required target-page architecture.

<a name="interactivity-patterns"></a>

## 6. Anti-Patterns

### 3D anything

3D bars and pies distort the data — the foreground bar always reads taller, the back slice always reads smaller. The visual encodes a lie before the reader even processes the numbers. Power BI does not offer 3D natively, but custom visuals do; resist them. No analytical benefit justifies the perceptual distortion.

**Do this instead:** flat 2D versions — see [Bar Chart](chart-catalog.md#bar-chart).

### Pie/donut with more than 5 slices

Humans cannot compare arc lengths accurately past a handful of slices. After 5, the chart becomes decorative — a color-legend guessing game where the smallest wedges are invisible and the ranking is unreadable without hovering on every segment. The data exists; the chart fails to communicate it.

**Do this instead:** sorted bar chart — see [Bar Chart](chart-catalog.md#bar-chart).

### Dual-axis charts that mislead

Two measures on independent Y axes can be scaled to imply correlation that isn't there. If the two axes don't share a meaningful zero or unit, the visual lies — a line that tracks a bar perfectly looks like causation but may be an artifact of axis scaling. The reader cannot verify the scaling without reading the axis labels carefully, and most readers don't.

**Do this instead:** small multiples — see [Line Chart](chart-catalog.md#line-chart).

### Rainbow palettes on ordinal data

Using categorical hues on data with an inherent order (e.g., satisfaction 1–5, risk Low/Medium/High) hides the order. The eye sees five unrelated categories instead of five steps on a scale, stripping the chart of the directional signal that makes the data meaningful. Categorical color is for unordered groups; ordinal data demands an ordered palette.

**Do this instead:** sequential palette — see §3 Color above.

### Decoration over data

Backgrounds, drop shadows on individual bars, gradients, branding flair applied to every visual — every pixel that isn't data competes with the data. The reader's attention is finite; decoration spends it on nothing. Brand belongs in the page header and the report theme, not on every bar or card interior.

**Do this instead:** the SimBI default `db-card` style is intentionally minimal; resist customizations that add visual weight.

## 7. Further Reading

- **[DataSense — Dashboard Design Best Practices](https://datasense.to/blog/dashboard-design-best-practices)** — the canonical reference. This playbook is a digest; the blog has the worked examples and theory.
- **Cole Nussbaumer Knaflic — _Storytelling with Data_** — the canonical book on narrative dashboard design.
- **Stephen Few — _Information Dashboard Design_** — the canonical book on at-a-glance dashboards.
