# Power BI Dashboard: Step-by-Step Build Guide

You'll build a 4-page interactive dashboard from the Parquet files in `dashboard/data/`. Plan on **4–6 hours** across a few sessions. Save often (**Ctrl+S**) as `dashboard/cfpb_complaints.pbix`.

Each part ends with a **checkpoint**: numbers your dashboard must show. They come from the SQL results, so if Power BI matches, your model and DAX are right. Checking the BI tool against the source is a habit worth mentioning in interviews.

> Power BI's menus move a little between monthly releases. If a button isn't exactly where described, search for it with the **Search** box in the title bar.

---

## Part 0 — Install and prepare (15 min)

1. Install **Power BI Desktop** from the Microsoft Store (free), or run:
   ```
   winget install --id 9NTXR16HNW1T --source msstore
   ```
2. From the project folder, make sure the extracts exist (this rebuilds them after the tests pass):
   ```
   .venv\Scripts\python.exe run_pipeline.py --skip-raw
   ```
   You should see 6 `.parquet` files in `dashboard\data\`.
3. Open Power BI Desktop → close the splash screen → **File > Options and settings > Options**:
   - *Current file > Data load*: **uncheck "Auto date/time"**. We have our own date table; the automatic one bloats the model and conflicts with time intelligence.
   - *Current file > Regional settings*: English (United States).

## Part 1 — Load the data (15 min)

1. **Home > Get data > More… > search "Parquet" > Connect.**
2. Paste the full path to `dashboard\data\fact_complaints_monthly.parquet` (for example `C:\Users\lekha\projects\cfpb-complaints-analysis\dashboard\data\fact_complaints_monthly.parquet`) → **OK** → **Load**.
3. Repeat for the other 5 files: `dim_company`, `dim_product`, `dim_issue`, `dim_geography`, `dim_date`.
4. In the **Data** pane (right side) you should now have 6 tables named after the files.

**Why Import mode:** the data is loaded into Power BI's in-memory engine, which is fast and works with Publish to web. Parquet keeps column types (dates stay dates, numbers stay numbers), so there's no manual type fixing.

## Part 2 — Build the star-schema model (20 min)

1. Click the **Model view** icon (left rail, third icon).
2. Power BI may auto-detect some relationships. **Delete any it created** (select the line → Delete) and create these 5 by dragging from the fact column onto the dimension column:

   | From (many side) `fact_complaints_monthly` | To (one side) | |
   |---|---|---|
   | `month_key` | `dim_date[date_key]` | |
   | `company_key` | `dim_company[company_key]` | |
   | `product_key` | `dim_product[product_key]` | |
   | `issue_key` | `dim_issue[issue_key]` | |
   | `state_code` | `dim_geography[state_code]` | |

   Each should read **Many-to-one (\*:1)**, cross-filter direction **Single**. Single direction means the filters flow from the dimensions to the fact, which is the standard star-schema setup and avoids ambiguous filter paths.

3. **Mark the date table:** select `dim_date` → right-click → **Mark as date table** → date column: `date`. This turns on `SAMEPERIODLASTYEAR`, `DATEADD`, etc.
   - Why `month_key` points at a daily date table: the fact is monthly, keyed to the 1st of each month, and every 1st exists in `dim_date`, so time intelligence still works.
4. **Sort month names:** Data view → `dim_date` → select `month_name` → **Column tools > Sort by column > month_num** (otherwise Apr comes before Jan).
5. **Geography category:** `dim_geography` → select `state_name` → **Column tools > Data category > State or Province**. Do the same for `state_code`. This tells maps what the values are.
6. **Hide the keys:** in Model view, right-click each `*_key` column and `state_code` in the fact table → **Hide in report view**. Report users filter by names, not IDs.
7. **Hide the raw count columns** in the fact table too (`complaints`, `timely_count`, …). Everyone should use the measures, so every visual computes rates the same way.

✅ **Checkpoint 2:** Model view shows the fact table in the middle with 5 dimensions around it, like a star.

## Part 3 — Add the DAX measures (30–45 min)

1. **Home > Enter data** → name the table `_Measures` → **Load**. (A dedicated table keeps measures in one place at the top of the field list.)
2. Select `_Measures` → **Home > New measure** → paste one measure from [`measures.dax`](measures.dax) → press Enter. Repeat for each measure, in file order (later ones reference earlier ones).
3. After adding the first measure, delete the placeholder `Column1` from `_Measures`.
4. **Format each measure** (select it → **Measure tools** ribbon):
   - Counts (`Complaints`, `Closed Complaints`, etc.): Whole number, thousands separator.
   - Every `%` measure and `Relief Rate vs Peer Avg`: **Percentage, 1 decimal**.
   - `Complaints 3M Avg`, `Complaints 12M Avg`, `Complaints per 100K (annualized)`, `Complaints Index (2018 = 100)`: Whole number.
   - `Latest Data Month`: Date, format `mmm yyyy`.
5. Optional but tidy: in Model view, select measures and set **Display folder** (`Counts`, `Rates`, `Time`, `Geography`, `Peers`).

**Key DAX ideas to be able to explain:**
- `DIVIDE` instead of `/`: returns blank instead of an error when the denominator is 0.
- `CALCULATE` changes the filter context. `Complaints PY` recalculates `Complaints` with the dates shifted back a year.
- The rolling averages build a small table of month totals (`ADDCOLUMNS` over `VALUES`) for the trailing window, then average it. That's a true average of monthly totals, not a sum divided by a guess.
- `REMOVEFILTERS(dim_company)` inside `Peer Avg Relief Rate %` makes the peer average ignore whichever bank is on the current row, so every row compares against the same benchmark.

✅ **Checkpoint 3.** Drop a **Card** on a blank page with each measure. With no filters:

| Measure | Expected |
|---|---|
| Complaints | 16,586,389 |
| Timely Response % | 99.5% |
| Relief Rate % | 37.3% |
| Credit Bureau Share % | 81.2% |

Then delete those test cards.

## Part 4 — Theme and page setup (10 min)

1. **View > Themes > Browse for themes** → select [`theme.json`](theme.json). This applies a colorblind-safe palette (validated categorical order), consistent fonts and a light background.
2. **Canvas:** Format pane (with no visual selected) → *Canvas settings* → Type **16:9**.
3. Create 4 pages (the **+** at the bottom), named exactly:
   `Executive Overview` · `Product & Issue Trends` · `Company Benchmarking` · `Geographic View`

### Shared slicers (build once on page 1, then sync)

Put a row of 5 slicers across the top of **Executive Overview**:

| Slicer | Field | Style |
|---|---|---|
| Date range | `dim_date[date]` | Between (slider) |
| Company type | `dim_company[company_type]` | Dropdown, multi-select |
| Company | `dim_company[company_name]` | Dropdown, **search on** (Format > Slicer settings > Options) |
| Product | `dim_product[product_group]` | Dropdown |
| State | `dim_geography[state_name]` | Dropdown, search on |

- **Company type default:** select *Other company* and *Regions peer group* (Ctrl+click). That leaves out the three credit bureaus, which would otherwise dominate every chart. The `Credit Bureau Share %` card on page 1 keeps their scale visible.
- **Sync them:** **View > Sync slicers** → for each slicer tick **Sync** and **Visible** on all 4 pages. Filters now carry across pages, like a real product.
- Add a **Reset** button: **Insert > Buttons > Reset**, action *Bookmark*. First create a bookmark of the default state (**View > Bookmarks > Add**, name it "Default").

## Part 5 — Build the pages (2–3 h)

General rules (these follow the data-viz guidelines the project uses):
- One measure per axis. **Never use a dual y-axis.** Two measures with different scales go in two charts.
- Titles say what the chart shows: "Relief rate by bank", not "Chart 3".
- Turn off data labels except where a few values matter. Gridlines stay light (the theme handles this).
- Max ~6 series per chart. With more, use small multiples or a Top N filter.

### Page 1 — Executive Overview

*Answers: how big is the problem, is it growing, and how well do companies respond?*

1. **KPI row** (Insert > **Card (new)**, one card with several measures, or 5 separate cards):
   `Complaints` · `Complaints YoY %` · `Timely Response %` · `Relief Rate %` · `Credit Bureau Share %`.
   - For `Complaints YoY %` to make sense, it needs a one-year context. Add a card-level filter `dim_date[year]` = latest full year (2025), and title it "YoY growth, 2025".
2. **Line chart:** "Monthly complaints with 12-month average"
   - X-axis: `dim_date[month_start]` (right-click the field → use the actual date, not the Date Hierarchy)
   - Y-axis: `Complaints` and `Complaints 12M Avg` (two lines, **same scale**, so a single axis is correct)
   - Visual filter: `dim_date[is_complete_month]` = True
3. **Bar chart:** "Complaints by product": Y `dim_product[product_group]`, X `Complaints`, sorted descending.
4. **Table:** "Top 10 companies": `dim_company[company_name]`, `Complaints`, `Timely Response %`, `Relief Rate %`. Filter pane → `company_name` → *Top N* = 10 by `Complaints`.
5. **Text box** (Insert > Text box) with one sentence of the key insight, e.g. *"Excluding the credit bureaus, complaints more than doubled from mid-2024 to Aug 2026 (12-month average 30K → 71K per month)."*

✅ **Checkpoint 5.1:** Set Company type to all three values (bureaus included) and Date range to 2025 → Complaints **5,442,963**, YoY **+99.1%**.

### Page 2 — Product & Issue Trends

*Answers business question 1: which products and issues, and how they're trending.*

1. **Line chart with small multiples:** "Yearly complaints by product"
   - X `dim_date[year]`, Y `Complaints`, **Small multiples** `dim_product[product_group]`
   - Each panel gets its own trend with one color, which avoids 11 colors on one chart.
   - Format > Small multiples > **Y-axis: independent scales** so small products aren't flattened (say so in the subtitle).
2. **Matrix:** "Year-over-year change by product"
   - Rows `product_group`, Columns `dim_date[year]`, Values `Complaints YoY %`
   - Visual filter: year 2019–2025 (full years)
   - Format > Cell elements > **Background color** → fx → Gradient: lowest `#cde2fb` (light blue), highest `#d03b3b` (red) so fast growth stands out.
