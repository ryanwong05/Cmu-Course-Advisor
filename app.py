import json

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from Engine.planning import (
    generate_multiple_paths,
    get_path_explanation
)
from Engine.workload import calculate_semester_load


app = FastAPI()


def load_json(path):
    with open(path, "r") as file:
        return json.load(file)


courses = load_json("data/courses.json")
requirements = load_json("data/requirements.json")
course_metrics = load_json("data/course_metrics.json")


class PlanRequest(BaseModel):
    completed_courses: list[str]
    goal: str
    start_semester: str = "spring"
    max_units: int = 24

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

    result = generate_multiple_paths(
    completed_courses=request.completed_courses,
    courses=courses,
    program_id=request.goal,
    requirements=requirements,
    start_semester=request.start_semester
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
    StaticFiles(directory="static", html=True),
    name="static"
)