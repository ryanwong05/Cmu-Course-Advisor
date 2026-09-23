"""Standardized primary-degree baselines and separate goal audits."""

COLLEGE_BASELINES = {
    "engineering": {"name": "Engineering primary-major baseline", "units": 30},
    "dietrich": {"name": "Dietrich primary-major baseline", "units": 27},
    "mcs": {"name": "MCS primary-major baseline", "units": 30},
    "scs": {"name": "SCS primary-major baseline", "units": 36},
    "cfa": {"name": "CFA primary-major baseline", "units": 36},
    "tepper": {"name": "Tepper primary-major baseline", "units": 30},
    "heinz": {"name": "Interdisciplinary primary-major baseline", "units": 30},
    "intercollege": {"name": "Intercollege primary-major baseline", "units": 30},
}

MAJOR_BASELINES = {
    "computer-science": {
        "name": "Computer Science verified curriculum",
        "units": 0,
        "status": "verified_curriculum",
        "note": (
            "The 2026–27 Computer Science core, mathematics, constrained "
            "electives, SCS electives, and technical communication choices "
            "are represented directly; general education and the required "
            "minor or concentration are audited separately."
        ),
    },
    "electrical-and-computer-engineering": {
        "name": "Electrical and Computer Engineering verified curriculum",
        "units": 0,
        "status": "verified_curriculum",
        "note": (
            "The 2026–27 ECE fixed technical requirements and explicit "
            "math/science, foundation, breadth, advanced, and capstone choice "
            "groups are represented directly."
        ),
    },
    "information-systems": {
        "name": "Information Systems verified curriculum",
        "units": 0,
        "status": "verified_curriculum",
        "note": (
            "The 2026–27 Information Systems core, prerequisites, breadth "
            "areas, and concentration choices are represented directly; "
            "Dietrich general education is audited separately."
        ),
    },
    "stats-ml": {
        "name": "Statistics & Machine Learning verified curriculum",
        "units": 0,
        "status": "verified_curriculum",
        "note": (
            "The 2026–27 official fixed courses and course-choice groups are "
            "represented directly; no estimated primary-major reserve is used."
        ),
    },
    "mechanical-engineering": {
        "name": "Mechanical Engineering verified curriculum",
        "units": 0,
        "status": "verified_curriculum",
        "note": (
            "The official 2026–27 MechE recommended curriculum is represented "
            "with named core courses and explicit choice groups."
        ),
    },
    "logic-and-computation": {
        "name": "Logic and Computation verified curriculum",
        "units": 0,
        "status": "verified_curriculum",
        "note": (
            "The 2026–27 Logic and Computation formal-systems, logic, "
            "computer-science, advanced-elective, and senior-thesis "
            "requirements are represented directly."
        ),
    },
    "mathematical-sciences--b-s": {
        "name": "Mathematical Sciences B.S. verified curriculum",
        "units": 0,
        "status": "verified_curriculum",
        "note": (
            "The 2026–27 flexible Mathematical Sciences B.S. core and "
            "depth-elective requirements are represented directly; MCS "
            "general education is audited separately."
        ),
    },
}


def primary_baseline_for(student):
    baseline = MAJOR_BASELINES.get(student.primary_major) or COLLEGE_BASELINES.get(
        student.college,
        {"name": "Primary-major baseline", "units": 30},
    )
    return {
        **baseline,
        "college": student.college,
        "program": student.primary_major,
        "status": baseline.get("status", "fallback_template"),
        "note": baseline.get("note", (
            "A standard workload placeholder is used until this major's "
            "complete verified curriculum is available. Replace it with "
            "specific courses as the student customizes the plan."
        )),
    }


def _remaining_requirement_count(curriculum, completed_courses):
    """Count concrete fixed courses plus still-open choice slots."""
    if not curriculum:
        return None
    completed = set(completed_courses)
    fixed_remaining = sum(
        course_id not in completed
        for course_id in curriculum.get("required_courses", curriculum.get("required_course_ids", []))
    )
    choice_remaining = 0
    for group in curriculum.get("requirement_groups", []):
        satisfied = sum(
            set(option.split(" + ")).issubset(completed)
            for option in group.get("options", [])
        )
        choice_remaining += max(0, group.get("choose", 1) - satisfied)
    return fixed_remaining + choice_remaining


def _requirement_total(curriculum):
    """Return the number of fixed-course and choose-N requirement slots."""
    if not curriculum:
        return None
    return len(curriculum.get(
        "required_courses",
        curriculum.get("required_course_ids", []),
    )) + sum(
        group.get("choose", 1)
        for group in curriculum.get("requirement_groups", [])
    )


def _planned_course_ids(path_result):
    """Collect real future course choices without treating them as completed."""
    planned = set()
    for semester in path_result.get("path", []):
        planned.update(semester.get("courses", []))
        for requirement in semester.get("program_requirements", []):
            option = requirement.get("default_option")
            if option:
                planned.update(option.split(" + "))
    return planned


