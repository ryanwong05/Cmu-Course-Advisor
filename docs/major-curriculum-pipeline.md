# Program curriculum pipeline

This pipeline indexes primary majors, additional majors, and minors from their
official CMU catalog pages. Extraction and publication are intentionally separate:
a successful download does not make a curriculum verified.

## Current coverage audit

The September 2026 full run downloaded and parsed all 193 catalog programs with
zero request failures: 71 primary majors, 17 additional majors, and 105 minors.
Eighty-eight extracts passed the strict automatic candidate gate: 36 primary
majors, 10 additional majors, and 42 minors. This is not the live
planning-coverage number: these records still require human review before
publication. The remaining records are available in the review queue rather
than being silently presented as verified policy.

The live planner therefore uses a smaller curated layer in
`Data/processed/requirements.json`. Logic and Computation is now included in
that layer. Never publish the remaining raw extracts merely to increase the
coverage number; several currently over-count sample schedules or every course
in an elective pool as required.

## Run

```bash
venv/bin/python Scripts/data_pipeline/scrape_major_curricula.py
venv/bin/python Scripts/data_pipeline/scrape_major_curricula.py --program-type all
```

Use `--offline` to reparse the cached official pages without downloading them
again. Use `--limit N` for a small development run.

## Outputs

- `Data/scraped/major_curricula/*.html`: raw catalog snapshots.
- `Data/scraped/major_curricula/*.json`: per-program extracted records.
- `Data/processed/major_curriculum_registry.json`: normalized full registry.
- `Data/processed/major_curriculum_report.json`: run totals and review queue.
- `Data/scraped/program_curricula/*`: all-program source snapshots and extracts.
- `Data/processed/program_curriculum_registry.json`: normalized all-program registry.
- `Data/processed/program_curriculum_report.json`: all-program validation report.
- `Data/processed/program_coverage_report.json`: catalog, extraction, candidate,
  and verified-planner coverage layers.

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
venv/bin/python Scripts/data_pipeline/build_major_template_candidates.py --all
```

The second command writes `Data/processed/program_template_candidates.json`.
Existing curated
program profiles and verified major templates are skipped. Candidate records stay
`review_required` until their groups, unit totals, and program-specific policies
have been checked against the official source.

## Scalable expansion workflow

1. Scrape the complete official directory and cache every source page.
2. Parse tables into typed rules: `required`, `choose_n`, `one_of`, `track`,
   `minimum_units`, `substitution`, `cross_listed`, `prerequisite`, and
   `sample_only`. Preserve double-counting prose as reviewable policy signals.
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
