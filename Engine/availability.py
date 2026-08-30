def get_available_courses(completed_courses, courses):
    available = []

    for course in courses:
        course_id = course["id"]

        if course_id in completed_courses:
            continue

        prerequisites = course["prerequisites"]

        can_take = True

        for prerequisite in prerequisites:
            if prerequisite not in completed_courses:
                can_take = False

        if can_take:
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
        prerequisites = course["prerequisites"]

        can_take = True

        for prerequisite in prerequisites:
            if prerequisite not in completed_courses:
                can_take = False

        if can_take:
            available.append(course_id)

    return available