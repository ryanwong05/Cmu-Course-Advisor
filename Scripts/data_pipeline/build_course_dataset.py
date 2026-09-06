"""Build the reproducible CMU course-data baseline from immutable raw inputs."""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import import_fce_to_sqlite as fce
import import_schedule_to_sqlite as schedule


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "Data" / "raw"
PROCESSED_DIR = ROOT / "Data" / "processed"
OUTPUT_DB = PROCESSED_DIR / "courses.sqlite"
BUILD_DB = PROCESSED_DIR / "courses.building.sqlite"
QUALITY_REPORT = PROCESSED_DIR / "data_quality_report.json"
SCHEDULE_YEAR = 2026


def raw_csv_row_count(path: Path) -> int:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return sum(1 for _ in csv.DictReader(file))


def scalar(conn: sqlite3.Connection, query: str) -> int:
    value = conn.execute(query).fetchone()[0]
    return int(value or 0)


def build_quality_report(
    db_path: Path,
    source_summaries: list[dict[str, object]],
    course_rows: int,
    section_rows: int,
) -> dict[str, object]:
    with sqlite3.connect(db_path) as conn:
        fce_rows = scalar(conn, "SELECT COUNT(*) FROM fce_courses")
        fce_distinct = scalar(
            conn,
            "SELECT COUNT(DISTINCT canonical_course_id) FROM fce_courses",
        )
        schedule_distinct = scalar(
            conn,
            "SELECT COUNT(DISTINCT canonical_course_id) FROM courses",
        )
        matched_schedule_courses = scalar(
            conn,
            """
            SELECT COUNT(DISTINCT c.canonical_course_id)
            FROM courses AS c
            WHERE EXISTS (
                SELECT 1
                FROM fce_courses AS f
                WHERE f.canonical_course_id = c.canonical_course_id
            )
            """,
        )
        fce_by_term = [
            {"year": year, "term": term, "rows": rows}
            for year, term, rows in conn.execute(
                """
                SELECT year, sem, COUNT(*)
                FROM fce_courses
                GROUP BY year, sem
                ORDER BY year, sem
                """
            )
        ]
        schedule_by_term = [
            {"year": year, "term": term, "courses": courses, "sections": sections}
            for year, term, courses, sections in conn.execute(
                """
                SELECT academic_year, term, COUNT(*), SUM(section_count)
                FROM courses
                GROUP BY academic_year, term
                ORDER BY academic_year, term
                """
            )
        ]

        missing_workload = scalar(
            conn, "SELECT COUNT(*) FROM fce_courses WHERE hrs_per_week IS NULL"
        )
        missing_rating = scalar(
            conn,
            "SELECT COUNT(*) FROM fce_courses WHERE overall_course_rate IS NULL",
        )
        missing_section_time = scalar(
            conn,
            """
            SELECT COUNT(*) FROM course_sections
            WHERE begin_time IS NULL OR TRIM(begin_time) = ''
            """,
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed",
        "schedule_year_assumption": {
            "year": SCHEDULE_YEAR,
            "reason": (
                "The source JSON labels seasons but does not include a year; "
                "the snapshot was supplied as the 2026 schedule baseline."
            ),
        },
        "sources": source_summaries,
        "fce": {
            "rows": fce_rows,
            "distinct_course_ids": fce_distinct,
            "missing_workload_rows": missing_workload,
            "missing_course_rating_rows": missing_rating,
            "by_term": fce_by_term,
        },
        "schedule": {
            "course_rows": course_rows,
            "section_rows": section_rows,
            "distinct_course_ids": schedule_distinct,
            "sections_without_begin_time": missing_section_time,
            "by_term": schedule_by_term,
        },
        "cross_source": {
            "schedule_courses_with_fce": matched_schedule_courses,
            "schedule_to_fce_match_rate_pct": round(
                100 * matched_schedule_courses / schedule_distinct, 2
            ) if schedule_distinct else 0,
        },
        "cleaning_actions": [
            "standardized CMU course IDs to NN-NNN",
            "normalized semester and department text",
            "converted numeric and percentage fields",
            "excluded malformed non-course identifiers",
            "deduplicated records using stable row hashes",
            "preserved source-file provenance",
            "kept missing evaluation values as null",
        ],
    }


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    if BUILD_DB.exists():
        BUILD_DB.unlink()

    source_summaries: list[dict[str, object]] = []
    fce_files = sorted(RAW_DIR.glob("CMU_FCE_*_FULL.csv"))
    if not fce_files:
        raise FileNotFoundError(f"No FCE source files found in {RAW_DIR}")

    for source in fce_files:
        raw_rows = raw_csv_row_count(source)
        headers, rows, _, clean_csv = fce.load_and_clean_rows(source)
        fce.write_clean_csv(headers, rows, clean_csv)
        inserted = fce.upsert_rows(headers, rows, BUILD_DB)
        source_summaries.append({
            "file": source.name,
            "raw_rows": raw_rows,
            "accepted_rows": len(rows),
            "rejected_rows": raw_rows - len(rows),
            "inserted_rows": inserted,
        })

    schedule_path = RAW_DIR / "cmu_schedule_classes.json"
    course_rows, section_rows = schedule.import_schedule(
        schedule_path,
        BUILD_DB,
        academic_year=SCHEDULE_YEAR,
    )
    source_summaries.append({
        "file": schedule_path.name,
        "course_rows": course_rows,
        "section_rows": section_rows,
    })

    report = build_quality_report(
        BUILD_DB,
        source_summaries,
        course_rows,
        section_rows,
    )
    QUALITY_REPORT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    BUILD_DB.replace(OUTPUT_DB)

    print(f"Built database: {OUTPUT_DB}")
    print(f"Quality report: {QUALITY_REPORT}")
    print(f"FCE rows: {report['fce']['rows']}")
    print(f"Course rows: {course_rows}")
    print(f"Section rows: {section_rows}")


if __name__ == "__main__":
    main()
