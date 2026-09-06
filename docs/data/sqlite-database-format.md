# SQLite Database Format

This document describes the current SQLite schema used by `CMU-course-selector` at:

- `data/courses.sqlite`

It focuses on the schedule-related tables currently used by the `sqlite_reader` skill, and briefly notes the legacy FCE table that also exists in the same database file.

## Short answer: what is "course id"?

There are two different identifiers in the current schedule schema:

1. Internal row id:
   - `courses.id`
   - Type: `INTEGER PRIMARY KEY AUTOINCREMENT`
   - Purpose: internal database primary key

2. CMU course number:
   - `courses.num`
   - Type: `TEXT`
   - Examples: `15122`, `17214`, `69101`
   - Purpose: the user-facing course number that people usually mean when they say "course id"

So:

- If you mean the database primary key, the field is `id`
- If you mean the CMU course number, the field is `num`

In most application-level lookups, the current helper functions use `num`, not `id`.

## Main schedule tables

The current schedule data is stored in two related tables:

1. `courses`
2. `course_sections`

### `courses`

Purpose:

- one row per `(semester_name, num)` course record imported from `data/cmu_schedule_classes.json`

Schema:

```sql
CREATE TABLE courses (
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
```

Field meanings:

- `id`
  - internal primary key
- `semester_name`
  - original semester label from the JSON
  - examples: `Spring Class Schedule`, `Fall Class Schedule`
- `semester_slug`
  - normalized version of `semester_name`
  - examples: `spring_class_schedule`, `fall_class_schedule`
- `dept`
  - inferred department code
  - examples: `CS`, `S3D`, `ATH`, `ROTC`
- `num`
  - CMU course number stored as text
  - examples: `15122`, `17214`
- `title`
  - course title for that semester record
- `units_raw`
  - original units string from source JSON
  - examples: `12.0`, `VAR`, `3-18`
- `units`
  - numeric units when parseable, otherwise `NULL`
- `section_count`
  - number of section/meeting entries imported for that course row
- `course_info_json`
  - raw normalized section list as JSON text
  - useful for debugging, but `course_sections` is better for querying
- `source_file`
  - source JSON path used for import
- `course_key`
  - normalized helper key based on semester, course number, and title
- `row_hash`
  - unique row fingerprint used to keep records stable

### `course_sections`

Purpose:

- one row per section or meeting block for a course

Schema:

```sql
CREATE TABLE course_sections (
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
```

Field meanings:

- `id`
  - internal primary key for the section row
- `course_id`
  - foreign key to `courses.id`
- `semester_name`
  - copied from parent course row
- `semester_slug`
  - copied from parent course row
- `num`
  - copied course number
- `title`
  - copied course title
- `units_raw`
  - copied units string
- `units`
  - copied numeric units if parseable
- `section_index`
  - import-time order of the section entry within the course
- `lec_sec`
  - section label
  - examples: `Lec`, `A`, `B2`, `Lec 1`
- `days`
  - meeting day string
  - examples: `MWF`, `TR`, `TBA`
- `begin_time`
  - meeting start time as text
- `end_time`
  - meeting end time as text
- `location`
  - meeting location as text
- `section_hash`
  - unique fingerprint for the section row

## Table relationship

The relationship is:

- `course_sections.course_id -> courses.id`

This is the main join path and the correct relational link.

In SQL:

```sql
SELECT
  c.id AS course_row_id,
  c.num,
  c.title,
  c.semester_name,
  s.id AS section_row_id,
  s.section_index,
  s.lec_sec,
  s.days,
  s.begin_time,
  s.end_time,
  s.location
FROM courses c
LEFT JOIN course_sections s
  ON s.course_id = c.id
WHERE c.num = '15122'
ORDER BY c.semester_name, s.section_index;
```

## How rows are identified in practice

### Course-level identification

Use this when you want the course itself:

- best application-level identifier: `(semester_name, num)`
- internal relational identifier: `courses.id`

Notes:

- `num` alone is not unique across the whole table because the same course number appears in multiple semesters
- `id` is unique, but it is an internal database key, not the normal user-facing course identifier

### Section-level identification

Use this when you want a specific section row:

- internal relational identifier: `course_sections.id`
- logical grouping: `course_sections.course_id`

Notes:

- `num` also repeats across many section rows
- the proper parent-child linkage is through `course_id`

## Current helper behavior

The current helper functions in `skills/sqlite_reader/sqlite_database_tools.py` mostly treat the user-facing course identifier as:

- `num`

Examples:

- `fetch_course_by_id(course_id)` actually queries `courses.num = ?`
- `fetch_course_sections_by_id(course_id)` actually queries `course_sections.num = ?`

So in the current codebase, "course id" in helper names usually means:

- CMU course number (`num`)

not:

- internal SQLite primary key (`id`)

## Department field

`courses.dept` is not present in the original source JSON. It is inferred during import using:

1. exact or latest-year matches from `fce_courses`
2. legacy-code normalization from `data/reference/dept_map.json`
3. manual prefix fallback rules from `data/reference/dept_map.json`

Examples:

- `15122 -> CS`
- `17214 -> S3D`
- `69101 -> ATH`
- `32102 -> ROTC`

## Legacy FCE table

The same SQLite file also contains:

- `fce_courses`

This is a separate dataset used for Faculty Course Evaluation data. It is not the same as the schedule tables above.

Its purpose is different:

- evaluation / rating data
- instructor rows
- response counts
- teaching and course ratings

The schedule importer currently uses `fce_courses` only as a supporting source for department inference.

## Recommended query patterns

### Get a course by course number across semesters

```sql
SELECT *
FROM courses
WHERE num = '15122'
ORDER BY semester_name;
```

### Get all sections for one course number

```sql
SELECT *
FROM course_sections
WHERE num = '15122'
ORDER BY semester_name, section_index;
```

### Get one semester-specific course with its sections

```sql
SELECT *
FROM courses
WHERE num = '15122'
  AND semester_name = 'Fall Class Schedule';
```

Then join sections by `course_id` / `courses.id`:

```sql
SELECT s.*
FROM course_sections s
JOIN courses c
  ON s.course_id = c.id
WHERE c.num = '15122'
  AND c.semester_name = 'Fall Class Schedule'
ORDER BY s.section_index;
```

### Get all courses for one department

```sql
SELECT *
FROM courses
WHERE dept = 'CS'
ORDER BY semester_name, num;
```

## Summary

If you need a quick mental model:

- `courses.id` = internal DB primary key
- `courses.num` = CMU course number that users usually mean
- `course_sections.course_id` = foreign key to `courses.id`
- query by `num` for user-facing lookups
- join by `course_id = courses.id` for relational correctness
