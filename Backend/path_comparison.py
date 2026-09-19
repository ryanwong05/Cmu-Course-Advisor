"""Deterministic comparisons between plans produced by the existing planner."""

from __future__ import annotations

import json
from pathlib import Path


def load_path_alternatives(policy_dir: Path) -> dict:
    with (policy_dir / "path_alternatives.json").open(encoding="utf-8") as file:
        return json.load(file)


def discover_path_alternatives(
    goal: dict,
    student: dict,
    policy: dict,
    program_profiles: dict,
    program_names: dict[str, str],
) -> list[dict]:
    """Return configured, planner-supported alternatives in a stable order."""
    key = f"{goal['program']}|{goal['type']}"
    alternatives = []
    for candidate in policy.get("alternatives", {}).get(key, []):
        program = candidate["program"]
        goal_type = candidate["goal_type"]
        if program == goal["program"] and goal_type == goal["type"]:
            continue
        if goal_type == "minor" and student.get("college") == "scs":
            continue
        if goal_type not in program_profiles.get("programs", {}).get(program, {}):
            continue
        alternatives.append({
            "program": program,
            "program_name": program_names.get(program, program),
            "goal_type": goal_type,
            "label": candidate.get("label") or _goal_label(
                program_names.get(program, program), goal_type
            ),
        })
    return alternatives[: policy.get("max_alternatives", 4)]


def _goal_label(program_name: str, goal_type: str) -> str:
    suffix = {
        "minor": "Minor",
        "additional_major": "Additional Major",
        "internal_transfer": "Transfer",
    }.get(goal_type, goal_type.replace("_", " ").title())
    return f"{program_name} {suffix}"


def _split_course_option(option: str | None) -> list[str]:
    if not option:
        return []
    return [part.strip() for part in option.split(" + ") if part.strip()]


def _planned_goal_courses(plan: dict) -> tuple[set[str], dict[str, str]]:
    course_ids: set[str] = set()
    course_terms: dict[str, str] = {}
    for semester in plan.get("path", []):
        term = f"{semester.get('academic_year_name', '')} {semester.get('semester', '')}".strip()
        semester_ids = set(semester.get("goal_courses", []))
        semester_ids.update(semester.get("shared_courses", []))
        for requirement in semester.get("program_requirements", []):
            if requirement.get("scope", "goal") == "primary_major":
                continue
            semester_ids.update(_split_course_option(requirement.get("default_option")))
        for course_id in semester_ids:
            course_ids.add(course_id)
            course_terms.setdefault(course_id, term)
    return course_ids, course_terms


def _unscheduled(plan: dict) -> list[dict]:
    details = list(plan.get("unscheduled_requirements", []))
    seen = {item.get("id") for item in details}
    for course_id in plan.get("remaining", []):
        if course_id not in seen:
            details.append({"id": course_id, "name": course_id, "reason": "planning_horizon_exhausted"})
    for requirement in plan.get("remaining_program_requirements", []):
        requirement_id = requirement.get("id")
        if requirement_id not in seen:
            details.append({
                "id": requirement_id,
                "name": requirement.get("name", requirement_id),
                "reason": requirement.get("unscheduled_reason", "planning_horizon_exhausted"),
            })
    return details


def summarize_generated_plan(
    result: dict,
    primary_course_ids: set[str],
    completed_courses: set[str],
) -> dict:
    """Build factual metrics from one generated plan, without a second planner."""
    plan = result["fastest"]
    catalog = result.get("course_catalog", {})
    path = plan.get("path", [])
    goal_courses, course_terms = _planned_goal_courses(plan)
    actual_shared_courses = {
        course_id
        for semester in plan.get("path", [])
        for course_id in semester.get("shared_courses", [])
    }
    potential_overlap_courses = goal_courses.intersection(primary_course_ids)
    additional_courses = goal_courses.difference(primary_course_ids, completed_courses)
    unknown_units = sorted(course_id for course_id in additional_courses if course_id not in catalog)
    additional_units = sum(
        catalog.get(course_id, {}).get("units", 0)
        for course_id in additional_courses
    )
    shared_units = sum(
        catalog.get(course_id, {}).get("units", 0)
        for course_id in actual_shared_courses
    )
    unscheduled = _unscheduled(plan)
    has_overload = any(
        semester.get("total_units", 0) > semester.get("unit_limit", 10**9)
        for semester in path
    )
    overload_required = has_overload if plan.get("goal_complete") else None

    goal_term_numbers = [
        semester.get("semester_number", 0)
        for semester in path
        if set(semester.get("goal_courses", [])).intersection(goal_courses)
        or semester.get("shared_courses")
        or any(
            requirement.get("scope", "goal") != "primary_major"
            for requirement in semester.get("program_requirements", [])
        )
    ]
    completion_term = None
    if goal_term_numbers:
        last_number = max(goal_term_numbers)
        last_term = next(
            (semester for semester in path if semester.get("semester_number") == last_number),
            None,
        )
        if last_term:
            completion_term = f"{last_term.get('academic_year_name')} {last_term.get('semester')}"

    workload_values = [
        semester.get("workload", {}).get("average_workload")
        for semester in path
        if semester.get("workload", {}).get("average_workload") is not None
    ]
    peak_workload = max(workload_values) if workload_values else None
    high_workload_semesters = sum(
        semester.get("workload", {}).get("warning_level") == "high"
        or semester.get("high_intensity_count", 0) >= 2
        for semester in path
    )
    free_elective_units = sum(max(0, semester.get("free_choice_units", 0)) for semester in path)

    prerequisite_bottlenecks = []
    limited_offerings = []
    for course_id in sorted(goal_courses):
        course = catalog.get(course_id, {})
        prerequisites = [
            prerequisite for prerequisite in course.get("prerequisites", [])
            if prerequisite not in completed_courses
        ]
        if prerequisites:
            prerequisite_bottlenecks.append({
                "course": course_id,
                "prerequisites": prerequisites,
                "status": course.get("prerequisite_data_status", "not_verified"),
            })
        offered = course.get("offered", [])
        if len(offered) == 1:
            limited_offerings.append({"course": course_id, "offered": offered})

    return {
        "goal_complete": bool(plan.get("goal_complete")),
        "additional_courses": len(additional_courses),
        "additional_course_ids": sorted(additional_courses),
        "additional_units": None if unknown_units else additional_units,
        "unknown_unit_courses": unknown_units,
        "shared_courses": sorted(actual_shared_courses),
        "shared_course_count": len(actual_shared_courses),
        "potential_overlap_courses": sorted(potential_overlap_courses),
        "potential_overlap_course_count": len(potential_overlap_courses),
        "overlap_units_saved": shared_units,
        "completion_term": completion_term,
        "completion_semester_number": max(goal_term_numbers) if goal_term_numbers else None,
        "high_workload_semesters": high_workload_semesters,
        "peak_workload": peak_workload,
        "overload_required": overload_required,
        "free_elective_units": free_elective_units,
        "unscheduled_requirements": unscheduled,
        "prerequisite_bottlenecks": prerequisite_bottlenecks,
        "limited_offerings": limited_offerings,
        "course_terms": course_terms,
    }


