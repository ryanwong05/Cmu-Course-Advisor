import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

COLLEGE_REQUIREMENTS_PATH = (
    PROJECT_ROOT
    / "Data"
    / "scraped_college_requirements.json"
)


def load_college_requirements():
    with open(
        COLLEGE_REQUIREMENTS_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)

def get_college_by_id(college_id):
    colleges = load_college_requirements()

    for college in colleges:
        if college["id"] == college_id:
            return college

    return None

def get_due_requirements(
    college_id,
    current_year,
):
    college = get_college_by_id(college_id)

    if college is None:
        return []

    due_requirements = []

    for requirement in college["requirements"]:
        timeline = requirement.get("timeline", {})

        if timeline.get("type") != "complete_by":
            continue

        deadline_year = timeline.get("year")

        if (
            deadline_year is not None
            and deadline_year <= current_year
        ):
            due_requirements.append(requirement)

    return due_requirements

def is_requirement_satisfied(requirement, completed_courses):
    courses = requirement.get("courses", [])

    if not courses:
        return False

    return any(
        course in completed_courses
        for course in courses
    )

def get_unsatisfied_due_requirements(
    college_id,
    current_year,
    completed_courses,
):
    due_requirements = get_due_requirements(
        college_id,
        current_year,
    )

    return [
        requirement
        for requirement in due_requirements
        if not is_requirement_satisfied(
            requirement,
            completed_courses,
        )
    ]

def calculate_baseline_units(
    college_id,
    current_year,
    completed_courses,
):
    requirements = get_unsatisfied_due_requirements(
        college_id,
        current_year,
        completed_courses,
    )

    total_units = sum(
        requirement.get("units", 0)
        for requirement in requirements
    )

    return {
        "requirements": requirements,
        "total_units": total_units,
    }

def calculate_goal_capacity(
    max_units,
    college_id,
    current_year,
    completed_courses,
):
    baseline = calculate_baseline_units(
        college_id,
        current_year,
        completed_courses,
    )

    baseline_units = baseline["total_units"]

    available_units = max(
        0,
        max_units - baseline_units,
    )

    return {
        "max_units": max_units,
        "baseline_units": baseline_units,
        "available_goal_units": available_units,
        "baseline_requirements": baseline["requirements"],
    }

def get_student_baseline(student_state):
    college_id = student_state["college"]
    current_year = student_state["year"]
    completed_courses = student_state["completed_courses"]

    requirements = get_unsatisfied_due_requirements(
        college_id,
        current_year,
        completed_courses,
    )

    total_units = sum(
        requirement.get("units", 0)
        for requirement in requirements
    )

    return {
        "college": college_id,
        "requirements": requirements,
        "total_units": total_units,
    }