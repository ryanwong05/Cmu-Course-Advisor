from Engine.availability import (
    get_available_courses,
    prerequisite_course_ids,
    prerequisites_satisfied,
)

def count_downstream_courses(
    course_id,
    courses,
    remaining_courses,
    visited=None
):
    visited = set() if visited is None else set(visited)
    if course_id in visited:
        return 0
    visited.add(course_id)

    total = 0

    for course in courses:
        other_course_id = course["id"]

        if other_course_id not in remaining_courses:
            continue

        if course_id in prerequisite_course_ids(course):
            total += 1

            total += count_downstream_courses(
                other_course_id,
                courses,
                remaining_courses,
                visited
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

        if prerequisites_satisfied(course, completed_courses):
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

        if best_course in prerequisite_course_ids(course):
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
    max_units=52,
    baseline_requirements=None,
    first_semester_max_units=52,
    semester_unit_limits=None,
    student_year=1,
    goal_max_units=None,
    planning_year=None,
    current_major_courses=None,
    course_metrics=None,
    max_high_intensity_courses=2,
    program_requirement_slots=None,
    required_course_tiers=None,
):
    completed = list(completed_courses)
    path = []

    current_semester = start_semester

    goal_required_courses = requirements[program_id]["required_courses"]
    current_major_courses = current_major_courses or []
    course_metrics = course_metrics or {}
    required_course_tiers = required_course_tiers or {}
    required_courses = list(dict.fromkeys(
        goal_required_courses + current_major_courses
    ))
    remaining_baseline = [
        dict(requirement)
        for requirement in (baseline_requirements or [])
        if requirement.get("status") != "completed"
    ]
    remaining_program_slots = [
        dict(requirement)
        for requirement in (program_requirement_slots or [])
        if requirement.get("status") != "completed"
    ]
    semester_unit_limits = semester_unit_limits or []

    def unit_limit_for(semester_index):
        if semester_index < len(semester_unit_limits):
            return semester_unit_limits[semester_index]
        if semester_index == 0:
            return first_semester_max_units
        return max_units

    def baseline_deadline(requirement):
        timeline = requirement.get("timeline", {})
        if timeline.get("type") != "complete_by":
            return None
        path_start_year = planning_year or student_year
        current_absolute_semester = (path_start_year - 1) * 2 + (
            2 if start_semester == "spring" else 1
        )
        deadline_absolute_semester = timeline.get("year", student_year) * 2
        return max(1, deadline_absolute_semester - current_absolute_semester + 1)

    for semester_number in range(1, num_semesters + 1):

        path_start_year = planning_year or student_year
        academic_year = path_start_year + (
            (semester_number - 1 + (1 if start_semester == "spring" else 0)) // 2
        )

        remaining = [
            course_id
            for course_id in required_courses
            if course_id not in completed
        ]

        if not remaining and not remaining_baseline and not remaining_program_slots:
            break

        semester_limit = unit_limit_for(semester_number - 1)
        baseline_slots = []
        baseline_units = 0
        eligible_baseline = []
        for requirement in remaining_baseline:
            timeline = requirement.get("timeline", {})
            minimum_semester = 1
            if timeline.get("type") == "after_semester":
                minimum_semester = timeline.get("semester", 1) + 1
            if semester_number >= minimum_semester:
                eligible_baseline.append(requirement)

        eligible_baseline.sort(
            key=lambda requirement: (
                baseline_deadline(requirement) is None,
                baseline_deadline(requirement) or num_semesters + 1,
            )
        )
        deadline_groups = {}
        for requirement in eligible_baseline:
            deadline_groups.setdefault(
                baseline_deadline(requirement), []
            ).append(requirement)

        selected_baseline_ids = set()
        dated_deadlines = [
            deadline for deadline in deadline_groups
            if deadline is not None
        ]
        active_deadline = min(dated_deadlines) if dated_deadlines else None
        for deadline, group in deadline_groups.items():
            if deadline is None or deadline != active_deadline:
                continue
            semesters_left = max(1, deadline - semester_number + 1)
            slots_now = max(1, (len(group) + semesters_left - 1) // semesters_left)
            selected_baseline_ids.update(
                requirement["id"] for requirement in group[:slots_now]
            )

        no_deadline = deadline_groups.get(None, [])
        if no_deadline and semester_number > 1:
            selected_baseline_ids.add(no_deadline[0]["id"])

        for requirement in eligible_baseline:
            if requirement["id"] not in selected_baseline_ids:
                continue
            units = requirement.get("units", 0)
            if (
                len(baseline_slots) < 5
                and (semester_limit is None or baseline_units + units <= semester_limit)
            ):
                baseline_slots.append(requirement)
                baseline_units += units

        available = []

        for course in courses:
            course_id = course["id"]

            if course_id in completed:
                continue

            if course_id not in remaining:
                continue

            if current_semester not in course["offered"]:
                continue

            if academic_year < course.get("minimum_year", 1):
                continue

            if prerequisites_satisfied(course, completed):
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
        high_intensity_count = 0

        for item in scored_courses:
            course_id = item["course"]

            course = get_course_by_id(
                course_id,
                courses
            )

            if course is None:
                continue

            new_total = semester_units + course["units"]
            is_high_intensity = (
                course_metrics.get(course_id, {}).get("intensity")
                == "high_intensity"
            )

            total_with_baseline = baseline_units + new_total
            within_goal_limit = (
                goal_max_units is None
                or new_total <= goal_max_units
            )
            within_total_limit = (
                semester_limit is None
                or total_with_baseline <= semester_limit
            )
            within_intensity_limit = (
                not is_high_intensity
                or high_intensity_count < max_high_intensity_courses
            )
            if (
                within_goal_limit
                and within_total_limit
                and within_intensity_limit
                and len(baseline_slots) + len(semester_courses) < 5
            ):
                semester_courses.append(course_id)
                semester_units = new_total
                if is_high_intensity:
                    high_intensity_count += 1

        program_slots = []
        program_slot_units = 0
        max_slots_now = 1 if goal_max_units is not None else 2
        for requirement in remaining_program_slots:
            if len(program_slots) >= max_slots_now:
                break
            if len(baseline_slots) + len(semester_courses) + len(program_slots) >= 5:
                break
            units = requirement.get("units", 0)
            total_with_slot = (
                baseline_units + semester_units + program_slot_units + units
            )
            within_total_limit = (
                semester_limit is None or total_with_slot <= semester_limit
            )
            within_goal_limit = (
                goal_max_units is None
                or semester_units + program_slot_units + units <= goal_max_units
            )
            if within_total_limit and within_goal_limit:
                program_slots.append(requirement)
                program_slot_units += units

        semester_shared_courses = [
            course_id for course_id in semester_courses
            if course_id in goal_required_courses
            and course_id in current_major_courses
        ]
        semester_goal_courses = [
            course_id for course_id in semester_courses
            if course_id in goal_required_courses
            and course_id not in semester_shared_courses
        ]
        semester_current_major_courses = [
            course_id for course_id in semester_courses
            if course_id in current_major_courses
            and course_id not in goal_required_courses
        ]
        goal_units = calculate_total_units(semester_goal_courses, courses)
        current_major_units = calculate_total_units(
            semester_current_major_courses,
            courses,
        )
        shared_units = calculate_total_units(semester_shared_courses, courses)
        course_by_id = {course["id"]: course for course in courses}
        course_blocks = []
        for course_id in semester_courses:
            if course_id in semester_shared_courses:
                kind = "shared"
            elif course_id in semester_current_major_courses:
                kind = "current_major"
            else:
                kind = "goal"
            course_blocks.append({
                "id": course_id,
                "name": course_by_id[course_id].get("name", course_id),
                "units": course_by_id[course_id]["units"],
                "kind": kind,
                "locked": True,
                "program_tier": required_course_tiers.get(course_id),
            })
        course_blocks.extend({
            "id": requirement["id"],
            "name": requirement["name"],
            "units": requirement.get("units", 0),
            "kind": "baseline",
            "locked": False,
            "options": requirement.get("courses", []),
        } for requirement in baseline_slots)
        course_blocks.extend({
            "id": requirement["id"],
            "name": requirement["name"],
            "units": requirement.get("units", 0),
            "kind": "program_choice",
            "locked": False,
            "options": requirement.get("options", []),
            "program_tier": requirement.get("program_tier"),
        } for requirement in program_slots)

        path.append({
            "semester_number": semester_number,
            "semester": current_semester,
            "academic_year": academic_year,
            "academic_year_name": [
                "Freshman", "Sophomore", "Junior", "Senior"
            ][min(max(academic_year, 1), 4) - 1],
            "course_blocks": course_blocks,
            "courses": semester_courses,
            "goal_courses": semester_goal_courses,
            "current_major_courses": semester_current_major_courses,
            "shared_courses": semester_shared_courses,
            "units": semester_units,
            "goal_units": goal_units,
            "current_major_units": current_major_units,
            "shared_units": shared_units,
            "baseline_requirements": baseline_slots,
            "baseline_units": baseline_units,
            "program_requirements": program_slots,
            "program_requirement_units": program_slot_units,
            "total_units": (
                goal_units + current_major_units + shared_units
                + baseline_units + program_slot_units
            ),
            "high_intensity_count": high_intensity_count,
            "unit_limit": semester_limit,
            "free_choice_units": (
                None if semester_limit is None
                else max(
                    0,
                    semester_limit - semester_units
                    - baseline_units - program_slot_units,
                )
            ),
            "elective_guidance": (
                "No planner hard limit; add electives with advisor approval."
                if semester_limit is None
                else "Available for math, GenEd options, or other electives."
            ),
        })

        completed.extend(semester_courses)
        scheduled_ids = {item["id"] for item in baseline_slots}
        remaining_baseline = [
            item for item in remaining_baseline
            if item["id"] not in scheduled_ids
        ]
        scheduled_program_ids = {item["id"] for item in program_slots}
        remaining_program_slots = [
            item for item in remaining_program_slots
            if item["id"] not in scheduled_program_ids
        ]

        current_semester = get_next_semester_name(
            current_semester
        )

    remaining_after_plan = [
        course_id
        for course_id in goal_required_courses
        if course_id not in completed
    ]
    remaining_current_major = [
        course_id
        for course_id in current_major_courses
        if course_id not in completed
    ]

    return {
        "path": path,
        "remaining": remaining_after_plan,
        "remaining_current_major": remaining_current_major,
        "remaining_baseline": remaining_baseline,
        "remaining_program_requirements": remaining_program_slots,
        "goal_complete": (
            len(remaining_after_plan) == 0
            and len(remaining_program_slots) == 0
        ),
        "baseline_complete": len(remaining_baseline) == 0,
    }

def generate_multiple_paths(
    completed_courses,
    courses,
    program_id,
    requirements,
    start_semester,
    max_units=52,
    baseline_requirements=None,
    first_semester_max_units=52,
    semester_unit_limits=None,
    student_year=1,
    planning_year=None,
    current_major_courses=None,
    course_metrics=None,
    max_high_intensity_courses=2,
    program_requirement_slots=None,
    required_course_tiers=None,
):
    fastest = generate_semester_path(
        completed_courses=completed_courses,
        courses=courses,
        program_id=program_id,
        requirements=requirements,
        start_semester=start_semester,
        num_semesters=4,
        max_units=max_units,
        baseline_requirements=baseline_requirements,
        first_semester_max_units=first_semester_max_units,
        semester_unit_limits=semester_unit_limits,
        student_year=student_year,
        goal_max_units=None,
        planning_year=planning_year,
        current_major_courses=current_major_courses,
        course_metrics=course_metrics,
        max_high_intensity_courses=max_high_intensity_courses,
        program_requirement_slots=program_requirement_slots,
        required_course_tiers=required_course_tiers,
    )

    lower_workload = generate_semester_path(
        completed_courses=completed_courses,
        courses=courses,
        program_id=program_id,
        requirements=requirements,
        start_semester=start_semester,
        num_semesters=6,
        max_units=max_units,
        baseline_requirements=baseline_requirements,
        first_semester_max_units=first_semester_max_units,
        semester_unit_limits=semester_unit_limits,
        student_year=student_year,
        goal_max_units=12,
        planning_year=planning_year,
        current_major_courses=current_major_courses,
        course_metrics=course_metrics,
        max_high_intensity_courses=max_high_intensity_courses,
        program_requirement_slots=program_requirement_slots,
        required_course_tiers=required_course_tiers,
    )

    return {
        "fastest": fastest,
        "lower_workload": lower_workload
    }
