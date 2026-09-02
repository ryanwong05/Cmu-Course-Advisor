def build_student_state(
    college,
    primary_major,
    year,
    completed_courses,
):
    return {
        "college": college,
        "primary_major": primary_major,
        "year": year,
        "completed_courses": list(completed_courses),
    }


def build_planning_request(student, goals, constraints=None):
    """Build the shared input used by baseline and planning services."""
    return {
        "student": student,
        "goals": list(goals),
        "constraints": constraints or {},
    }
