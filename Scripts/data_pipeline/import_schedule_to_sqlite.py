from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.setting import settings


DEFAULT_JSON_PATH = settings.dataStoragePath / "cmu_schedule_classes.json"
DEFAULT_DB_PATH = settings.database_path
DEPT_MAP_PATH = settings.dataStoragePath / "reference" / "dept_map.json"


def clean_text(value: object) -> str:
    return str(value or "").strip()


def to_float(value: str) -> float | None:
    value = clean_text(value)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def slugify(value: str) -> str:
    value = clean_text(value).lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def build_course_key(semester_name: str, num: str, title: str) -> str:
    parts = [slugify(semester_name), clean_text(num), slugify(title)]
    return "__".join(parts)


def load_dept_mapping_config() -> tuple[dict[str, str], dict[str, str]]:
    if not DEPT_MAP_PATH.exists():
        return {}, {}

    payload = json.loads(DEPT_MAP_PATH.read_text(encoding="utf-8"))
    legacy_code_map = {
        clean_text(key).upper(): clean_text(value).upper()
        for key, value in (payload.get("legacy_code_map") or {}).items()
        if clean_text(key) and clean_text(value)
    }
    manual_prefix_map = {
        clean_text(key): clean_text(value).upper()
        for key, value in (payload.get("manual_prefix_map") or {}).items()
        if clean_text(key) and clean_text(value)
    }
    return legacy_code_map, manual_prefix_map


def canonicalize_dept(dept: str | None, legacy_code_map: dict[str, str]) -> str | None:
    dept = clean_text(dept).upper()
    if not dept:
        return None
    return legacy_code_map.get(dept, dept)


def build_dept_resolver(db_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    num_to_dept: dict[str, str] = {}
    prefix_to_dept: dict[str, str] = {}
    legacy_code_map, manual_prefix_map = load_dept_mapping_config()

    if not db_path.exists():
        return num_to_dept, prefix_to_dept

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'fce_courses'
            """
        )
        if cursor.fetchone() is None:
            return num_to_dept, prefix_to_dept

        cursor.execute(
            """
            SELECT num, dept, year
            FROM fce_courses
            WHERE num IS NOT NULL
              AND TRIM(num) <> ''
              AND dept IS NOT NULL
              AND TRIM(dept) <> ''
            """
        )
        rows = cursor.fetchall()

    num_history: dict[str, list[tuple[int, str]]] = defaultdict(list)
    prefix_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for num, dept, year in rows:
        normalized_num = clean_text(num)
        normalized_dept = canonicalize_dept(dept, legacy_code_map)
        if not normalized_num or not normalized_dept:
            continue
        normalized_year = int(year or 0)
        num_history[normalized_num].append((normalized_year, normalized_dept))
        prefix_counts[normalized_num[:2]][normalized_dept] += 1

    for num, history in num_history.items():
        unique_depts = sorted({dept for _, dept in history})
        if len(unique_depts) == 1:
            num_to_dept[num] = unique_depts[0]
            continue

        latest_year = max(year for year, _ in history)
        latest_depts = sorted({dept for year, dept in history if year == latest_year})
        if len(latest_depts) == 1:
            num_to_dept[num] = latest_depts[0]

    for prefix, counter in prefix_counts.items():
        most_common = counter.most_common(1)
        if not most_common:
            continue
        dept, count = most_common[0]
        total = sum(counter.values())
        if total and (count / total) >= 0.95:
            prefix_to_dept[prefix] = dept

    prefix_to_dept.update(manual_prefix_map)
    return num_to_dept, prefix_to_dept


def infer_dept(num: str, num_to_dept: dict[str, str], prefix_to_dept: dict[str, str]) -> str | None:
    normalized_num = clean_text(num)
    if not normalized_num:
        return None
    if normalized_num in num_to_dept:
        return num_to_dept[normalized_num]
    return prefix_to_dept.get(normalized_num[:2])


def load_schedule_data(json_path: Path) -> dict[str, dict[str, dict[str, object]]]:
    if not json_path.exists():
        raise FileNotFoundError(f"Schedule JSON not found: {json_path}")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Schedule JSON root must be an object keyed by semester name.")
    return payload


def ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            semester_name TEXT NOT NULL,
            semester_slug TEXT NOT NULL,
            dept TEXT,
            num TEXT NOT NULL,
            title TEXT NOT NULL,
            units_raw TEXT,
            units REAL,
            section_count INTEGER NOT NULL DEFAULT 0,
            course_info_json TEXT NOT NULL,
            source_file TEXT NOT NULL,
            course_key TEXT NOT NULL,
            row_hash TEXT NOT NULL UNIQUE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS course_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            semester_name TEXT NOT NULL,
            semester_slug TEXT NOT NULL,
            num TEXT NOT NULL,
            title TEXT NOT NULL,
            units_raw TEXT,
            units REAL,
            section_index INTEGER NOT NULL,
            lec_sec TEXT,
            days TEXT,
            begin_time TEXT,
            end_time TEXT,
            location TEXT,
            section_hash TEXT NOT NULL UNIQUE,
            FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
        )
        """
    )
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_courses_num ON courses(num)",
        "CREATE INDEX IF NOT EXISTS idx_courses_semester_num ON courses(semester_slug, num)",
        "CREATE INDEX IF NOT EXISTS idx_courses_title ON courses(title)",
        "CREATE INDEX IF NOT EXISTS idx_sections_course_id ON course_sections(course_id)",
        "CREATE INDEX IF NOT EXISTS idx_sections_num ON course_sections(num)",
        "CREATE INDEX IF NOT EXISTS idx_sections_semester_num ON course_sections(semester_slug, num)",
    ]
    for statement in indexes:
        conn.execute(statement)


