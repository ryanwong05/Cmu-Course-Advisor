# CMU Undergraduate Program Inventory Audit

Audit date: 2026-09-23  
Catalog year: 2026-2027

## Scope and source hierarchy

The audit uses the official CMU Undergraduate Catalog Programs A-Z directory as
the base inventory, then checks the cached official curriculum page for each
primary major for program forms that the A-Z index does not expose as separate
links. Third-party sources are not used.

Program existence is kept separate from requirement extraction, planner
readiness, internal-transfer policy, and application/declaration policy.

## Inventory result

| Program form | Official entries | Planner ready | Not planner ready |
| --- | ---: | ---: | ---: |
| Primary major | 71 | 11 | 60 |
| Additional major | 36 | 6 | 30 |
| Additional degree / dual degree | 1 | 0 | 1 |
| Minor | 105 | 8 | 97 |
| **Total** | **213** | **25** | **188** |

- 193 entries come directly from Programs A-Z.
- 20 additional program forms were verified on official curriculum pages and
  passed through the reviewed-inventory gate.
- Requirement pages have been extracted for all 193 unique A-Z entries. The 20
  supplemental forms point to their reviewed primary curriculum source rather
  than duplicating scraped requirement data.
- 88 extracted curricula pass automatic structural validation, but they remain
  review candidates until their academic rules are approved for the live
  planner.
- 10 of 71 primary-major entries currently have a published internal-transfer
  policy/profile in the project. A degree curriculum alone does not establish
  that internal transfer is allowed.

## Program forms missing from Programs A-Z but verified on program pages

### Additional majors

- Anthropology
- Behavioral Economics
- Chemistry
- Cognitive Science
- Computational Finance
- Decision Science
- Economics and Statistics
- Ethics, History and Public Policy
- History
- Logic and Computation
- Mathematical Sciences
- Philosophy
- Policy and Management
- Psychology
- Science, Technology and Society
- Statistics and Data Science
- Statistics and Data Science (Mathematical Sciences Track)
- Statistics and Data Science (Neuroscience Track)
- Statistics and Machine Learning

### Additional degree / dual degree

- Computer Science (Dual Degree)

These entries are discoverable but are not automatically planner-ready. Their
source curriculum may be loaded while additional-major-specific omissions,
double-counting rules, college requirements, application gates, or total-unit
rules still require review.

## Computational Finance finding

The official umbrella page lists the B.S. and Minor as program options. The B.S.
page separately states that students may pursue Computational Finance as an
additional major. This explains why an A-Z-only scraper found the B.S. and Minor
but missed the Additional Major.

The canonical inventory now records all three forms:

| Capability | B.S. | Additional major | Minor |
| --- | --- | --- | --- |
| Discoverable | Yes | Yes | Yes |
| Requirements extracted | Yes | Yes, shared reviewed B.S. source | Yes |
| Planner ready | No | No | No |
| Application/declaration policy loaded | No | Yes | Yes |

Planner support remains disabled because requirement extraction is not the same
as reviewed planning behavior. In particular, home-college differences,
double-counting restrictions, declaration/application gates, and prerequisite
chains must be enforced before a plan can be represented as valid.

The affiliation metadata was corrected to reflect the official joint program:
Mellon College of Science and Tepper are possible home colleges, with Heinz also
listed as a joint sponsor.

## Architecture after the audit

1. The official Programs A-Z scraper creates the base directory.
2. `Data/policies/program_inventory_review.json` contains only human-reviewed
   official page-level program forms omitted by A-Z.
3. The scraper merges those forms into the existing canonical
   `program_directory.json`; it does not create a parallel production registry.
4. Each entry receives `canonical_program_id` and `available_as` metadata.
5. The API derives requirement, planner, transfer-policy, and declaration-policy
   capability independently at runtime.
6. Program Explorer consumes canonical API groups and no longer has an SCS
   browser-side allowlist.
7. Scraped requirement changes remain candidates: fetch/parse -> normalize ->
   validate/diff -> human review -> live data.

## Remaining review queue

- 188 discoverable program forms are not yet planner-ready.
- 95 unique extracted curricula still fail or require manual review under the
  current promotion checks.
- 61 primary-major entries do not have a verified internal-transfer profile;
  this does not mean transfer is available or unavailable, only that the
  project has not encoded a verified policy.
- Additional-degree availability is only recorded where an official page makes
  it explicit. The audit does not infer dual-degree availability from the
  existence of a primary major.

The machine-readable details, including every not-ready entry and its source,
are in `Data/processed/program_coverage_report.json`.
