from __future__ import annotations

import csv
import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_FCE_DIR = PROCESSED_DIR / "fce"
DB_PATH = PROCESSED_DIR / "courses.sqlite"
TABLE_NAME = "fce_courses"

HEADER_RENAMES = {
    "# Responses": "response_count",
    "Total # Students": "total_students",
    "Response Rate": "response_rate_raw",
    "Hrs Per Week": "hrs_per_week",
}

INT_FIELDS = {"year", "total_students", "response_count"}
REAL_FIELDS = {
    "response_rate_pct",
    "hrs_per_week",
    "interest_in_student_learning",
    "clearly_explain_course_requirements",
    "clear_learning_objectives_goals",
    "instructor_provides_feedback_to_students_to_improve",
    "demonstrate_importance_of_subject_matter",
    "explains_subject_matter_of_course",
    "show_respect_for_all_students",
    "overall_teaching_rate",
    "overall_course_rate",
}
RATING_FIELDS = [
    "hrs_per_week",
    "interest_in_student_learning",
    "clearly_explain_course_requirements",
    "clear_learning_objectives_goals",
    "instructor_provides_feedback_to_students_to_improve",
    "demonstrate_importance_of_subject_matter",
    "explains_subject_matter_of_course",
    "show_respect_for_all_students",
    "overall_teaching_rate",
    "overall_course_rate",
]


def normalize_course_id(value: str | None) -> str | None:
    """Convert CMU course numbers to NN-NNN, restoring a leading zero."""
    raw_value = clean_text(value)
    if not raw_value.isdigit() or len(raw_value) not in {4, 5}:
        return None
    digits = raw_value.zfill(5)
    return f"{digits[:2]}-{digits[2:]}"


