"""Small command-line smoke test for the course-planning engine."""

import json
from pathlib import Path

from Engine.availability import get_available_courses
from Engine.planning import generate_semester_path, get_course_priority
from Engine.requirements import check_requirements


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "Data" / "processed"


def load_json(path):
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


def main():
    courses = load_json(DATA_DIR / "courses.json")
    requirements = load_json(DATA_DIR / "requirements.json")
    completed_courses = ["15-112", "21-127", "15-122"]

    result = check_requirements(completed_courses, "cs-transfer", requirements)
    available = get_available_courses(completed_courses, courses)
    priorities = get_course_priority(
        completed_courses,
        courses,
        "cs-transfer",
        requirements,
    )
    path = generate_semester_path(
        completed_courses,
        courses,
        "cs-transfer",
        requirements,
        start_semester="spring",
        num_semesters=4,
        max_units=52,
    )

    print("Requirement status:", result)
    print("Available next:", available)
    print("Priorities:", priorities)
    print("Path:", path)


if __name__ == "__main__":
    main()
