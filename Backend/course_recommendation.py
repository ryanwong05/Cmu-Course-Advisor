"""Explainable course recommendations for slots produced by the planner."""

from __future__ import annotations

import json
from pathlib import Path

from Engine.availability import prerequisite_course_ids, prerequisites_satisfied


def load_recommendation_policy(policy_dir: Path) -> dict:
    with (policy_dir / "course_recommendation.json").open(encoding="utf-8") as file:
        return json.load(file)


def recommendation_slots_from_plan(
    plan: dict,
    baseline_candidate_pools: dict[str, dict] | None = None,
) -> list[dict]:
    """Extract editable requirement slots without interpreting new academic rules."""
    baseline_candidate_pools = baseline_candidate_pools or {}
    slots = []
    for semester in plan.get("path", []):
        common = {
            "semester_number": semester.get("semester_number"),
            "semester": semester.get("semester"),
            "academic_year": semester.get("academic_year", 1),
            "unit_limit": semester.get("unit_limit"),
            "semester_total_units": semester.get("total_units", 0),
            "semester_high_intensity_count": semester.get("high_intensity_count", 0),
        }
        for requirement in semester.get("program_requirements", []):
            if not requirement.get("options"):
                continue
            slots.append({
                **common,
                "requirement_id": requirement["id"],
                "requirement_name": requirement.get("name", requirement["id"]),
                "options": list(requirement.get("options", [])),
                "reserved_units": requirement.get("units", 0),
                "current_default": requirement.get("default_option"),
                "scope": requirement.get("scope", "goal"),
                "overlap_limit": requirement.get("cross_scope_overlap_limit"),
                "overlap_allowed": (
                    isinstance(requirement.get("cross_scope_overlap_limit"), int)
                    and requirement["cross_scope_overlap_limit"] > 0
                ),
                "eligibility_verified": True,
                "eligibility_note": None,
            })
        for requirement in semester.get("baseline_requirements", []):
            pool = baseline_candidate_pools.get(requirement["id"], {})
            options = list(requirement.get("courses", [])) or list(pool.get("options", []))
            if not options:
                slots.append({
                    **common,
                    "requirement_id": requirement["id"],
                    "requirement_name": requirement.get("name", requirement["id"]),
                    "options": [],
                    "reserved_units": requirement.get("units", 0),
                    "current_default": None,
                    "scope": "baseline",
                    "overlap_allowed": False,
                    "eligibility_verified": False,
                    "eligibility_note": pool.get("eligibility_note"),
                })
                continue
            slots.append({
                **common,
                "requirement_id": requirement["id"],
                "requirement_name": requirement.get("name", requirement["id"]),
                "options": options,
                "reserved_units": requirement.get("units", 0),
                "current_default": None,
                "scope": "baseline",
                "overlap_allowed": False,
                "eligibility_verified": bool(requirement.get("courses")) or bool(
                    pool.get("eligibility_verified")
                ),
                "eligibility_note": pool.get("eligibility_note"),
            })
    return slots


def _option_ids(option: str) -> list[str]:
    return [course_id.strip() for course_id in option.split(" + ") if course_id.strip()]


def _course_units(option_ids: list[str], catalog: dict[str, dict]) -> float:
    return sum(float(catalog.get(course_id, {}).get("units", 0)) for course_id in option_ids)


def _option_name(option: str, catalog: dict[str, dict]) -> str:
    names = [catalog.get(course_id, {}).get("name", course_id) for course_id in _option_ids(option)]
    return " + ".join(names)


def _planned_before(plan: dict, semester_number: int) -> set[str]:
    planned = set()
    for semester in plan.get("path", []):
        if semester.get("semester_number", 0) >= semester_number:
            continue
        planned.update(semester.get("courses", []))
        for requirement in semester.get("program_requirements", []):
            planned.update(_option_ids(requirement.get("default_option") or ""))
    return planned


