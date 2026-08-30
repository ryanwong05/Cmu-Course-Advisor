import json

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from Engine.planning import (
    generate_semester_path,
    get_path_explanation
)


app = FastAPI()


def load_json(path):
    with open(path, "r") as file:
        return json.load(file)


courses = load_json("data/courses.json")
requirements = load_json("data/requirements.json")


class PlanRequest(BaseModel):
    completed_courses: list[str]
    goal: str
    start_semester: str = "spring"
    max_units: int = 24


@app.post("/api/plan")
def create_plan(request: PlanRequest):

    result = generate_semester_path(
        completed_courses=request.completed_courses,
        courses=courses,
        program_id=request.goal,
        requirements=requirements,
        start_semester=request.start_semester,
        num_semesters=4,
        max_units=request.max_units
    )

    explanation = get_path_explanation(
        completed_courses=request.completed_courses,
        courses=courses,
        program_id=request.goal,
        requirements=requirements
    )

    result["explanation"] = explanation

    return result


app.mount(
    "/",
    StaticFiles(directory="static", html=True),
    name="static"
)