# Major curriculum pipeline

This pipeline indexes every primary undergraduate major in the program directory
from its official CMU catalog page. Extraction and publication are intentionally
separate: a successful download does not make a curriculum verified.

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
