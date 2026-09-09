import json
import re
import sqlite3
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
from Engine.degree_audit import build_degree_audits, primary_baseline_for


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
program_directory = load_json(DATA_DIR / "program_directory.json")

INTENSITY_LABELS = {
    1: "Very light", 2: "Light", 3: "Moderate", 4: "Heavy", 5: "Very heavy"
}


def load_fce_course_averages():
    """Aggregate historical FCE workload once for fast course rendering."""
    with sqlite3.connect(DATA_DIR / "courses.sqlite") as connection:
        return {
            course_id: {"hours_per_week": hours, "responses": responses}
            for course_id, hours, responses in connection.execute(
                """
                select canonical_course_id, avg(hrs_per_week), count(hrs_per_week)
                from fce_courses
                where hrs_per_week is not null and hrs_per_week > 0
                group by canonical_course_id
                """
            )
        }


fce_course_averages = load_fce_course_averages()


def five_level_course_metric(course_id: str, units: float = 9):
    """Return an explainable five-level workload+difficulty estimate."""
    curated = course_metrics.get(course_id)
    fce = fce_course_averages.get(course_id)
    level = int(course_id.split("-")[1][0]) if "-" in course_id else 1
    if curated:
        hours = float(curated.get("hours_per_week", units / 3))
        workload = float(curated.get("workload", 3))
        difficulty = float(curated.get("difficulty", workload))
        source = curated.get("source_status", "curated_estimate")
    else:
        hours = float(fce["hours_per_week"] if fce else units / 3)
        workload = max(1, min(5, 1 + (hours - 3) / 3))
        difficulty = max(1, min(5, 1.7 + level * .45 + max(0, hours - 8) * .08))
        source = "historical_fce" if fce else "units_and_course_level_estimate"
    composite = (workload + difficulty) / 2
    tier = 1 if composite < 1.8 else 2 if composite < 2.6 else 3 if composite < 3.4 else 4 if composite < 4.2 else 5
    return {
        "tier": tier,
        "label": INTENSITY_LABELS[tier],
        "score": round(composite, 1),
        "workload": round(workload, 1),
        "difficulty": round(difficulty, 1),
        "hours_per_week": round(hours, 1),
        "source": source,
        "sample_size": (fce or {}).get("responses", 0),
    }

ELECTIVE_CATEGORY_PREFIXES = {
    "math": ("21",),
    "humanities": ("76", "79", "80", "82"),
    "social-sciences": ("73", "79", "84", "85", "88"),
    "data-analysis": ("05", "10", "36"),
}
COMMUNICATION_COURSES = ["76-101", "76-102", "76-106", "76-107", "76-108"]
STATS_ML_MATH_GROUPS = {
    "21-111": "Calculus sequence", "21-112": "Calculus sequence",
    "21-120": "Calculus sequence",
    "21-256": "Multivariable calculus", "21-259": "Multivariable calculus",
    "21-266": "Multivariable calculus", "21-268": "Multivariable calculus",
    "21-240": "Linear algebra", "21-241": "Linear algebra",
    "21-242": "Linear algebra",
}