3. **Decomposition tree** (Insert > More visuals > Decomposition tree): Analyze `Complaints`; Explain by `product_group`, `subproduct`, `issue`, `subissue`. In the finished report, click **+** to drill down. It's a great interactive talking point for interviews.
4. **Bar chart:** "Top 10 issues": `dim_issue[issue]` by `Complaints`, Top N = 10.

✅ **Checkpoint 5.2:** Bureaus included, no date filter: Credit reporting row in the matrix, 2025 column ≈ **+103%** (4,810,301 vs 2,365,586).

### Page 3 — Company Benchmarking

*Answers business questions 2 and 4: worst responders, and Regions vs peers.*

**Top half: Regions vs peers.** Give every visual in this half a visual-level filter `dim_company[company_type]` = *Regions peer group*.

1. **Table scorecard:** "Regions vs peer banks": `company_label`, `Complaints`, `Timely Response %`, `Relief Rate %`, `Relief Rate vs Peer Avg`, `Monetary Relief %`.
   - Conditional formatting on `Relief Rate vs Peer Avg`: Font color → Rules: < 0 → `#d03b3b`, ≥ 0 → `#006300`. Add ▲/▼ icons (Cell elements > Icons) so color isn't the only cue.
2. **Bar chart:** "Relief rate by bank": Y `company_label`, X `Relief Rate %`.
   - **Focus + context coloring:** Format > Bars > Colors > **fx** → Format style *Field value* → `Bar Color (Regions Highlight)`. Regions is blue and peers gray, so the eye goes straight to Regions.
   - Analytics pane (magnifier icon) → **Average line** labelled "Peer group average".
