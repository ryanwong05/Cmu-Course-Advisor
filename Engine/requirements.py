def check_requirements(completed_courses, program_id, requirements):
    required_courses = requirements[program_id]["required_courses"]

    if not required_courses:
        return {
            "completed": [],
            "remaining": [],
            "progress": None,
            "status": "not_configured"
        }

    completed = []
    remaining = []

    for course in required_courses:
        if course in completed_courses:
            completed.append(course)
        else:
            remaining.append(course)

    progress = len(completed) / len(required_courses)

    return {
        "completed": completed,
        "remaining": remaining,
        "progress": progress,
        "status": "ready"
    }