# Official 2026-27 Statistics & Machine Learning sample path. Choice groups use
# one representative default here; the UI exposes every published alternative.
STATS_ML_STANDARD_PATH = requirements["stats-ml-major"]["required_courses"]
STATS_ML_CHOICE_COURSES = list(dict.fromkeys(
    option
    for group in requirements["stats-ml-major"]["requirement_groups"]
    for raw_option in group.get("options", [])
    for option in raw_option.split(" + ")
))
MECHE_STANDARD_PATH = requirements["mechanical-engineering-major"]["required_courses"]
MECHE_CHOICE_COURSES = list(dict.fromkeys(
    option
    for group in requirements["mechanical-engineering-major"]["requirement_groups"]
    for raw_option in group.get("options", [])
    for option in raw_option.split(" + ")
    if re.fullmatch(r"\d{2}-\d{3}", option)
))
ROBOTICS_ADDITIONAL_COURSES = [
    "16-450",
    *[
        option
        for group in program_profiles["programs"]["robotics"]["additional_major"]["requirement_groups"]
        for raw_option in group.get("options", [])
        for option in raw_option.split(" + ")
        if re.fullmatch(r"\d{2}-\d{3}", option)
    ],
]
IS_MINOR_COURSES = [
    "67-240", "67-250", "67-262", "15-112", "02-120",
    "67-206", "67-220", "67-265", "67-306", "67-336",
    "67-342", "67-347", "67-348", "67-364", "67-368",
]
STATS_ML_PREREQUISITES = {
    "36-202": ["36-200"],
    "21-256": ["21-120"],
    "36-235": ["21-120"],
    "36-236": ["36-235"],
    "21-241": [],
    "36-350": ["36-202"],
    "10-301": ["15-122", "36-235"],
    "36-401": ["21-241", "36-202", "36-236"],
    "36-402": ["36-401"],
    "15-351": ["15-122", "21-127"],
    "21-122": ["21-120"],
    "24-221": ["24-101", "21-122", "33-141"],
    "24-231": ["21-122", "33-141"],
    "24-261": ["24-101", "21-122", "33-141"],
    "24-262": ["24-261"],
    "21-254": ["21-122"],
    "21-260": ["21-122"],
    "24-321": ["24-231"],
    "24-322": ["24-221"],
    "24-351": ["24-101"],
    "24-352": ["24-351", "21-260"],
    "24-370": ["24-203", "24-262"],
    "24-452": ["24-321", "24-352"],
    "16-450": ["16-280"],
}
STATS_ML_MINIMUM_YEAR = {
    "36-235": 2, "36-236": 2, "36-350": 2,
    "10-301": 3, "36-401": 3, "36-402": 3, "15-351": 3,
    "24-221": 2, "24-231": 2, "24-261": 2, "24-262": 2,
    "21-254": 2, "21-260": 2, "24-203": 2, "24-251": 2,
    "24-302": 3, "24-311": 3, "24-321": 3, "24-322": 3,
    "24-351": 3, "24-352": 3, "24-370": 3, "36-220": 3,
    "24-441": 4, "24-452": 4, "24-671": 4, "16-450": 4,
}


def hydrate_scheduled_courses(course_list: list[dict], course_ids: list[str]):
    """Add selected scheduled courses from SQLite to the small planning graph."""
    existing = {course["id"]: course for course in course_list}
    placeholders = ",".join("?" for _ in course_ids)
    with sqlite3.connect(DATA_DIR / "courses.sqlite") as connection:
        rows = connection.execute(
            f"""
            select canonical_course_id, max(title), max(units),
                   group_concat(distinct lower(term))
            from courses where canonical_course_id in ({placeholders})
            group by canonical_course_id
            """,
            course_ids,
        ).fetchall()
    for course_id, title, units, offered in rows:
        schedule_terms = sorted(set((offered or "").split(",")) - {""})
        units = units if units is not None else 9
        if course_id in existing:
            # The SQLite schedule is the current source of truth for offering
            # terms; merge it even when the planning graph already has a node.
            existing[course_id]["offered"] = schedule_terms
            continue
        course_list.append({
            "id": course_id,
            "name": title,
            "units": int(units) if float(units).is_integer() else units,
            "prerequisites": STATS_ML_PREREQUISITES.get(course_id, []),
            "prerequisite_data_status": (
                "curated_mapping"
                if course_id in STATS_ML_PREREQUISITES
                else "catalog_not_imported"
            ),
            "offered": schedule_terms,
            "minimum_year": STATS_ML_MINIMUM_YEAR.get(course_id, 1),
            "source": "processed_schedule_sqlite",
        })


