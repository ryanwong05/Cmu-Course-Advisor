from copy import deepcopy


def _ordered_unique(values):
    return list(dict.fromkeys(value for value in values if value))


def course_ids_from_semester(semester):
    """Return real course IDs represented by one planner semester."""
    course_ids = list(semester.get("courses", []))
    for requirement in semester.get("program_requirements", []):
        default_option = requirement.get("default_option")
        if default_option:
            course_ids.extend(
                course_id.strip()
                for course_id in default_option.split(" + ")
            )
    for requirement in semester.get("baseline_requirements", []):
        selected_course = requirement.get("selected_course_id")
        if selected_course:
            course_ids.extend(
                course_id.strip()
                for course_id in selected_course.split(" + ")
            )
    return _ordered_unique(course_ids)


def derive_academic_state(student_state, completion_expander=None):
    """Build one normalized view of completed and committed coursework."""
    expand = completion_expander or (lambda values: list(values))
    locked_semesters = deepcopy(student_state.get("locked_semesters", []))
    reported_completed = _ordered_unique(student_state.get("completed_courses", []))
    in_progress = _ordered_unique(student_state.get("in_progress_courses", []))
    planned = _ordered_unique([
        *student_state.get("planned_courses", []),
        *(
            course_id
            for semester in locked_semesters
            for course_id in course_ids_from_semester(semester)
        ),
    ])
    completed = _ordered_unique(expand(reported_completed))
    accumulated = _ordered_unique(expand([
        *completed,
        *in_progress,
        *planned,
    ]))
    planned_requirement_ids = _ordered_unique(
        requirement.get("id")
        for semester in locked_semesters
        for requirement in semester.get("baseline_requirements", [])
    )
    return {
        "reported_completed_courses": reported_completed,
        "completed_courses": completed,
        "in_progress_courses": in_progress,
        "planned_courses": planned,
        "accumulated_courses": accumulated,
        "completed_requirement_ids": _ordered_unique(
            student_state.get("completed_requirement_ids", [])
        ),
        "planned_requirement_ids": planned_requirement_ids,
        "locked_semesters": locked_semesters,
    }


def planning_boundary_after_locked_semesters(locked_semesters):
    """Return the first term after immutable history, or None when absent."""
    if not locked_semesters:
        return None
    last = locked_semesters[-1]
    semester = last.get("semester")
    academic_year = int(last.get("academic_year", 1))
    if semester == "fall":
        return {"semester": "spring", "academic_year": academic_year}
    if semester == "spring":
        return {"semester": "fall", "academic_year": academic_year + 1}
    return None


def prepend_locked_semesters(path_result, locked_semesters):
    """Prefix immutable history without changing its semester contents."""
    if not locked_semesters:
        return path_result
    locked = deepcopy(locked_semesters)
    future = deepcopy(path_result.get("path", []))
    offset = max(
        (semester.get("semester_number", index + 1) for index, semester in enumerate(locked)),
        default=len(locked),
    )
    for index, semester in enumerate(future, start=1):
        semester["semester_number"] = offset + index
    path_result["path"] = [*locked, *future]
    path_result["locked_semester_count"] = len(locked)
    return path_result


def build_student_state(
    college,
    primary_major,
    year,
    completed_courses,
    in_progress_courses=None,
    planned_courses=None,
    locked_semesters=None,
):
    return {
        "college": college,
        "primary_major": primary_major,
        "year": year,
        "completed_courses": list(completed_courses),
        "in_progress_courses": list(in_progress_courses or []),
        "planned_courses": list(planned_courses or []),
        "locked_semesters": deepcopy(locked_semesters or []),
    }


def build_planning_request(student, goals, constraints=None):
    """Build the shared input used by baseline and planning services."""
    return {
        "student": student,
        "goals": list(goals),
        "constraints": constraints or {},
    }