def _all_planned_courses(plan: dict) -> set[str]:
    planned = set()
    for semester in plan.get("path", []):
        planned.update(semester.get("courses", []))
        for requirement in semester.get("program_requirements", []):
            planned.update(_option_ids(requirement.get("default_option") or ""))
    return planned


def _candidate(
    option: str,
    slot: dict,
    catalog: dict[str, dict],
    completed_before: set[str],
    unavailable_planned: set[str],
    primary_course_ids: set[str],
    goal_course_ids: set[str],
    future_course_ids: set[str],
    policy: dict,
) -> dict:
    weights = policy["weights"]
    option_ids = _option_ids(option)
    invalid_reasons = []
    warnings = []
    courses = [catalog.get(course_id) for course_id in option_ids]
    if not option_ids or any(course is None for course in courses):
        invalid_reasons.append("unsupported_course_data")
    if any(course_id in completed_before for course_id in option_ids):
        invalid_reasons.append("already_completed")
    if any(course_id in unavailable_planned for course_id in option_ids):
        invalid_reasons.append("already_planned_for_another_requirement")

    for course in (course for course in courses if course is not None):
        offered = course.get("offered", [])
        if offered and slot["semester"] not in offered:
            invalid_reasons.append("not_offered_in_slot_semester")
        if slot["academic_year"] < course.get("minimum_year", 1):
            invalid_reasons.append("class_standing_restriction")
        if not prerequisites_satisfied(course, completed_before):
            invalid_reasons.append("unmet_prerequisites")

    units = _course_units(option_ids, catalog)
    unit_limit = slot.get("unit_limit")
    total_with_option = slot.get("semester_total_units", 0) - slot.get("reserved_units", 0) + units
    if unit_limit is not None and total_with_option > unit_limit:
        invalid_reasons.append("semester_unit_limit")

    prerequisite_ids = sorted({
        prerequisite
        for course in (course for course in courses if course is not None)
        for prerequisite in prerequisite_course_ids(course)
        if prerequisite not in completed_before
    })
    future_unlocks = sum(
        any(course_id in prerequisite_course_ids(catalog.get(future_id, {})) for course_id in option_ids)
        for future_id in future_course_ids
    )
    offered_terms = sorted({
        term
        for course in (course for course in courses if course is not None)
        for term in course.get("offered", [])
    })
    intensity_tiers = [
        catalog.get(course_id, {}).get("intensity", {}).get("tier", 3)
        for course_id in option_ids
    ]
    maximum_tier = max(intensity_tiers, default=3)
    cross_program_ids = primary_course_ids if slot.get("scope") == "goal" else goal_course_ids
    overlap_count = len(set(option_ids).intersection(cross_program_ids)) if slot.get("overlap_allowed") else 0
    prerequisite_statuses = {
        catalog.get(course_id, {}).get("prerequisite_data_status", "catalog_not_imported")
        for course_id in option_ids
    }
    verified_prerequisites = prerequisite_statuses <= {"verified", "curated_mapping"}
    if not verified_prerequisites:
        warnings.append("Prerequisite information is not fully verified")
    if not slot.get("eligibility_verified"):
        warnings.append(
            slot.get("eligibility_note")
            or "Requirement approval is not fully verified; confirm in SIO or with an advisor"
        )

    components = {
        "cross_program_overlap": overlap_count * weights["cross_program_overlap"],
        "future_unlocks": future_unlocks * weights["future_unlock"],
        "no_additional_prerequisites": weights["no_additional_prerequisites"] if not prerequisite_ids else 0,
        "lighter_workload": weights["lighter_workload"] if maximum_tier <= 3 else 0,
        "planner_default": weights["planner_default"] if option == slot.get("current_default") else 0,
        "prerequisite_steps": len(prerequisite_ids) * weights["prerequisite_step"],
        "busy_semester_workload": (
            weights["heavy_course_in_busy_semester"]
            if maximum_tier >= 5 and slot.get("semester_high_intensity_count", 0) >= 1 else 0
        ),
        "single_term_offering": weights["single_term_offering"] if len(offered_terms) == 1 else 0,
        "unverified_prerequisites": 0 if verified_prerequisites else weights["unverified_prerequisites"],
        "unverified_requirement_eligibility": (
            0 if slot.get("eligibility_verified") else weights["unverified_requirement_eligibility"]
        ),
    }
    reasons = [f"Satisfies {slot['requirement_name']}"]
    if overlap_count:
        reasons.append("Also advances another verified program requirement within the published overlap limit")
    if future_unlocks:
        reasons.append(f"Unlocks {future_unlocks} later planned course{'s' if future_unlocks != 1 else ''}")
    if not prerequisite_ids:
        reasons.append("Does not add another prerequisite step")
    if maximum_tier <= 3:
        reasons.append("Has a moderate-or-lighter workload estimate")
    if len(offered_terms) > 1:
        reasons.append("Is listed in both Fall and Spring")
    return {
        "course_id": option,
        "course_name": _option_name(option, catalog),
        "units": units,
        "valid": not invalid_reasons,
        "invalid_reasons": sorted(set(invalid_reasons)),
        "reasons": reasons,
        "warnings": warnings,
        "factors": {
            "requirement_match": True,
            "requirement_eligibility_verified": bool(slot.get("eligibility_verified")),
            "cross_program_overlap": overlap_count,
            "future_unlocks": future_unlocks,
            "additional_prerequisites": prerequisite_ids,
            "workload_tier": maximum_tier,
            "offered_terms": offered_terms,
            "semester_units_after_selection": total_with_option,
        },
        "score_components": components,
        "ranking_score": sum(components.values()),
    }