hydrate_scheduled_courses(courses, STATS_ML_STANDARD_PATH + STATS_ML_CHOICE_COURSES)
hydrate_scheduled_courses(courses, IS_MINOR_COURSES)
hydrate_scheduled_courses(courses, MECHE_STANDARD_PATH + MECHE_CHOICE_COURSES)
hydrate_scheduled_courses(courses, ROBOTICS_ADDITIONAL_COURSES)

# Keep the planning catalog synchronized with every concrete course referenced
# by a verified requirement profile. Previously only a few hand-maintained
# majors were hydrated, leaving valid dropdown choices without units, offering
# terms, or workload data.
_referenced_requirement_courses = set()
for _requirement in requirements.values():
    _referenced_requirement_courses.update(_requirement.get("required_courses", []))
    for _group in _requirement.get("requirement_groups", []):
        for _raw_option in _group.get("options", []):
            _referenced_requirement_courses.update(
                _course_id for _course_id in _raw_option.split(" + ")
                if re.fullmatch(r"\d{2}-\d{3}", _course_id)
            )
for _program_profiles in program_profiles["programs"].values():
    for _profile in _program_profiles.values():
        _referenced_requirement_courses.update(_profile.get("required_course_ids", []))
        for _group in _profile.get("requirement_groups", []):
            for _raw_option in _group.get("options", []):
                _referenced_requirement_courses.update(
                    _course_id for _course_id in _raw_option.split(" + ")
                    if re.fullmatch(r"\d{2}-\d{3}", _course_id)
                )
hydrate_scheduled_courses(courses, sorted(_referenced_requirement_courses))

with sqlite3.connect(DATA_DIR / "courses.sqlite") as _connection:
    _robotics_elective_ids = [
        row[0] for row in _connection.execute(
            """
            select distinct canonical_course_id from courses
            where canonical_course_id glob '16-[34][0-9][0-9]'
            """
        ).fetchall()
    ]
hydrate_scheduled_courses(courses, _robotics_elective_ids)
for _course in courses:
    course_metrics.setdefault(_course["id"], {
        "hours_per_week": round(_course["units"] / 3, 1),
        "workload": 3.0,
        "difficulty": 3.0,
        "stress": 3.0,
        "intensity": "standard",
        "source": "unit_based_estimate",
    })


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
    curriculum = requirements.get(f"{student.primary_major}-major", {})
    return curriculum.get("required_courses", [])


def current_major_course_universe(student: "StudentState"):
    fixed = set(current_major_courses_for(student))
    curriculum = requirements.get(f"{student.primary_major}-major", {})
    for group in curriculum.get("requirement_groups", []):
        for option in group.get("options", []):
            fixed.update(option.split(" + "))
    return fixed


def primary_major_requirement_slots(primary_major: str, completed_courses: list[str]):
    """Build real choice slots for any verified primary-major curriculum."""
    completed = set(completed_courses)
    slots = []
    curriculum = requirements.get(f"{primary_major}-major", {})
    for group in curriculum.get("requirement_groups", []):
        group_options = list(group.get("options", []))
        if primary_major == "stats-ml" and group.get("id") == "linear-algebra":
            # 21-241 is the recommended Stats/ML linear-algebra route for the
            # product's early-path guidance. This changes the default ordering,
            # not the official set of valid alternatives.
            group_options.sort(key=lambda option: option != "21-241")
        satisfied = sum(
            1 for option in group_options
            if set(option.split(" + ")).issubset(completed)
        )
        remaining = max(0, group.get("choose", 1) - satisfied)
        per_choice_units = group.get("units", 9) / max(1, group.get("choose", 1))
        for index in range(remaining):
            slots.append({
                "id": f"{primary_major}-{group['id']}-{index + 1}",
                "name": group["name"],
                "units": int(per_choice_units) if per_choice_units.is_integer() else per_choice_units,
                "options": group_options,
                "minimum_year": group.get("minimum_year", 1),
                "offered": group.get("offered", []),
                "program_tier": "current_major",
                "scope": "primary_major",
            })
    return slots


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
    target_completion_year: int | None = Field(default=None, ge=1, le=4)


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
    if goal.type not in {"internal_transfer", "additional_major", "minor"}:
        return None
    # Existing SCS transfer planners use their dedicated admissions-course
    # templates. IS is the first full B.S. curriculum represented by the
    # generic profile model.
    if goal.type == "internal_transfer" and goal.program != "information-systems":
        return None
    return program_profiles["programs"].get(goal.program, {}).get(goal.type)


