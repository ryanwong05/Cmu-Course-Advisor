# CMU SmartEvals FCE Harvesting + SQLite Pipeline

This document describes the current working pipeline used to pull CMU SmartEvals Faculty Course Evaluation (FCE) results into `CMU-course-selector`.

## Goal

For each academic window (example: `2025Fall-2026Sum`):

1. Open the SmartEvals Results page manually in the browser.
2. Scrape all paginated rows from the table.
3. Save a merged `FULL.csv` in the project root.
4. Archive the raw CSV.
5. Generate a cleaned CSV.
6. Incrementally import rows into `data/fce.sqlite`.

---

## Why this pipeline exists

The SmartEvals site exposes export controls (`XLS`, `XLSX`, `PDF`, `CSV`), but in practice the export UI may be misleading:

- selecting a format triggers a POST back
- the server may return another HTML page instead of a file download
- from the user perspective, “clicking download does nothing”

Because of that, the reliable path is:

- scrape the rendered table directly
- walk all pages
- write our own CSV

---

## Preconditions

A human must do these steps first:

1. Open CMU SmartEvals / FCE in the browser.
2. Complete CMU login manually.
3. Navigate to the target Results page.

Expected URL pattern:

```text
https://mwfo3.smartevals.com/Reporting/Students/Results.aspx?Type=Classes&ay=<year>&Wizard=True&FiveYearsOnly=True
```

Examples:

- `ay=2025` -> `2025Fall-2026Sum`
- `ay=2024` -> `2024Fall-2025Sum`
- `ay=2023` -> `2023Fall-2024Sum`
- `ay=2022` -> `2022Fall-2023Sum`
- `ay=2021` -> `2021Fall-2022Sum`

---

## Tooling used

### 1) OpenClaw browser tool

Useful for:
- opening the initial page
- checking tabs
- snapshotting page structure

Limitation observed:
- browser actions can time out during click/act phases
- not reliable enough alone for long paginated harvesting

### 2) Local Playwright over Chrome DevTools Protocol (recommended fallback)

This is the reliable harvesting path.

Connection target:

```text
http://127.0.0.1:18800
```

Node package used:

- `playwright-core` from the installed OpenClaw package tree

Why this works well:
- reuses the same logged-in browser session
- avoids re-login
- allows direct DOM access and page-to-page automation

---

## Table scraping method

### Header extraction

Headers are read from the SmartEvals grid header row:

- selector pattern:
  - `tr#_ctl0_cphContent_grd1_DXHeadersRow0 th.dxgvHeader_Custom a`

### Row extraction

Visible data rows are read from:

- `tr.dxgvDataRow_Custom`
- `tr.dxgvDataRowAlt_Custom`

### Pagination

The grid uses ASPx pager actions.

Next-page behavior:

```javascript
ASPx.GVPagerOnClick('_ctl0_cphContent_grd1', 'PBN')
```

The scraper waits for the first-row signature to change before accepting a page transition.

### Dedupe at scrape stage

Rows are deduped in-memory per scrape run using the full row payload as a key.

This is only a first-pass dedupe.
SQLite import still performs the authoritative light dedupe via `row_hash`.

---

## Output naming convention

Each academic window is written to the project root as:

```text
CMU_FCE_<window>_FULL.csv
```

Examples:

- `CMU_FCE_2025Fall-2026Sum_FULL.csv`
- `CMU_FCE_2024Fall-2025Sum_FULL.csv`
- `CMU_FCE_2023Fall-2024Sum_FULL.csv`
- `CMU_FCE_2022Fall-2023Sum_FULL.csv`
- `CMU_FCE_2021Fall-2022Sum_FULL.csv`

---

## Import pipeline

Import script:

```text
scripts/import_fce_to_sqlite.py
```

### Usage

```bash
python scripts/import_fce_to_sqlite.py "D:\doses72Proj\CMU-course-selector\CMU_FCE_2024Fall-2025Sum_FULL.csv"
```

### What the script does

Given a single `FULL.csv` file, it:

1. copies the file to:
   - `data/raw/<same filename>`
2. generates a cleaned CSV at:
   - `data/processed/<same filename with _clean.csv>`
3. inserts rows into:
   - `data/fce.sqlite`

### Cleaning behavior

The script performs light normalization:

- header names -> `snake_case`
- trims surrounding whitespace
- parses integer fields such as:
  - `year`
  - `total_students`
  - `response_count`
- parses float fields for rating columns
- keeps `response_rate_raw`
- derives `response_rate_pct`
- derives `record_type`
- derives `course_key`
- derives `row_hash`

### Record type behavior

The pipeline preserves two kinds of rows:

- `instructor`
- `aggregate`

Current rule:
- if `instructor` is empty -> `aggregate`
- else -> `instructor`

This is intentional. Do **not** over-deduplicate these away.

### Light dedupe policy

The project currently wants light dedupe, not aggressive collapsing.

Current strategy:
- preserve distinct instructor and aggregate rows
- use `row_hash` as the SQLite uniqueness anchor
- use `INSERT OR IGNORE` during incremental loads

This allows repeated runs without duplicate insert storms.

---

## SQLite target

Database path:

```text
data/fce.sqlite
```

Main table:

```text
fce_courses
```

Important fields currently present include:

- `year`
- `sem`
- `college`
- `dept`
- `num`
- `section`
- `instructor`
- `course_name`
- `course_level`
- `total_students`
- `response_count`
- `response_rate_raw`
- `response_rate_pct`
- `hrs_per_week`
- rating columns
- `record_type`
- `course_key`
- `row_hash`

Indexes are created for:

- `(year, sem)`
- `(dept, num)`
- `course_name`
- `instructor`
- `college`
- `record_type`
- `course_key`
- unique `row_hash`

---

## Verified academic windows already imported

At the time this document was written, these windows were already processed:

- `2025Fall-2026Sum`
- `2024Fall-2025Sum`
- `2023Fall-2024Sum`
- `2022Fall-2023Sum`
- `2021Fall-2022Sum`

This pipeline should be reused for older windows rather than redesigned.

---

## Suggested operator workflow for future semesters

1. Human opens target SmartEvals Results page.
2. Agent confirms the `ay=` window.
3. Agent scrapes all pages and writes `CMU_FCE_<window>_FULL.csv`.
4. Agent runs:

```bash
python scripts/import_fce_to_sqlite.py "<FULL CSV path>"
```

5. Agent verifies:
   - raw archive exists
   - clean CSV exists
   - SQLite row count increased or remained stable if re-run

---

## Known limitations

1. Native SmartEvals export is unreliable.
2. Browser automation through the first-class browser tool can be flaky for repeated click actions.
3. The Playwright-over-CDP fallback currently depends on the local DevTools endpoint being available.
4. This pipeline currently ingests a wide single table instead of a normalized relational schema.

---

## Practical note for future developers

If you change the ingestion schema, do it carefully and preserve backward compatibility where possible. The existing query work expected by the project is built around:

- one SQLite DB
- one broad `fce_courses` table
- light dedupe only
- explicit retention of both instructor rows and aggregate rows
