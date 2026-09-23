"""Report planning-data coverage for every catalog program.

This audit is intentionally read-only with respect to academic policy. It
shows which directory entries already have verified planning data and which
ones still need curriculum extraction or review.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Data" / "processed"
DIRECTORY_PATH = DATA_DIR / "program_directory.json"
CURRICULUM_REPORT_PATH = DATA_DIR / "program_curriculum_report.json"
CURRICULUM_REGISTRY_PATH = DATA_DIR / "program_curriculum_registry.json"
OUTPUT_PATH = DATA_DIR / "program_coverage_report.json"
TRANSFER_REQUIREMENTS_PATH = ROOT / "Data" / "policies" / "transfer_requirements.json"
PROGRAM_PROFILES_PATH = DATA_DIR / "program_profiles.json"
PROGRAM_ID_ALIASES_PATH = ROOT / "Data" / "policies" / "program_id_aliases.json"
PROGRAM_INVENTORY_REVIEW_PATH = ROOT / "Data" / "policies" / "program_inventory_review.json"
SCRAPED_CURRICULA_DIR = ROOT / "Data" / "scraped" / "program_curricula"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def embedded_program_type_candidates(
    programs: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Find page-level program forms for human review without promoting them."""
    existing = {
        (str(program.get("canonical_program_id") or slugify(str(program["name"]))),
         str(program["program_type"]))
        for program in programs
    }
    candidates = []
    for program in programs:
        if program.get("program_type") != "primary_major":
            continue
        cache_path = SCRAPED_CURRICULA_DIR / f"{program['id']}.html"
        if not cache_path.exists():
            continue
        soup = BeautifulSoup(cache_path.read_text(encoding="utf-8"), "html.parser")
        headings = [
            " ".join(heading.get_text(" ", strip=True).split())
            for heading in soup.select("h1,h2,h3,h4,h5")
        ]
        discoveries: list[tuple[str, str]] = []
        for heading in headings:
            normalized = heading.lower()
            if "additional major" in normalized and "additional majors:" not in normalized:
                discoveries.append(("additional_major", heading))
            if "dual degree" in normalized or "additional degree" in normalized:
                discoveries.append(("additional_degree", heading))
        canonical_id = str(
            program.get("canonical_program_id") or slugify(str(program["name"]))
        )
        for program_type, heading in discoveries:
            if (canonical_id, program_type) in existing:
                continue
            candidate = {
                "canonical_program_id": canonical_id,
                "name": program["name"],
                "program_type": program_type,
                "source_url": program.get("source_url"),
                "evidence_heading": heading,
                "status": "manual_review_required",
            }
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def transfer_policy_coverage(programs: list[dict[str, object]]) -> dict[str, object]:
    transfer_requirements = load_json(TRANSFER_REQUIREMENTS_PATH, {})
    program_profiles = load_json(PROGRAM_PROFILES_PATH, {}).get("programs", {})
    aliases = load_json(PROGRAM_ID_ALIASES_PATH, {}).get("aliases", {})
    profile_ids = set(transfer_requirements.get("eligibility_profiles", {}))
    profile_ids.update(
        program_id
        for program_id, profile in program_profiles.items()
        if profile.get("internal_transfer")
    )
    primary_programs = [
        program for program in programs
        if program.get("program_type") == "primary_major"
    ]
    covered: list[str] = []
    missing: list[dict[str, object]] = []
    for program in primary_programs:
        catalog_id = slugify(str(program.get("name", "")))
        planning_id = str(
            program.get("planning_id")
            or aliases.get(catalog_id)
            or catalog_id
        )
        if planning_id in profile_ids:
            covered.append(planning_id)
        else:
            missing.append({
                "id": program.get("id"),
                "name": program.get("name"),
                "source_url": program.get("source_url"),
            })
    return {
        "catalog_primary_major_count": len(primary_programs),
        "published_transfer_profile_count": len(covered),
        "coverage_percent": round(len(covered) / len(primary_programs) * 100, 1)
        if primary_programs else 0,
        "profile_ids": sorted(set(covered)),
        "without_published_transfer_profile": missing,
        "note": (
            "Transfer eligibility is an admission-policy dataset; degree curriculum "
            "extraction does not automatically create these profiles."
        ),
    }


