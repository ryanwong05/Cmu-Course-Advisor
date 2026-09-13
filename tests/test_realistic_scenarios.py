"""Product-level regression gate for the 20 realistic student scenarios."""

import unittest

from fastapi import HTTPException

import app


SCENARIOS = [
    ("dietrich", "stats-ml", "internal_transfer", "computer-science"),
    ("dietrich", "stats-ml", "internal_transfer", "electrical-and-computer-engineering"),
    ("dietrich", "economics--b-a", "internal_transfer", "stats-ml"),
    ("dietrich", "information-systems", "internal_transfer", "computer-science"),
    ("mcs", "mathematical-sciences--b-s", "internal_transfer", "computer-science"),
    ("engineering", "mechanical-engineering", "internal_transfer", "electrical-and-computer-engineering"),
    ("engineering", "electrical-and-computer-engineering", "internal_transfer", "mechanical-engineering"),
    ("cfa", "architecture--b-arch", "internal_transfer", "stats-ml"),
    ("tepper", "business-administration--b-s", "internal_transfer", "information-systems"),
    ("dietrich", "stats-ml", "additional_major", "robotics"),
    ("dietrich", "stats-ml", "additional_major", "computer-science"),
    ("engineering", "electrical-and-computer-engineering", "additional_major", "robotics"),
    ("engineering", "mechanical-engineering", "additional_major", "robotics"),
    ("scs", "computer-science", "additional_major", "robotics"),
    ("dietrich", "stats-ml", "additional_major", "economics"),
    ("engineering", "mechanical-engineering", "minor", "computer-science"),
    ("tepper", "business-administration--b-s", "minor", "computer-science"),
    ("dietrich", "stats-ml", "minor", "business-administration"),
]


class RealisticScenarioRegressionTests(unittest.TestCase):
    def request_for(self, college, major, goal_type, program):
        return app.PlanningRequest(
            student=app.StudentState(
                college=college,
                primary_major=major,
                year=1,
                completed_courses=[],
            ),
            goals=[app.PlanningGoal(type=goal_type, program=program)],
            constraints=app.PlanningConstraints(target_completion_year=4),
        )

    def test_scenarios_1_to_15_and_17_to_19_return_auditable_results(self):
        for index, scenario in enumerate(SCENARIOS, 1):
            with self.subTest(case=index, scenario=scenario):
                result = app.create_plan(self.request_for(*scenario))
                self.assertIsNotNone(result["program_profile"])
                if result["program_profile"].get("minimum_courses", 0):
                    self.assertTrue(result["fastest"]["path"])
                else:
                    self.assertTrue(result["fastest"]["goal_complete"])
                self.assertIn("all_requirements_scheduled", result["degree_audits"]["selected_goal"])
                if not result["fastest"]["goal_complete"]:
                    self.assertIn(
                        "TARGET_DEADLINE_NOT_MET",
                        {warning["code"] for warning in result["planning_warnings"]},
                    )

    def test_scenario_16_returns_the_official_scs_ineligibility(self):
        request = self.request_for("scs", "computer-science", "minor", "machine-learning")
        with self.assertRaises(HTTPException) as context:
            app.create_plan(request)
        self.assertEqual(context.exception.status_code, 409)
        self.assertIn("outside SCS", context.exception.detail)

    def test_scenario_20_comparison_keeps_all_three_decisions_available(self):
        student = app.StudentState(
            college="dietrich",
            primary_major="stats-ml",
            year=1,
            completed_courses=["15-112", "21-127", "36-200"],
        )
        comparison = app.compare_programs(app.ComparisonRequest(
            student=student,
            programs=["computer-science", "robotics"],
        ))
        paths = {
            (item["program"], item["goal_type"])
            for item in comparison["comparisons"]
        }
        self.assertIn(("computer-science", "additional_major"), paths)
        self.assertIn(("robotics", "additional_major"), paths)
        self.assertEqual(comparison["current_major_scope"], "verified_subset")


if __name__ == "__main__":
    unittest.main()
