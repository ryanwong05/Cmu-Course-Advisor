"""Scrape and normalize every CMU undergraduate major curriculum page.

The pipeline deliberately separates extraction from promotion:

* ``Data/scraped/major_curricula`` stores reproducible page-derived records.
* ``Data/processed/major_curriculum_registry.json`` is the normalized registry.
* ``Data/processed/major_curriculum_report.json`` records confidence, warnings,
  hashes, and catalog changes that need review.

It never marks a curriculum verified solely because a web request succeeded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup, Tag


ROOT = Path(__file__).resolve().parents[2]
DIRECTORY_PATH = ROOT / "Data" / "processed" / "program_directory.json"
SCRAPED_DIR = ROOT / "Data" / "scraped" / "major_curricula"
REGISTRY_PATH = ROOT / "Data" / "processed" / "major_curriculum_registry.json"
REPORT_PATH = ROOT / "Data" / "processed" / "major_curriculum_report.json"
COURSE_DB_PATH = ROOT / "Data" / "processed" / "courses.sqlite"
CATALOG_YEAR = "2026-2027"
COURSE_RE = re.compile(r"\b\d{2}-\d{3}\b")
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
IGNORE_HEADINGS = (
    "sample schedule", "suggested schedule", "example schedule",
    "four-year plan", "course descriptions", "summary of degree",
)


def clean_text(value: str) -> str:
    return " ".join(value.replace("\u200b", " ").split())


def stable_id(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "requirement"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_units(text: str) -> float | None:
    matches = re.findall(r"(?:^|\s)(\d+(?:\.\d+)?)\s*$", text)
    return float(matches[-1]) if matches else None


def choose_count(text: str) -> int | None:
    lower = text.lower()
    if "complete all" in lower or "take all" in lower:
        return 0
    match = re.search(
        r"(?:complete|take|choose|select)\s+(?:at least\s+)?"
        r"(?:(\d+)|(" + "|".join(NUMBER_WORDS) + r"))\b",
        lower,
    )
    if not match:
        # Catalog pages frequently use captions such as "One Artificial
        # Intelligence elective" without an imperative verb.
        match = re.search(
            r"(?:^|[.!?]\s+)(?:(\d+)|(" + "|".join(NUMBER_WORDS)
            + r"))\s+[^.!?]{0,100}?\b(?:course|courses|elective|electives)\b",
            lower,
        )
    if not match:
        return None
    return int(match.group(1)) if match.group(1) else NUMBER_WORDS[match.group(2)]


def nearest_heading(element: Tag) -> str:
    heading = element.find_previous(["h2", "h3", "h4", "h5", "h6"])
    return clean_text(heading.get_text(" ", strip=True)) if heading else "Major requirements"


def nearby_instruction(table: Tag) -> str:
    pieces: list[str] = []
    sibling = table.previous_sibling
    while sibling is not None and len(pieces) < 4:
        if isinstance(sibling, Tag):
            if sibling.name in {"h2", "h3", "h4", "h5", "h6", "table"}:
                break
            text = clean_text(sibling.get_text(" ", strip=True))
            if text:
                pieces.append(text)
        sibling = sibling.previous_sibling
    sibling_text = " ".join(reversed(pieces))
    if choose_count(sibling_text) is not None or "following requirements" in sibling_text.lower():
        return sibling_text

    # Some catalog templates wrap a prose caption and its table in the same
    # div. Walk outward and collect only content that appears before the table.
    node: Tag | None = table
    for _ in range(4):
        parent = node.parent if node is not None else None
        if not isinstance(parent, Tag):
            break
        before: list[str] = []
        for child in parent.children:
            if child is node:
                break
            if isinstance(child, Tag):
                text = clean_text(child.get_text(" ", strip=True))
                if text and len(text) <= 1500:
                    before.append(text)
        candidate = clean_text(" ".join(before))
        if choose_count(candidate) is not None or "following requirements" in candidate.lower():
            return candidate
        node = parent
    return sibling_text


def table_courses(table: Tag) -> list[dict[str, object]]:
    courses: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in table.select("tr"):
        text = clean_text(row.get_text(" ", strip=True))
        ids = COURSE_RE.findall(text)
        if not ids:
            continue
        units = parse_units(text)
        for course_id in ids:
            if course_id in seen:
                continue
            seen.add(course_id)
            title = text
            title = re.sub(rf"^.*?{re.escape(course_id)}\s*", "", title)
            if units is not None:
                title = re.sub(rf"\s+{units:g}\s*$", "", title)
            courses.append({
                "id": course_id,
                "name": clean_text(title) or "Catalog course",
                "units": units,
                "source_text": text,
            })
    return courses


def parse_curriculum_html(html: str, program: dict[str, object]) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    fixed: list[dict[str, object]] = []
    groups: list[dict[str, object]] = []
    warnings: list[str] = []
    seen_fixed: set[str] = set()
    seen_groups: set[tuple[str, tuple[str, ...]]] = set()
    tables_seen = 0

    for table in main.select("table"):
        heading = nearest_heading(table)
        if any(marker in heading.lower() for marker in IGNORE_HEADINGS):
            continue
        courses = table_courses(table)
        if not courses:
            continue
        tables_seen += 1
        instruction = nearby_instruction(table)
        choose = choose_count(instruction)

        if choose == 0:
            for course in courses:
                if course["id"] not in seen_fixed:
                    fixed.append(course)
                    seen_fixed.add(str(course["id"]))
            continue

        if choose is None and len(courses) == 1:
            course = courses[0]
            if course["id"] not in seen_fixed:
                fixed.append(course)
                seen_fixed.add(str(course["id"]))
            continue

        if choose is None:
            choose = 1
            warnings.append(f"Assumed choose-one for ambiguous section: {heading}")
        option_ids = tuple(str(course["id"]) for course in courses)
        key = (heading, option_ids)
        if key in seen_groups:
            continue
        seen_groups.add(key)
        known_units = [float(course["units"]) for course in courses if course["units"] is not None]
        groups.append({
            "id": stable_id(heading),
            "name": heading,
            "choose": min(choose, len(option_ids)),
            "units": round((sum(known_units) / len(known_units)) * min(choose, len(option_ids)))
            if known_units else 9 * min(choose, len(option_ids)),
            "options": list(option_ids),
            "source_instruction": instruction or None,
        })

    course_count = len(fixed) + sum(len(group["options"]) for group in groups)
    ambiguous = len(warnings)
    explicit_groups = sum(
        choose_count(group.get("source_instruction") or "") is not None for group in groups
    )
    explicit_ratio = explicit_groups / len(groups) if groups else 0.0
    confidence = 0.0
    if tables_seen:
        confidence += 0.25
    if course_count >= 6:
        confidence += 0.25
    if fixed and groups:
        confidence += 0.2
    confidence += 0.25 * explicit_ratio
    confidence += max(0.0, 0.05 - ambiguous * 0.01)
    if groups and ambiguous / len(groups) > 0.25:
        confidence = min(confidence, 0.79)
    if not fixed or not groups:
        confidence = min(confidence, 0.69)
    confidence = round(min(1.0, confidence), 2)

    if not fixed:
        warnings.append("No unambiguous fixed-course table was found.")
    if not groups:
        warnings.append("No course-choice groups were found.")
    return {
        "program_id": program["id"],
        "planning_id": program.get("planning_id") or str(program["id"]).split("--")[0],
        "name": program["name"],
        "credential": program["credential"],
        "catalog_year": CATALOG_YEAR,
        "source_url": program["source_url"],
        "source_hash": sha256_text(clean_text(main.get_text(" ", strip=True))),
        "fixed_courses": fixed,
        "requirement_groups": groups,
        "extraction": {
            "tables_seen": tables_seen,
            "course_references": course_count,
            "confidence": confidence,
            "status": "high_confidence_candidate" if confidence >= 0.8 else "needs_review",
            "warnings": warnings,
            "explicit_group_ratio": round(explicit_ratio, 2),
        },
    }


def scheduled_course_ids() -> set[str]:
    if not COURSE_DB_PATH.exists():
        return set()
    with sqlite3.connect(COURSE_DB_PATH) as connection:
        rows = connection.execute(
            "SELECT DISTINCT canonical_course_id FROM courses"
        ).fetchall()
    return {str(row[0]) for row in rows}


def validate_curriculum(curriculum: dict[str, object], known_ids: set[str]) -> dict[str, object]:
    fixed_ids = [str(item["id"]) for item in curriculum["fixed_courses"]]
    groups = curriculum["requirement_groups"]
    option_ids = [str(option) for group in groups for option in group["options"]]
    all_ids = fixed_ids + option_ids
    blockers: list[str] = []
    warnings: list[str] = []
    duplicate_fixed = sorted({item for item in fixed_ids if fixed_ids.count(item) > 1})
    if duplicate_fixed:
        blockers.append("Duplicate fixed courses: " + ", ".join(duplicate_fixed))
    invalid_groups = [str(group["id"]) for group in groups if not 0 < int(group["choose"]) <= len(group["options"])]
    if invalid_groups:
        blockers.append("Invalid choice counts: " + ", ".join(invalid_groups))
    if len(fixed_ids) > 60 or len(groups) > 50:
        blockers.append("Implausibly large extracted curriculum; likely schedule/table contamination.")
    extracted_units = sum(float(item.get("units") or 0) for item in curriculum["fixed_courses"])
    extracted_units += sum(float(item.get("units") or 0) for item in groups)
    if extracted_units > 360:
        blockers.append(
            f"Extracted requirement total is implausible ({round(extracted_units)} units)."
        )
    ambiguous = len(curriculum["extraction"]["warnings"])
    if groups and ambiguous / len(groups) > 0.25:
        blockers.append("More than 25% of requirement groups rely on inferred choose-one rules.")
    missing = sorted(set(all_ids) - known_ids) if known_ids else []
    if missing:
        warnings.append(
            f"{len(missing)} catalog course IDs are absent from the current schedule database."
        )
    promotion_ready = (
        curriculum["extraction"]["status"] == "high_confidence_candidate"
        and not blockers
    )
    return {
        "promotion_ready": promotion_ready,
        "blockers": blockers,
        "warnings": warnings,
        "catalog_course_count": len(set(all_ids)),
        "extracted_unit_estimate": round(extracted_units),
        "scheduled_course_count": len(set(all_ids) & known_ids) if known_ids else None,
        "missing_schedule_course_ids": missing,
    }


def load_majors() -> list[dict[str, object]]:
    programs = json.loads(DIRECTORY_PATH.read_text(encoding="utf-8"))
    return [item for item in programs if item.get("program_type") == "primary_major"]


def fetch(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": "CMU-Course-Advisor/1.0 curriculum indexer"},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run(limit: int | None = None, offline: bool = False) -> dict[str, object]:
    previous = {}
    if REGISTRY_PATH.exists():
        previous = {
            item["program_id"]: item
            for item in json.loads(REGISTRY_PATH.read_text(encoding="utf-8")).get("programs", [])
        }
    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    changed: list[str] = []
    majors = load_majors()[:limit]
    known_ids = scheduled_course_ids()
    SCRAPED_DIR.mkdir(parents=True, exist_ok=True)

    for program in majors:
        cache_path = SCRAPED_DIR / f"{program['id']}.html"
        try:
            html = cache_path.read_text(encoding="utf-8") if offline else fetch(str(program["source_url"]))
            if not offline:
                cache_path.write_text(html, encoding="utf-8")
            parsed = parse_curriculum_html(html, program)
            parsed["validation"] = validate_curriculum(parsed, known_ids)
            old_hash = previous.get(str(program["id"]), {}).get("source_hash")
            if old_hash and old_hash != parsed["source_hash"]:
                changed.append(str(program["id"]))
            results.append(parsed)
            write_json(SCRAPED_DIR / f"{program['id']}.json", parsed)
        except Exception as error:  # keep the full-school run resilient
            failures.append({"program_id": str(program["id"]), "error": str(error)})

    generated_at = datetime.now(timezone.utc).isoformat()
    registry = {"catalog_year": CATALOG_YEAR, "generated_at": generated_at, "programs": results}
    report = {
        "catalog_year": CATALOG_YEAR,
        "generated_at": generated_at,
        "requested": len(majors),
        "parsed": len(results),
        "failed": len(failures),
        "high_confidence_candidates": sum(
            item["extraction"]["status"] == "high_confidence_candidate" for item in results
        ),
        "needs_review": sum(item["extraction"]["status"] == "needs_review" for item in results),
        "promotion_ready": sum(item["validation"]["promotion_ready"] for item in results),
        "blocked_candidates": sum(
            item["extraction"]["status"] == "high_confidence_candidate"
            and not item["validation"]["promotion_ready"]
            for item in results
        ),
        "review_queue": [
            {
                "program_id": item["program_id"],
                "name": item["name"],
                "confidence": item["extraction"]["confidence"],
                "blockers": item["validation"]["blockers"],
                "warnings": item["extraction"]["warnings"] + item["validation"]["warnings"],
            }
            for item in results if not item["validation"]["promotion_ready"]
        ],
        "changed_since_previous_run": changed,
        "failures": failures,
    }
    write_json(REGISTRY_PATH, registry)
    write_json(REPORT_PATH, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    report = run(limit=args.limit, offline=args.offline)
    # Keep terminal output concise; the complete per-program queue lives in
    # major_curriculum_report.json.
    print(json.dumps({key: value for key, value in report.items() if key != "review_queue"}, indent=2))


if __name__ == "__main__":
    main()
