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

## Part 3 — Add the DAX measures (10 min)

1. **Home > Enter data** → name the table `_Measures` → **Load** (or **Create**, then **Close & Apply** if the Power Query editor opens). A dedicated table keeps measures in one place at the top of the field list.
2. Open **TMDL view** (the `</>` icon in the left rail), click in the editor, and paste the whole of [`measures.tmdl`](measures.tmdl). Click **Apply**.
   - This creates all 29 measures at once, already formatted (whole numbers, 1-decimal percentages) and grouped into display folders: Counts, Response rates, Time, Geography, Market, Peers.
   - The editor may list "Cannot find name" problems for measures that reference each other. They're harmless: the editor checks the script against the model *before* it's applied. Click **Apply** again and they clear.
   - `measures.tmdl` is generated from [`measures.dax`](measures.dax) by `python dashboard/build_tmdl.py`; `measures.dax` stays the readable source of truth.
3. In the **Data** pane, set `dim_date[year]`, `quarter` and `month_num` to **Don't summarize** (**Column tools > Summarization**). Otherwise Power BI adds the years up ("Sum of year") when you put them on an axis.

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
- **Make slicers 2–5 dropdowns that allow several selections:** Format > search `style` → **Dropdown**; search `selection` → **Single select Off**.
- **Copy them to every page:** select all 5 slicers (Ctrl+click) → **Ctrl+C** → go to each other page → **Ctrl+V** → choose **Sync** when asked. Filters now carry across pages, like a real product. (The **View > Sync slicers** pane does the same, but copy-paste was more reliable.)

## Part 5 — Build the pages (2–3 h)

General rules (these follow the data-viz guidelines the project uses):
- One measure per axis. **Never use a dual y-axis.** Two measures with different scales go in two charts.
- Titles say what the chart shows: "Relief rate by bank", not "Chart 3".
- Turn off data labels except where a few values matter. Gridlines stay light (the theme handles this).
- Max ~6 series per chart. With more, use small multiples or a Top N filter.

### Page 1 — Executive Overview

*Answers: how big is the problem, is it growing, and how well do companies respond?*

1. **KPI cards** (4 Cards): `Complaints` · `Timely Response %` · `Relief Rate %` · `Credit Bureau Share %`.
2. **Line chart:** "Complaints more than doubled since mid-2024 (12-month average)"
   - X-axis: `dim_date[month_start]` (choose the field itself, not *Date Hierarchy*)
   - Y-axis: `Complaints` and `Complaints 12M Avg`. Both count complaints, so one axis is correct.
   - Colors: `Complaints` gray `#c3c2b7`, `Complaints 12M Avg` blue `#2a78d6`, stroke width 3, so the trend is the focus and the monthly spikes are context.
3. **Bar chart:** "Complaints by product": `dim_product[product_group]` by `Complaints`, sorted descending.

✅ **Checkpoint 5.1** (default view, bureaus excluded): Complaints **3,125,047**, Timely **97.3%**, Relief **17.3%**, Credit Bureau Share **81.2%**. The monthly line peaks at about **124K in Jan 2025**.

### Page 2 — Product & Issue Trends

*Answers business question 1: which products and issues, and how they're trending.*

1. **Line chart with small multiples:** "Complaints by product, per year"
   - X `dim_date[year]`, Y `Complaints`, **Small multiples** `dim_product[product_group]`. Each product gets its own panel, which avoids 11 colors on one chart.
   - Format > **Y-axis > Range**: **Shared y-axis Off**, **Scale to fit On**, so small products aren't flattened. Subtitle: "Full years 2018–2025; each panel has its own scale".
   - Format > **Small multiples > Layout**: 4 rows × 3 columns.
   - Visual filter `year` ≤ 2025, so the partial year 2026 doesn't look like a drop.
2. **Bar chart:** "Top 10 complaint issues": `dim_issue[issue]` by `Complaints`, visual filter *Top N* = 10 by `Complaints`.

✅ **Checkpoint 5.2** (default view): top issue **Incorrect information on your report** (467,113), then **Attempts to collect debt not owed** (381,233). Mortgage is the only roughly flat panel.

### Page 3 — Company Benchmarking

*Answers business questions 2 and 4: Regions vs peers, and the companies least likely to give relief.*

Give the first three visuals a visual-level filter `dim_company[company_type]` = *Regions peer group*.

1. **Table:** "Regions vs peer banks": `company_label` (renamed *Bank*), `Complaints`, `Timely Response %`, `Relief Rate %`, `Relief Rate vs Peer Avg`, `Monetary Relief %`. Totals off; sorted by Relief Rate % descending.
2. **Bar chart:** "Relief rate: Regions ranks #2 of 6": `company_label` by `Relief Rate %`, data labels on.
   - **Focus + context coloring:** Format > Bars > Colors > **fx** → *Field value* → `Bar Color (Regions Highlight)`. Regions is blue and peers gray.
