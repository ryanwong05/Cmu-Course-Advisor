import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from Engine.planning import (
    generate_multiple_paths,
    get_path_explanation
)
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


class PlanRequest(BaseModel):
    completed_courses: list[str]
    goal: str
    start_semester: Literal["spring", "fall"] = "spring"
    max_units: int = 24


@app.get("/api/programs")
def list_programs():
    return programs

def attach_workload_to_path(path_result):
    for semester in path_result["path"]:

        workload = calculate_semester_load(
            semester["courses"],
            course_metrics
        )

        semester["workload"] = workload

    return path_result

@app.post("/api/plan")
def create_plan(request: PlanRequest):
    if request.goal not in requirements:
        raise HTTPException(status_code=404, detail="Unknown planning goal")

    goal_requirements = requirements[request.goal]
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

    if request.max_units < 1:
        raise HTTPException(status_code=422, detail="max_units must be positive")

    result = generate_multiple_paths(
        completed_courses=request.completed_courses,
        courses=courses,
        program_id=request.goal,
        requirements=requirements,
        start_semester=request.start_semester,
        max_units=request.max_units,
    )
    result["fastest"] = attach_workload_to_path(
        result["fastest"]
            )

    result["lower_workload"] = attach_workload_to_path(
        result["lower_workload"]
        )

    explanation = get_path_explanation(
        completed_courses=request.completed_courses,
        courses=courses,
        program_id=request.goal,
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
