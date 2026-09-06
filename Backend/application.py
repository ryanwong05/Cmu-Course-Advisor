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


app = FastAPI(
    title="CMU Path API",
    description="Course-planning API and frontend host for CMU Path.",
)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "Data" / "processed"
STATIC_DIR = PROJECT_ROOT / "static"


def load_json(path: Path):
    """Load one generated application dataset from Data/processed."""
    with path.open(encoding="utf-8") as file:
        return json.load(file)


courses = load_json(DATA_DIR / "courses.json")
requirements = load_json(DATA_DIR / "requirements.json")
course_metrics = load_json(DATA_DIR / "course_metrics.json")
programs = load_json(DATA_DIR / "programs.json")
program_profiles = load_json(DATA_DIR / "program_profiles.json")
advanced_credit = load_json(DATA_DIR / "advanced_credit.json")


# Completing a later course in a strict sequence is evidence that the earlier
# course requirement has already been met, whether by CMU coursework,
# transfer/advanced credit, or an approved placement decision.  Keep this
# deliberately small and evidence-based; it is not a general "guess credits"
# system.
COURSE_COMPLETION_IMPLICATIONS = {
    "21-122": ["21-120"],
    "15-122": ["15-112"],
    "15-210": ["15-150", "21-127"],
    "15-213": ["15-122"],
    "15-251": ["15-150", "21-127"],
}


def expand_completed_courses(course_ids: list[str]) -> list[str]:
    """Return a stable, de-duplicated prerequisite completion closure."""
    completed = list(dict.fromkeys(course_ids))
    index = 0
    while index < len(completed):
        for implied_id in COURSE_COMPLETION_IMPLICATIONS.get(completed[index], []):
            if implied_id not in completed:
                completed.append(implied_id)
        index += 1
    return completed


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


def profile_for_goal(goal: PlanningGoal):
    if goal.type not in {"additional_major", "minor"}:
        return None
    return program_profiles["programs"].get(goal.program, {}).get(goal.type)


