import json
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal, Union

# json       → 读 JSON
# os         → 环境变量，例如 OpenAI API key
# re         → 正则表达式，识别 15-122 / 15-3xx
# sqlite3    → 查课程数据库
# closing    → 自动关闭 DB connection
# Path       → 文件路径
# Literal    → Pydantic 类型限制

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import requests
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
from Engine.student_state import (
    derive_academic_state,
    planning_boundary_after_locked_semesters,
    prepend_locked_semesters,
)
from Backend.requirements import (
    apply_requirement_option_preferences,
    build_primary_major_requirement_slots,
    collect_requirement_course_ids,
    expand_course_completion,
    expand_profile_requirement_options,
    extract_profile_course_ids,
    find_courses_from_named_set,
    find_courses_matching_pattern,
    find_official_program_source,
    get_program_requirement_adjustment,
    get_transfer_profile,
    hydrate_courses_from_schedule,
    load_transfer_requirements,
    primary_major_course_universe,
    primary_major_required_courses,
    resolve_curriculum_requirement_options,
    resolve_data_requirement_option,
)
from Backend.course_metrics import (
    calculate_five_level_course_metric,
    load_fce_course_averages,
)
from Backend.transfer_advisor import (
    TRANSFER_ADVICE_SCHEMA,
    request_ollama_transfer_advice,
    request_openai_transfer_advice,
)
from Backend.path_comparison import (
    compare_generated_plans,
    discover_path_alternatives,
    load_path_alternatives,
)
from Backend.course_recommendation import (
    load_recommendation_policy,
    recommendation_slots_from_plan,
    recommend_courses_for_plan,
)

# Backend/application.py
#         ↓
# Engine/planning.py

# Main FastAPI application.
# This object registers all backend API routes and hosts the frontend.
app = FastAPI(
    title="CMU Path API",
    description="Course-planning API and frontend host for CMU Path.",
)

# Repo Root
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
program_curriculum_registry = {
    item["program_id"]: item
    for item in load_json(DATA_DIR / "program_curriculum_registry.json").get(
        "programs", []
    )
}

INTENSITY_LABELS = {
    1: "Very light", 2: "Light", 3: "Moderate", 4: "Heavy", 5: "Very heavy"
}


fce_course_averages = load_fce_course_averages(DATA_DIR / "courses.sqlite")


def five_level_course_metric(course_id: str, units: float = 9):
    """Compatibility wrapper around the shared course metric calculator."""
    return calculate_five_level_course_metric(
        course_id,
        units,
        course_metrics,
        fce_course_averages,
        INTENSITY_LABELS,
    )

# 从 Data/policies 加载 elective 候选筛选规则。
# Backend 不保存具体学术政策，只读取结构化 policy data。
# 这些 prefix / course groups 仅用于生成候选课程，
# 不代表课程一定满足官方 requirement。
POLICY_DIR = PROJECT_ROOT / "Data" / "policies"

elective_rules = load_json(POLICY_DIR / "elective_rules.json")
program_declaration_policies = load_json(
    POLICY_DIR / "program_declaration_policies.json"
).get("policies", {})

ELECTIVE_CATEGORY_PREFIXES = elective_rules["elective_category_prefixes"]
ELECTIVE_CATEGORY_GROUPS = elective_rules.get("elective_category_groups", {})
PROGRAM_ELECTIVE_PREFIXES = elective_rules["program_elective_prefixes"]
GENERAL_EDUCATION_PREFIXES = tuple(elective_rules["general_education_prefixes"])
COMMUNICATION_COURSES = elective_rules["communication_courses"]
MATH_EQUIVALENCY_GROUPS = elective_rules["math_equivalency_groups"]
NAMED_COURSE_SETS = elective_rules["named_course_sets"]
REQUIREMENT_OPTION_SETS = elective_rules["requirement_option_sets"]
COURSE_PATTERN_CONSTRAINTS = elective_rules["course_pattern_constraints"]
PROGRAM_REQUIREMENT_ADJUSTMENTS = elective_rules["program_requirement_adjustments"]
PATH_ALTERNATIVES = load_path_alternatives(POLICY_DIR)
COURSE_RECOMMENDATION_POLICY = load_recommendation_policy(POLICY_DIR)
COURSE_COMPLETION_IMPLICATIONS = load_json(POLICY_DIR / "completion_implications.json")
course_progression_rules = load_json(POLICY_DIR / "course_progression_rules.json")
CURATED_PREREQUISITES = course_progression_rules["prerequisites"]
COURSE_RECOMMENDED_EARLIEST_YEAR = course_progression_rules["recommended_earliest_year"]
# 兼容旧测试 / 旧调用。
# 数据本身仍然只有一个 source of truth：
# Data/policies/course_progression_rules.json
STATS_ML_PREREQUISITES = CURATED_PREREQUISITES
# Backward-compatibility alias.
# TODO: Remove after tests and internal callers fully migrate to the universal name.
STATS_ML_MATH_GROUPS = MATH_EQUIVALENCY_GROUPS

def extract_course_ids_from_requirement_profile(profile: dict) -> list[str]:
    return extract_profile_course_ids(profile, courses_matching_pattern)

def all_requirement_course_ids() -> list[str]:
    return collect_requirement_course_ids(
        requirements,
        program_profiles,
        extract_course_ids_from_requirement_profile,
    )