3. **Matrix heatmap:** "Complaint mix by product": Rows `company_label`, Columns `product_group`, Values `Share of Company Complaints %`. Background color gradient white → `#104281` (one hue, light to dark). A heatmap shows the mix without 11 legend colors.
4. **Line chart:** "Overdraft complaints: Regions vs peers": X `dim_date[year]`, Y `Overdraft Share % (Regions)` and `Overdraft Share % (Peers)`. Set the Regions line to blue `#2a78d6` and the peers line to gray `#898781`. Turn on data labels for the last point only (Format > Data labels > *Customize series*).
5. **Line chart:** "Complaint growth (2018 = 100)": X `year`, Y `Complaints Index (2018 = 100)`, Legend `company_label`. Filter year 2018–2025.

**Bottom half: all companies (business question 2).**

6. **Table:** "Companies with the highest no-relief rate (≥1,000 closed complaints)": `company_name`, `Closed Complaints`, `No Relief Rate %`, `Monetary Relief %`, `Timely Response %`.
   - Visual filter: `Closed Complaints` *is greater than or equal to* 1000 (drag the measure into the filter pane).
   - Sort by `No Relief Rate %` descending, then Ctrl+click `Closed Complaints` for the tie-break.

✅ **Checkpoint 5.3:** Scorecard, no date filter → Regions: Relief Rate **25.1%**, vs peer avg **+4.1%**, Timely **99.96%** (use 2 decimals to see it). Huntington 31.6%, Fifth Third 12.2%.

