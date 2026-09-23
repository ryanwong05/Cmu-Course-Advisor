"""Small, data-backed helpers for academic requirement policies."""

import json
import re
import sqlite3
from copy import deepcopy
from contextlib import closing
from pathlib import Path


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def load_transfer_requirements(policy_dir: Path) -> dict:
    """Load transfer policies and resolve their source references."""
    requirements = deepcopy(
        _load_json(policy_dir / "transfer_requirements.json")
    )
    sources = _load_json(policy_dir / "policy_sources.json").get("sources", {})

    profiles = [
        *requirements.get("eligibility_profiles", {}).values(),
        requirements.get("scs_transfer", {}).get("defaults", {}),
    ]
    for profile in profiles:
        source_id = profile.pop("source_id", None)
        if source_id:
            profile["source_url"] = sources[source_id]["url"]

    return requirements


def get_transfer_profile(
    program_id: str,
    transfer_requirements: dict,
    program_profiles: dict,
) -> dict | None:
    """Return the normalized admission policy for one transfer target."""
    policy = transfer_requirements.get("eligibility_profiles", {}).get(program_id)
    if policy is None:
        policy = program_profiles.get("programs", {}).get(program_id, {}).get(
            "internal_transfer"
        )
    if policy is None:
        return None

    policy = dict(policy)
    scs_transfer = transfer_requirements.get("scs_transfer", {})
    if program_id in scs_transfer.get("programs", []):
        policy = {**scs_transfer.get("defaults", {}), **policy}
        if "15-122" in policy.get("required_course_ids", []):
            policy.setdefault("preparation_courses", ["15-112"])
    return policy


def find_official_program_source(
    program_directory: list[dict],
    program_id: str,
    goal_type: str,
) -> str | None:
    """Find the catalog source already attached to a directory entry."""
    directory_type = "primary_major" if goal_type == "internal_transfer" else goal_type
    return next((
        item.get("source_url")
        for item in program_directory
        if item.get("planning_id") == program_id
        and item.get("program_type") == directory_type
        and item.get("source_url")
    ), None)


def find_courses_matching_pattern(option: str, database: Path) -> list[str]:
    """Expand an XX-Xxx course pattern using scheduled course data."""
    match = re.fullmatch(r"(\d{2})-(\d)xx", option, re.IGNORECASE)
    if not match:
        return []
    prefix, level = match.groups()
    with closing(sqlite3.connect(database)) as connection:
        rows = connection.execute(
            """
            select distinct canonical_course_id
            from courses
            where substr(canonical_course_id, 1, 2) = ?
              and substr(canonical_course_id, 4, 1) = ?
            """,
            (prefix, level),
        ).fetchall()
    return [row[0] for row in rows]


def find_courses_from_named_set(
    set_id: str,
    named_course_sets: dict,
    planning_courses: list[dict],
    database: Path,
) -> list[str]:
    """Resolve one named candidate set from its data-defined filtering rule."""
    rule = named_course_sets.get(set_id)
    if not rule:
        return []

    prefixes = rule.get("department_prefixes", [])
    source = rule.get("source", "course_database")
    minimum_course_number = rule.get("minimum_course_number")
    maximum_course_number = rule.get("maximum_course_number")
    explicit_courses = rule.get("courses", [])
    excluded_courses = set(rule.get("excluded_courses", []))
    if source == "planning_course_graph":
        matched = [
            course["id"]
            for course in planning_courses
            if (not prefixes or course["id"][:2] in prefixes)
            and (
                minimum_course_number is None
                or int(course["id"].split("-")[1]) >= minimum_course_number
            )
            and (
                maximum_course_number is None
                or int(course["id"].split("-")[1]) <= maximum_course_number
            )
        ]
        return [
            course_id
            for course_id in dict.fromkeys([*explicit_courses, *matched])
            if course_id not in excluded_courses
        ]
    if not prefixes:
        return [
            course_id
            for course_id in dict.fromkeys(explicit_courses)
            if course_id not in excluded_courses
        ]

    placeholders = ",".join("?" for _ in prefixes)
    query = f"""
        select distinct canonical_course_id
        from courses
        where substr(canonical_course_id, 1, 2) in ({placeholders})
    """
    parameters = list(prefixes)
    if minimum_course_number is not None:
        query += """
            and cast(substr(canonical_course_id, 4, 3) as integer) >= ?
        """
        parameters.append(minimum_course_number)
    if maximum_course_number is not None:
        query += """
            and cast(substr(canonical_course_id, 4, 3) as integer) <= ?
        """
        parameters.append(maximum_course_number)
    with closing(sqlite3.connect(database)) as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [
        course_id
        for course_id in dict.fromkeys([
            *explicit_courses,
            *(row[0] for row in rows),
        ])
        if course_id not in excluded_courses
    ]


