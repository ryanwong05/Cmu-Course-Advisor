import json


# def load_json(path):
#     with open(path, "r") as file:
#         return json.load(file)


# requirements = load_json("data/requirements.json")


# def check_requirements(completed_courses, program_id):
#     required_courses = requirements[program_id]["required_courses"]

#     completed = []
#     remaining = []

#     for course in required_courses:
#         if course in completed_courses:
#             completed.append(course)
#         else:
#             remaining.append(course)

#     progress = len(completed) / len(required_courses)

#     return {
#         "completed": completed,
#         "remaining": remaining,
#         "progress": progress
#     }

# courses = load_json("data/courses.json")

# student_courses = [
#     "15-112",
#     "21-127",
#     "15-122"
# ]

# result = check_requirements(
#     student_courses,
#     "cs-transfer"
# )

# def get_available_courses(completed_courses, courses):
#     available = []

#     for course in courses:
#         course_id = course["id"]

#         if course_id in completed_courses:
#             continue

#         prerequisites = course["prerequisites"]

#         can_take = True

#         for prerequisite in prerequisites:
#             if prerequisite not in completed_courses:
#                 can_take = False

#         if can_take:
#             available.append(course_id)

#     return available

# available = get_available_courses(student_courses, courses)

# def get_course_priority(completed_courses, courses, program_id):
#     required_courses = requirements[program_id]["required_courses"]

#     remaining_courses = [
#         course
#         for course in required_courses
#         if course not in completed_courses
#     ]

#     available_courses = get_available_courses(
#         completed_courses,
#         courses
#     )

#     priority_results = []

#     for course_id in available_courses:

#         if course_id not in remaining_courses:
#             continue

#         downstream_count = count_downstream_courses(
#             course_id,
#             courses,
#             remaining_courses
#         )

#         if downstream_count >= 2:
#             priority = "HIGH"
#         elif downstream_count == 1:
#             priority = "MEDIUM"
#         else:
#             priority = "LOW"

#         priority_results.append({
#             "course": course_id,
#             "priority": priority,
#             "downstream_count": downstream_count
#         })

#     return priority_results

# def count_downstream_courses(course_id, courses, remaining_courses):
#     total = 0

#     for course in courses:
#         other_course_id = course["id"]

#         if other_course_id not in remaining_courses:
#             continue

#         if course_id in course["prerequisites"]:
#             total += 1

#             total += count_downstream_courses(
#                 other_course_id,
#                 courses,
#                 remaining_courses
#             )

#     return total

# priorities = get_course_priority(
#     student_courses,
#     courses,
#     "cs-transfer"
# )

# print("\nCourse Priority:")

# for item in priorities:
#     print(
#         item["course"],
#         "->",
#         item["priority"],
#         "| Downstream courses:",
#         item["downstream_count"]
#     )
    

# print("Available next:", available)
# print("Completed:", result["completed"])
# print("Remaining:", result["remaining"])
# print("Progress:", round(result["progress"] * 100), "%")



import json

from Engine.requirements import check_requirements
from Engine.availability import get_available_courses
from Engine.planning import (
    get_course_priority,
    calculate_delay_if_skipped,
    build_next_semester_plan,
    generate_semester_path
)


def load_json(path):
    with open(path, "r") as file:
        return json.load(file)


courses = load_json("data/courses.json")
requirements = load_json("data/requirements.json")

student_courses = [
    "15-112",
    "21-127",
    "15-122"
]


result = check_requirements(
    student_courses,
    "cs-transfer",
    requirements
)

print("Completed:", result["completed"])
print("Remaining:", result["remaining"])
print("Progress:", round(result["progress"] * 100), "%")


available = get_available_courses(
    student_courses,
    courses
)

print("Available next:", available)


priorities = get_course_priority(
    student_courses,
    courses,
    "cs-transfer",
    requirements
)

print("\nCourse Priority:")

for item in priorities:
    print(
        item["course"],
        "->",
        item["priority"],
        "| Downstream:",
        item["downstream_count"]
    )


print("\nDelay Analysis:")

for course_id in available:
    if course_id not in requirements["cs-transfer"]["required_courses"]:
        continue

    delay = calculate_delay_if_skipped(
        course_id,
        student_courses,
        courses,
        "cs-transfer",
        requirements
    )

    print(
        course_id,
        "-> delay:",
        delay,
        "semester(s)"
    )

from Engine.planning import (
    get_course_priority,
    calculate_delay_if_skipped,
    build_next_semester_plan
)

next_plan = build_next_semester_plan(
    student_courses,
    courses,
    "cs-transfer",
    requirements,
    "spring",
    24
)

print("\nRecommended Next Semester:")
print("Courses:", next_plan["courses"])
print("Units:", next_plan["units"])

four_semester_plan = generate_semester_path(
    student_courses,
    courses,
    "cs-transfer",
    requirements,
    start_semester="spring",
    num_semesters=4,
    max_units=12
)

print("\n4-Semester Path:")

for semester in four_semester_plan["path"]:
    print(
        f'Semester {semester["semester_number"]} '
        f'({semester["semester"]})'
    )

    print("Courses:", semester["courses"])
    print("Units:", semester["units"])
    print()

print("Goal complete:", four_semester_plan["goal_complete"])
print("Remaining:", four_semester_plan["remaining"])