def planning_inputs_for_profile(
    goal: PlanningGoal,
    completed_courses: list[str],
    primary_major: str | None = None,
):
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
    minor_group_ids = {
        group["id"] for group in (minor_profile or {}).get("requirement_groups", [])
    }
    minor_option_ids = {
        option
        for group in (minor_profile or {}).get("requirement_groups", [])
        for option in group.get("options", [])
        if " + " not in option and "xxx" not in option.lower()
    }
    # An additional major is its own official curriculum, not the union of the
    # minor and major curricula. Minor data is used only to color overlapping
    # requirements as foundation work.
    fixed_ids = list(dict.fromkeys(profile.get("required_course_ids", [])))
    course_tiers = {
        course_id: (
            None
            if goal.type == "internal_transfer"
            else (
                "minor_foundation"
                if course_id in minor_fixed_ids or course_id in minor_option_ids
                else (
                    "minor_foundation"
                    if goal.type == "minor" else "additional_major"
                )
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
    # A course already completed by the student may satisfy a choice group.
    # Do not let a fixed requirement automatically satisfy another requirement
    # in the same program (for example, required 16-450 cannot also become one
    # of the two Robotics electives merely because it is numbered 16-4xx).
    courses_satisfying_groups = completed_set
    combined_groups = []
    seen_group_ids = set()
    for group in profile.get("requirement_groups", []):
        source_tier = (
            "minor_foundation"
            if goal.type == "minor" or group["id"] in minor_group_ids
            else "additional_major"
        )
        if group["id"] in seen_group_ids:
            continue
        seen_group_ids.add(group["id"])
        combined_groups.append((source_tier, group))

    for source_tier, group in combined_groups:
        # The Robotics Institute explicitly permits MechE students to use
        # 24-441 for the Robotics capstone. The verified MechE curriculum
        # already schedules that capstone choice, so do not create a second,
        # duplicate capstone slot in the additional-major extension.
        if (
            primary_major == "mechanical-engineering"
            and goal.type == "additional_major"
            and goal.program == "robotics"
            and group.get("id") == "capstone"
        ):
            continue
        options = []
        for option in group.get("options", []):
            if option == "16-3xx":
                options.extend(course["id"] for course in courses if re.fullmatch(r"16-3\d{2}", course["id"]))
            elif option == "16-4xx":
                options.extend(course["id"] for course in courses if re.fullmatch(r"16-4\d{2}", course["id"]))
            else:
                options.append(option)
        options = list(dict.fromkeys(options))
        if goal.program == "robotics" and primary_major == "mechanical-engineering":
            preferred = {
                "controls": ["24-451"],
                "building": ["24-671", "24-778"],
                "capstone": ["24-441"],
            }.get(group["id"], [])
            preferred_rank = {option: index for index, option in enumerate(preferred)}
            options.sort(key=lambda option: (option not in preferred_rank, preferred_rank.get(option, 0)))
        completed_in_group = len(courses_satisfying_groups.intersection(options))
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
                "minimum_year": group.get("minimum_year", 1),
                "offered": group.get("offered", []),
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


@app.get("/api/program-directory")
def list_program_directory(
    college: str | None = None,
    program_type: Literal["primary_major", "additional_major", "minor"] | None = None,
):
    """Return CMU-wide directory entries, optionally filtered by affiliation."""
    results = program_directory
    if college:
        results = [
            program
            for program in results
            if college in program.get("affiliations", [])
            or college in program.get("home_colleges", [])
        ]
    if program_type:
        results = [
            program
            for program in results
            if program.get("program_type") == program_type
        ]
    return {
        "catalog_year": "2026-2027",
        "count": len(results),
        "programs": results,
    }


@app.get("/api/electives")
def list_electives(
    term: Literal["fall", "spring"] = "fall",
    category: str = "free-elective",
):
    """Return real scheduled courses for the semester elective picker."""
    database = DATA_DIR / "courses.sqlite"
    prefixes = ELECTIVE_CATEGORY_PREFIXES.get(category)
    where = [
        "lower(term) = ?",
        "units > 0",
        # CMU numbers 600+ are graduate level. Keep the broad undergraduate
        # catalog available, including 0xx StuCos, but never mix grad courses
        # into the default elective picker.
        "cast(substr(canonical_course_id, 4, 3) as integer) < 600",
    ]
    parameters: list[object] = [term]
    if category == "communication":
        where.append(
            f"canonical_course_id in ({','.join('?' for _ in COMMUNICATION_COURSES)})"
        )
        parameters.extend(COMMUNICATION_COURSES)
    elif category == "stats-ml-math":
        allowed = list(STATS_ML_MATH_GROUPS)
        where.append(
            f"canonical_course_id in ({','.join('?' for _ in allowed)})"
        )
        parameters.extend(allowed)
    elif prefixes:
        where.append(f"substr(canonical_course_id, 1, 2) in ({','.join('?' for _ in prefixes)})")
        parameters.extend(prefixes)

    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            f"""
            select canonical_course_id, max(title), max(units), max(section_count)
            from courses
            where {' and '.join(where)}
            group by canonical_course_id
            order by canonical_course_id
            """,
            parameters,
        ).fetchall()

    planning_course_by_id = {course["id"]: course for course in courses}
    results = [
        {
            "id": course_id,
            "name": title,
            "units": units,
            "term": term,
            "sections": section_count,
            "level": int(course_id.split("-")[1][0]) * 100,
            "requirement_group": STATS_ML_MATH_GROUPS.get(course_id),
            "minimum_year": planning_course_by_id.get(course_id, {}).get(
                "minimum_year", 1
            ),
            "prerequisites": planning_course_by_id.get(course_id, {}).get(
                "prerequisites", []
            ),
            "prerequisite_data_status": planning_course_by_id.get(
                course_id, {}
            ).get("prerequisite_data_status", "catalog_not_imported"),
            "description": (
                (f"{STATS_ML_MATH_GROUPS[course_id]} · " if course_id in STATS_ML_MATH_GROUPS else "")
                + f"{units:g} units · Offered {term.title()} 2026 · "
                f"{section_count} scheduled section{'s' if section_count != 1 else ''}."
            ),
            "intensity": five_level_course_metric(course_id, units),
        }
        for course_id, title, units, section_count in rows
    ]
    if category == "communication":
        scheduled = {course["id"]: course for course in results}
        full_courses = [
            scheduled[course_id]
            for course_id in ("76-101", "76-102")
            if course_id in scheduled
        ]
        mini_pairs = []
        mini_ids = [
            course_id for course_id in ("76-106", "76-107", "76-108")
            if course_id in scheduled
        ]
        for index, first_id in enumerate(mini_ids):
            for second_id in mini_ids[index + 1:]:
                first = scheduled[first_id]
                second = scheduled[second_id]
                mini_pairs.append({
                    "id": f"{first_id} + {second_id}",
                    "name": f"{first['name']} + {second['name']}",
                    "units": first["units"] + second["units"],
                    "term": term,
                    "sections": min(first["sections"], second["sections"]),
                    "level": 100,
                    "requirement_group": "Communication · two-mini pathway",
                    "description": (
                        f"9 units total · two consecutive minis · Offered {term.title()} 2026. "
                        "Choose different mini-session section numbers."
                    ),
                    "intensity": {
                        "tier": max(first["intensity"]["tier"], second["intensity"]["tier"]),
                        "label": INTENSITY_LABELS[max(
                            first["intensity"]["tier"], second["intensity"]["tier"]
                        )],
                        "score": round((
                            first["intensity"]["score"] + second["intensity"]["score"]
                        ) / 2, 2),
                        "workload": round((
                            first["intensity"]["workload"] + second["intensity"]["workload"]
                        ) / 2, 2),
                        "difficulty": round((
                            first["intensity"]["difficulty"] + second["intensity"]["difficulty"]
                        ) / 2, 2),
                        "hours_per_week": round(
                            first["intensity"]["hours_per_week"]
                            + second["intensity"]["hours_per_week"],
                            1,
                        ),
                        "source": "combined-mini-courses",
                        "sample_size": (
                            first["intensity"].get("sample_size", 0)
                            + second["intensity"].get("sample_size", 0)
                        ),
                    },
                })
        results = full_courses + mini_pairs
    return {
        "term": term,
        "category": category,
        "count": len(results),
        "courses": results,
        "approval_note": (
            "Communication options follow the official First-Year Writing pathways."
            if category == "communication"
            else "These are scheduled candidates; confirm that a course satisfies your specific GenEd category in SIO or with your advisor."
        ),
    }


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
    minor_profile = program_profiles["programs"].get(program_id, {}).get("minor", {})
    minor_course_ids = set(minor_profile.get("required_course_ids", []))
    minor_course_ids.update(
        option
        for group in minor_profile.get("requirement_groups", [])
        for option in group.get("options", [])
        if " + " not in option and "xxx" not in option.lower()
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
                "program_tier": (
                    "transfer_goal"
                    if goal_type == "internal_transfer"
                    else (
                        "minor_foundation"
                        if goal_type == "minor" or course_id in minor_course_ids
                        else "additional_major"
                    )
                ),
            }
            for course_id in profile.get("required_course_ids", [])
        ],
        "requirement_groups": profile.get("requirement_groups", []),
        "advanced_credit_policy": advanced_credit["policy"],
    }


