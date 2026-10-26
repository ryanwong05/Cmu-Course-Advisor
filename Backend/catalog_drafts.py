"""Clearly provisional planning inputs from the scraped program catalog.

The catalog extractor is useful for exploration, but it is not an academic
policy audit. Keep its output separate from curated planner profiles.
"""

from __future__ import annotations

import re


COURSE_ID = re.compile(r"\d{2}-\d{3}")


def catalog_course_ids(curricula: dict[str, dict]) -> list[str]:
    """Collect concrete IDs for one batch of schedule-data hydration."""
    ids = []
    for curriculum in curricula.values():
        ids.extend(item["id"] for item in curriculum.get("fixed_courses", []))
        ids.extend(
            course_id
            for group in curriculum.get("requirement_groups", [])
            for option in group.get("options", [])
            for course_id in COURSE_ID.findall(str(option))
        )
    return list(dict.fromkeys(ids))


def find_catalog_entry(
    directory: list[dict], program_id: str, goal_type: str,
) -> dict | None:
    directory_type = (
        "primary_major" if goal_type in {"current_major", "internal_transfer"}
        else goal_type
    )
    return next((
        entry for entry in directory
        if entry.get("program_type") == directory_type
        and program_id in {entry.get("id"), entry.get("planning_id")}
    ), None)


def build_catalog_draft_profile(
    entry: dict,
    curriculum: dict,
    scheduled_course_ids: set[str],
    goal_type: str,
    credential_evidence: dict | None = None,
) -> dict:
    """Expose only concrete extractable choices, with unresolved work explicit.

    A shared page may contain different requirements for a major, additional
    major, or degree. Base courses are tentative candidates for a secondary
    credential only when its own section explicitly says to inherit them.
    """
    unresolved = []
    source_id = entry.get("requirements_source_program_id") or entry["id"]
    shared_page_variant = source_id != entry["id"]
    inherited_course_hint = bool(
        shared_page_variant
        and credential_evidence
        and credential_evidence.get("program_id") == entry["id"]
        and credential_evidence.get("source_program_id") == source_id
        and credential_evidence.get("parent_source_hash") == curriculum.get("source_hash")
        and credential_evidence.get("may_inherit_base_courses")
    )
    track_rule = curriculum.get("track_rule") or {}
    unresolved_track = (
        len(track_rule.get("tracks", [])) > 1
        and track_rule.get("type") == "unresolved"
    )
    if shared_page_variant:
        unresolved.append({
            "id": "credential-specific-rules",
            "name": f"{entry.get('credential', 'Program')} requirements",
            "reason": "credential_rules_not_separately_parsed",
            "detail": (
                "The official section says this credential follows the base major's courses. Those courses are tentative here; exceptions, double-counting, and additional conditions still need review."
                if inherited_course_hint else
                "This credential shares a catalog page with another program. Its own rules must be reviewed before courses are assigned."
            ),
        })
    if unresolved_track:
        unresolved.append({
            "id": "track-selection",
            "name": "Choose and verify a program track",
            "reason": "track_selection_pending",
            "detail": "The catalog lists multiple tracks, but the extracted data cannot safely select one.",
        })

    may_schedule = (not shared_page_variant or inherited_course_hint) and not unresolved_track
    fixed = []
    groups = []
    if may_schedule:
        for item in curriculum.get("fixed_courses", []):
            course_id = str(item.get("id", ""))
            if course_id in scheduled_course_ids:
                fixed.append(course_id)
            else:
                unresolved.append({
                    "id": f"missing-course-{course_id}",
                    "name": f"{course_id} — catalog-listed course",
                    "reason": "course_schedule_data_missing",
                    "detail": "This catalog-listed course is not in the current scheduling data.",
                })
        for group in curriculum.get("requirement_groups", []):
            group_id = str(group.get("id", "requirement"))
            rule = group.get("selection_rule") or {}
            options = [
                str(option) for option in group.get("options", [])
                if all(
                    part in scheduled_course_ids
                    for part in str(option).split(" + ")
                ) and all(
                    COURSE_ID.fullmatch(part)
                    for part in str(option).split(" + ")
                )
            ]
            choose = group.get("choose")
            if (
                rule.get("type") != "unresolved"
                and isinstance(choose, int)
                and 0 < choose <= len(set(options))
            ):
                groups.append({
                    "id": group_id,
                    "name": group.get("name", group_id),
                    "choose": choose,
                    "units": group.get("units") or choose * 9,
                    "options": list(dict.fromkeys(options)),
                    "selection_rule": rule,
                })
            else:
                unresolved.append({
                    "id": f"unresolved-group-{group_id}",
                    "name": group.get("name", group_id),
                    "reason": "catalog_choice_rule_pending",
                    "detail": "The course choices or selection count cannot yet be safely resolved from the catalog extract.",
                })

    for heading in curriculum.get("extraction", {}).get("unrepresented_unit_headings", []):
        unresolved.append({
            "id": f"unparsed-{len(unresolved) + 1}",
            "name": str(heading.get("heading") or "Unparsed unit requirement"),
            "reason": "catalog_requirement_not_parsed",
            "detail": "The catalog describes units here, but the extractor did not find approved course choices.",
        })
    if goal_type == "internal_transfer":
        unresolved.append({
            "id": "transfer-admission-policy",
            "name": "Internal-transfer admission requirements",
            "reason": "transfer_policy_not_verified",
            "detail": "A degree curriculum is not an internal-transfer admission policy; confirm eligibility and application rules with the destination program.",
        })
    # A structural parser check is never a human verification of the whole
    # credential. Keep every draft visibly incomplete, even if all known
    # extracted courses fit in the selected semesters.
    unresolved.append({
        "id": "catalog-policy-review",
        "name": "Complete official requirement review",
        "reason": "catalog_policy_unverified",
        "detail": "This is an exploratory draft from catalog text, not a verified degree or admission audit.",
    })
    return {
        "required_course_ids": list(dict.fromkeys(fixed)),
        "requirement_groups": groups,
        "minimum_courses": len(set(fixed)) + sum(group["choose"] for group in groups),
        "minimum_units": None,
        "eligibility": "Exploratory catalog draft only. Confirm every requirement, track, substitution, and approval with the program advisor.",
        "policy_status": "catalog_extracted_unverified",
        "source_url": entry.get("source_url") or curriculum.get("source_url"),
        "catalog_year": curriculum.get("catalog_year"),
        "draft_unresolved_requirements": unresolved,
        "catalog_extraction_status": curriculum.get("extraction", {}).get("status"),
    }


def mark_catalog_draft_unresolved(path_result: dict, profile: dict) -> None:
    """Keep unknown catalog rules outside semesters and visible in diagnostics."""
    unresolved = profile.get("draft_unresolved_requirements", [])
    if not unresolved:
        return
    path_result["goal_complete"] = False
    path_result["remaining_program_requirements"] = [
        *path_result.get("remaining_program_requirements", []),
        *({"id": item["id"], "name": item["name"], "options": []} for item in unresolved),
    ]
    path_result["unscheduled_requirements"] = [
        *path_result.get("unscheduled_requirements", []),
        *({"type": "catalog_review", **item} for item in unresolved),
    ]