def hydrate_scheduled_courses(course_list: list[dict], course_ids: list[str]):
    hydrate_courses_from_schedule(
        course_list,
        course_ids,
        DATA_DIR / "courses.sqlite",
        CURATED_PREREQUISITES,
        COURSE_RECOMMENDED_EARLIEST_YEAR,
    )

def courses_matching_pattern(option: str) -> list[str]:
    return find_courses_matching_pattern(option, DATA_DIR / "courses.sqlite")

def courses_from_named_set(set_id: str) -> list[str]:
    return find_courses_from_named_set(
        set_id,
        NAMED_COURSE_SETS,
        courses,
        DATA_DIR / "courses.sqlite",
    )


def resolve_requirement_option(option: str) -> list[str]:
    return resolve_data_requirement_option(
        option,
        courses_matching_pattern,
        courses_from_named_set,
    )
# 补全所有 requirement profile 中实际引用到的课程。
# 新增专业、转专业、additional major 或 minor 时，
# 只需要更新 Data 层，不再需要在这里新增专属课程列表。
hydrate_scheduled_courses(
    courses,
    all_requirement_course_ids()
)
 
# 自动加载 Data/policies/elective_rules.json 中定义的所有课程集合。
# 新增新的 named course set 时，不需要再修改 application.py。
for set_id in NAMED_COURSE_SETS:
    hydrate_scheduled_courses(
        courses,
        courses_from_named_set(set_id)
    )


# 为没有 workload 数据的课程补充低置信度默认指标。
# 这些值只是 fallback estimate，不应该和真实 FCE / curated 数据等价展示。
for _course in courses:
    course_metrics.setdefault(
        _course["id"],
        {
            "hours_per_week": round(_course["units"] / 3, 1),
            "workload": 3.0,
            "difficulty": 3.0,
            "stress": 3.0,
            "intensity": "standard",
            "source": "unit_based_estimate",
            "confidence": "low",
        },
    )



def expand_completed_courses(course_ids: list[str]) -> list[str]:
    return expand_course_completion(course_ids, COURSE_COMPLETION_IMPLICATIONS)


def current_major_courses_for(student: "StudentState") -> list[str]:
    return primary_major_required_courses(
        student.primary_major,
        requirements,
    )

def current_major_course_universe(student: "StudentState") -> set[str]:
    return primary_major_course_universe(
        student.primary_major,
        requirements,
        extract_course_ids_from_requirement_profile,
    )

def primary_major_requirement_slots(primary_major: str, completed_courses: list[str]):
    return build_primary_major_requirement_slots(
        primary_major,
        completed_courses,
        requirements,
        resolve_requirement_option,
    )

# 开发时禁用浏览器缓存，确保 API 每次都返回最新数据。
# 所有 HTTP 请求会先经过这个 middleware。
# call_next(request) 让请求继续执行真正的 API。
# API 返回结果后，给 response 加上 "Cache-Control: no-store"，
# 告诉浏览器不要缓存这次结果，避免开发时读取到旧的 API 数据。
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
    in_progress_courses: list[str] = Field(default_factory=list)
    planned_courses: list[str] = Field(default_factory=list)
    locked_semesters: list[dict] = Field(default_factory=list)


class PlanningGoal(BaseModel):
    type: Literal["current_major", "internal_transfer", "additional_major", "minor"]
    program: str
    college: str | None = None
    include_post_transfer_plan: bool = False


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
    current_goal: PlanningGoal | None = None
    alternative_goal: PlanningGoal | None = None
    constraints: PlanningConstraints = Field(default_factory=PlanningConstraints)
    current_plan: dict | None = None


class CourseRecommendationRequest(PlanningRequest):
    current_plan: dict | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    manual_selections: dict[str, str] = Field(default_factory=dict)


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


transfer_requirements = load_transfer_requirements(POLICY_DIR)
TRANSFER_ELIGIBILITY_PROFILES = transfer_requirements["eligibility_profiles"]
SCS_TRANSFER_PROGRAMS = set(transfer_requirements["scs_transfer"]["programs"])
SCS_TRANSFER_POLICY_DEFAULTS = transfer_requirements["scs_transfer"]["defaults"]
POST_TRANSFER_PLAN_PROGRAMS = set(
    transfer_requirements["post_transfer_plan_programs"]
)


def official_program_source(program_id: str, goal_type: str) -> str | None:
    return find_official_program_source(
        program_directory,
        program_id,
        goal_type,
    )


def transfer_policy_for_goal(goal: PlanningGoal):
    """Return one normalized admission policy for every supported transfer."""
    return get_transfer_profile(
        goal.program,
        transfer_requirements,
        program_profiles,
    )


def expand_requirement_options(raw_options: list[str]) -> list[str]:
    return expand_profile_requirement_options(
        raw_options,
        courses,
        REQUIREMENT_OPTION_SETS,
        COURSE_PATTERN_CONSTRAINTS,
        courses_from_named_set,
        program_profiles,
    )


def profile_for_goal(goal: PlanningGoal):
    if goal.type not in {"internal_transfer", "additional_major", "minor"}:
        return None
    if goal.type == "internal_transfer" and not goal.include_post_transfer_plan:
        eligibility_profile = transfer_policy_for_goal(goal)
        if eligibility_profile is not None:
            return eligibility_profile
    # Program profiles are the authoritative source for generic transfer,
    # additional-major, and minor planning.  Keeping a second allowlist here
    # caused valid catalog-backed SCS transfer profiles to appear unavailable.
    profile = program_profiles["programs"].get(goal.program, {}).get(goal.type)
    if profile is not None:
        return profile
    if goal.type == "internal_transfer":
        # A graduation curriculum is not an admissions policy. Do not silently
        # plan the whole destination degree when transfer criteria are absent.
        return None
    return None


