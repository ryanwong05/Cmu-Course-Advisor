"""Regression coverage for generated-plan alternative comparisons."""

import unittest

import app
from fastapi.testclient import TestClient


class PathComparisonTests(unittest.TestCase):
    def setUp(self):
        self.student = app.StudentState(
            college="dietrich",
            primary_major="information-systems",
            year=1,
            completed_courses=["21-127", "36-200", "15-112", "66-136", "73-102"],
            completed_requirement_ids=[
                "data-analysis", "computational-thinking", "social-sciences",
            ],
        )
        self.constraints = app.PlanningConstraints(
            start_semester="spring",
            planning_year=1,
            target_completion_year=4,
            max_units=52,
        )

    def compare(self, current_goal, alternative_goal, constraints=None):
        constraints = constraints or self.constraints
        current_plan = app.create_plan(app.PlanningRequest(
            student=self.student,
            goals=[current_goal],
            constraints=constraints,
        ))
        return app.compare_programs(app.ComparisonRequest(
            student=self.student,
            current_goal=current_goal,
            alternative_goal=alternative_goal,
            constraints=constraints,
            current_plan=current_plan,
        ))

    def test_ai_additional_major_compares_with_ai_minor_from_actual_plans(self):
        result = self.compare(
            app.PlanningGoal(type="additional_major", program="artificial-intelligence"),
            app.PlanningGoal(type="minor", program="artificial-intelligence"),
        )
        current = result["current"]["metrics"]
        alternative = result["alternative"]["metrics"]

        self.assertEqual(current["additional_courses"], len(current["additional_course_ids"]))
        self.assertEqual(alternative["additional_courses"], len(alternative["additional_course_ids"]))
        self.assertEqual(len(current["additional_course_ids"]), len(set(current["additional_course_ids"])))
        self.assertIsNotNone(current["completion_term"])
        self.assertIsNotNone(alternative["completion_term"])
        self.assertIsNotNone(current["completion_semester_number"])
        self.assertGreater(current["potential_overlap_course_count"], 0)
        self.assertEqual(current["shared_course_count"], len(current["shared_courses"]))
        self.assertGreaterEqual(current["overlap_units_saved"], 0)
        self.assertTrue(result["opportunity_cost"])
        self.assertTrue(any("shared planned course" in item for item in result["opportunity_cost"]))

    def test_additional_major_can_compare_with_another_additional_major(self):
        result = self.compare(
            app.PlanningGoal(type="additional_major", program="artificial-intelligence"),
            app.PlanningGoal(type="additional_major", program="robotics"),
        )
        self.assertEqual(result["alternative"]["goal"]["program"], "robotics")
        self.assertTrue(
            result["course_diff"]["only_current"]
            or result["course_diff"]["only_alternative"]
        )

    def test_incomplete_alternative_reports_unscheduled_requirements(self):
        short_horizon = self.constraints.model_copy(update={"target_completion_year": 1})
        result = self.compare(
            app.PlanningGoal(type="minor", program="artificial-intelligence"),
            app.PlanningGoal(type="additional_major", program="robotics"),
            short_horizon,
        )
        alternative = result["alternative"]["metrics"]
        self.assertFalse(alternative["goal_complete"])
        self.assertTrue(alternative["unscheduled_requirements"])
        self.assertIsNone(alternative["overload_required"])

    def test_shared_and_diff_courses_are_unique(self):
        result = self.compare(
            app.PlanningGoal(type="additional_major", program="artificial-intelligence"),
            app.PlanningGoal(type="minor", program="artificial-intelligence"),
        )
        diff = result["course_diff"]
        only_current = set(diff["only_current"])
        shared = set(diff["shared"])
        only_alternative = set(diff["only_alternative"])
        self.assertTrue(only_current.isdisjoint(shared))
        self.assertTrue(only_alternative.isdisjoint(shared))
        self.assertTrue(only_current.isdisjoint(only_alternative))
        for change in diff["semester_changes"]:
            self.assertIn(change["course"], shared)
            self.assertNotEqual(change["current_term"], change["alternative_term"])

    def test_alternatives_are_configured_and_only_return_supported_profiles(self):
        goal = app.PlanningGoal(type="additional_major", program="artificial-intelligence")
        plan = app.create_plan(app.PlanningRequest(
            student=self.student,
            goals=[goal],
            constraints=self.constraints,
        ))
        alternatives = plan["path_alternatives"]
        self.assertGreaterEqual(len(alternatives), 2)
        self.assertEqual(alternatives[0]["goal_type"], "minor")
        for alternative in alternatives:
            self.assertIn(
                alternative["goal_type"],
                app.program_profiles["programs"][alternative["program"]],
            )

    def test_program_comparison_endpoint_accepts_generated_path_comparison(self):
        response = TestClient(app.app).post("/api/program-comparison", json={
            "student": self.student.model_dump(),
            "current_goal": {
                "type": "minor", "program": "artificial-intelligence",
            },
            "alternative_goal": {
                "type": "minor", "program": "robotics",
            },
            "constraints": self.constraints.model_dump(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["alternative"]["goal"]["program"], "robotics")


if __name__ == "__main__":
    unittest.main()