def compare_generated_plans(
    current_result: dict,
    alternative_result: dict,
    current_goal: dict,
    alternative_goal: dict,
    primary_course_ids: set[str],
    completed_courses: set[str],
    program_names: dict[str, str],
) -> dict:
    current = summarize_generated_plan(current_result, primary_course_ids, completed_courses)
    alternative = summarize_generated_plan(alternative_result, primary_course_ids, completed_courses)
    current_ids = set(current["additional_course_ids"])
    alternative_ids = set(alternative["additional_course_ids"])
    shared = current_ids & alternative_ids
    semester_changes = [
        {
            "course": course_id,
            "current_term": current["course_terms"].get(course_id),
            "alternative_term": alternative["course_terms"].get(course_id),
        }
        for course_id in sorted(shared)
        if current["course_terms"].get(course_id) != alternative["course_terms"].get(course_id)
    ]

    tradeoffs = []
    removed_courses = current_ids - alternative_ids
    added_courses = alternative_ids - current_ids
    if removed_courses:
        tradeoffs.append(
            f"The alternative removes {len(removed_courses)} courses used only by the current path."
        )
    if added_courses:
        tradeoffs.append(
            f"The alternative introduces {len(added_courses)} courses not used by the current path."
        )
    if current["additional_units"] is not None and alternative["additional_units"] is not None:
        unit_delta = alternative["additional_units"] - current["additional_units"]
        if unit_delta:
            tradeoffs.append(
                f"The alternative uses {abs(unit_delta)} {'more' if unit_delta > 0 else 'fewer'} additional units."
            )
    workload_delta = alternative["high_workload_semesters"] - current["high_workload_semesters"]
    if workload_delta:
        tradeoffs.append(
            f"The alternative has {abs(workload_delta)} {'more' if workload_delta > 0 else 'fewer'} high-workload semesters."
        )
    current_completion = current["completion_semester_number"]
    alternative_completion = alternative["completion_semester_number"]
    if current_completion is not None and alternative_completion is not None:
        completion_delta = alternative_completion - current_completion
        if completion_delta:
            tradeoffs.append(
                f"The alternative finishes {abs(completion_delta)} semester{'s' if abs(completion_delta) != 1 else ''} "
                f"{'later' if completion_delta > 0 else 'earlier'} in the generated plan."
            )
    flexibility_delta = alternative["free_elective_units"] - current["free_elective_units"]
    if flexibility_delta:
        tradeoffs.append(
            f"The alternative leaves {abs(flexibility_delta)} {'more' if flexibility_delta > 0 else 'fewer'} units of open semester capacity."
        )
    if shared:
        tradeoffs.append(
            f"The two paths preserve {len(shared)} shared planned course{'s' if len(shared) != 1 else ''}."
        )
    offering_delta = len(alternative["limited_offerings"]) - len(current["limited_offerings"])
    if offering_delta:
        tradeoffs.append(
            f"The alternative has {abs(offering_delta)} {'more' if offering_delta > 0 else 'fewer'} limited-offering course bottlenecks."
        )
    if alternative["unscheduled_requirements"]:
        tradeoffs.append(
            f"The alternative leaves {len(alternative['unscheduled_requirements'])} requirements unscheduled within this horizon."
        )
    if not tradeoffs:
        tradeoffs.append("The generated plans have similar measured workload and course-count impact.")

    return {
        "current": {
            "goal": current_goal,
            "label": _goal_label(program_names.get(current_goal["program"], current_goal["program"]), current_goal["type"]),
            "metrics": current,
        },
        "alternative": {
            "goal": alternative_goal,
            "label": _goal_label(program_names.get(alternative_goal["program"], alternative_goal["program"]), alternative_goal["type"]),
            "metrics": alternative,
        },
        "course_diff": {
            "only_current": sorted(current_ids - alternative_ids),
            "shared": sorted(shared),
            "only_alternative": sorted(alternative_ids - current_ids),
            "semester_changes": semester_changes,
        },
        "opportunity_cost": tradeoffs,
    }
