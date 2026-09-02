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
from Engine.baseline import get_student_baseline
from Engine.workload import calculate_semester_load


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


@app.middleware("http")
async def disable_dev_cache(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


class StudentState(BaseModel):
    college: str
    primary_major: str
    year: int
    completed_courses: list[str] = Field(default_factory=list)


class PlanningGoal(BaseModel):
    type: Literal["current_major", "internal_transfer", "additional_major"]
    program: str
    college: str | None = None


class PlanningConstraints(BaseModel):
    start_semester: Literal["spring", "fall"] = "spring"
    max_units: int = 24


class PlanningRequest(BaseModel):
    student: StudentState
    goals: list[PlanningGoal]
    constraints: PlanningConstraints = Field(default_factory=PlanningConstraints)


class LegacyPlanRequest(BaseModel):
    completed_courses: list[str]
    goal: str
    start_semester: Literal["spring", "fall"] = "spring"
    max_units: int = 24


# Kept as an import-compatible name for older Python callers.
PlanRequest = LegacyPlanRequest


def planner_key_for_goal(goal: PlanningGoal):
    key_by_goal = {
        ("current_major", "stats-ml"): "stats-ml-major",
        ("internal_transfer", "computer-science"): "cs-transfer",
        ("internal_transfer", "robotics"): "robotics-transfer",
        ("additional_major", "robotics"): "robotics-additional-major",
    }
    return key_by_goal.get((goal.type, goal.program))


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
        "baseline": get_student_baseline(request.student.model_dump()),
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

    result = generate_multiple_paths(
        completed_courses=completed_courses,
        courses=courses,
        program_id=goal_key,
        requirements=requirements,
        start_semester=start_semester,
        max_units=max_units,
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

    return {
        "fastest": result["fastest"],
        "lower_workload": result["lower_workload"],
        "explanation": explanation
    }


app.mount(
    "/",
    StaticFiles(directory=STATIC_DIR, html=True),
    name="static"
)