### Page 4 — Geographic View

*Answers business question 3: where complaints come from, per capita.*

1. **Map:** Insert **Azure Maps** (or **Filled map** if that's what your version offers). Location `dim_geography[state_name]`, and color by `Complaints per 100K (annualized)`.
   - Filled-layer colors: *Gradient*, min `#cde2fb` → max `#104281` (single-hue sequential, so darker = more).
   - If maps are disabled in your version or tenant, use **Shape map** (Options > Preview features) with the US states map, or skip the map and make the bar chart below the main visual.
2. **Bar chart:** "Complaints per 100K residents by state": Y `state_name`, X `Complaints per 100K (annualized)`, sorted descending, Top N 15.
3. **Table:** "By census region": `census_region`, `Population`, `Complaints`, `Complaints per 100K (annualized)`. Visual filter `dim_geography[is_state]` = True.
4. **Card:** `Complaints per 100K (annualized)` with a title that responds to the filters. For a dynamic title: Format > Title > fx → create a measure such as
   `Map Title = "Complaints per 100K residents, " & FORMAT(MIN(dim_date[date]),"mmm yyyy") & " – " & FORMAT([Latest Data Month],"mmm yyyy")`.

✅ **Checkpoint 5.4:** Bureaus included, Date range = 2025 → Georgia **3,777** per 100K (#1), South region **2,358**.

## Part 6 — Polish (30 min)

- **Tooltips:** for key visuals, add `Relief Rate %` and `Timely Response %` to the *Tooltips* well so hovering shows context.
- **Edit interactions:** select a slicer or chart → **Format > Edit interactions** → make sure the Credit Bureau Share card is set to **None** (it should never filter).
- **Alt text:** Format > General > Alt text for each chart (accessibility, and reviewers notice).
- **Mobile layout** (optional): View > Mobile layout, drag in the KPI cards and one chart per page.
- **Performance check:** View > Performance analyzer → Start recording → Refresh visuals. Every visual should take under ~1 s thanks to the aggregate table.
- Take screenshots of each page (Win+Shift+S) → save to `images/` as `dashboard_overview.png`, `dashboard_products.png`, `dashboard_benchmark.png`, `dashboard_geo.png`.

## Part 7 — Publish

This part needs a decision about your Microsoft account (see the project chat). We'll do it together once the report is built.

---

### Troubleshooting

| Symptom | Fix |
|---|---|
| Time-intelligence measures return blank | `dim_date` isn't marked as a date table, or the relationship uses the wrong column (must be `month_key` → `date_key`) |
| Totals don't match the checkpoints | Check the Company type slicer (bureaus excluded by default) and that no visual-level filters are left over |
| Month names out of order | Sort `month_name` by `month_num` (Part 2, step 4) |
| A dimension doesn't filter a chart | Missing relationship, or cross-filter direction set wrong |
| "Can't determine relationships between the fields" | You used a column from the fact table in a slicer; use the dimension's column instead |
