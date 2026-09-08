"""Build reviewable planning-template candidates from validated catalog extracts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "Data" / "processed" / "major_curriculum_registry.json"
REQUIREMENTS_PATH = ROOT / "Data" / "processed" / "requirements.json"
PROFILES_PATH = ROOT / "Data" / "processed" / "program_profiles.json"
OUTPUT_PATH = ROOT / "Data" / "processed" / "major_template_candidates.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def curated_planning_ids() -> set[str]:
    requirements = load_json(REQUIREMENTS_PATH)
    ids = {
        key.removesuffix("-major")
        for key, value in requirements.items()
        if key.endswith("-major") and value.get("curriculum_status") == "verified"
    }
    profiles = load_json(PROFILES_PATH).get("programs", {})
    # A manually maintained profile should always win over a generated record.
    ids.update(profiles)
    return ids


def estimated_units(curriculum: dict[str, object]) -> int:
    fixed = sum(float(item.get("units") or 0) for item in curriculum["fixed_courses"])
    groups = sum(float(item.get("units") or 0) for item in curriculum["requirement_groups"])
    return round(fixed + groups)


def build_candidate(curriculum: dict[str, object]) -> dict[str, object]:
    return {
        "planner_status": "review_required",
        "curriculum_status": "catalog_extracted_candidate",
        "catalog_year": curriculum["catalog_year"],
        "program_id": curriculum["program_id"],
        "planning_id": curriculum["planning_id"],
        "name": curriculum["name"],
        "credential": curriculum["credential"],
        "minimum_major_units_estimate": estimated_units(curriculum),
        "required_courses": [item["id"] for item in curriculum["fixed_courses"]],
        "requirement_groups": [
            {
                "id": item["id"],
                "name": item["name"],
                "choose": item["choose"],
                "units": item["units"],
                "options": item["options"],
            }
            for item in curriculum["requirement_groups"]
        ],
        "provenance": {
            "source_url": curriculum["source_url"],
            "source_hash": curriculum["source_hash"],
            "extraction_confidence": curriculum["extraction"]["confidence"],
            "automatic_validation": curriculum["validation"],
        },
    }


def run() -> dict[str, object]:
    registry = load_json(REGISTRY_PATH)
    curated = curated_planning_ids()
    candidates: dict[str, object] = {}
    skipped: list[dict[str, str]] = []
    for curriculum in registry["programs"]:
        if not curriculum["validation"]["promotion_ready"]:
            continue
        planning_id = str(curriculum["planning_id"])
        if planning_id in curated:
            skipped.append({
                "program_id": str(curriculum["program_id"]),
                "reason": "curated_template_exists",
            })
            continue
        candidates[str(curriculum["program_id"])] = build_candidate(curriculum)
    payload = {
        "catalog_year": registry["catalog_year"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "review_required",
        "candidate_count": len(candidates),
        "candidates": candidates,
        "skipped": skipped,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = run()
    print(json.dumps({
        "candidate_count": result["candidate_count"],
        "skipped": result["skipped"],
        "output": str(OUTPUT_PATH),
    }, indent=2))
