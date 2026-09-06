import unittest

from fastapi import HTTPException

import app
from Engine.availability import prerequisites_satisfied


class PlanningIntegrationTests(unittest.TestCase):
    def shared_request(self, goal):
        return app.PlanningRequest(
            student=app.StudentState(
                college="dietrich",
                primary_major="stats-ml",
                year=1,
                completed_courses=[],
            ),
            goals=[app.PlanningGoal(**goal)],
        )

    def test_current_major_uses_student_baseline(self):
        result = app.create_baseline(self.shared_request({
            "type": "current_major",
            "program": "stats-ml",
        }))
        self.assertEqual(result["baseline"]["college"], "dietrich")
        self.assertEqual(result["planner_key"], "stats-ml-major")

    def test_transfer_target_does_not_replace_home_college(self):
        result = app.create_baseline(self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        }))
        self.assertEqual(result["student"]["college"], "dietrich")
        self.assertEqual(result["baseline"]["college"], "dietrich")
        self.assertEqual(result["planner_key"], "cs-transfer")

    def test_additional_major_target_does_not_replace_home_college(self):
        result = app.create_baseline(self.shared_request({
            "type": "additional_major",
            "college": "scs",
            "program": "robotics",
        }))
        self.assertEqual(result["student"]["college"], "dietrich")
        self.assertEqual(result["baseline"]["college"], "dietrich")
        self.assertEqual(result["planner_key"], "robotics-additional-major")
        self.assertEqual(result["planner_status"], "ready_with_requirement_slots")

    def test_all_five_scs_programs_expose_three_paths(self):
        self.assertEqual(len(app.programs), 5)
        for program in app.programs:
            self.assertEqual(
                set(program["available_goal_types"]),
                {"internal_transfer", "additional_major", "minor"},
            )

    def test_comparison_keeps_overlap_separate_from_double_counting(self):
        request = app.ComparisonRequest(
            student=self.shared_request({
                "type": "internal_transfer",
                "program": "computer-science",
            }).student,
            programs=["computer-science"],
        )
        result = app.compare_programs(request)
        cs_minor = next(
            item for item in result["comparisons"]
            if item["goal_type"] == "minor"
        )
        self.assertEqual(cs_minor["double_count_limit"], 2)
        self.assertEqual(
            set(cs_minor["potential_overlap_courses"]),
            {"15-112", "15-122", "21-127"},
        )

    def test_program_profile_supports_generic_continue_page(self):
        result = app.get_program_profile("artificial-intelligence", "minor")
        self.assertEqual(result["program_name"], "Artificial Intelligence")
        self.assertEqual(result["goal_type"], "minor")
        self.assertGreater(len(result["fixed_courses"]), 0)
        self.assertGreater(result["profile"]["choice_slots"], 0)

    def test_all_five_additional_majors_and_minors_generate_plans(self):
        for program in app.programs:
            for goal_type in ("additional_major", "minor"):
                request = self.shared_request({
                    "type": goal_type,
                    "college": "scs",
                    "program": program["id"],
                })
                result = app.create_plan(request)
                self.assertTrue(result["fastest"]["path"])
                self.assertIsNotNone(result["program_profile"])
                self.assertTrue(any(
                    semester["program_requirements"]
                    for semester in result["fastest"]["path"]
                ) or result["fastest"]["remaining_program_requirements"])

    def test_program_slots_participate_in_capacity(self):
        request = self.shared_request({
            "type": "minor",
            "college": "scs",
            "program": "robotics",
        })
        request.constraints.max_units = 24
        result = app.create_plan(request)
        for semester in result["fastest"]["path"]:
            self.assertLessEqual(semester["total_units"], 24)
            self.assertEqual(
                semester["free_choice_units"],
                semester["unit_limit"] - semester["total_units"],
            )

    def test_semesters_use_academic_year_names_and_five_blocks_max(self):
        request = self.shared_request({
            "type": "additional_major",
            "college": "scs",
            "program": "artificial-intelligence",
        })
        request.constraints.start_semester = "fall"
        request.constraints.planning_year = 1
        path = app.create_plan(request)["fastest"]["path"]
        self.assertEqual(
            [(path[0]["academic_year_name"], path[0]["semester"]),
             (path[1]["academic_year_name"], path[1]["semester"]),
             (path[2]["academic_year_name"], path[2]["semester"])],
            [("Freshman", "fall"), ("Freshman", "spring"), ("Sophomore", "fall")],
        )
        self.assertTrue(all(len(semester["course_blocks"]) <= 5 for semester in path))

    def test_additional_major_plan_marks_minor_foundation_and_extension(self):
        request = self.shared_request({
            "type": "additional_major",
            "college": "scs",
            "program": "artificial-intelligence",
        })
        result = app.create_plan(request)
        blocks = [
            block for semester in result["fastest"]["path"]
            for block in semester["course_blocks"]
        ]
        tiers = {block.get("program_tier") for block in blocks}
        self.assertIn("minor_foundation", tiers)
        self.assertIn("additional_major", tiers)

    def test_additional_major_secondary_path_is_the_actual_minor_foundation(self):
        request = self.shared_request({
            "type": "additional_major",
            "college": "scs",
            "program": "artificial-intelligence",
        })
        result = app.create_plan(request)
        self.assertEqual(result["secondary_path_type"], "minor_foundation")
        blocks = [
            block for semester in result["lower_workload"]["path"]
            for block in semester["course_blocks"]
        ]
        self.assertTrue(blocks)
        self.assertNotIn(
            "additional_major",
            {block.get("program_tier") for block in blocks},
        )

    def test_scs_student_gets_minor_unavailable_warning_for_ai(self):
        request = self.shared_request({
            "type": "additional_major",
            "college": "scs",
            "program": "artificial-intelligence",
        })
        request.student.college = "scs"
        result = app.create_plan(request)
        self.assertFalse(result["minor_status"]["available"])

    def test_shared_request_still_generates_existing_cs_plan(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        request.student.completed_courses = ["15-112", "21-127", "15-122"]
        result = app.create_plan(request)
        self.assertIn("fastest", result)
        first = result["fastest"]["path"][0]
        self.assertIn("baseline_requirements", first)
        self.assertEqual(
            first["total_units"],
            first["goal_units"]
            + first["current_major_units"]
            + first["shared_units"]
            + first["baseline_units"],
        )
        self.assertLessEqual(first["total_units"], 52)

    def test_stats_ml_student_without_calculus_credit_gets_21_120(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        path = app.create_plan(request)["fastest"]["path"]
        current_major_courses = {
            course
            for semester in path
            for course in semester["current_major_courses"]
        }
        self.assertIn("21-120", current_major_courses)

    def test_completed_21_120_is_not_scheduled_again(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        request.student.completed_courses = ["21-120"]
        result = app.create_plan(request)
        scheduled = {
            course
            for semester in result["fastest"]["path"]
            for course in semester["courses"]
        }
        self.assertNotIn("21-120", scheduled)

    def test_completed_21_122_implies_21_120_and_is_not_scheduled_twice(self):
        request = self.shared_request({
            "type": "additional_major",
            "college": "scs",
            "program": "artificial-intelligence",
        })
        request.student.completed_courses = ["21-122"]
        result = app.create_plan(request)
        scheduled = [
            course
            for semester in result["fastest"]["path"]
            for course in semester["courses"]
        ]
        self.assertNotIn("21-120", scheduled)
        self.assertNotIn("21-122", scheduled)
        self.assertEqual(len(scheduled), len(set(scheduled)))

    def test_profile_required_courses_are_stably_deduplicated(self):
        goal = app.PlanningGoal(
            type="additional_major",
            college="scs",
            program="artificial-intelligence",
        )
        inputs = app.planning_inputs_for_profile(goal, [])
        self.assertEqual(
            len(inputs["required_courses"]),
            len(set(inputs["required_courses"])),
        )

    def test_21_127_is_not_scheduled_with_21_120(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        path = app.create_plan(request)["fastest"]["path"]
        calculus_semester = next(
            semester["semester_number"]
            for semester in path
            if "21-120" in semester["courses"]
        )
        concepts_semester = next(
            semester["semester_number"]
            for semester in path
            if "21-127" in semester["courses"]
        )
        self.assertGreater(concepts_semester, calculus_semester)

    def test_21_127_accepts_any_verified_prerequisite(self):
        course = next(item for item in app.courses if item["id"] == "21-127")
        self.assertTrue(prerequisites_satisfied(course, ["21-120"]))
        self.assertTrue(prerequisites_satisfied(course, ["15-112"]))
        self.assertTrue(prerequisites_satisfied(course, ["21-112"]))
        self.assertFalse(prerequisites_satisfied(course, []))

    def test_21_122_is_not_a_direct_21_127_prerequisite(self):
        course = next(item for item in app.courses if item["id"] == "21-127")
        options = {
            option["course_id"]
            for option in course["prerequisite_expression"]["options"]
        }
        self.assertNotIn("21-122", options)

    def test_experiential_learning_is_a_slot_not_course_36_200(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        baseline = app.create_baseline(request)["baseline"]
        experiential = next(
            item for item in baseline["requirements"]
            if item["id"] == "experiential-learning"
        )
        self.assertEqual(experiential["courses"], [])
        self.assertEqual(experiential["timeline"]["type"], "after_semester")

    def test_baseline_units_reduce_goal_capacity(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        request.student.enrollment_status = "precollege"
        request.constraints.first_semester_max_units = 20
        result = app.create_plan(request)
        first = result["fastest"]["path"][0]
        self.assertLessEqual(first["total_units"], 20)
        self.assertGreater(first["baseline_units"], 0)

    def test_semester_limit_can_be_unbounded_for_overload(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        request.constraints.semester_unit_limits = [None]
        result = app.create_plan(request)
        self.assertIsNone(result["fastest"]["path"][0]["unit_limit"])

    def test_completed_gened_is_not_scheduled_again(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        request.student.completed_requirement_ids = ["communication"]
        result = app.create_plan(request)
        scheduled = {
            item["id"]
            for semester in result["fastest"]["path"]
            for item in semester["baseline_requirements"]
        }
        self.assertNotIn("communication", scheduled)

    def test_incoming_freshman_spreads_first_year_baseline(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        request.student.enrollment_status = "precollege"
        request.constraints.start_semester = "fall"
        request.constraints.planning_year = 1
        result = app.create_plan(request)["fastest"]["path"]
        self.assertLess(len(result[0]["baseline_requirements"]), 3)
        self.assertGreater(len(result[1]["baseline_requirements"]), 0)
        scheduled_courses = [
            course
            for semester in result
            for course in semester["courses"]
        ]
        self.assertIn("15-112", scheduled_courses)

    def test_free_choice_units_are_reported(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        semester = app.create_plan(request)["fastest"]["path"][0]
        self.assertEqual(
            semester["free_choice_units"],
            semester["unit_limit"] - semester["total_units"],
        )

    def test_stats_ml_cs_transfer_overlap_is_reported(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        result = app.create_plan(request)
        self.assertEqual(
            set(result["overlap_summary"]["courses"]),
            {"15-112", "15-122", "21-127"},
        )
        self.assertEqual(result["overlap_summary"]["units"], 36)

    def test_three_high_intensity_courses_are_never_scheduled_together(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        path = app.create_plan(request)["fastest"]["path"]
        self.assertTrue(all(
            semester["high_intensity_count"] <= 2
            for semester in path
        ))

    def test_two_high_intensity_courses_produce_warning(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        path = app.create_plan(request)["fastest"]["path"]
        warned = [
            semester for semester in path
            if semester["workload"]["warning_level"] == "high"
        ]
        self.assertTrue(warned)
        self.assertTrue(all(
            len(semester["workload"]["high_intensity_courses"]) == 2
            for semester in warned
        ))

    def test_every_supported_course_has_an_intensity_rating(self):
        self.assertEqual(
            {course["id"] for course in app.courses},
            set(app.course_metrics),
        )
        self.assertTrue(all(
            metrics["intensity"] in {
                "standard", "demanding", "high_intensity"
            }
            for metrics in app.course_metrics.values()
        ))

    def test_max_units_changes_fastest_path(self):
        completed = ["15-112", "21-127", "15-122"]
        low = app.create_plan(
            app.PlanRequest(
                completed_courses=completed,
                goal="cs-transfer",
                max_units=12,
            )
        )
        high = app.create_plan(
            app.PlanRequest(
                completed_courses=completed,
                goal="cs-transfer",
                max_units=24,
            )
        )
        self.assertTrue(all(item["units"] <= 12 for item in low["fastest"]["path"]))
        self.assertNotEqual(low["fastest"]["path"], high["fastest"]["path"])

    def test_unconfigured_robotics_goal_is_not_complete(self):
        with self.assertRaises(HTTPException) as context:
            app.create_plan(
                app.PlanRequest(completed_courses=[], goal="robotics-transfer")
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_unknown_goal_is_not_found(self):
        with self.assertRaises(HTTPException) as context:
            app.create_plan(app.PlanRequest(completed_courses=[], goal="missing"))
        self.assertEqual(context.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
