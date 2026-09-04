def prerequisite_course_ids(course):
    expression = course.get("prerequisite_expression")
    if expression:
        return [option["course_id"] for option in expression.get("options", [])]
    return course.get("prerequisites", [])


def prerequisites_satisfied(course, completed_courses):
    completed = set(completed_courses)
    expression = course.get("prerequisite_expression")
    if not expression:
        return all(
            prerequisite in completed
            for prerequisite in course.get("prerequisites", [])
        )

    checks = [
        option["course_id"] in completed
        for option in expression.get("options", [])
    ]
    if expression.get("type") == "any_of":
        return any(checks)
    if expression.get("type") == "all_of":
        return all(checks)
    return False


def get_available_courses(completed_courses, courses):
    available = []

    for course in courses:
        course_id = course["id"]

        if course_id in completed_courses:
            continue

        if prerequisites_satisfied(course, completed_courses):
            available.append(course_id)

    return available

def get_available_courses_for_semester(
    completed_courses,
    courses,
    semester
):
    available = []

    for course in courses:
        course_id = course["id"]

        # 已修过
        if course_id in completed_courses:
            continue

        # 这学期不开
        if semester not in course["offered"]:
            continue

        # prerequisite 检查
        if prerequisites_satisfied(course, completed_courses):
            available.append(course_id)

    return available