def reset_tables(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM course_sections")
    conn.execute("DELETE FROM courses")


def import_schedule(json_path: Path, db_path: Path) -> tuple[int, int]:
    data = load_schedule_data(json_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    num_to_dept, prefix_to_dept = build_dept_resolver(db_path)

    course_count = 0
    section_count = 0

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        ensure_tables(conn)
        reset_tables(conn)

        for semester_name, semester_courses in data.items():
            if not isinstance(semester_courses, dict):
                continue

            semester_slug = slugify(semester_name)

            for num, raw_course in semester_courses.items():
                if not isinstance(raw_course, dict):
                    continue

                dept = infer_dept(str(num), num_to_dept, prefix_to_dept)
                title = clean_text(raw_course.get("title"))
                units_raw = clean_text(raw_course.get("units"))
                units = to_float(units_raw)
                course_info = raw_course.get("course_info") or []

                normalized_sections: list[dict[str, str]] = []
                for item in course_info:
                    if not isinstance(item, dict):
                        continue
                    normalized_sections.append(
                        {
                            "lec_sec": clean_text(item.get("lec_sec")),
                            "days": clean_text(item.get("days")),
                            "begin": clean_text(item.get("begin")),
                            "end": clean_text(item.get("end")),
                            "location": clean_text(item.get("location")),
                        }
                    )

                course_key = build_course_key(semester_name, str(num), title)
                course_info_json = json.dumps(normalized_sections, ensure_ascii=False)
                row_payload = "|".join(
                    [
                        semester_name,
                        str(num),
                        title,
                        units_raw,
                        course_info_json,
                    ]
                )
                row_hash = hashlib.sha256(row_payload.encode("utf-8")).hexdigest()

                cursor = conn.execute(
                    """
                    INSERT INTO courses (
                        semester_name,
                        semester_slug,
                        dept,
                        num,
                        title,
                        units_raw,
                        units,
                        section_count,
                        course_info_json,
                        source_file,
                        course_key,
                        row_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        semester_name,
                        semester_slug,
                        dept,
                        clean_text(num),
                        title,
                        units_raw,
                        units,
                        len(normalized_sections),
                        course_info_json,
                        str(json_path),
                        course_key,
                        row_hash,
                    ),
                )
                course_id = cursor.lastrowid
                course_count += 1

                for index, section in enumerate(normalized_sections, start=1):
                    section_payload = "|".join(
                        [
                            str(course_id),
                            str(index),
                            section["lec_sec"],
                            section["days"],
                            section["begin"],
                            section["end"],
                            section["location"],
                        ]
                    )
                    section_hash = hashlib.sha256(section_payload.encode("utf-8")).hexdigest()
                    conn.execute(
                        """
                        INSERT INTO course_sections (
                            course_id,
                            semester_name,
                            semester_slug,
                            num,
                            title,
                            units_raw,
                            units,
                            section_index,
                            lec_sec,
                            days,
                            begin_time,
                            end_time,
                            location,
                            section_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            course_id,
                            semester_name,
                            semester_slug,
                            clean_text(num),
                            title,
                            units_raw,
                            units,
                            index,
                            section["lec_sec"],
                            section["days"],
                            section["begin"],
                            section["end"],
                            section["location"],
                            section_hash,
                        ),
                    )
                    section_count += 1

        conn.commit()

    return course_count, section_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CMU schedule JSON into SQLite.")
    parser.add_argument(
        "--json",
        dest="json_path",
        type=Path,
        default=DEFAULT_JSON_PATH,
        help=f"Path to the schedule JSON file. Default: {DEFAULT_JSON_PATH}",
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to the SQLite database. Default: {DEFAULT_DB_PATH}",
    )
    args = parser.parse_args()

    courses, sections = import_schedule(args.json_path, args.db_path)
    print(f"Imported {courses} course rows")
    print(f"Imported {sections} section rows")
    print(f"Source JSON: {args.json_path}")
    print(f"SQLite DB: {args.db_path}")


if __name__ == "__main__":
    main()
