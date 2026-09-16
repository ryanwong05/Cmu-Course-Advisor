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
import math
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
ALL_SCRAPED_DIR = ROOT / "Data" / "scraped" / "program_curricula"
ALL_REGISTRY_PATH = ROOT / "Data" / "processed" / "program_curriculum_registry.json"
ALL_REPORT_PATH = ROOT / "Data" / "processed" / "program_curriculum_report.json"
COURSE_DB_PATH = ROOT / "Data" / "processed" / "courses.sqlite"
CATALOG_YEAR = "2026-2027"
COURSE_RE = re.compile(r"\b\d{2}-\d{3}\b")
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
IGNORE_HEADINGS = (
    "sample schedule", "suggested schedule", "example schedule",
    "sample course sequence", "sample plan", "roadmap",
    "four-year plan", "sample curricula", "sample curriculum",
    "course descriptions", "summary of degree", "recommended courses",
)
PROGRAM_TYPES = ("primary_major", "additional_major", "minor")


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
    if (
        "complete all" in lower
        or "take all" in lower
        or "all of the following" in lower
        or "all the following" in lower
    ):
        return 0
    match = re.search(
        r"(?:complete|take|choose|select)\s+(?:at least\s+)?"
        r"(?:(\d+)|(" + "|".join(NUMBER_WORDS) + r"))\b"
        r"(?!\s*(?:units?|credits?)\b)",
        lower,
    )
    if not match:
        match = re.search(
            r"(?:(\d+)|(" + "|".join(NUMBER_WORDS)
            + r"))\s+of\s+(?:the\s+)?following\b",
            lower,
        )
    if not match:
        match = re.search(
            r"\(\s*(?:(\d+)|(" + "|".join(NUMBER_WORDS)
            + r"))\s+(?:course|courses|elective|electives)\s*\)",
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


def required_units(text: str) -> float | None:
    """Return an explicitly stated course-block unit requirement, if present."""
    match = re.search(
        r"(?:at least\s+|minimum(?:\s+of)?\s+|min\.\s*)?"
        r"(\d+(?:\.\d+)?)\s*(?:units?|credits?)\b",
        text,
        re.IGNORECASE,
    )
    return float(match.group(1)) if match else None


def shared_credit_signals(text: str) -> dict[str, object]:
    """Extract reviewable double-counting signals without inventing policy scope."""
    sentences = [
        clean_text(sentence)
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if re.search(
            r"\b(?:double[- ]count(?:ing|ed)?|count(?:ed)? toward both|shared credit)\b",
            sentence,
            re.IGNORECASE,
        )
    ]
    course_limits: set[int] = set()
    unit_limits: set[int] = set()
    number_pattern = r"(\d+|" + "|".join(NUMBER_WORDS) + r")"
    for sentence in sentences:
        for match in re.finditer(
            r"(?:maximum of|up to|no more than|at most)?\s*"
            + number_pattern
            + r"\s+(courses?|units?)\b",
            sentence,
            re.IGNORECASE,
        ):
            raw_number = match.group(1).lower()
            value = int(raw_number) if raw_number.isdigit() else NUMBER_WORDS[raw_number]
            if match.group(2).lower().startswith("course"):
                course_limits.add(value)
            else:
                unit_limits.add(value)
    return {
        "present": bool(sentences),
        "course_limit_candidates": sorted(course_limits),
        "unit_limit_candidates": sorted(unit_limits),
        "unlimited_exception_present": any(
            "unlimited" in sentence.lower() for sentence in sentences
        ),
        "prohibition_language_present": any(
            re.search(r"\b(?:may not|cannot|can't)\s+double[- ]count(?:ing|ed)?\b", sentence, re.IGNORECASE)
            for sentence in sentences
        ),
        "source_sentences": sentences[:8],
    }


def nearest_heading(element: Tag) -> str:
    heading = element.find_previous(["h2", "h3", "h4", "h5", "h6"])
    return clean_text(heading.get_text(" ", strip=True)) if heading else "Major requirements"


def heading_context(element: Tag) -> list[str]:
    """Return the current catalog outline from nearest heading to its parents."""
    nearest = element.find_previous(["h2", "h3", "h4", "h5", "h6"])
    if nearest is None:
        return []
    context = [clean_text(nearest.get_text(" ", strip=True))]
    current_level = int(nearest.name[1])
    for heading in nearest.find_all_previous(["h2", "h3", "h4", "h5", "h6"]):
        level = int(heading.name[1])
        if level >= current_level:
            continue
        context.append(clean_text(heading.get_text(" ", strip=True)))
        current_level = level
        if level <= 2:
            break
    return context


def nearby_instruction(table: Tag) -> str:
    # Course-list tables put their governing rule in direct child cells, for
    # example "All of the following" or "Two electives". Prefer that local
    # structure over surrounding page prose, which may contain the entire
    # curriculum and produce false choice counts.
    direct_cells = table.find_all("td", recursive=False)
    direct_text = clean_text(" ".join(
        cell.get_text(" ", strip=True)
        for cell in direct_cells
        if "hourscol" not in (cell.get("class") or [])
    ))
    if direct_text:
        return direct_text

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

    return sibling_text


def table_courses(table: Tag) -> list[dict[str, object]]:
    courses: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in table.select("tr"):
        cells = row.find_all("td", recursive=False)
        code_cell = next((
            cell for cell in cells
            if "codecol" in (cell.get("class") or [])
        ), None)
        if code_cell is None and cells:
            # Some archived/test catalog markup omits CMU's codecol class. A
            # strict first-cell fallback preserves those pages without ever
            # scanning descriptions, prerequisites, or notes for course IDs.
            first_text = clean_text(cells[0].get_text(" ", strip=True))
            if COURSE_RE.fullmatch(first_text):
                code_cell = cells[0]
        if code_cell is None:
            continue
        text = clean_text(row.get_text(" ", strip=True))
        ids = COURSE_RE.findall(clean_text(code_cell.get_text(" ", strip=True)))
        if not ids:
            continue
        hours_cell = next((
            cell for cell in cells
            if "hourscol" in (cell.get("class") or [])
        ), None)
        units = parse_units(clean_text(hours_cell.get_text(" ", strip=True))) if hours_cell else None
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


def table_requirement_segments(table: Tag) -> list[dict[str, object]]:
    """Split one catalog table into locally governed requirement segments."""
    initial_instruction = nearby_instruction(table)
    segments: list[dict[str, object]] = []
    current = {"instruction": initial_instruction, "courses": []}

    def finish_current() -> None:
        nonlocal current
        if current["courses"]:
            segments.append(current)
        current = {"instruction": "", "courses": []}

    for row in table.select("tr"):
        cells = row.find_all("td", recursive=False)
        code_cell = next((
            cell for cell in cells
            if "codecol" in (cell.get("class") or [])
        ), None)
        if code_cell is None and cells:
            first_text = clean_text(cells[0].get_text(" ", strip=True))
            if COURSE_RE.fullmatch(first_text):
                code_cell = cells[0]
        if code_cell is None:
            instruction = clean_text(row.get_text(" ", strip=True))
            lower = instruction.lower()
            starts_requirement = (
                choose_count(instruction) is not None
                or "all of the following" in lower
                or "all the following" in lower
                or lower.startswith("plus ")
            )
            if instruction and starts_requirement:
                finish_current()
                current["instruction"] = instruction
            continue

        code_text = clean_text(code_cell.get_text(" ", strip=True))
        ids = COURSE_RE.findall(code_text)
        if not ids:
            continue
        hours_cell = next((
            cell for cell in cells
            if "hourscol" in (cell.get("class") or [])
        ), None)
        units = parse_units(clean_text(hours_cell.get_text(" ", strip=True))) if hours_cell else None
        title_cell = next((
            cell for cell in cells
            if cell is not code_cell and "hourscol" not in (cell.get("class") or [])
        ), None)
        title = clean_text(title_cell.get_text(" ", strip=True)) if title_cell else "Catalog course"
        current["courses"].append({
            "id": " + ".join(ids),
            "course_ids": ids,
            "code_text": code_text,
            "relation": (
                "equivalent"
                if len(ids) > 1 and "/" in code_text and "&" not in code_text
                else "bundle" if len(ids) > 1 else "single"
            ),
            "is_alternative": code_text.lower().startswith("or "),
            "name": title,
            "units": units,
            "source_text": clean_text(row.get_text(" ", strip=True)),
        })

    finish_current()
    return segments


def course_option_ids(course: dict[str, object]) -> list[str]:
    """Convert one catalog row into planner option IDs without losing meaning."""
    course_ids = [str(item) for item in course.get("course_ids", [])]
    if course.get("relation") == "equivalent":
        return course_ids
    return [" + ".join(course_ids)] if course_ids else []


def fixed_requirement_clusters(
    courses: list[dict[str, object]],
) -> list[list[dict[str, object]]]:
    """Attach each catalog ``or`` row to the required row immediately above."""
    clusters: list[list[dict[str, object]]] = []
    for course in courses:
        if course.get("is_alternative") and clusters:
            clusters[-1].append(course)
        else:
            clusters.append([course])
    return clusters


def merge_minimum_unit_groups(groups: list[dict[str, object]]) -> list[dict[str, object]]:
    """Merge category tables governed by one shared heading-level unit rule."""
    merged: list[dict[str, object]] = []
    by_key: dict[tuple[str, float], dict[str, object]] = {}
    for group in groups:
        rule = group.get("selection_rule", {})
        if rule.get("type") != "minimum_units":
            merged.append(group)
            continue
        key = (str(group.get("heading", group["name"])), float(rule["minimum_units"]))
        existing = by_key.get(key)
        if existing is None:
            group = dict(group)
            group["source_categories"] = [group["name"]]
            group["name"] = key[0]
            group["id"] = stable_id(key[0])
            by_key[key] = group
            merged.append(group)
            continue
        existing["options"] = list(dict.fromkeys([
            *existing["options"], *group["options"],
        ]))
        existing["source_categories"].append(group["name"])
        existing["choose"] = min(
            len(existing["options"]),
            max(int(existing["choose"]), int(group["choose"])),
        )
        existing["selection_rule"]["course_count_estimate"] = existing["choose"]
    return merged


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
        outline = " ".join(heading_context(table)).lower()
        if any(marker in outline for marker in IGNORE_HEADINGS):
            continue
        segments = table_requirement_segments(table)
        if not segments:
            continue
        tables_seen += 1
        for segment_index, segment in enumerate(segments):
            courses = segment["courses"]
            instruction = str(segment.get("instruction") or "")
            combined_rule_text = clean_text(f"{heading}. {instruction}")
            structural_context = clean_text(
                " ".join([*heading_context(table)[:2], instruction])
            )
            choose = choose_count(combined_rule_text)
            assumed_choice = False
            lower_instruction = instruction.lower()
            lower_heading = heading.lower()
            lower_rule_text = combined_rule_text.lower()
            lower_structural_context = structural_context.lower()
            if any(
                marker in lower_rule_text
                for marker in (
                    "recommended course", "recommended for", "may satisfy",
                    "may be used", "up to ", "sample course", "example course",
                )
            ):
                continue
            unit_requirement = required_units(combined_rule_text)
            track_heading = next((
                item for item in heading_context(table)[:2]
                if re.search(r"\btrack\b", item, re.IGNORECASE)
            ), None)
            track_context = track_heading is not None
            elective_context = any(
                marker in lower_structural_context
                for marker in ("elective", "option", "concentration", "track", "area of study")
            )
            fixed_context = any(
                marker in lower_structural_context
                for marker in (
                    "required course", "required courses", "prerequisite course",
                    "prerequisite courses", "core requirement", "requirements",
                )
            ) or bool(re.search(
                r"\b(?:first|second|third|fourth)[- ]year\b",
                lower_structural_context,
            )) or bool(re.search(
                r"\b(?:prerequisites?|core(?: courses?)?|required|required:|"
                r"programming requirement|foundations?|senior work)\b",
                lower_structural_context,
            ))
            known_course_units = [
                float(course["units"])
                for course in courses
                if course["units"] is not None and float(course["units"]) > 0
            ]
            if (
                choose is None
                and track_context
                and re.search(r"\b(?:core|required)\b", lower_structural_context)
            ):
                choose = sum(not course.get("is_alternative") for course in courses)
            if (
                choose is None
                and unit_requirement
                and known_course_units
                and len(known_course_units) == len(courses)
                and not (fixed_context and not elective_context)
            ):
                choose = min(
                    len(courses),
                    max(1, math.ceil(unit_requirement / max(known_course_units))),
                )
                warnings.append(
                    f"Inferred {choose} choices from an explicit {unit_requirement:g}-unit rule: {heading}"
                )
            is_fixed = (
                choose == 0
                or (choose is None and len(courses) == 1 and not track_context)
                or (choose is None and lower_instruction.startswith("plus "))
                or (choose is None and fixed_context and not elective_context)
            )

            if is_fixed:
                for cluster_index, cluster in enumerate(fixed_requirement_clusters(courses)):
                    cluster_options = [
                        option
                        for course in cluster
                        for option in course_option_ids(course)
                    ]
                    if len(cluster_options) > 1 or cluster[0].get("relation") == "equivalent":
                        group_id = stable_id(
                            f"{heading}-{segment_index + 1}-alternative-{cluster_index + 1}"
                        )
                        key = (group_id, tuple(cluster_options))
                        if key not in seen_groups:
                            seen_groups.add(key)
                            group_units = float(cluster[0].get("units") or 9)
                            groups.append({
                                "id": group_id,
                                "name": str(cluster[0].get("name") or heading),
                                "heading": heading,
                                "choose": 1,
                                "units": round(group_units),
                                "options": list(dict.fromkeys(cluster_options)),
                                "source_instruction": instruction or None,
                                "selection_rule": {"type": "course_count", "count": 1},
                                "relationship": "substitution",
                            })
                        continue
                    for course_id in cluster[0]["course_ids"]:
                        if course_id in seen_fixed:
                            continue
                        fixed.append({
                            "id": course_id,
                            "name": cluster[0]["name"],
                            "units": cluster[0]["units"],
                            "source_text": cluster[0]["source_text"],
                        })
                        seen_fixed.add(course_id)
                continue

            if choose is None:
                choose = 1
                assumed_choice = True
                warnings.append(
                    f"Assumed choose-one for ambiguous section: {heading}"
                )
            option_ids = tuple(
                option
                for course in courses
                for option in course_option_ids(course)
            )
            segment_name = heading
            if segment_index or instruction:
                generic_headers = {
                    "one of the following courses:",
                    "all of the following:",
                    "all of the following courses:",
                }
                if instruction.lower() not in generic_headers:
                    segment_name = instruction.rstrip(":") or heading
            key = (segment_name, option_ids)
            if key in seen_groups:
                continue
            seen_groups.add(key)
            known_units = [
                float(course["units"])
                for course in courses
                if course["units"] is not None
            ]
            selected_count = min(choose, len(option_ids))
            per_choice_units = (
                unit_requirement / selected_count
                if unit_requirement
                else min(known_units) if known_units else 9
            )
            groups.append({
                "id": stable_id(f"{heading}-{segment_index + 1}"),
                "name": segment_name,
                "heading": heading,
                "choose": selected_count,
                "units": round(per_choice_units * selected_count),
                "options": list(option_ids),
                "source_instruction": instruction or None,
                "selection_rule": (
                    {
                        "type": "minimum_units",
                        "minimum_units": unit_requirement,
                        "course_count_estimate": selected_count,
                    }
                    if unit_requirement
                    else {
                        "type": "unresolved" if assumed_choice else "course_count",
                        "count": selected_count,
                    }
                ),
                "track": (
                    clean_text(re.split(r"\btrack\b", track_heading, maxsplit=1, flags=re.IGNORECASE)[0])
                    + " Track"
                    if track_heading
                    else None
                ),
            })

    groups = merge_minimum_unit_groups(groups)
    tracks: dict[str, list[str]] = {}
    for group in groups:
        if group.get("track"):
            tracks.setdefault(str(group["track"]), []).append(str(group["id"]))
    page_text = clean_text(main.get_text(" ", strip=True))
    track_selection_count = choose_count(
        next((
            sentence
            for sentence in re.split(r"(?<=[.!?])\s+", page_text)
            if "track" in sentence.lower()
            and re.search(r"\b(?:choose|select)\b", sentence, re.IGNORECASE)
        ), "")
    )
    track_rule = None
    if tracks:
        track_rule = {
            "type": "choose_tracks" if track_selection_count else "unresolved",
            "count": track_selection_count,
            "tracks": [
                {"id": stable_id(name), "name": name, "requirement_group_ids": ids}
                for name, ids in tracks.items()
            ],
        }

    course_count = len(fixed) + sum(len(group["options"]) for group in groups)
    ambiguous = sum(
        warning.startswith("Assumed choose-one") for warning in warnings
    )
    explicit_groups = sum(
        group.get("selection_rule", {}).get("type") != "unresolved"
        for group in groups
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
        "program_type": program.get("program_type", "primary_major"),
        "catalog_year": CATALOG_YEAR,
        "source_url": program["source_url"],
        "source_hash": sha256_text(clean_text(main.get_text(" ", strip=True))),
        "fixed_courses": fixed,
        "requirement_groups": groups,
        "track_rule": track_rule,
        "policy_signals": {
            "shared_credit": shared_credit_signals(page_text),
        },
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
    track_rule = curriculum.get("track_rule")
    if (
        track_rule
        and len(track_rule.get("tracks", [])) > 1
        and track_rule.get("type") == "unresolved"
    ):
        blockers.append("Multiple tracks require an explicit track-selection rule.")
    extracted_units = sum(float(item.get("units") or 0) for item in curriculum["fixed_courses"])
    extracted_units += sum(float(item.get("units") or 0) for item in groups)
    if extracted_units > 360:
        blockers.append(
            f"Extracted requirement total is implausible ({round(extracted_units)} units)."
        )
    unresolved_groups = [
        str(group["id"])
        for group in groups
        if group.get("selection_rule", {}).get("type") == "unresolved"
    ]
    if unresolved_groups:
        blockers.append(
            f"{len(unresolved_groups)} requirement groups have unresolved selection rules."
        )
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


def load_programs(program_types: Iterable[str] = PROGRAM_TYPES) -> list[dict[str, object]]:
    programs = json.loads(DIRECTORY_PATH.read_text(encoding="utf-8"))
    selected = set(program_types)
    return [item for item in programs if item.get("program_type") in selected]


def load_majors() -> list[dict[str, object]]:
    """Compatibility wrapper for callers of the original major-only pipeline."""
    return load_programs(("primary_major",))


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


def run(
    limit: int | None = None,
    offline: bool = False,
    program_types: Iterable[str] = ("primary_major",),
) -> dict[str, object]:
    program_types = tuple(dict.fromkeys(program_types))
    all_programs = set(program_types) == set(PROGRAM_TYPES)
    scraped_dir = ALL_SCRAPED_DIR if all_programs else SCRAPED_DIR
    registry_path = ALL_REGISTRY_PATH if all_programs else REGISTRY_PATH
    report_path = ALL_REPORT_PATH if all_programs else REPORT_PATH
    previous = {}
    if registry_path.exists():
        previous = {
            item["program_id"]: item
            for item in json.loads(registry_path.read_text(encoding="utf-8")).get("programs", [])
        }
    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    changed: list[str] = []
    programs = load_programs(program_types)[:limit]
    known_ids = scheduled_course_ids()
    scraped_dir.mkdir(parents=True, exist_ok=True)

    for program in programs:
        cache_path = scraped_dir / f"{program['id']}.html"
        legacy_cache_path = SCRAPED_DIR / f"{program['id']}.html"
        try:
            if offline:
                readable_cache = cache_path if cache_path.exists() else legacy_cache_path
                html = readable_cache.read_text(encoding="utf-8")
            else:
                html = fetch(str(program["source_url"]))
            if not offline:
                cache_path.write_text(html, encoding="utf-8")
            parsed = parse_curriculum_html(html, program)
            parsed["validation"] = validate_curriculum(parsed, known_ids)
            old_hash = previous.get(str(program["id"]), {}).get("source_hash")
            if old_hash and old_hash != parsed["source_hash"]:
                changed.append(str(program["id"]))
            results.append(parsed)
            write_json(scraped_dir / f"{program['id']}.json", parsed)
        except Exception as error:  # keep the full-school run resilient
            failures.append({"program_id": str(program["id"]), "error": str(error)})

    generated_at = datetime.now(timezone.utc).isoformat()
    registry = {"catalog_year": CATALOG_YEAR, "generated_at": generated_at, "programs": results}
    report = {
        "catalog_year": CATALOG_YEAR,
        "generated_at": generated_at,
        "program_types": list(program_types),
        "requested": len(programs),
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
    write_json(registry_path, registry)
    write_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--program-type",
        action="append",
        choices=(*PROGRAM_TYPES, "all"),
        dest="program_types",
        help="Repeat to select types, or pass 'all' for all catalog programs.",
    )
    args = parser.parse_args()
    requested_types = args.program_types or ["primary_major"]
    program_types = PROGRAM_TYPES if "all" in requested_types else tuple(requested_types)
    report = run(limit=args.limit, offline=args.offline, program_types=program_types)
    # Keep terminal output concise; the complete per-program queue lives in
    # major_curriculum_report.json.
    print(json.dumps({key: value for key, value in report.items() if key != "review_queue"}, indent=2))


if __name__ == "__main__":
    main()