def resolve_data_requirement_option(
    option: str,
    pattern_resolver,
    named_set_resolver,
) -> list[str]:
    """Resolve a concrete course, bundle, pattern, or named set."""
    option = option.strip()
    if re.fullmatch(r"\d{2}-\d{3}", option):
        return [option]
    bundle_courses = [course_id.strip() for course_id in option.split(" + ")]
    if len(bundle_courses) > 1 and all(
        re.fullmatch(r"\d{2}-\d{3}", course_id)
        for course_id in bundle_courses
    ):
        return [" + ".join(bundle_courses)]
    if re.fullmatch(r"\d{2}-\dxx", option, re.IGNORECASE):
        return pattern_resolver(option)
    named_set_prefix = "named_set:"
    if option.startswith(named_set_prefix):
        return named_set_resolver(option.removeprefix(named_set_prefix))
    return []


def expand_profile_requirement_options(
    raw_options: list[str],
    planning_courses: list[dict],
    requirement_option_sets: dict,
    course_pattern_constraints: dict,
    named_set_resolver,
    program_profiles: dict,
) -> list[str]:
    """Expand program-profile options using data-defined candidate rules."""
    expanded = []
    course_ids = [course["id"] for course in planning_courses]

    def matching_courses(pattern: str) -> list[str]:
        match = re.fullmatch(r"(\d{2})-(\d|x)xx", pattern.lower())
        if not match:
            return []
        department, level = match.groups()
        constraints = {
            **course_pattern_constraints.get("default", {}),
            **course_pattern_constraints.get(pattern, {}),
        }
        minimum = constraints.get("minimum_course_number", 0)
        maximum = constraints.get("maximum_course_number", 999)
        return [
            course_id
            for course_id in course_ids
            if course_id.startswith(f"{department}-")
            and (level == "x" or course_id.split("-")[1].startswith(level))
            and minimum <= int(course_id.split("-")[1]) <= maximum
        ]

    for option in raw_options:
        if re.fullmatch(r"\d{2}-(\d|x)xx", option.lower()):
            expanded.extend(matching_courses(option))
            continue

        rule = requirement_option_sets.get(option)
        if rule is None:
            expanded.append(option)
            continue

        candidates = []
        pattern_candidates = {
            course_id
            for pattern in rule.get("course_patterns", [])
            for course_id in matching_courses(pattern)
        }
        candidates.extend(
            course_id for course_id in course_ids
            if course_id in pattern_candidates
        )
        candidates.extend(rule.get("courses", []))

        named_set = rule.get("named_course_set")
        if named_set:
            named_candidates = set(named_set_resolver(named_set))
            candidates.extend(
                course_id for course_id in course_ids
                if course_id in named_candidates
            )

        profile_reference = rule.get("profile_requirement_groups")
        if profile_reference:
            profile = (
                program_profiles.get("programs", {})
                .get(profile_reference["program"], {})
                .get(profile_reference["goal_type"], {})
            )
            group_ids = set(profile_reference.get("group_ids", []))
            candidates.extend(
                candidate
                for group in profile.get("requirement_groups", [])
                if group.get("id") in group_ids
                for candidate in group.get("options", [])
            )

        minimum = rule.get("minimum_course_number", 0)
        maximum = rule.get("maximum_course_number", 999)
        expanded.extend(
            course_id
            for course_id in candidates
            if not re.fullmatch(r"\d{2}-\d{3}", course_id)
            or minimum <= int(course_id.split("-")[1]) <= maximum
        )

    return list(dict.fromkeys(expanded))


def apply_requirement_option_preferences(
    options: list[str],
    preferred_options: list[str],
) -> list[str]:
    """Apply stable, data-defined recommendation ordering to valid options."""
    preferred_rank = {
        option: index
        for index, option in enumerate(preferred_options)
    }
    return sorted(
        options,
        key=lambda option: (
            option not in preferred_rank,
            preferred_rank.get(option, 0),
        ),
    )


def resolve_curriculum_requirement_options(
    curriculum: dict | None,
    option_resolver,
) -> dict | None:
    """Return a curriculum whose group options are concrete planner choices."""
    if curriculum is None:
        return None
    resolved = dict(curriculum)
    resolved["requirement_groups"] = []
    for group in curriculum.get("requirement_groups", []):
        options = []
        for option in group.get("options", []):
            options.extend(option_resolver(option))
        resolved["requirement_groups"].append({
            **group,
            "options": list(dict.fromkeys(options)),
        })
    return resolved


