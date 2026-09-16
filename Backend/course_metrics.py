"""Course workload and difficulty metrics used by API responses."""

import sqlite3
from contextlib import closing
from pathlib import Path


def load_fce_course_averages(database: Path) -> dict:
    """Precompute historical average weekly workload for each course."""
    with closing(sqlite3.connect(database)) as connection:
        return {
            course_id: {
                "hours_per_week": hours,
                "responses": responses,
            }
            for course_id, hours, responses in connection.execute(
                """
                select canonical_course_id,
                       avg(hrs_per_week),
                       count(hrs_per_week)
                from fce_courses
                where hrs_per_week is not null
                  and hrs_per_week > 0
                group by canonical_course_id
                """
            )
        }


def calculate_five_level_course_metric(
    course_id: str,
    units: float,
    curated_metrics: dict,
    fce_averages: dict,
    intensity_labels: dict[int, str],
) -> dict:
    """Return the existing five-level course intensity assessment."""
    curated = curated_metrics.get(course_id)
    fce = fce_averages.get(course_id)
    level = int(course_id.split("-")[1][0]) if "-" in course_id else 1

    if curated:
        hours = float(curated.get("hours_per_week", units / 3))
        workload = float(curated.get("workload", 3))
        difficulty = float(curated.get("difficulty", workload))
        source = curated.get("source", "curated_estimate")
    else:
        hours = float(
            fce["hours_per_week"]
            if fce
            else units / 3
        )
        workload = max(1, min(5, 1 + (hours - 3) / 3))
        difficulty = max(
            1,
            min(
                5,
                1.7
                + level * 0.45
                + max(0, hours - 8) * 0.08,
            ),
        )
        source = (
            "historical_fce"
            if fce
            else "units_and_course_level_estimate"
        )

    composite = (workload + difficulty) / 2
    tier = (
        1 if composite < 1.8
        else 2 if composite < 2.6
        else 3 if composite < 3.4
        else 4 if composite < 4.2
        else 5
    )

    return {
        "tier": tier,
        "label": intensity_labels[tier],
        "score": round(composite, 1),
        "workload": round(workload, 1),
        "difficulty": round(difficulty, 1),
        "hours_per_week": round(hours, 1),
        "source": source,
        "sample_size": (fce or {}).get("responses", 0),
    }