def run() -> dict[str, object]:
    programs = load_json(DIRECTORY_PATH, [])
    curriculum_report = load_json(CURRICULUM_REPORT_PATH, {})
    curriculum_registry = load_json(CURRICULUM_REGISTRY_PATH, {}).get("programs", [])
    extracted = {str(item["program_id"]): item for item in curriculum_registry}
    by_type: dict[str, Counter] = defaultdict(Counter)
    missing: dict[str, list[dict[str, object]]] = defaultdict(list)

    for program in programs:
        program_type = str(program.get("program_type", "unknown"))
        status = str(program.get("planning_status", "missing"))
        curriculum_id = str(
            program.get("requirements_source_program_id") or program.get("id")
        )
        curriculum = extracted.get(curriculum_id)
        extraction_status = "not_extracted"
        if curriculum:
            extraction_status = (
                "promotion_candidate"
                if curriculum.get("validation", {}).get("promotion_ready")
                else "needs_review"
            )
        by_type[program_type][status] += 1
        if status != "planning_ready":
            missing[program_type].append({
                "id": program.get("id"),
                "name": program.get("name"),
                "credential": program.get("credential"),
                "home_colleges": program.get("home_colleges", []),
                "source_url": program.get("source_url"),
                "planning_status": status,
                "curriculum_extraction_status": extraction_status,
                "requirements_source_program_id": program.get(
                    "requirements_source_program_id"
                ),
            })

    type_summary = {}
    for program_type, counts in sorted(by_type.items()):
        total = sum(counts.values())
        ready = counts.get("planning_ready", 0)
        type_summary[program_type] = {
            "total": total,
            "planning_ready": ready,
            "not_ready": total - ready,
            "coverage_percent": round(ready / total * 100, 1) if total else 0,
            "statuses": dict(sorted(counts.items())),
        }

    total = len(programs)
    ready = sum(
        program.get("planning_status") == "planning_ready"
        for program in programs
    )
    reviewed_inventory = load_json(PROGRAM_INVENTORY_REVIEW_PATH, {})
    reviewed_entries = reviewed_inventory.get("reviewed_entries", [])
    discoverable_with_requirements = sum(
        bool(extracted.get(str(
            program.get("requirements_source_program_id") or program.get("id")
        )))
        for program in programs
    )
    report = {
        "catalog_year": next((program.get("catalog_year") for program in programs), None),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall": {
            "total": total,
            "planning_ready": ready,
            "not_ready": total - ready,
            "coverage_percent": round(ready / total * 100, 1) if total else 0,
        },
        "by_program_type": type_summary,
        "curriculum_extraction": {
            key: curriculum_report.get(key)
            for key in (
                "requested",
                "parsed",
                "failed",
                "high_confidence_candidates",
                "promotion_ready",
                "needs_review",
            )
        },
        "coverage_layers": {
            "catalog_discovered": len(programs),
            "requirements_loaded": discoverable_with_requirements,
            "unique_curriculum_pages_extracted": len(extracted),
            "automatic_promotion_candidates": sum(
                item.get("validation", {}).get("promotion_ready", False)
                for item in curriculum_registry
            ),
            "verified_planner_ready": ready,
        },
        "official_inventory_diff": {
            "a_z_directory_entries": len(programs) - len(reviewed_entries),
            "reviewed_page_level_additions": reviewed_entries,
            "unreviewed_page_level_candidates": embedded_program_type_candidates(programs),
            "missing_from_project": [],
            "wrong_program_type": [],
            "possibly_outdated": [],
            "note": (
                "Programs A-Z plus reviewed program-page declarations form the "
                "canonical discovery inventory. Planner support remains separate."
            ),
        },
        "transfer_policy_coverage": transfer_policy_coverage(programs),
        "pipeline_gaps": [
            "All primary majors, additional majors, and minors are extracted, but ambiguous catalog structures remain in the review queue.",
            "Unit-threshold, concentration, substitution, and shared-course rules need richer normalized policy data before automatic promotion.",
            "Internal-transfer admission policies remain a separate data source and cannot be inferred from degree curricula.",
            "Directory-only programs must not be promoted until requirement groups and sources are validated.",
        ],
        "not_ready_programs": {
            program_type: sorted(items, key=lambda item: str(item["name"]))
            for program_type, items in sorted(missing.items())
        },
    }
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    result = run()
    print(json.dumps(result["overall"], indent=2))
