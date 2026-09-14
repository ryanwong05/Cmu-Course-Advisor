# Major curriculum pipeline

This pipeline indexes every primary undergraduate major in the program directory
from its official CMU catalog page. Extraction and publication are intentionally
separate: a successful download does not make a curriculum verified.

## Current coverage audit

The September 2026 full run downloaded and parsed 71 primary-major pages with
zero request failures. Only four raw extracts passed the original generic
promotion gate. This low number is a parser-quality result, not a scraping
failure: catalog pages mix required-course tables, OR choices, tracks, sample
curricula, recommended schedules, and narrative exceptions in different ways.

The live planner therefore uses a smaller curated layer in
`Data/processed/requirements.json`. Logic and Computation is now included in
that layer. Never publish the remaining raw extracts merely to increase the
coverage number; several currently over-count sample schedules or every course
in an elective pool as required.

## Run

```bash
venv/bin/python Scripts/data_pipeline/scrape_major_curricula.py
```

Use `--offline` to reparse the cached official pages without downloading them
again. Use `--limit N` for a small development run.

## Outputs

- `Data/scraped/major_curricula/*.html`: raw catalog snapshots.
- `Data/scraped/major_curricula/*.json`: per-program extracted records.
- `Data/processed/major_curriculum_registry.json`: normalized full registry.
- `Data/processed/major_curriculum_report.json`: run totals and review queue.

## Publication gate

A curriculum is `promotion_ready` only when extraction confidence is high and
automatic validation finds no blockers. Missing courses in the current schedule
database are warnings because a valid catalog course may not be offered in the
currently imported term. Ambiguous choice rules, invalid group sizes, duplicates,
and likely schedule-table contamination prevent automatic promotion.

`promotion_ready` means suitable for human review and promotion into the live
planning templates; it does not mean the curriculum has already been published
or advisor-certified.

Generate engine-shaped review candidates with:

```bash
venv/bin/python Scripts/data_pipeline/build_major_template_candidates.py
```

This writes `Data/processed/major_template_candidates.json`. Existing curated
program profiles and verified major templates are skipped. Candidate records stay
`review_required` until their groups, unit totals, and program-specific policies
have been checked against the official source.

## Scalable expansion workflow

1. Scrape the complete official directory and cache every source page.
2. Parse tables into typed rules: `required`, `choose_n`, `one_of`, `track`,
   `minimum_units`, `prerequisite`, and `sample_only`.
3. Reject impossible totals, duplicated requirements, contaminated sample
   schedules, empty options, and unknown course identifiers.
4. Compare each new source hash with the previous catalog snapshot.
5. Put ambiguous programs in the review queue, grouped by parser failure type.
6. Promote reviewed records into the live requirements database and run
   scheduling, prerequisite, unit-total, and UI tests.

This architecture supports one-command full-school scraping. Accurate planning
coverage still requires parser families for the common CMU page shapes and a
review gate for program-specific prose. A language model may help propose a
typed record, but its output must pass the same deterministic checks and must
never directly overwrite verified requirements.
