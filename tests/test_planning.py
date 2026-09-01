import unittest

from fastapi import HTTPException

import app


class PlanningIntegrationTests(unittest.TestCase):
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