def planning_inputs_for_profile(
    goal: PlanningGoal,
    completed_courses: list[str],
    primary_major: str | None = None,
):
    profile = profile_for_goal(goal)
    if profile is None:
        return None
    profile = dict(profile)
    profile.setdefault("source_url", official_program_source(goal.program, goal.type))
    profile.setdefault("policy_status", "official_verified")

    supported_ids = {
        course["id"] for course in courses
        if course.get("name")
        and isinstance(course.get("units"), (int, float))
        and course["units"] >= 0
    }
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
    official_fixed_ids = list(dict.fromkeys(profile.get("required_course_ids", [])))
    preparation_ids = [
        course_id for course_id in profile.get("preparation_courses", [])
        if course_id not in completed_courses
    ]
    # Admission pages list the checkpoint courses, not every prerequisite
    # needed to reach them. Add the verified prerequisite chain to the plan as
    # clearly labelled preparation so requirements such as 15-251 never remain
    # mysteriously unschedulable.
    planning_course_by_id = {course["id"]: course for course in courses}
    prerequisite_queue = [*official_fixed_ids, *preparation_ids]
    seen_prerequisites = set(prerequisite_queue)
    while prerequisite_queue:
        course_id = prerequisite_queue.pop(0)
        course = planning_course_by_id.get(course_id, {})
        for prerequisite in course.get("prerequisites", []):
            if prerequisite in completed_courses or prerequisite in seen_prerequisites:
                continue
            preparation_ids.append(prerequisite)
            seen_prerequisites.add(prerequisite)
            prerequisite_queue.append(prerequisite)
    fixed_ids = list(dict.fromkeys([*preparation_ids, *official_fixed_ids]))
    course_tiers = {
        course_id: (
            (
                "transfer_preparation"
                if course_id in preparation_ids
                else "transfer_goal"
            )
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
            "transfer_goal"
            if goal.type == "internal_transfer"
            else (
                "minor_foundation"
                if goal.type == "minor" or group["id"] in minor_group_ids
                else "additional_major"
            )
        )
        if group["id"] in seen_group_ids:
            continue
        seen_group_ids.add(group["id"])
        combined_groups.append((source_tier, group))

    requirement_adjustment = get_program_requirement_adjustment(
        PROGRAM_REQUIREMENT_ADJUSTMENTS,
        primary_major,
        goal.type,
        goal.program,
    )
    for source_tier, group in combined_groups:
        if group.get("id") in requirement_adjustment.get("skip_groups", []):
            continue
        options = expand_requirement_options(group.get("options", []))
        options = apply_requirement_option_preferences(
            options,
            requirement_adjustment.get("preferred_options", {}).get(
                group["id"],
                [],
            ),
        )
        completed_in_group = sum(
            set(option.split(" + ")).issubset(courses_satisfying_groups)
            for option in options
        )
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
                "cross_scope_overlap_limit": (
                    profile.get("double_count_limit")
                    if source_tier != "transfer_goal" else None
                ),
            })

    return {
        "required_courses": schedulable_courses,
        "official_required_courses": official_fixed_ids,
        "preparation_courses": preparation_ids,
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


def baseline_through_year_for_plan(request: PlanningRequest) -> int:
    """Schedule college requirements due within this plan, not a fixed two years."""
    target = request.constraints.target_completion_year
    if target is not None:
        return target
    start = request.constraints.planning_year or request.student.year
    return min(4, start + 1)


@app.get("/api/programs")
def list_programs():
    return programs


@app.get("/api/program-directory")
def list_program_directory(
    college: str | None = None,
    program_type: Literal[
        "primary_major", "additional_major", "additional_degree", "minor"
    ] | None = None,
):
    """Return official program existence separately from planning capability."""
    results = []
    for raw_program in program_directory:
        program = dict(raw_program)
        planning_id = program.get("planning_id") or program.get("id")
        profile_type = {
            "additional_major": "additional_major",
            "minor": "minor",
        }.get(program.get("program_type"))
        has_profile = bool(
            profile_type
            and program_profiles["programs"].get(planning_id, {}).get(profile_type)
        )
        has_primary_curriculum = bool(
            program.get("program_type") == "primary_major"
            and requirements.get(f"{planning_id}-major", {}).get("planner_status") == "ready"
        )
        has_transfer_profile = bool(
            program.get("program_type") == "primary_major"
            and (
                planning_id in TRANSFER_ELIGIBILITY_PROFILES
                or program_profiles["programs"].get(planning_id, {}).get("internal_transfer")
            )
        )
        curriculum_id = (
            program.get("requirements_source_program_id") or program.get("id")
        )
        curriculum = program_curriculum_registry.get(curriculum_id)
        requirements_loaded = curriculum is not None
        requirements_validation_status = "not_loaded"
        if curriculum:
            requirements_validation_status = (
                "promotion_ready"
                if curriculum.get("validation", {}).get("promotion_ready")
                else "needs_review"
            )
        planner_ready_for_entry = has_profile or has_primary_curriculum
        if program.get("program_type") == "primary_major":
            program["current_major_planning_status"] = (
                "planning_ready" if has_primary_curriculum else "directory_only"
            )
            program["transfer_planning_status"] = (
                "planning_ready" if has_transfer_profile else "directory_only"
            )
        available_as = list(program.get("available_as", [program.get("program_type")]))
        if has_transfer_profile and "transfer_destination" not in available_as:
            available_as.append("transfer_destination")
        program["available_as"] = available_as
        program["discoverable"] = True
        program["requirements_loaded"] = requirements_loaded
        program["requirements_validation_status"] = requirements_validation_status
        program["planner_ready"] = planner_ready_for_entry
        program["application_policy_loaded"] = program["id"] in program_declaration_policies
        program["support"] = {
            "discoverable": True,
            "requirements_loaded": requirements_loaded,
            "planner_ready": planner_ready_for_entry,
            "transfer_policy_loaded": has_transfer_profile,
            "application_policy_loaded": program["application_policy_loaded"],
        }
        if program["application_policy_loaded"]:
            program["application_policy"] = program_declaration_policies[program["id"]]
        if has_profile or has_primary_curriculum or has_transfer_profile:
            program["planning_id"] = planning_id
            program["planning_status"] = "planning_ready"
        results.append(program)
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
    canonical_programs_by_id = {}
    for program in results:
        canonical_id = program.get("canonical_program_id") or program["id"]
        canonical = canonical_programs_by_id.setdefault(canonical_id, {
            "id": canonical_id,
            "name": program["name"],
            "home_colleges": [],
            "affiliations": [],
            "available_as": [],
            "variants": [],
        })
        for field in ("home_colleges", "affiliations", "available_as"):
            canonical[field] = list(dict.fromkeys([
                *canonical[field], *program.get(field, [])
            ]))
        canonical["variants"].append(program)
    return {
        "catalog_year": "2026-2027",
        "count": len(results),
        "programs": results,
        "canonical_count": len(canonical_programs_by_id),
        "canonical_programs": sorted(
            canonical_programs_by_id.values(),
            key=lambda item: item["name"],
        ),
    }


@app.get("/api/electives")
def list_electives(
    term: Literal["fall", "spring"] = "fall",
    category: str = "free-elective",
    primary_major: str | None = None,
    goal_program: str | None = None,
):
    """Return real scheduled courses for the semester elective picker."""
    database = DATA_DIR / "courses.sqlite"
    prefixes = ELECTIVE_CATEGORY_PREFIXES.get(category)
    if category == "current-major":
        prefixes = PROGRAM_ELECTIVE_PREFIXES.get(primary_major or "")
    elif category == "goal-program":
        prefixes = PROGRAM_ELECTIVE_PREFIXES.get(goal_program or "")
    elif category == "general-education":
        prefixes = GENERAL_EDUCATION_PREFIXES
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
        allowed = list(MATH_EQUIVALENCY_GROUPS)
        where.append(
            f"canonical_course_id in ({','.join('?' for _ in allowed)})"
        )
        parameters.extend(allowed)
    elif prefixes:
        where.append(f"substr(canonical_course_id, 1, 2) in ({','.join('?' for _ in prefixes)})")
        parameters.extend(prefixes)

    with closing(sqlite3.connect(database)) as connection:
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
            "requirement_group": MATH_EQUIVALENCY_GROUPS.get(course_id),
            "display_group": ELECTIVE_CATEGORY_GROUPS.get(category, {}).get(
                course_id[:2]
            ),
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
                (f"{MATH_EQUIVALENCY_GROUPS[course_id]} · " if course_id in MATH_EQUIVALENCY_GROUPS else "")
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
    degree_profile = profile
    if goal_type == "internal_transfer":
        profile = transfer_policy_for_goal(PlanningGoal(
            type="internal_transfer", program=program_id
        )) or profile
    profile = dict(profile)
    profile.setdefault("source_url", official_program_source(program_id, goal_type))
    profile.setdefault("policy_status", "official_verified")
    course_names = {course["id"]: course["name"] for course in courses}
    public_profile = dict(profile)
    public_profile["requirement_groups"] = [
        {
            **group,
            "options": expand_requirement_options(group.get("options", [])),
            "catalog_rule": group.get("options", []),
        }
        for group in profile.get("requirement_groups", [])
    ]
    public_profile["choice_slots"] = sum(
        group.get("choose", 1) for group in public_profile.get("requirement_groups", [])
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
        "transfer_eligibility": public_profile if goal_type == "internal_transfer" else None,
        "post_transfer_profile_available": bool(
            goal_type == "internal_transfer"
            and program_id in POST_TRANSFER_PLAN_PROGRAMS
            and degree_profile
        ),
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
        "requirement_groups": public_profile.get("requirement_groups", []),
        "advanced_credit_policy": advanced_credit["policy"],
    }


@app.get("/api/primary-majors/{program_id}")
def get_primary_major_profile(program_id: str):
    curriculum = requirements.get(f"{program_id}-major")
    if curriculum is None or curriculum.get("planner_status") != "ready":
        raise HTTPException(status_code=404, detail="Primary-major curriculum is not configured")
    public_curriculum = resolve_curriculum_requirement_options(
        curriculum,
        resolve_requirement_option,
    )
    course_by_id = {course["id"]: course for course in courses}
    return {
        "program_id": program_id,
        "catalog_year": public_curriculum.get("catalog_year"),
        "curriculum_status": public_curriculum.get("curriculum_status"),
        "minimum_degree_units": public_curriculum.get("minimum_degree_units"),
        "fixed_courses": [
            {
                "id": course_id,
                "name": course_by_id.get(course_id, {}).get("name", "Catalog requirement"),
                "is_current_major": True,
            }
            for course_id in public_curriculum.get("required_courses", [])
        ],
        "requirement_groups": public_curriculum.get("requirement_groups", []),
        "notes": public_curriculum.get("notes", []),
    }


@app.post("/api/program-comparison")
def compare_programs(request: ComparisonRequest):
    academic_state = derive_academic_state(
        request.student.model_dump(),
        expand_completed_courses,
    )
    if request.current_goal is not None or request.alternative_goal is not None:
        if request.current_goal is None or request.alternative_goal is None:
            raise HTTPException(
                status_code=422,
                detail="Both current_goal and alternative_goal are required for a path comparison",
            )
        current_result = request.current_plan or create_plan(PlanningRequest(
            student=request.student,
            goals=[request.current_goal],
            constraints=request.constraints,
        ))
        alternative_result = create_plan(PlanningRequest(
            student=request.student,
            goals=[request.alternative_goal],
            constraints=request.constraints,
        ))
        return compare_generated_plans(
            current_result=current_result,
            alternative_result=alternative_result,
            current_goal=request.current_goal.model_dump(),
            alternative_goal=request.alternative_goal.model_dump(),
            primary_course_ids=current_major_course_universe(request.student),
            completed_courses=set(academic_state["accumulated_courses"]),
            program_names={program["id"]: program["name"] for program in programs},
        )

    selected = request.programs or [program["id"] for program in programs]
    names = {program["id"]: program["name"] for program in programs}
    current_major_courses = current_major_course_universe(request.student)
    completed_courses = set(academic_state["accumulated_courses"])
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


def recommendation_baseline_pools(plan: dict, request: CourseRecommendationRequest):
    """Reuse the existing elective catalog without claiming unverified approval."""
    pools = {}
    candidate_catalog = {}
    for semester in plan.get("path", []):
        term = semester.get("semester", request.constraints.start_semester)
        for requirement in semester.get("baseline_requirements", []):
            requirement_id = requirement["id"]
            category_policy = COURSE_RECOMMENDATION_POLICY[
                "baseline_candidate_categories"
            ].get(requirement_id)
            if not category_policy or requirement_id in pools:
                continue
            category = category_policy["category"]
            response = list_electives(
                term=term,
                category=category,
                primary_major=request.student.primary_major,
                goal_program=request.goals[0].program if request.goals else None,
            )
            options = [course["id"] for course in response["courses"]]
            verified = bool(category_policy.get("eligibility_verified")) or bool(
                requirement.get("courses")
            )
            note = (
                None
                if verified
                else "Scheduled candidate only; confirm that it satisfies this Dietrich category in SIO or with an advisor"
            )
            pools[requirement_id] = {
                "options": options,
                "eligibility_verified": verified,
                "eligibility_note": note,
            }
            for course in response["courses"]:
                existing = candidate_catalog.get(course["id"], {})
                candidate_catalog[course["id"]] = {
                    **existing,
                    **course,
                    "offered": sorted({
                        *existing.get("offered", []),
                        course["term"],
                    }),
                    "prerequisite_expression": None,
                }
    return pools, candidate_catalog


@app.post("/api/recommend-courses")
def recommend_courses(request: CourseRecommendationRequest):
    if not request.goals:
        raise HTTPException(status_code=422, detail="At least one goal is required")
    planning_request = PlanningRequest(
        student=request.student,
        goals=request.goals,
        constraints=request.constraints,
    )
    generated = (
        request.current_plan
        if request.current_plan and request.current_plan.get("course_catalog")
        else create_plan(planning_request)
    )
    fastest = generated.get("fastest", generated)
    pools, candidate_catalog = recommendation_baseline_pools(fastest, request)
    slots = recommendation_slots_from_plan(fastest, pools)
    catalog = dict(generated.get("course_catalog", {}))
    for course_id, candidate in candidate_catalog.items():
        existing = catalog.get(course_id, {})
        catalog[course_id] = {
            **candidate,
            **existing,
            "offered": sorted({
                *candidate.get("offered", []),
                *existing.get("offered", []),
            }),
        }
    goal_profile = profile_for_goal(request.goals[0]) or {}
    academic_state = derive_academic_state(
        request.student.model_dump(),
        expand_completed_courses,
    )
    result = recommend_courses_for_plan(
        plan=fastest,
        slots=slots,
        catalog=catalog,
        completed_courses=set(academic_state["accumulated_courses"]),
        primary_course_ids=current_major_course_universe(request.student),
        goal_course_ids=set(extract_course_ids_from_requirement_profile(goal_profile)),
        manual_selections=request.manual_selections,
        policy=COURSE_RECOMMENDATION_POLICY,
        requirement_ids=set(request.requirement_ids) or None,
    )
    return {
        **result,
        "policy_version": COURSE_RECOMMENDATION_POLICY["version"],
        "advisory_only": True,
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

    academic_state = derive_academic_state(
        request.student.model_dump(),
        expand_completed_courses,
    )
    baseline_student = request.student.model_dump()
    baseline_student["completed_courses"] = academic_state["accumulated_courses"]
    baseline_student["completed_requirement_ids"] = list(dict.fromkeys([
        *academic_state["completed_requirement_ids"],
        *academic_state["planned_requirement_ids"],
    ]))
    return {
        "student": request.student.model_dump(),
        "goal": goal.model_dump(),
        "baseline": get_student_planning_baseline(
            baseline_student,
            # The requirement-selection and audit screens must always show the
            # full college curriculum. Scheduling uses the narrower planning
            # horizon separately below.
            through_year=4,
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


def trim_to_transfer_application(
    path_result,
    completed_courses,
    profile_inputs,
):
    """Stop an eligibility plan in the first term when the student can apply."""
    path = path_result.get("path", [])
    if not path:
        return None

    completed = set(completed_courses)
    required_courses = set(profile_inputs.get("required_courses", []))
    required_slots = {
        slot["id"] for slot in profile_inputs.get("program_requirement_slots", [])
    }
    scheduled_slots = set()
    application_index = None

    for index, semester in enumerate(path):
        completed.update(semester.get("courses", []))
        scheduled_slots.update(
            item["id"] for item in semester.get("program_requirements", [])
            if item.get("scope", "goal") != "primary_major"
        )
        if required_courses.issubset(completed) and required_slots.issubset(scheduled_slots):
            application_index = index
            break

    # Even when eligibility was already satisfied before this planning
    # horizon, retain the next real semester for current-major coursework and
    # place the application milestone at its end.
    if application_index is None:
        return None
    application_index = max(0, application_index)
    path_result["path"] = path[:application_index + 1]
    application_semester = path_result["path"][-1]
    application_semester.setdefault("milestones", []).append({
        "id": "internal-transfer-application",
        "kind": "transfer_application",
        "name": "Apply for internal transfer",
        "description": profile_inputs.get("profile", {}).get(
            "application_milestone",
            "Submit the application after final grades for this term are available.",
        ),
    })
    return {
        "semester": application_semester["semester"],
        "academic_year": application_semester["academic_year"],
        "academic_year_name": application_semester["academic_year_name"],
    }

@app.post("/api/plan")
def create_plan(request: Union[PlanningRequest, LegacyPlanRequest]):
    goal_key, completed_courses, start_semester, max_units = planning_context(request)

    goal = request.goals[0] if isinstance(request, PlanningRequest) else None
    academic_state = None
    locked_semesters = []
    transfer_boundary = None
    effective_planning_year = (
        request.constraints.planning_year
        if isinstance(request, PlanningRequest) else 1
    )
    effective_first_semester_max_units = (
        request.constraints.first_semester_max_units
        if isinstance(request, PlanningRequest) else max_units
    )
    effective_semester_unit_limits = (
        request.constraints.semester_unit_limits
        if isinstance(request, PlanningRequest) else []
    )
    planning_student_state = (
        request.student.model_dump()
        if isinstance(request, PlanningRequest) else None
    )
    if isinstance(request, PlanningRequest):
        academic_state = derive_academic_state(
            request.student.model_dump(),
            expand_completed_courses,
        )
        completed_courses = academic_state["accumulated_courses"]
        planning_student_state["completed_courses"] = completed_courses
        planning_student_state["completed_requirement_ids"] = list(dict.fromkeys([
            *academic_state["completed_requirement_ids"],
            *academic_state["planned_requirement_ids"],
        ]))
        if goal is not None and goal.type == "internal_transfer" and goal.include_post_transfer_plan:
            locked_semesters = academic_state["locked_semesters"]
            transfer_boundary = planning_boundary_after_locked_semesters(
                locked_semesters
            )
            if transfer_boundary is not None:
                start_semester = transfer_boundary["semester"]
                effective_planning_year = transfer_boundary["academic_year"]
                effective_first_semester_max_units = max_units
                effective_semester_unit_limits = request.constraints.semester_unit_limits[
                    len(locked_semesters):
                ]
                if goal.college:
                    planning_student_state["college"] = goal.college
    if (
        isinstance(request, PlanningRequest)
        and goal is not None
        and goal.type == "minor"
        and goal.program == "machine-learning"
        and request.student.college == "scs"
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "The Machine Learning minor is available only to students outside "
                "SCS. SCS students should use the Machine Learning concentration."
            ),
        )
    profile_inputs = (
        planning_inputs_for_profile(
            goal,
            completed_courses,
            request.student.primary_major if isinstance(request, PlanningRequest) else None,
        )
        if goal is not None else None
    )
    display_profile = (
        (profile_inputs or {}).get("profile")
        or (
            program_profiles["programs"]
            .get(goal.program, {})
            .get(goal.type)
            if goal is not None
            else None
        )
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
        and profile_inputs is None
    ):
        raise HTTPException(
            status_code=409,
            detail="This goal has no configured planner requirements",
        )

    if max_units < 1:
        raise HTTPException(status_code=422, detail="max_units must be positive")

    transfer_replaces_primary = (
        isinstance(request, PlanningRequest)
        and goal is not None
        and goal.type == "internal_transfer"
        and goal.include_post_transfer_plan
    )
    current_major_courses = (
        current_major_courses_for(request.student)
        if isinstance(request, PlanningRequest) and (
            not transfer_replaces_primary
            or (
                goal is not None
                and goal.type == "internal_transfer"
                and not goal.include_post_transfer_plan
            )
        )
        else []
    )
    primary_baseline = (
        primary_baseline_for(request.student)
        if isinstance(request, PlanningRequest) else None
    )
    if transfer_replaces_primary:
        primary_baseline = {
            **primary_baseline,
            "name": "Previous primary major replaced after internal transfer",
            "units": 0,
            "status": "replaced_by_transfer",
            "note": (
                f"{goal.program} becomes the student's primary degree after transfer. "
                "The former major is not scheduled as a second degree; completed "
                "courses are reused wherever they satisfy the destination curriculum."
            ),
        }
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
        and not transfer_replaces_primary
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
                planning_student_state,
                through_year=baseline_through_year_for_plan(request),
            )["requirements"]
            if isinstance(request, PlanningRequest)
            else []
        ),
        first_semester_max_units=(
            effective_first_semester_max_units
            if (
                isinstance(request, PlanningRequest)
                and request.student.enrollment_status == "precollege"
            )
            else max_units
        ),
        semester_unit_limits=(
            effective_semester_unit_limits
            if isinstance(request, PlanningRequest)
            else []
        ),
        student_year=(effective_planning_year if isinstance(request, PlanningRequest) else 1),
        planning_year=(
            effective_planning_year
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
        and program_profiles["programs"].get(goal.program, {}).get("minor") is not None
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
                planning_student_state,
                through_year=baseline_through_year_for_plan(request),
            )["requirements"],
            first_semester_max_units=(
                request.constraints.first_semester_max_units
                if request.student.enrollment_status == "precollege"
                else max_units
            ),
            semester_unit_limits=effective_semester_unit_limits,
            student_year=effective_planning_year,
            planning_year=effective_planning_year,
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
    transfer_application_term = None
    if (
        isinstance(request, PlanningRequest)
        and goal is not None
        and goal.type == "internal_transfer"
        and not goal.include_post_transfer_plan
        and profile_inputs is not None
    ):
        transfer_application_term = trim_to_transfer_application(
            result["fastest"], completed_courses, profile_inputs
        )
        trim_to_transfer_application(
            result["lower_workload"], completed_courses, profile_inputs
        )

    result["fastest"] = attach_workload_to_path(
        result["fastest"]
            )

    result["lower_workload"] = attach_workload_to_path(
        result["lower_workload"]
        )
    if locked_semesters:
        # Workload and scheduling are calculated only for the future plan.
        # Locked history must remain byte-for-byte equivalent to the plan the
        # student approved before crossing the transfer boundary.
        prepend_locked_semesters(result["fastest"], locked_semesters)
        prepend_locked_semesters(result["lower_workload"], locked_semesters)

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
    planning_warnings = []
    if not result["fastest"].get("goal_complete"):
        remaining_courses = result["fastest"].get("remaining", [])
        remaining_groups = result["fastest"].get(
            "remaining_program_requirements", []
        )
        unscheduled_details = result["fastest"].get(
            "unscheduled_requirements", []
        )
        unscheduled = len(remaining_courses) + len(remaining_groups)
        unresolved_labels = [
            f"{item.get('name', item.get('id', 'requirement'))} "
            f"({item.get('reason', 'unknown reason').replace('_', ' ')})"
            for item in unscheduled_details
        ]
        if not unresolved_labels:
            unresolved_labels = [*remaining_courses]
            unresolved_labels.extend(
                group.get("name", group.get("id", "requirement choice"))
                if isinstance(group, dict) else str(group)
                for group in remaining_groups
            )
        unresolved_summary = ", ".join(unresolved_labels[:6])
        if len(unresolved_labels) > 6:
            unresolved_summary += f", and {len(unresolved_labels) - 6} more"
        planning_warnings.append({
            "code": "TARGET_DEADLINE_NOT_MET",
            "severity": "error",
            "requirements": unscheduled_details,
            "message": (
                f"{unscheduled} goal requirements could not be scheduled by "
                f"the selected completion year: {unresolved_summary}. "
                "They remain visible as unscheduled requirements."
            ),
        })
    if primary_baseline and primary_baseline.get("status") == "fallback_template":
        planning_warnings.append({
            "code": "PRIMARY_CURRICULUM_ESTIMATED",
            "severity": "warning",
            "message": primary_baseline["note"],
        })
    if display_profile and display_profile.get("eligibility"):
        planning_warnings.append({
            "code": "ELIGIBILITY_CHECKPOINT",
            "severity": "info",
            "message": display_profile["eligibility"],
        })
    scheduled_ids = {
        course_id
        for semester in result["fastest"]["path"]
        for course_id in semester.get("courses", [])
    }
    course_by_id = {course["id"]: course for course in courses}
    unverified_prerequisites = sorted(
        course_id for course_id in scheduled_ids
        if course_by_id.get(course_id, {}).get(
            "prerequisite_data_status", "catalog_not_imported"
        ) != "verified"
    )
    if unverified_prerequisites:
        planning_warnings.append({
            "code": "PREREQUISITE_DATA_INCOMPLETE",
            "severity": "warning",
            "course_ids": unverified_prerequisites,
            "message": (
                f"Prerequisite data is not fully verified for "
                f"{len(unverified_prerequisites)} scheduled courses."
            ),
        })
    audit_student = (
        request.student.model_copy(update={
            "completed_courses": academic_state["completed_courses"],
        })
        if isinstance(request, PlanningRequest) and academic_state is not None
        else None
    )
    degree_audits = (
        build_degree_audits(
            audit_student,
            goal,
            display_profile,
            result["fastest"],
            primary_baseline,
            resolve_curriculum_requirement_options(
                requirements.get(f"{request.student.primary_major}-major"),
                resolve_requirement_option,
            ),
            {
                "required_courses": goal_requirements.get("required_courses", []),
                "requirement_groups": goal_requirements.get("requirement_groups", []),
            },
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
        "planning_warnings": planning_warnings,
        "overlap_summary": {
            "courses": shared_course_ids,
            "units": sum(
                course["units"]
                for course in courses
                if course["id"] in shared_course_ids
            ),
            "current_major_scope": (primary_baseline or {}).get("status"),
        },
        "program_profile": display_profile,
        "transfer_planning": (
            {
                "mode": "post_transfer_degree" if (
                    goal.include_post_transfer_plan
                    and goal.program in POST_TRANSFER_PLAN_PROGRAMS
                ) else "eligibility",
                "policy": transfer_policy_for_goal(goal),
                "post_transfer_plan_available": goal.program in POST_TRANSFER_PLAN_PROGRAMS,
                "application_term": transfer_application_term,
                "effective_term": transfer_boundary,
                "locked_semester_count": len(locked_semesters),
            }
            if goal is not None and goal.type == "internal_transfer"
            else None
        ),
        "course_catalog": {
            course["id"]: {
                "name": course["name"],
                "units": course["units"],
                "metadata_status": (
                    "catalog_zero_unit"
                    if course["units"] == 0
                    else "available"
                ),
                "source": course.get("source"),
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
        "path_alternatives": (
            discover_path_alternatives(
                goal.model_dump(),
                request.student.model_dump(),
                PATH_ALTERNATIVES,
                program_profiles,
                {program["id"]: program["name"] for program in programs},
            )
            if isinstance(request, PlanningRequest) and goal is not None
            else []
        ),
    }


def verified_transfer_context(request: PlanningRequest, plan: dict) -> dict:
    """Return only server-produced facts that the advisor may discuss."""
    goal = request.goals[0]
    transfer = plan["transfer_planning"]
    policy = transfer["policy"] or {}
    return {
        "student": {
            "college": request.student.college,
            "primary_major": request.student.primary_major,
            "year": request.student.year,
            "current_term": request.student.current_term,
            "completed_courses": request.student.completed_courses,
        },
        "transfer_goal": {
            "program": goal.program,
            "target_college": goal.college,
            "planning_mode": transfer["mode"],
            "target_completion_year": plan["target_completion_year"],
        },
        "verified_policy": {
            key: policy.get(key)
            for key in (
                "policy_status", "eligibility", "minimum_grade",
                "minimum_overall_gpa", "minimum_core_gpa", "capacity_limited",
                "application_timing", "required_course_ids",
                "requirement_groups", "preparation_courses",
                "application_requirements", "source_url",
            )
        },
        "generated_plan": [
            {
                "year": semester["academic_year_name"],
                "term": semester["semester"],
                "total_units": semester["total_units"],
                "unit_limit": semester["unit_limit"],
                "courses": [
                    {
                        "id": block["id"],
                        "name": block["name"],
                        "units": block["units"],
                        "kind": block["kind"],
                    }
                    for block in semester["course_blocks"]
                    if not block.get("estimated")
                ],
            }
            for semester in plan["fastest"]["path"]
        ],
        "planner_assessment": {
            "goal_complete": plan["fastest"]["goal_complete"],
            "remaining_requirements": plan["fastest"]["remaining_program_requirements"],
            "warnings": plan["planning_warnings"],
            "overlap": plan["overlap_summary"],
        },
    }


@app.post("/api/transfer-advice")
def transfer_advice(request: PlanningRequest):
    if not request.goals or request.goals[0].type != "internal_transfer":
        raise HTTPException(
            status_code=422,
            detail="AI Transfer Advisor is available only for internal-transfer plans.",
        )
    # Re-run the existing deterministic planner server-side. The model never
    # receives or calculates requirements from unverified frontend state.
    plan = create_plan(request)
    context = verified_transfer_context(request, plan)
    provider = os.environ.get("TRANSFER_ADVISOR_PROVIDER", "auto").lower()
    if provider not in {"auto", "ollama", "openai"}:
        raise HTTPException(
            status_code=500,
            detail="TRANSFER_ADVISOR_PROVIDER must be auto, ollama, or openai.",
        )

    ollama_error = None
    if provider in {"auto", "ollama"}:
        try:
            return request_ollama_transfer_advice(context)
        except requests.HTTPError as error:
            ollama_error = error
        except (requests.RequestException, ValueError, json.JSONDecodeError) as error:
            ollama_error = error

    api_key = os.environ.get("OPENAI_API_KEY")
    if provider in {"auto", "openai"} and api_key:
        return request_openai_transfer_advice(context, api_key)

    if provider == "openai":
        raise HTTPException(
            status_code=503,
            detail="OpenAI mode is not configured. Set OPENAI_API_KEY on the server.",
        )

    if isinstance(ollama_error, requests.HTTPError):
        response = ollama_error.response
        status = response.status_code if response is not None else None
        if status == 404:
            detail = (
                "The free local model is not installed. Run: ollama pull qwen3:1.7b"
            )
        else:
            detail = "Ollama is running but could not generate the advisor analysis."
    else:
        detail = (
            "Free local AI is not running. Install Ollama, run "
            "'ollama pull qwen3:1.7b', then try again."
        )
    raise HTTPException(status_code=503, detail=detail)


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
