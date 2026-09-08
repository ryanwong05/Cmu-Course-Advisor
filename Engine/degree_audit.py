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


def build_degree_audits(student, goal, profile, path_result, primary_baseline):
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
    }

    if profile is None:
        goal_audit = {
            "type": goal.type,
            "program": goal.program,
            "status": "not_verified",
            "message": "No verified requirement profile is available for this goal.",
        }
    else:
        total = profile.get("minimum_courses", 0)
        remaining = len(path_result.get("remaining", [])) + len(
            path_result.get("remaining_program_requirements", [])
        )
        placed = max(0, total - remaining)
        goal_audit = {
            "type": goal.type,
            "program": goal.program,
            "status": "mapped" if path_result.get("goal_complete") else "in_progress",
            "total_requirements": total,
            "requirements_placed": placed,
            "requirements_remaining": remaining,
            "minimum_units": profile.get("minimum_units"),
            "requirements_verified": True,
            "message": (
                "All published curriculum requirements are placed in the plan."
                if remaining == 0
                else f"{remaining} curriculum requirements remain outside this planning horizon."
            ),
        }

    return {"primary_degree": primary, "selected_goal": goal_audit}
