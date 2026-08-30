from Engine.availability import get_available_courses

def count_downstream_courses(course_id, courses, remaining_courses):
    total = 0

    for course in courses:
        other_course_id = course["id"]

        if other_course_id not in remaining_courses:
            continue

        if course_id in course["prerequisites"]:
            total += 1

            total += count_downstream_courses(
                other_course_id,
                courses,
                remaining_courses
            )

    return total

def get_course_priority(  
    completed_courses,
    courses,
    program_id,
    requirements
):
    required_courses = requirements[program_id]["required_courses"]

    remaining_courses = [
        course
        for course in required_courses
        if course not in completed_courses
    ]

    available_courses = get_available_courses(
        completed_courses,
        courses
    )

    priority_results = []

    for course_id in available_courses:

        if course_id not in remaining_courses:
            continue

        downstream_count = count_downstream_courses(
            course_id,
            courses,
            remaining_courses
        )

        if downstream_count >= 2:
            priority = "HIGH"
        elif downstream_count == 1:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        priority_results.append({
            "course": course_id,
            "priority": priority,
            "downstream_count": downstream_count
        })

    return priority_results

def semesters_to_finish(
        
    completed_courses,
    courses,
    program_id,
    requirements
):
    required_courses = requirements[program_id]["required_courses"]

    completed = set(completed_courses)
    semesters = 0

    while True:
        remaining = [
            course
            for course in required_courses
            if course not in completed
        ]

        if not remaining:
            return semesters

        available = get_available_courses(
            list(completed),
            courses
        )

        available_required = [
            course
            for course in available
            if course in remaining
        ]

        if not available_required:
            return None

        completed.update(available_required)
        semesters += 1

def calculate_delay_if_skipped(
    course_id,
    completed_courses,
    courses,
    program_id,
    requirements
):
    normal_semesters = semesters_to_finish(
        completed_courses,
        courses,
        program_id,
        requirements
    )

    if normal_semesters is None:
        return None
    
    required_courses = requirements[program_id]["required_courses"]

    available = get_available_courses(
        completed_courses,
        courses
    )

    courses_taken_this_semester = [
        course
        for course in available
        if (
            course in required_courses
            and course != course_id
        )
    ]

    completed_after_skip = (
        completed_courses
        + courses_taken_this_semester
    )

    semesters_after_skip = semesters_to_finish(
        completed_after_skip,
        courses,
        program_id,
        requirements
    )

    if semesters_after_skip is None:
        return None

    total_with_skip = 1 + semesters_after_skip

    return total_with_skip - normal_semesters

def get_course_by_id(course_id, courses):
    for course in courses:
        if course["id"] == course_id:
            return course

    return None

def calculate_total_units(course_ids, courses):
    total = 0

    for course_id in course_ids:
        course = get_course_by_id(course_id, courses)

        if course is not None:
            total += course["units"]

    return total

def build_next_semester_plan(
    completed_courses,
    courses,
    program_id,
    requirements,
    semester,
    max_units
):
    required_courses = requirements[program_id]["required_courses"]

    available = []

    for course in courses:
        course_id = course["id"]

        if course_id in completed_courses:
            continue

        if course_id not in required_courses:
            continue

        if semester not in course["offered"]:
            continue

        prerequisites = course["prerequisites"]

        can_take = True

        for prerequisite in prerequisites:
            if prerequisite not in completed_courses:
                can_take = False

        if can_take:
            available.append(course_id)

    priorities = get_course_priority(
        completed_courses,
        courses,
        program_id,
        requirements
    )

    priority_map = {
        item["course"]: item["downstream_count"]
        for item in priorities
    }

    available.sort(
        key=lambda course_id: priority_map.get(course_id, 0),
        reverse=True
    )

    plan = []
    total_units = 0

    for course_id in available:
        course = get_course_by_id(course_id, courses)

        if course is None:
            continue

        new_total = total_units + course["units"]

        if new_total <= max_units:
            plan.append(course_id)
            total_units = new_total

    return {
        "courses": plan,
        "units": total_units
    }

def get_next_semester_name(current_semester):
    if current_semester == "fall":
        return "spring"
    return "fall"

def get_path_explanation(
    completed_courses,
    courses,
    program_id,
    requirements
):
    required_courses = requirements[program_id]["required_courses"]

    remaining_courses = [
        course_id
        for course_id in required_courses
        if course_id not in completed_courses
    ]

    available_courses = get_available_courses(
        completed_courses,
        courses
    )

    best_course = None
    best_downstream_count = -1

    for course_id in available_courses:

        if course_id not in remaining_courses:
            continue

        downstream_count = count_downstream_courses(
            course_id,
            courses,
            remaining_courses
        )

        if downstream_count > best_downstream_count:
            best_course = course_id
            best_downstream_count = downstream_count

    if best_course is None:
        return None

    unlocks = []

    for course in courses:

        course_id = course["id"]

        if course_id not in remaining_courses:
            continue

        if best_course in course["prerequisites"]:
            unlocks.append(course_id)

    delay = calculate_delay_if_skipped(
        best_course,
        completed_courses,
        courses,
        program_id,
        requirements
    )

    return {
        "critical_course": best_course,
        "downstream_count": best_downstream_count,
        "unlocks": unlocks,
        "delay_if_skipped": delay
    }

def generate_semester_path(
    completed_courses,
    courses,
    program_id,
    requirements,
    start_semester,
    num_semesters=4,
    max_units=24
):
    completed = list(completed_courses)
    path = []

    current_semester = start_semester

    required_courses = requirements[program_id]["required_courses"]

    for semester_number in range(1, num_semesters + 1):

        remaining = [
            course_id
            for course_id in required_courses
            if course_id not in completed
        ]

        if not remaining:
            break

        available = []

        for course in courses:
            course_id = course["id"]

            if course_id in completed:
                continue

            if course_id not in remaining:
                continue

            if current_semester not in course["offered"]:
                continue

            prerequisites = course["prerequisites"]

            can_take = True

            for prerequisite in prerequisites:
                if prerequisite not in completed:
                    can_take = False
                    break

            if can_take:
                available.append(course_id)

        # 给当前 available courses 计算 priority
        scored_courses = []

        for course_id in available:
            downstream_count = count_downstream_courses(
                course_id,
                courses,
                remaining
            )

            scored_courses.append({
                "course": course_id,
                "score": downstream_count
            })

        # downstream 越多，越优先
        scored_courses.sort(
            key=lambda item: item["score"],
            reverse=True
        )

        semester_courses = []
        semester_units = 0

        for item in scored_courses:
            course_id = item["course"]

            course = get_course_by_id(
                course_id,
                courses
            )

            if course is None:
                continue

            new_total = semester_units + course["units"]

            if new_total <= max_units:
                semester_courses.append(course_id)
                semester_units = new_total

        path.append({
            "semester_number": semester_number,
            "semester": current_semester,
            "courses": semester_courses,
            "units": semester_units
        })

        completed.extend(semester_courses)

        current_semester = get_next_semester_name(
            current_semester
        )

    remaining_after_plan = [
        course_id
        for course_id in required_courses
        if course_id not in completed
    ]

    return {
        "path": path,
        "remaining": remaining_after_plan,
        "goal_complete": len(remaining_after_plan) == 0
    }