3. **Line chart:** "Overdraft complaints: Regions vs peers": X `year`, Y `Overdraft Share % (Regions)` (blue `#2a78d6`, width 3) and `Overdraft Share % (Peers)` (gray `#898781`). Visual filter `year` ≤ 2025; Y-axis minimum 0 so the gap isn't exaggerated.
4. **Table:** "Highest no-relief rates (1,000+ closed complaints)": `company_name` (renamed *Company*), `Closed Complaints`, `No Relief Rate %`, `Monetary Relief %`.
   - Visual filter: `Closed Complaints` ≥ 1000.
   - Sort by `No Relief Rate %` descending, then **Shift+click** `Closed Complaints` so the largest of the many 100% companies come first. Totals off.

✅ **Checkpoint 5.3:** Regions: Relief Rate **25.1%**, vs peer avg **+4.1%**; Huntington 31.6%, Fifth Third 12.2%. Overdraft line ends at **10.1%** (Regions) vs **4.0%** (peers). Top no-relief company: **Early Warning Services** (36,481 closed complaints).

### Page 4 — Geographic View

*Answers business question 3: where complaints come from, per capita.*

1. **Filled map:** "Complaints per 100K residents, per year"
   - If Power BI says map visuals are disabled: **File > Options and settings > Options > Global > Security** → tick **Use Map and Filled Map visuals**. (Maps send the location values, here public state names, to Microsoft's mapping service.)
   - Location `dim_geography[state_name]`; visual filter `is_state` = True (otherwise territory and military codes get placed on the wrong continent).
   - Format > **Fill colors > fx** → *Gradient* on `Complaints per 100K (annualized)`, min `#cde2fb` → max `#104281`.
   - Format > **Map settings**: Style **Grayscale**; **Auto zoom Off**, then zoom to the lower 48 states.
2. **Bar chart:** "Top 15 states per 100K residents": `state_name` by `Complaints per 100K (annualized)`; visual filters `is_state` = True and *Top N* = 15.
3. **Table:** "By census region": `census_region`, `Population`, `Complaints`, `Complaints per 100K (annualized)`; visual filter `is_state` = True; sorted by per-100K descending; totals off.

✅ **Checkpoint 5.4** (default view, full date range): **District of Columbia ~223**, **Georgia ~215**, **Florida ~166** per 100K per year; South region **130**.

## Part 6 — Polish and screenshots

- **Titles state the takeaway**, and auto-generated subtitles ("X by Y") are turned off.
- Save a screenshot of each page to `images/` as `dashboard_overview.png`, `dashboard_products.png`, `dashboard_benchmark.png`, `dashboard_geo.png`; the README shows them.
- Optional extras: tooltips with `Relief Rate %` and `Timely Response %`, alt text for each chart, and **View > Performance analyzer** to confirm visuals load in under a second (thanks to the monthly aggregate table).

## Part 7 — Sharing

Power BI's *Publish to web* needs a work or school Microsoft account and an admin setting, so this project shares the dashboard as **screenshots in the README plus the `.pbix` file** in the repo. Anyone can open the `.pbix` in the free Power BI Desktop.

---

### Troubleshooting

| Symptom | Fix |
|---|---|
| Time-intelligence measures return blank | `dim_date` isn't marked as a date table, or the relationship uses the wrong column (must be `month_key` → `date_key`) |
| Totals don't match the checkpoints | Check the Company type slicer (bureaus excluded by default) and that no visual-level filters are left over |
| Month names out of order | Sort `month_name` by `month_num` (Part 2, step 4) |
| A dimension doesn't filter a chart | Missing relationship, or cross-filter direction set wrong |
| "Can't determine relationships between the fields" | You used a column from the fact table in a slicer; use the dimension's column instead |
| A chart shows "Sum of year" | Set `dim_date[year]` to **Don't summarize** (Part 3, step 3) and move `year` to the X-axis |
| Ticking fields created a bar chart instead of a line | Select the visual and click the **Line chart** icon; the fields stay in place |
| Format options show *Bars/Ribbons* on a "line chart" | It's still a column chart; switch the visual type to Line chart |
| A slicer always has one value selected and cards show "--" | Format > search `selection` → **Single select Off** (and **Force selection Off**), then clear the slicer with its eraser icon |
| Numbers show as 13,38,33,983 | Windows region is India; set **Options > Regional settings** to English (United States), or change the Windows region format |
