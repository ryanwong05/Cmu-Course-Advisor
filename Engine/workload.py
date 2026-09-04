def get_course_metrics(course_id, course_metrics):
    return course_metrics.get(course_id)


def calculate_semester_load(
    course_ids,
    course_metrics
):
    total_hours = 0
    total_workload = 0
    total_difficulty = 0
    total_stress = 0

    rated_courses = 0
    high_intensity_courses = []
    data_statuses = set()

    for course_id in course_ids:

        metrics = get_course_metrics(
            course_id,
            course_metrics
        )

        if metrics is None:
            continue

        total_hours += metrics["hours_per_week"]
        total_workload += metrics["workload"]
        total_difficulty += metrics["difficulty"]
        total_stress += metrics["stress"]
        data_statuses.add(metrics.get("source_status", "unknown"))
        if metrics.get("intensity") == "high_intensity":
            high_intensity_courses.append(course_id)

        rated_courses += 1

    if rated_courses == 0:
        return {
            "hours_per_week": 0,
            "average_workload": 0,
            "average_difficulty": 0,
            "average_stress": 0,
            "high_intensity_courses": [],
            "warning_level": "none",
            "data_status": "unrated",
        }

    high_count = len(high_intensity_courses)
    return {
        "hours_per_week": total_hours,

        "average_workload": round(
            total_workload / rated_courses,
            1
        ),

        "average_difficulty": round(
            total_difficulty / rated_courses,
            1
        ),

        "average_stress": round(
            total_stress / rated_courses,
            1
        ),
        "high_intensity_courses": high_intensity_courses,
        "warning_level": "high" if high_count >= 2 else "none",
        "data_status": (
            "estimated" if "estimated" in data_statuses else "verified"
        ),
    }