@app.get("/api/primary-majors/{program_id}")
def get_primary_major_profile(program_id: str):
    curriculum = requirements.get(f"{program_id}-major")
    if curriculum is None or curriculum.get("planner_status") != "ready":
        raise HTTPException(status_code=404, detail="Primary-major curriculum is not configured")
    course_by_id = {course["id"]: course for course in courses}
    return {
        "program_id": program_id,
        "catalog_year": curriculum.get("catalog_year"),
        "curriculum_status": curriculum.get("curriculum_status"),
        "minimum_degree_units": curriculum.get("minimum_degree_units"),
        "fixed_courses": [
            {
                "id": course_id,
                "name": course_by_id.get(course_id, {}).get("name", "Catalog requirement"),
                "is_current_major": True,
            }
            for course_id in curriculum.get("required_courses", [])
        ],
        "requirement_groups": curriculum.get("requirement_groups", []),
        "notes": curriculum.get("notes", []),
    }


@app.post("/api/program-comparison")
def compare_programs(request: ComparisonRequest):
    selected = request.programs or [program["id"] for program in programs]
    names = {program["id"]: program["name"] for program in programs}
    current_major_courses = current_major_course_universe(request.student)
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
        primary_units = semester.get("primary_major_reserved_units", 0)
        estimated_units = slot_units + primary_units
        if estimated_units:
            # Slots reserve real academic capacity, but have no course-specific
            # FCE metric yet. Use units/3 as a visible planning estimate.
            workload["hours_per_week"] = round(
                workload["hours_per_week"] + estimated_units / 3,
                1,
            )
            workload["data_status"] = "estimated_with_reserved_requirements"

    return path_result

