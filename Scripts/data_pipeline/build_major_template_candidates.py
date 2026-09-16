"""Build reviewable planning-template candidates from validated catalog extracts."""

from __future__ import annotations

import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

try:
    from Scripts.data_pipeline.scrape_program_directory import load_planning_capabilities
except ModuleNotFoundError:  # direct script execution from the repository root
    from scrape_program_directory import load_planning_capabilities


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "Data" / "processed" / "major_curriculum_registry.json"
OUTPUT_PATH = ROOT / "Data" / "processed" / "major_template_candidates.json"
ALL_REGISTRY_PATH = ROOT / "Data" / "processed" / "program_curriculum_registry.json"
ALL_OUTPUT_PATH = ROOT / "Data" / "processed" / "program_template_candidates.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


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
        "program_type": curriculum.get("program_type", "primary_major"),
        "minimum_major_units_estimate": estimated_units(curriculum),
        "required_courses": [item["id"] for item in curriculum["fixed_courses"]],
        "requirement_groups": [
            {
                "id": item["id"],
                "name": item["name"],
                "choose": item["choose"],
                "units": item["units"],
                "options": item["options"],
                "selection_rule": item.get("selection_rule"),
                **({"relationship": item["relationship"]} if item.get("relationship") else {}),
                **({"track": item["track"]} if item.get("track") else {}),
            }
            for item in curriculum["requirement_groups"]
        ],
        "track_rule": curriculum.get("track_rule"),
        "policy_signals": curriculum.get("policy_signals", {}),
        "provenance": {
            "source_url": curriculum["source_url"],
            "source_hash": curriculum["source_hash"],
            "extraction_confidence": curriculum["extraction"]["confidence"],
            "automatic_validation": curriculum["validation"],
        },
    }


def run(
    registry_path: Path = REGISTRY_PATH,
    output_path: Path = OUTPUT_PATH,
) -> dict[str, object]:
    registry = load_json(registry_path)
    capabilities = load_planning_capabilities()
    candidates: dict[str, object] = {}
    skipped: list[dict[str, str]] = []
    for curriculum in registry["programs"]:
        if not curriculum["validation"]["promotion_ready"]:
            continue
        planning_id = str(curriculum["planning_id"])
        program_type = str(curriculum.get("program_type", "primary_major"))
        if program_type in capabilities.get(planning_id, set()):
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
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--all",
        action="store_true",
        help="Build candidates for majors, additional majors, and minors.",
    )
    args = parser.parse_args()
    registry_path = ALL_REGISTRY_PATH if args.all else REGISTRY_PATH
    output_path = ALL_OUTPUT_PATH if args.all else OUTPUT_PATH
    result = run(registry_path=registry_path, output_path=output_path)
    print(json.dumps({
        "candidate_count": result["candidate_count"],
        "skipped": result["skipped"],
        "output": str(output_path),
    }, indent=2))