def snake_case(name: str) -> str:
    if name in HEADER_RENAMES:
        return HEADER_RENAMES[name]
    name = name.strip().replace("&", " and ")
    name = re.sub(r"[^\w\s]+", " ", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name.lower()


def clean_text(value: str | None) -> str:
    return (value or "").strip()


def to_int(value: str) -> int | None:
    value = clean_text(value)
    if not value:
        return None
    return int(value)


def to_float(value: str) -> float | None:
    value = clean_text(value)
    if not value:
        return None
    return float(value)


def parse_pct(value: str) -> float | None:
    value = clean_text(value)
    if not value:
        return None
    return float(value.rstrip("%"))


def detect_record_type(row: dict[str, object]) -> str:
    return "aggregate" if not row.get("instructor") else "instructor"


def build_course_key(row: dict[str, object]) -> str:
    parts = [
        str(row.get("year") or ""),
        str(row.get("sem") or ""),
        str(row.get("dept") or ""),
        str(row.get("num") or ""),
        str(row.get("section") or ""),
        str(row.get("instructor") or "AGGREGATE"),
        str(row.get("course_name") or ""),
    ]
    normalized = [re.sub(r"\s+", " ", part.strip()).upper().replace(" ", "_") for part in parts]
    return "__".join(normalized)


def normalize_row(raw_row: dict[str, str], headers: Iterable[str]) -> dict[str, object]:
    row: dict[str, object] = {}
    for header in headers:
        row[header] = clean_text(raw_row.get(header, ""))

    row["year"] = to_int(str(row["year"]))
    row["sem"] = clean_text(str(row["sem"])).title()
    row["dept"] = clean_text(str(row["dept"])).upper()
    row["canonical_course_id"] = normalize_course_id(str(row["num"]))
    row["total_students"] = to_int(str(row["total_students"]))
    row["response_count"] = to_int(str(row["response_count"]))
    row["response_rate_pct"] = parse_pct(str(row["response_rate_raw"]))

    for field in [f for f in RATING_FIELDS if f != "response_rate_raw"]:
        if field in row:
            row[field] = to_float(str(row[field]))

    row["record_type"] = detect_record_type(row)
    row["course_key"] = build_course_key(row)
    hash_fields = [
        "year", "sem", "college", "dept", "num", "section", "instructor",
        "course_name", "course_level", "total_students", "response_count",
        "response_rate_raw", "hrs_per_week", "interest_in_student_learning",
        "clearly_explain_course_requirements", "clear_learning_objectives_goals",
        "instructor_provides_feedback_to_students_to_improve",
        "demonstrate_importance_of_subject_matter",
        "explains_subject_matter_of_course", "show_respect_for_all_students",
        "overall_teaching_rate", "overall_course_rate", "record_type",
    ]
    payload = "|".join(str(row.get(field, "")) for field in hash_fields)
    row["row_hash"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return row


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_FCE_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_and_clean_rows(source_csv: Path) -> tuple[list[str], list[dict[str, object]], Path, Path]:
    if not source_csv.exists():
        raise FileNotFoundError(f"Source CSV not found: {source_csv}")

    raw_csv = source_csv
    clean_csv = PROCESSED_FCE_DIR / source_csv.name.replace("_FULL.csv", "_clean.csv")

    with source_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        original_headers = reader.fieldnames or []
        cleaned_headers = [snake_case(h) for h in original_headers]

        rows: list[dict[str, object]] = []
        seen: set[tuple[object, ...]] = set()
        for raw in reader:
            remapped = {snake_case(k): v for k, v in raw.items() if k is not None}
            row = normalize_row(remapped, cleaned_headers)

            # Exclude test labels and malformed identifiers such as the known
            # "Email Testing" record. Keep the source file untouched.
            if row["canonical_course_id"] is None:
                continue

            row["source_file"] = source_csv.name

            dedupe_key = tuple(row.get(field) for field in (
                "year", "sem", "college", "dept", "num", "section", "instructor",
                "course_name", "course_level", "total_students", "response_count",
                "response_rate_raw", "hrs_per_week", "interest_in_student_learning",
                "clearly_explain_course_requirements", "clear_learning_objectives_goals",
                "instructor_provides_feedback_to_students_to_improve",
                "demonstrate_importance_of_subject_matter",
                "explains_subject_matter_of_course", "show_respect_for_all_students",
                "overall_teaching_rate", "overall_course_rate",
            ))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rows.append(row)

    output_headers = cleaned_headers + [
        "canonical_course_id",
        "response_rate_pct",
        "record_type",
        "course_key",
        "source_file",
        "row_hash",
    ]
    return output_headers, rows, raw_csv, clean_csv


def write_clean_csv(headers: list[str], rows: list[dict[str, object]], clean_csv: Path) -> None:
    with clean_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def ensure_table(conn: sqlite3.Connection, headers: list[str]) -> None:
    column_types: dict[str, str] = {header: "TEXT" for header in headers}
    for field in INT_FIELDS:
        column_types[field] = "INTEGER"
    for field in REAL_FIELDS:
        column_types[field] = "REAL"

    columns_sql = ",\n        ".join(
        ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
        + [f"{name} {column_types.get(name, 'TEXT')}" for name in headers]
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            {columns_sql}
        )
        """
    )
    index_statements = [
        f"CREATE INDEX IF NOT EXISTS idx_fce_year_sem ON {TABLE_NAME}(year, sem)",
        f"CREATE INDEX IF NOT EXISTS idx_fce_dept_num ON {TABLE_NAME}(dept, num)",
        f"CREATE INDEX IF NOT EXISTS idx_fce_course_name ON {TABLE_NAME}(course_name)",
        f"CREATE INDEX IF NOT EXISTS idx_fce_instructor ON {TABLE_NAME}(instructor)",
        f"CREATE INDEX IF NOT EXISTS idx_fce_college ON {TABLE_NAME}(college)",
        f"CREATE INDEX IF NOT EXISTS idx_fce_record_type ON {TABLE_NAME}(record_type)",
        f"CREATE INDEX IF NOT EXISTS idx_fce_course_key ON {TABLE_NAME}(course_key)",
        f"CREATE INDEX IF NOT EXISTS idx_fce_canonical_course_id ON {TABLE_NAME}(canonical_course_id)",
        f"CREATE UNIQUE INDEX IF NOT EXISTS idx_fce_row_hash ON {TABLE_NAME}(row_hash)",
    ]
    for stmt in index_statements:
        conn.execute(stmt)


def upsert_rows(
    headers: list[str],
    rows: list[dict[str, object]],
    db_path: Path = DB_PATH,
) -> int:
    with sqlite3.connect(db_path) as conn:
        ensure_table(conn, headers)
        placeholders = ", ".join(["?" for _ in headers])
        insert_sql = f"INSERT OR IGNORE INTO {TABLE_NAME} ({', '.join(headers)}) VALUES ({placeholders})"
        before = conn.total_changes
        conn.executemany(insert_sql, ([row.get(h) for h in headers] for row in rows))
        conn.commit()
        return conn.total_changes - before


def main() -> None:
    import sys

    ensure_dirs()
    source_csv = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else RAW_DIR / "CMU_FCE_2025Fall-2026Sum_FULL.csv"
    )
    headers, rows, raw_csv, clean_csv = load_and_clean_rows(source_csv)
    write_clean_csv(headers, rows, clean_csv)
    inserted = upsert_rows(headers, rows)
    print(f"Prepared {len(rows)} rows")
    print(f"Inserted {inserted} new rows")
    print(f"Raw CSV: {raw_csv}")
    print(f"Clean CSV: {clean_csv}")
    print(f"SQLite DB: {DB_PATH}")


if __name__ == "__main__":
    main()