def _requirement_progress(curriculum, completed_courses, planned_courses):
    """Keep academic completion, future placement, and unresolved work separate."""
    total = _requirement_total(curriculum)
    if total is None:
        return {
            "total_requirements": None,
            "requirements_completed": None,
            "requirements_planned": None,
            "requirements_unresolved": None,
        }
    completed_remaining = _remaining_requirement_count(curriculum, completed_courses)
    covered_remaining = _remaining_requirement_count(
        curriculum,
        set(completed_courses) | set(planned_courses),
    )
    return {
        "total_requirements": total,
        "requirements_completed": max(0, total - completed_remaining),
        "requirements_planned": max(0, completed_remaining - covered_remaining),
        "requirements_unresolved": covered_remaining,
    }


def build_degree_audits(
    student,
    goal,
    profile,
    path_result,
    primary_baseline,
    primary_curriculum=None,
    goal_curriculum=None,
):
    planned_course_ids = _planned_course_ids(path_result)
    completed_semesters = max(
        0,
        (student.year - 1) * 2 + (1 if student.current_term == "spring" else 0),
    )
    planned_primary_units = sum(
        semester.get("primary_major_reserved_units", 0)
        + semester.get("current_major_units", 0)
        + sum(
            item.get("units", 0)
            for item in semester.get("program_requirements", [])
            if item.get("scope") == "primary_major"
        )
        for semester in path_result["path"]
    )
    verified_primary = primary_baseline.get("status") == "verified_curriculum"
    primary_major_complete = path_result.get("primary_major_complete", False)
    primary = {
        "type": "primary_degree",
        "program": student.primary_major,
        "status": primary_baseline.get("status", "baseline_estimate"),
        "completed_semesters": completed_semesters,
        "total_semesters": 8,
        "future_semesters_planned": len(path_result["path"]),
        "planned_primary_units": planned_primary_units,
        "requirements_verified": verified_primary,
        "major_requirements_planned": verified_primary and primary_major_complete,
        # Dietrich GenEd and the 360-unit degree total remain separate checks.
        "graduation_ready": False,
        "message": primary_baseline.get("note"),
        "requirements_remaining_to_graduate": _remaining_requirement_count(
            primary_curriculum, student.completed_courses
        ),
        "minimum_degree_units": (primary_curriculum or {}).get("minimum_degree_units"),
        **_requirement_progress(
            primary_curriculum,
            student.completed_courses,
            planned_course_ids,
        ),
    }

    if goal.type == "internal_transfer" and goal.include_post_transfer_plan:
        primary.update({
            "status": "replaced_by_transfer",
            "planned_primary_units": 0,
            "major_requirements_planned": False,
            "requirements_remaining_to_graduate": 0,
            "message": (
                "The former major is not an additional degree requirement after "
                "internal transfer. Completed courses may still satisfy the target degree."
            ),
        })

    if profile is None:
        legacy_remaining = _remaining_requirement_count(
            goal_curriculum, student.completed_courses
        )
        all_scheduled = bool(path_result.get("goal_complete"))
        goal_audit = {
            "type": goal.type,
            "program": goal.program,
            "status": "scheduled" if all_scheduled else "partially_scheduled",
            "all_requirements_scheduled": all_scheduled,
            "requirements_scheduled": None,
            "requirements_unscheduled": len(path_result.get("remaining", [])),
            "requirements_remaining_to_complete": legacy_remaining,
            "requirements_verified": legacy_remaining is not None,
            "message": (
                "Published planning requirements are mapped for this path."
                if legacy_remaining is not None
                else "No verified requirement profile is available for this goal."
            ),
            **_requirement_progress(
                goal_curriculum,
                student.completed_courses,
                planned_course_ids,
            ),
        }
    else:
        total = profile.get("minimum_courses", 0)
        official_fixed = set(profile.get("required_course_ids", []))
        remaining_fixed = path_result.get("remaining", [])
        if official_fixed:
            # Preparation such as 15-112 belongs on the schedule but is not
            # one of an SCS program's six admission-course requirements.
            remaining_fixed = [
                course_id for course_id in remaining_fixed
                if course_id in official_fixed
            ]
        remaining = len(remaining_fixed) + len(
            path_result.get("remaining_program_requirements", [])
        )
        placed = max(0, total - remaining)
        all_scheduled = bool(path_result.get("goal_complete"))
        goal_audit = {
            "type": goal.type,
            "program": goal.program,
            "status": "scheduled" if all_scheduled else "partially_scheduled",
            "all_requirements_scheduled": all_scheduled,
            "total_requirements": total,
            "requirements_scheduled": placed,
            "requirements_unscheduled": remaining,
            # Compatibility aliases for older clients. These describe plan
            # placement, never academic completion.
            "requirements_placed": placed,
            "requirements_remaining": remaining,
            "requirements_remaining_to_complete": _remaining_requirement_count(
                profile, student.completed_courses
            ),
            "minimum_units": profile.get("minimum_units"),
            "requirements_verified": True,
            "message": (
                "All published curriculum requirements are scheduled; they are not marked academically completed until the student reports completion."
                if remaining == 0
                else f"{remaining} curriculum requirements remain outside this planning horizon."
            ),
            **_requirement_progress(
                profile,
                student.completed_courses,
                planned_course_ids,
            ),
        }

    return {"primary_degree": primary, "selected_goal": goal_audit}
