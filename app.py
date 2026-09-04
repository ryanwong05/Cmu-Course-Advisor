import json
from pathlib import Path
from typing import Literal, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from Engine.planning import (
    generate_multiple_paths,
    get_path_explanation
)
from Engine.workload import calculate_semester_load
from Engine.baseline import (
    get_requirements_through_year,
    get_student_planning_baseline,
)


app = FastAPI()
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "Data"
STATIC_DIR = PROJECT_ROOT / "static"


def load_json(path):
    with open(path, "r") as file:
        return json.load(file)


courses = load_json(DATA_DIR / "courses.json")
requirements = load_json(DATA_DIR / "requirements.json")
course_metrics = load_json(DATA_DIR / "course_metrics.json")
programs = load_json(DATA_DIR / "programs.json")
program_profiles = load_json(DATA_DIR / "program_profiles.json")


def current_major_courses_for(student: "StudentState"):
    if student.primary_major == "stats-ml":
        # Verified subset only. The remaining Stats/ML curriculum is not yet
        # configured, so these must not be presented as the complete major.
        return ["21-120", "21-127", "15-112", "15-122"]
    return []


@app.middleware("http")
async def disable_dev_cache(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


class StudentState(BaseModel):
    college: str
    primary_major: str
    year: int
    enrollment_status: Literal["precollege", "enrolled"] = "enrolled"
    current_term: Literal["fall", "spring"] = "fall"
    completed_courses: list[str] = Field(default_factory=list)
    completed_requirement_ids: list[str] = Field(default_factory=list)


class PlanningGoal(BaseModel):
    type: Literal["current_major", "internal_transfer", "additional_major", "minor"]
    program: str
    college: str | None = None


class PlanningConstraints(BaseModel):
    start_semester: Literal["spring", "fall"] = "spring"
    max_units: int = 52
    first_semester_max_units: int = 52
    semester_unit_limits: list[int | None] = Field(default_factory=list)
    planning_year: int = 1


class PlanningRequest(BaseModel):
    student: StudentState
    goals: list[PlanningGoal]
    constraints: PlanningConstraints = Field(default_factory=PlanningConstraints)


class ComparisonRequest(BaseModel):
    student: StudentState
    programs: list[str] = Field(default_factory=list)
    goal_types: list[Literal["internal_transfer", "additional_major", "minor"]] = Field(
        default_factory=lambda: ["additional_major", "minor"]
    )


class LegacyPlanRequest(BaseModel):
    completed_courses: list[str]
    goal: str
    start_semester: Literal["spring", "fall"] = "spring"
    max_units: int = 52


# Kept as an import-compatible name for older Python callers.
PlanRequest = LegacyPlanRequest


def planner_key_for_goal(goal: PlanningGoal):
    legacy_keys = {
        ("current_major", "stats-ml"): "stats-ml-major",
        ("internal_transfer", "computer-science"): "cs-transfer",
        ("additional_major", "robotics"): "robotics-additional-major",
    }
    legacy_key = legacy_keys.get((goal.type, goal.program))
    if legacy_key:
        return legacy_key
    if goal.type == "current_major":
        return f"{goal.program}-major"
    suffixes = {
        "internal_transfer": "transfer",
        "additional_major": "additional-major",
        "minor": "minor",
    }
    suffix = suffixes.get(goal.type)
    return f"{goal.program}-{suffix}" if suffix else None


def planning_context(request: Union[PlanningRequest, LegacyPlanRequest]):
    if isinstance(request, LegacyPlanRequest):
        return (
            request.goal,
            request.completed_courses,
            request.start_semester,
            request.max_units,
        )

    if not request.goals:
        raise HTTPException(status_code=422, detail="At least one goal is required")

    goal_key = planner_key_for_goal(request.goals[0])
    if goal_key is None:
        raise HTTPException(status_code=404, detail="Unknown planning goal")

    return (
        goal_key,
        request.student.completed_courses,
        request.constraints.start_semester,
        request.constraints.max_units,
    )


@app.get("/api/programs")
def list_programs():
    return programs


@app.get("/api/programs/{program_id}/{goal_type}")
def get_program_profile(program_id: str, goal_type: str):
    profile = program_profiles["programs"].get(program_id, {}).get(goal_type)
    if profile is None:
        raise HTTPException(status_code=404, detail="Unknown program path")
    course_names = {course["id"]: course["name"] for course in courses}
    return {
        "program_id": program_id,
        "program_name": next(
            (item["name"] for item in programs if item["id"] == program_id),
            program_id,
        ),
        "goal_type": goal_type,
        "catalog_year": program_profiles["catalog_year"],
        "profile": profile,
        "fixed_courses": [
            {"id": course_id, "name": course_names.get(course_id, "Catalog requirement")}
            for course_id in profile.get("required_course_ids", [])
        ],
    }


@app.post("/api/program-comparison")
def compare_programs(request: ComparisonRequest):
    selected = request.programs or [program["id"] for program in programs]
    names = {program["id"]: program["name"] for program in programs}
    current_major_courses = set(current_major_courses_for(request.student))
    completed_courses = set(request.student.completed_courses)
    course_units = {course["id"]: course["units"] for course in courses}
    comparisons = []

    for program_id in selected:
        profile_by_type = program_profiles["programs"].get(program_id)
        if profile_by_type is None:
            continue
        for goal_type in request.goal_types:
            profile = profile_by_type.get(goal_type)
            if profile is None:
                continue
            explicit = set(profile.get("required_course_ids", []))
            completed_matches = explicit & completed_courses
            potential_overlap = explicit & current_major_courses
            completed_units = sum(course_units.get(item, 0) for item in completed_matches)
            overlap_units = sum(course_units.get(item, 0) for item in potential_overlap)
            comparisons.append({
                "program": program_id,
                "program_name": names.get(program_id, program_id),
                "goal_type": goal_type,
                "minimum_courses": profile["minimum_courses"],
                "minimum_units": profile["minimum_units"],
                "remaining_minimum_units": max(0, profile["minimum_units"] - completed_units),
                "potential_overlap_courses": sorted(potential_overlap),
                "potential_overlap_units": overlap_units,
                "double_count_limit": profile.get("double_count_limit"),
                "minimum_unique_courses": profile.get("minimum_unique_courses"),
                "choice_slots": profile.get("choice_slots", 0),
                "eligibility": profile["eligibility"],
                "estimate_status": "catalog_minimum",
            })

    return {
        "catalog_year": program_profiles["catalog_year"],
        "current_major_scope": "verified_subset",
        "comparisons": comparisons,
        "notes": program_profiles["notes"],
    }


@app.post("/api/baseline")
def create_baseline(request: PlanningRequest):
    if not request.goals:
        raise HTTPException(status_code=422, detail="At least one goal is required")

    goal = request.goals[0]
    planner_key = planner_key_for_goal(goal)
    planner_status = "not_configured"
    if planner_key in requirements:
        planner_status = requirements[planner_key].get(
            "planner_status", "not_configured"
        )

    return {
        "student": request.student.model_dump(),
        "goal": goal.model_dump(),
        "baseline": get_student_planning_baseline(
            request.student.model_dump(),
            through_year=2,
        ),
        "planner_key": planner_key,
        "planner_status": planner_status,
    }

def attach_workload_to_path(path_result):
    for semester in path_result["path"]:

        workload = calculate_semester_load(
            semester["courses"],
            course_metrics
        )

        semester["workload"] = workload

    return path_result

@app.post("/api/plan")
def create_plan(request: Union[PlanningRequest, LegacyPlanRequest]):
    goal_key, completed_courses, start_semester, max_units = planning_context(request)

    if goal_key not in requirements:
        raise HTTPException(status_code=404, detail="Unknown planning goal")

    goal_requirements = requirements[goal_key]
    if goal_requirements.get("planner_status") != "ready":
        raise HTTPException(
            status_code=409,
            detail="Requirements exist, but this planner is not configured yet",
        )

    if not goal_requirements.get("required_courses"):
        raise HTTPException(
            status_code=409,
            detail="This goal has no configured planner requirements",
        )

    if max_units < 1:
        raise HTTPException(status_code=422, detail="max_units must be positive")

    current_major_courses = (
        current_major_courses_for(request.student)
        if isinstance(request, PlanningRequest)
        else []
    )
    result = generate_multiple_paths(
        completed_courses=completed_courses,
        courses=courses,
        program_id=goal_key,
        requirements=requirements,
        start_semester=start_semester,
        max_units=max_units,
        baseline_requirements=(
            get_student_planning_baseline(
                request.student.model_dump(),
                through_year=2,
            )["requirements"]
            if isinstance(request, PlanningRequest)
            else []
        ),
        first_semester_max_units=(
            request.constraints.first_semester_max_units
            if (
                isinstance(request, PlanningRequest)
                and request.student.enrollment_status == "precollege"
            )
            else max_units
        ),
        semester_unit_limits=(
            request.constraints.semester_unit_limits
            if isinstance(request, PlanningRequest)
            else []
        ),
        student_year=(request.student.year if isinstance(request, PlanningRequest) else 1),
        planning_year=(
            request.constraints.planning_year
            if isinstance(request, PlanningRequest)
            else 1
        ),
        current_major_courses=current_major_courses,
        course_metrics=course_metrics,
    )
    result["fastest"] = attach_workload_to_path(
        result["fastest"]
            )

    result["lower_workload"] = attach_workload_to_path(
        result["lower_workload"]
        )

    explanation = get_path_explanation(
        completed_courses=completed_courses,
        courses=courses,
        program_id=goal_key,
        requirements=requirements
    )

    shared_course_ids = [
        course_id
        for course_id in goal_requirements["required_courses"]
        if course_id in current_major_courses
    ]
    return {
        "fastest": result["fastest"],
        "lower_workload": result["lower_workload"],
        "explanation": explanation,
        "overlap_summary": {
            "courses": shared_course_ids,
            "units": sum(
                course["units"]
                for course in courses
                if course["id"] in shared_course_ids
            ),
            "current_major_scope": "verified_subset",
        },
    }


@app.get("/api/baseline")
def get_baseline(
    college: str,
    through_year: int,
    completed_courses: str = "",
):
    completed = [
        course.strip()
        for course in completed_courses.split(",")
        if course.strip()
    ]

    requirements = get_requirements_through_year(
        college,
        through_year,
        completed,
    )

    return {
        "college": college,
        "through_year": through_year,
        "requirements": requirements,
    }

app.mount(
    "/",
    StaticFiles(directory=STATIC_DIR, html=True),
    name="static"
)