def get_program_requirement_adjustment(
    adjustments: dict,
    primary_major: str | None,
    goal_type: str,
    program_id: str,
) -> dict:
    """Return an optional data-defined planning adjustment for one program pair."""
    key = f"{primary_major}|{goal_type}|{program_id}"
    return adjustments.get(key, {})


def extract_profile_course_ids(profile: dict, pattern_resolver) -> list[str]:
    """Extract concrete course IDs referenced by one requirement profile."""
    course_ids = set(profile.get("required_courses", []))
    course_ids.update(profile.get("required_course_ids", []))
    for group in profile.get("requirement_groups", []):
        for raw_option in group.get("options", []):
            for option in raw_option.split(" + "):
                if re.fullmatch(r"\d{2}-\d{3}", option):
                    course_ids.add(option)
                elif re.fullmatch(r"\d{2}-\dxx", option, re.IGNORECASE):
                    course_ids.update(pattern_resolver(option))
    return sorted(course_ids)


def collect_requirement_course_ids(
    primary_requirements: dict,
    program_profiles: dict,
    profile_extractor,
) -> list[str]:
    """Collect all concrete courses referenced by configured programs."""
    course_ids = set()
    for requirement in primary_requirements.values():
        course_ids.update(profile_extractor(requirement))
    for profiles_by_type in program_profiles.get("programs", {}).values():
        for profile in profiles_by_type.values():
            course_ids.update(profile_extractor(profile))
    return sorted(course_ids)


def hydrate_courses_from_schedule(
    course_list: list[dict],
    course_ids: list[str],
    database: Path,
    prerequisites: dict,
    recommended_earliest_year: dict,
) -> None:
    """Add selected scheduled courses to the small planning graph."""
    if not course_ids:
        return
    existing = {course["id"]: course for course in course_list}
    placeholders = ",".join("?" for _ in course_ids)
    with closing(sqlite3.connect(database)) as connection:
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
        schedule_terms = sorted(
            term for term in (offered or "").split(",") if term
        )
        units = units if units is not None else 9
        if course_id in existing:
            existing[course_id]["offered"] = schedule_terms
            continue
        course_list.append({
            "id": course_id,
            "name": title,
            "units": int(units) if float(units).is_integer() else units,
            "prerequisites": prerequisites.get(course_id, []),
            "prerequisite_data_status": (
                "curated_mapping"
                if course_id in prerequisites
                else "catalog_not_imported"
            ),
            "offered": schedule_terms,
            "minimum_year": recommended_earliest_year.get(course_id, 1),
            "source": "processed_schedule_sqlite",
        })


def expand_course_completion(
    course_ids: list[str],
    completion_implications: dict,
) -> list[str]:
    """Return a stable, de-duplicated completion implication closure."""
    completed = list(dict.fromkeys(course_ids))
    index = 0
    while index < len(completed):
        for implied_id in completion_implications.get(completed[index], []):
            if implied_id not in completed:
                completed.append(implied_id)
        index += 1
    return completed


def primary_major_required_courses(
    primary_major: str,
    primary_requirements: dict,
) -> list[str]:
    curriculum = primary_requirements.get(f"{primary_major}-major", {})
    return curriculum.get("required_courses", [])


def primary_major_course_universe(
    primary_major: str,
    primary_requirements: dict,
    profile_extractor,
) -> set[str]:
    curriculum = primary_requirements.get(f"{primary_major}-major", {})
    return set(profile_extractor(curriculum))


def build_primary_major_requirement_slots(
    primary_major: str,
    completed_courses: list[str],
    primary_requirements: dict,
    option_resolver,
) -> list[dict]:
    """Build choice slots from one data-defined primary-major curriculum."""
    completed = set(completed_courses)
    slots = []
    curriculum = primary_requirements.get(f"{primary_major}-major", {})
    for group in curriculum.get("requirement_groups", []):
        group_options = []
        for option in group.get("options", []):
            group_options.extend(option_resolver(option))
        group_options = list(dict.fromkeys(group_options))
        group_options = apply_requirement_option_preferences(
            group_options,
            group.get("preferred_options", []),
        )
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
                "units": (
                    int(per_choice_units)
                    if per_choice_units.is_integer()
                    else per_choice_units
                ),
                "options": group_options,
                "minimum_year": group.get("minimum_year", 1),
                "offered": group.get("offered", []),
                "program_tier": "current_major",
                "scope": "primary_major",
            })
    return slots
