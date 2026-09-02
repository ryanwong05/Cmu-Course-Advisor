import unittest

from fastapi import HTTPException

import app


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
        self.assertEqual(result["planner_status"], "not_configured")

    def test_shared_request_still_generates_existing_cs_plan(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        request.student.completed_courses = ["15-112", "21-127", "15-122"]
        result = app.create_plan(request)
        self.assertIn("fastest", result)

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