def recommend_courses_for_plan(
    plan: dict,
    slots: list[dict],
    catalog: dict[str, dict],
    completed_courses: set[str],
    primary_course_ids: set[str],
    goal_course_ids: set[str],
    manual_selections: dict[str, str],
    policy: dict,
    requirement_ids: set[str] | None = None,
) -> dict:
    """Return a duplicate-free, semester-feasible greedy recommendation set."""
    selected_ids = set(completed_courses)
    replaced_default_ids = set()
    all_planned = _all_planned_courses(plan)
    recommendations = []
    diagnostics = []
    semester_unit_deltas: dict[int, float] = {}
    cross_scope_overlap_used = 0
    maximum_alternatives = policy.get("maximum_alternatives", 4)
    ordered_slots = sorted(slots, key=lambda item: (item.get("semester_number", 99), item["requirement_id"]))

    for slot in ordered_slots:
        slot = dict(slot)
        semester_number = slot["semester_number"]
        slot["semester_total_units"] = (
            slot.get("semester_total_units", 0)
            + semester_unit_deltas.get(semester_number, 0)
        )
        overlap_limit = slot.get("overlap_limit")
        slot["overlap_allowed"] = (
            isinstance(overlap_limit, int)
            and cross_scope_overlap_used < overlap_limit
        )
        requirement_id = slot["requirement_id"]
        if requirement_ids and requirement_id not in requirement_ids:
            continue
        if not slot.get("options"):
            diagnostic = {
                "requirement_id": requirement_id,
                "requirement_name": slot["requirement_name"],
                "code": "insufficient_verified_data",
                "message": slot.get("eligibility_note") or "No structured approved-course set is available for this requirement.",
            }
            diagnostics.append(diagnostic)
            recommendations.append({**diagnostic, "status": "no_recommendation", "recommended": None, "alternatives": []})
            continue

        completed_before = (
            set(completed_courses)
            | (_planned_before(plan, slot["semester_number"]) - replaced_default_ids)
            | selected_ids
        )
        current_ids = set(_option_ids(slot.get("current_default") or ""))
        unavailable_planned = (all_planned - current_ids) | (selected_ids - completed_before)
        future_ids = {
            course_id
            for semester in plan.get("path", [])
            if semester.get("semester_number", 0) > slot["semester_number"]
            for course_id in (
                list(semester.get("courses", []))
                + [
                    option_id
                    for requirement in semester.get("program_requirements", [])
                    for option_id in _option_ids(requirement.get("default_option") or "")
                ]
            )
        }
        candidates = [
            _candidate(
                option, slot, catalog, completed_before, unavailable_planned,
                primary_course_ids, goal_course_ids, future_ids, policy,
            )
            for option in slot["options"]
        ]
        valid = sorted(
            (candidate for candidate in candidates if candidate["valid"]),
            key=lambda candidate: (-candidate["ranking_score"], candidate["course_id"]),
        )
        manual = manual_selections.get(requirement_id)
        manual_candidate = next((candidate for candidate in valid if candidate["course_id"] == manual), None)
        if manual and manual_candidate is None:
            diagnostics.append({
                "requirement_id": requirement_id,
                "requirement_name": slot["requirement_name"],
                "code": "invalid_manual_selection",
                "message": "The saved manual choice is not valid in the currently planned semester.",
            })
        recommended = manual_candidate or (valid[0] if valid else None)
        if recommended is None:
            reason_counts = sorted({reason for candidate in candidates for reason in candidate["invalid_reasons"]})
            code = reason_counts[0] if len(reason_counts) == 1 else "no_valid_candidate"
            diagnostic = {
                "requirement_id": requirement_id,
                "requirement_name": slot["requirement_name"],
                "code": code,
                "message": "No candidate passes the current semester, prerequisite, unit, and duplicate-course checks.",
                "filter_reasons": reason_counts,
            }
            diagnostics.append(diagnostic)
            recommendations.append({**diagnostic, "status": "no_recommendation", "recommended": None, "alternatives": []})
            continue

        if manual_candidate:
            recommended = dict(recommended)
            recommended["reasons"] = ["Preserves your valid manual selection", *recommended["reasons"]]
        recommended_ids = set(_option_ids(recommended["course_id"]))
        if recommended["course_id"] != slot.get("current_default"):
            replaced_default_ids.update(current_ids)
        selected_ids.update(recommended_ids)
        all_planned.update(recommended_ids)
        semester_unit_deltas[semester_number] = (
            semester_unit_deltas.get(semester_number, 0)
            + recommended["units"]
            - slot.get("reserved_units", 0)
        )
        if recommended["factors"]["cross_program_overlap"]:
            cross_scope_overlap_used += 1
        alternatives = [candidate for candidate in valid if candidate["course_id"] != recommended["course_id"]][
            :maximum_alternatives
        ]
        for rank, candidate in enumerate([recommended, *alternatives], start=1):
            candidate["rank"] = rank
        recommendations.append({
            "requirement_id": requirement_id,
            "requirement_name": slot["requirement_name"],
            "semester_number": slot["semester_number"],
            "semester": slot["semester"],
            "status": (
                "manual_selection_preserved" if manual_candidate
                else "recommended" if slot.get("eligibility_verified")
                else "candidate_requires_verification"
            ),
            "recommended": recommended,
            "alternatives": alternatives,
            "only_legal_candidate": len(valid) == 1,
        })

    chosen = [item["recommended"] for item in recommendations if item.get("recommended")]
    chosen_ids = [course_id for item in chosen for course_id in _option_ids(item["course_id"])]
    return {
        "recommendations": recommendations,
        "diagnostics": diagnostics,
        "validation": {
            "coherent": len(chosen_ids) == len(set(chosen_ids)),
            "duplicate_free": len(chosen_ids) == len(set(chosen_ids)),
            "unit_limits_respected": all(
                candidate["factors"]["semester_units_after_selection"]
                <= next(
                    (
                        slot["unit_limit"]
                        for slot in slots
                        if slot["requirement_id"] == item["requirement_id"]
                        and slot.get("unit_limit") is not None
                    ),
                    float("inf"),
                )
                for item in recommendations if item.get("recommended")
                for candidate in [item["recommended"]]
            ),
            "prerequisites_respected": all(
                not candidate["invalid_reasons"]
                for candidate in chosen
            ),
        },
    }