def planning_inputs_for_profile(goal: PlanningGoal, completed_courses: list[str]):
    profile = profile_for_goal(goal)
    if profile is None:
        return None

    supported_ids = {course["id"] for course in courses}
    course_units = {course["id"]: course["units"] for course in courses}
    minor_profile = (
        program_profiles["programs"].get(goal.program, {}).get("minor")
        if goal.type == "additional_major" else profile
    )
    minor_fixed_ids = (minor_profile or {}).get("required_course_ids", [])
    minor_option_ids = {
        option
        for group in (minor_profile or {}).get("requirement_groups", [])
        for option in group.get("options", [])
        if " + " not in option and "xxx" not in option.lower()
    }
    fixed_ids = list(dict.fromkeys(
        minor_fixed_ids + (
            profile.get("required_course_ids", [])
            if goal.type == "additional_major" else []
        )
    ))
    course_tiers = {
        course_id: (
            "minor_foundation"
            if course_id in minor_fixed_ids or course_id in minor_option_ids
            else (
                "minor_foundation"
                if goal.type == "minor" else "additional_major"
            )
        )
        for course_id in fixed_ids
    }
    schedulable_courses = [course_id for course_id in fixed_ids if course_id in supported_ids]
    slot_specs = []

    # A named slot preserves an official fixed requirement when its reliable
    # prerequisite graph has not yet been loaded into courses.json.
    for course_id in fixed_ids:
        if course_id not in supported_ids and course_id not in completed_courses:
            slot_specs.append({
                "id": f"fixed-{course_id}",
                "name": f"{course_id} — fixed program requirement",
                "units": 9,
                "kind": "fixed_course_pending_data",
                "program_tier": course_tiers.get(course_id),
            })

    fixed_units = sum(course_units.get(course_id, 9) for course_id in fixed_ids)
    completed_set = set(completed_courses)
    combined_groups = []
    seen_group_ids = set()
    profile_sources = (
        [("minor_foundation", profile)]
        if goal.type == "minor"
        else [
            ("minor_foundation", minor_profile),
            ("additional_major", profile),
        ]
    )
    for source_tier, source_profile in profile_sources:
        if source_profile is None:
            continue
        for group in source_profile.get("requirement_groups", []):
            if group["id"] in seen_group_ids:
                continue
            seen_group_ids.add(group["id"])
            combined_groups.append((source_tier, group))

    for source_tier, group in combined_groups:
        options = group.get("options", [])
        completed_in_group = len(completed_set.intersection(options))
        remaining_choices = max(0, group.get("choose", 1) - completed_in_group)
        total_group_units = group.get("units", group.get("choose", 1) * 9)
        per_choice_units = max(1, total_group_units // max(1, group.get("choose", 1)))
        option_summary = ", ".join(options)
        for index in range(remaining_choices):
            slot_specs.append({
                "id": f"{group['id']}-{index + 1}",
                "name": group["name"],
                "units": per_choice_units,
                "kind": "course_choice_group",
                "options": options,
                "option_summary": option_summary,
                "program_tier": source_tier,
            })

    return {
        "required_courses": schedulable_courses,
        "program_requirement_slots": slot_specs,
        "profile": profile,
        "required_course_tiers": course_tiers,
    }


def planning_context(request: Union[PlanningRequest, LegacyPlanRequest]):
    if isinstance(request, LegacyPlanRequest):
        return (
            request.goal,
            expand_completed_courses(request.completed_courses),
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
        expand_completed_courses(request.student.completed_courses),
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
    public_profile = dict(profile)
    public_profile["choice_slots"] = sum(
        group.get("choose", 1) for group in profile.get("requirement_groups", [])
    )
    return {
        "program_id": program_id,
        "program_name": next(
            (item["name"] for item in programs if item["id"] == program_id),
            program_id,
        ),
        "goal_type": goal_type,
        "catalog_year": program_profiles["catalog_year"],
        "profile": public_profile,
        "fixed_courses": [
            {
                "id": course_id,
                "name": course_names.get(course_id, "Catalog requirement"),
                "advanced_credit": advanced_credit["course_awards"].get(course_id, []),
                "advanced_credit_status": (
                    "official_direct_equivalency"
                    if course_id in advanced_credit["course_awards"]
                    else "no_direct_ap_ib_equivalency_listed"
                ),
            }
            for course_id in profile.get("required_course_ids", [])
        ],
        "requirement_groups": profile.get("requirement_groups", []),
        "advanced_credit_policy": advanced_credit["policy"],
    }


@app.post("/api/program-comparison")
def compare_programs(request: ComparisonRequest):
    selected = request.programs or [program["id"] for program in programs]
    names = {program["id"]: program["name"] for program in programs}
    current_major_courses = set(current_major_courses_for(request.student))
    completed_courses = set(expand_completed_courses(request.student.completed_courses))
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
                "choice_slots": sum(
                    group.get("choose", 1)
                    for group in profile.get("requirement_groups", [])
                ),
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
    if profile_for_goal(goal) is not None:
        planner_status = "ready_with_requirement_slots"
    elif planner_key in requirements:
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
        slot_units = semester.get("program_requirement_units", 0)
        if slot_units:
            # Slots reserve real academic capacity, but have no course-specific
            # FCE metric yet. Use units/3 as a visible planning estimate.
            workload["hours_per_week"] = round(
                workload["hours_per_week"] + slot_units / 3,
                1,
            )
            workload["data_status"] = "estimated_with_requirement_slots"

    return path_result

@app.post("/api/plan")
def create_plan(request: Union[PlanningRequest, LegacyPlanRequest]):
    goal_key, completed_courses, start_semester, max_units = planning_context(request)

    goal = request.goals[0] if isinstance(request, PlanningRequest) else None
    profile_inputs = (
        planning_inputs_for_profile(goal, completed_courses)
        if goal is not None else None
    )
    effective_requirements = requirements
    if profile_inputs is not None:
        effective_requirements = dict(requirements)
        effective_requirements[goal_key] = {
            "planner_status": "ready",
            "required_courses": profile_inputs["required_courses"],
        }

    if goal_key not in effective_requirements:
        raise HTTPException(status_code=404, detail="Unknown planning goal")

    goal_requirements = effective_requirements[goal_key]
    if goal_requirements.get("planner_status") != "ready":
        raise HTTPException(
            status_code=409,
            detail="Requirements exist, but this planner is not configured yet",
        )

    if (
        not goal_requirements.get("required_courses")
        and not (profile_inputs or {}).get("program_requirement_slots")
    ):
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
        requirements=effective_requirements,
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
        program_requirement_slots=(
            profile_inputs["program_requirement_slots"]
            if profile_inputs is not None else []
        ),
        required_course_tiers=(
            profile_inputs["required_course_tiers"]
            if profile_inputs is not None else {}
        ),
    )
    secondary_path_type = "lower_workload"
    if (
        isinstance(request, PlanningRequest)
        and goal is not None
        and goal.type == "additional_major"
    ):
        minor_goal = PlanningGoal(
            type="minor",
            program=goal.program,
            college=goal.college,
        )
        minor_key = planner_key_for_goal(minor_goal)
        minor_inputs = planning_inputs_for_profile(minor_goal, completed_courses)
        minor_requirements = dict(requirements)
        minor_requirements[minor_key] = {
            "planner_status": "ready",
            "required_courses": minor_inputs["required_courses"],
        }
        minor_result = generate_multiple_paths(
            completed_courses=completed_courses,
            courses=courses,
            program_id=minor_key,
            requirements=minor_requirements,
            start_semester=start_semester,
            max_units=max_units,
            baseline_requirements=get_student_planning_baseline(
                request.student.model_dump(), through_year=2
            )["requirements"],
            first_semester_max_units=(
                request.constraints.first_semester_max_units
                if request.student.enrollment_status == "precollege"
                else max_units
            ),
            semester_unit_limits=request.constraints.semester_unit_limits,
            student_year=request.student.year,
            planning_year=request.constraints.planning_year,
            current_major_courses=current_major_courses,
            course_metrics=course_metrics,
            program_requirement_slots=minor_inputs["program_requirement_slots"],
            required_course_tiers=minor_inputs["required_course_tiers"],
        )
        result["lower_workload"] = minor_result["fastest"]
        secondary_path_type = "minor_foundation"
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
        requirements=effective_requirements
    )

    shared_course_ids = [
        course_id
        for course_id in goal_requirements["required_courses"]
        if course_id in current_major_courses
    ]
    return {
        "fastest": result["fastest"],
        "lower_workload": result["lower_workload"],
        "secondary_path_type": secondary_path_type,
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
        "program_profile": (
            profile_inputs["profile"] if profile_inputs is not None else None
        ),
        "course_catalog": {
            course["id"]: {
                "name": course["name"],
                "units": course["units"],
                "offered": course.get("offered", []),
                "prerequisites": course.get("prerequisites", []),
                "prerequisite_expression": course.get("prerequisite_expression"),
                "metrics": course_metrics.get(course["id"]),
            }
            for course in courses
        },
        "minor_status": (
            {
                "available": not (
                    isinstance(request, PlanningRequest)
                    and request.student.college == "scs"
                ),
                "note": (
                    "SCS minors are for non-SCS students. For an SCS student, these courses are shown only as a foundation toward the additional major."
                    if isinstance(request, PlanningRequest)
                    and request.student.college == "scs"
                    else program_profiles["programs"].get(goal.program, {}).get("minor", {}).get("eligibility")
                ),
            }
            if goal is not None and goal.type == "additional_major"
            else None
        ),
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