@app.post("/api/plan")
def create_plan(request: Union[PlanningRequest, LegacyPlanRequest]):
    goal_key, completed_courses, start_semester, max_units = planning_context(request)

    goal = request.goals[0] if isinstance(request, PlanningRequest) else None
    profile_inputs = (
        planning_inputs_for_profile(
            goal,
            completed_courses,
            request.student.primary_major if isinstance(request, PlanningRequest) else None,
        )
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
    primary_baseline = (
        primary_baseline_for(request.student)
        if isinstance(request, PlanningRequest) else None
    )
    # A partial curriculum needs both named verified courses and a reserve for
    # the still-unselected parts. The planner subtracts named current-major
    # units from this reserve semester by semester, so nothing is double-counted.
    primary_reserved_units = (
        primary_baseline["units"] if primary_baseline is not None else 0
    )
    primary_requirement_slots = (
        primary_major_requirement_slots(
            request.student.primary_major,
            completed_courses + goal_requirements.get("required_courses", [])
        )
        if isinstance(request, PlanningRequest)
        and requirements.get(f"{request.student.primary_major}-major", {}).get(
            "curriculum_status"
        ) == "verified"
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
        target_completion_year=(
            request.constraints.target_completion_year
            if isinstance(request, PlanningRequest)
            else None
        ),
        primary_major_reserved_units=primary_reserved_units,
        primary_major_baseline_name=(primary_baseline or {}).get(
            "name", "Primary-major baseline"
        ),
        current_major_courses=current_major_courses,
        course_metrics=course_metrics,
        program_requirement_slots=(
            primary_requirement_slots + (
                profile_inputs["program_requirement_slots"]
                if profile_inputs is not None else []
            )
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
        minor_inputs = planning_inputs_for_profile(
            minor_goal, completed_courses, request.student.primary_major
        )
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
            target_completion_year=request.constraints.target_completion_year,
            primary_major_reserved_units=primary_reserved_units,
            primary_major_baseline_name=primary_baseline["name"],
            current_major_courses=current_major_courses,
            course_metrics=course_metrics,
            program_requirement_slots=(
                primary_requirement_slots + minor_inputs["program_requirement_slots"]
            ),
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

    overlap_course_ids = (
        current_major_course_universe(request.student)
        if isinstance(request, PlanningRequest)
        else set(current_major_courses)
    )
    shared_course_ids = [
        course_id
        for course_id in goal_requirements["required_courses"]
        if course_id in overlap_course_ids
    ]
    degree_audits = (
        build_degree_audits(
            request.student,
            goal,
            (profile_inputs or {}).get("profile"),
            result["fastest"],
            primary_baseline,
        )
        if isinstance(request, PlanningRequest) and goal is not None
        else None
    )
    return {
        "fastest": result["fastest"],
        "lower_workload": result["lower_workload"],
        "target_completion_year": result.get("target_completion_year"),
        "secondary_path_type": secondary_path_type,
        "primary_baseline": primary_baseline,
        "degree_audits": degree_audits,
        "explanation": explanation,
        "overlap_summary": {
            "courses": shared_course_ids,
            "units": sum(
                course["units"]
                for course in courses
                if course["id"] in shared_course_ids
            ),
            "current_major_scope": (primary_baseline or {}).get("status"),
        },
        "program_profile": (
            profile_inputs["profile"] if profile_inputs is not None else None
        ),
        "course_catalog": {
            course["id"]: {
                "name": course["name"],
                "units": course["units"],
                "offered": course.get("offered", []),
                "minimum_year": course.get("minimum_year", 1),
                "prerequisites": course.get("prerequisites", []),
                "prerequisite_expression": course.get("prerequisite_expression"),
                "prerequisite_data_status": course.get(
                    "prerequisite_data_status", "catalog_not_imported"
                ),
                "recommended_preparation": course.get(
                    "recommended_preparation", []
                ),
                "metrics": course_metrics.get(course["id"]),
                "intensity": five_level_course_metric(course["id"], course["units"]),
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
