"""Regression tests for explainable, planner-context course recommendations."""

import unittest

import app
from Backend.course_recommendation import (
    recommend_courses_for_plan,
    recommendation_slots_from_plan,
)
from fastapi.testclient import TestClient


class CourseRecommendationTests(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "maximum_alternatives": 3,
            "weights": {
                "cross_program_overlap": 24,
                "future_unlock": 8,
                "no_additional_prerequisites": 6,
                "lighter_workload": 5,
                "planner_default": 3,
                "prerequisite_step": -3,
                "heavy_course_in_busy_semester": -12,
                "single_term_offering": -5,
                "unverified_prerequisites": -8,
                "unverified_requirement_eligibility": -20,
            },
        }
        self.catalog = {
            "10-100": self.course("10-100", tier=3),
            "10-200": self.course("10-200", tier=5),
            "10-300": self.course("10-300", prerequisites=["99-999"]),
            "10-310": self.course("10-310", offered=["fall"]),
            "10-400": self.course("10-400", prerequisites=["10-100"]),
            "99-999": self.course("99-999"),
        }
        self.plan = {
            "path": [
                {
                    "semester_number": 1,
                    "semester": "spring",
                    "academic_year": 1,
                    "unit_limit": 30,
                    "total_units": 21,
                    "high_intensity_count": 1,
                    "courses": [],
                    "program_requirements": [{
                        "id": "choice-1",
                        "name": "Technical choice",
                        "units": 9,
                        "options": ["10-100", "10-200", "10-300", "10-310"],
                        "default_option": "10-100",
                        "scope": "goal",
                        "cross_scope_overlap_limit": 1,
                    }],
                    "baseline_requirements": [],
                },
                {
                    "semester_number": 2,
                    "semester": "fall",
                    "academic_year": 2,
                    "unit_limit": 52,
                    "total_units": 12,
                    "high_intensity_count": 0,
                    "courses": ["10-400"],
                    "program_requirements": [],
                    "baseline_requirements": [],
                },
            ]
        }

    @staticmethod
    def course(course_id, tier=3, prerequisites=None, offered=None, units=9):
        return {
            "name": f"Course {course_id}",
            "units": units,
            "offered": offered or ["fall", "spring"],
            "minimum_year": 1,
            "prerequisites": prerequisites or [],
            "prerequisite_expression": None,
            "prerequisite_data_status": "verified",
            "intensity": {"tier": tier, "label": "Moderate" if tier <= 3 else "Very heavy"},
        }

    def recommend(self, plan=None, primary=None, manual=None, slots=None):
        plan = plan or self.plan
        slots = slots or recommendation_slots_from_plan(plan)
        return recommend_courses_for_plan(
            plan=plan,
            slots=slots,
            catalog=self.catalog,
            completed_courses=set(),
            primary_course_ids=set(primary or []),
            goal_course_ids=set(),
            manual_selections=manual or {},
            policy=self.policy,
        )

    def test_valid_candidates_are_ranked_and_unmet_prerequisite_is_filtered(self):
        result = self.recommend()
        item = result["recommendations"][0]
        self.assertEqual(item["recommended"]["course_id"], "10-100")
        self.assertTrue(item["recommended"]["reasons"])
        returned = {item["recommended"]["course_id"], *(option["course_id"] for option in item["alternatives"])}
        self.assertNotIn("10-300", returned)
        self.assertNotIn("10-310", returned)

    def test_overlap_bonus_only_applies_when_slot_policy_allows_it(self):
        allowed = self.recommend(primary={"10-200"})["recommendations"][0]
        overlap = next(
            option for option in [allowed["recommended"], *allowed["alternatives"]]
            if option["course_id"] == "10-200"
        )
        self.assertEqual(overlap["factors"]["cross_program_overlap"], 1)

        slots = recommendation_slots_from_plan(self.plan)
        slots[0]["overlap_limit"] = None
        slots[0]["overlap_allowed"] = False
        blocked = self.recommend(primary={"10-200"}, slots=slots)["recommendations"][0]
        same_course = next(
            option for option in [blocked["recommended"], *blocked["alternatives"]]
            if option["course_id"] == "10-200"
        )
        self.assertEqual(same_course["factors"]["cross_program_overlap"], 0)

    def test_overlap_bonus_respects_the_published_global_limit(self):
        plan = {"path": [dict(self.plan["path"][0])]}
        plan["path"][0]["program_requirements"] = [
            {
                "id": "choice-1", "name": "First", "units": 9,
                "options": ["10-100"], "default_option": "10-100",
                "scope": "goal", "cross_scope_overlap_limit": 1,
            },
            {
                "id": "choice-2", "name": "Second", "units": 9,
                "options": ["10-200"], "default_option": "10-200",
                "scope": "goal", "cross_scope_overlap_limit": 1,
            },
        ]
        plan["path"][0]["total_units"] = 18
        result = self.recommend(plan=plan, primary={"10-100", "10-200"})
        first, second = result["recommendations"]
        self.assertEqual(first["recommended"]["factors"]["cross_program_overlap"], 1)
        self.assertEqual(second["recommended"]["factors"]["cross_program_overlap"], 0)

    def test_heavy_course_is_penalized_in_already_busy_semester(self):
        item = self.recommend()["recommendations"][0]
        heavy = next(option for option in item["alternatives"] if option["course_id"] == "10-200")
        self.assertLess(heavy["ranking_score"], item["recommended"]["ranking_score"])
        self.assertLess(heavy["score_components"]["busy_semester_workload"], 0)

    def test_single_term_candidate_is_filtered_when_not_offered_in_slot_term(self):
        item = self.recommend()["recommendations"][0]
        candidates = {item["recommended"]["course_id"], *(option["course_id"] for option in item["alternatives"])}
        self.assertNotIn("10-310", candidates)

    def test_valid_manual_choice_is_preserved(self):
        item = self.recommend(manual={"choice-1": "10-200"})["recommendations"][0]
        self.assertEqual(item["status"], "manual_selection_preserved")
        self.assertEqual(item["recommended"]["course_id"], "10-200")
        self.assertEqual(item["recommended"]["reasons"][0], "Preserves your valid manual selection")

    def test_global_recommendations_are_duplicate_free_and_respect_units(self):
        plan = {"path": [dict(self.plan["path"][0])]}
        plan["path"][0]["program_requirements"] = [
            {
                "id": "choice-1", "name": "First", "units": 9,
                "options": ["10-100", "10-200"], "default_option": "10-100",
                "scope": "goal", "cross_scope_overlap_limit": 0,
            },
            {
                "id": "choice-2", "name": "Second", "units": 9,
                "options": ["10-100", "10-200"], "default_option": "10-200",
                "scope": "goal", "cross_scope_overlap_limit": 0,
            },
        ]
        plan["path"][0]["total_units"] = 18
        result = self.recommend(plan=plan)
        choices = [item["recommended"]["course_id"] for item in result["recommendations"]]
        self.assertEqual(len(choices), len(set(choices)))
        self.assertTrue(result["validation"]["duplicate_free"])
        self.assertTrue(result["validation"]["unit_limits_respected"])
        self.assertTrue(result["validation"]["prerequisites_respected"])

    def test_multiple_recommendations_share_one_semester_unit_budget(self):
        self.catalog["10-500"] = self.course("10-500", units=12)
        self.catalog["10-510"] = self.course("10-510", units=12)
        plan = {"path": [dict(self.plan["path"][0])]}
        plan["path"][0]["unit_limit"] = 27
        plan["path"][0]["total_units"] = 24
        plan["path"][0]["program_requirements"] = [
            {
                "id": "choice-1", "name": "First", "units": 9,
                "options": ["10-500"], "default_option": None,
                "scope": "goal", "cross_scope_overlap_limit": 0,
            },
            {
                "id": "choice-2", "name": "Second", "units": 9,
                "options": ["10-510"], "default_option": None,
                "scope": "goal", "cross_scope_overlap_limit": 0,
            },
        ]
        result = self.recommend(plan=plan)
        first, second = result["recommendations"]
        self.assertEqual(first["recommended"]["course_id"], "10-500")
        self.assertEqual(first["recommended"]["factors"]["semester_units_after_selection"], 27)
        self.assertEqual(second["status"], "no_recommendation")
        self.assertIn("semester_unit_limit", second["filter_reasons"])
        self.assertTrue(result["validation"]["unit_limits_respected"])

    def test_no_valid_candidate_returns_explicit_diagnostic(self):
        plan = {"path": [dict(self.plan["path"][0])]}
        plan["path"][0]["program_requirements"] = [{
            "id": "blocked", "name": "Blocked choice", "units": 9,
            "options": ["10-300"], "default_option": None, "scope": "goal",
            "cross_scope_overlap_limit": 0,
        }]
        item = self.recommend(plan=plan)["recommendations"][0]
        self.assertEqual(item["status"], "no_recommendation")
        self.assertIsNone(item["recommended"])
        self.assertIn("unmet_prerequisites", item["filter_reasons"])

    def test_unverified_requirement_is_never_presented_without_warning(self):
        slots = recommendation_slots_from_plan(self.plan)
        slots[0]["eligibility_verified"] = False
        slots[0]["eligibility_note"] = "Confirm category approval"
        item = self.recommend(slots=slots)["recommendations"][0]
        self.assertEqual(item["status"], "candidate_requires_verification")
        self.assertIn("Confirm category approval", item["recommended"]["warnings"])

    def test_api_reuses_existing_planner_and_returns_coherent_recommendations(self):
        student = app.StudentState(
            college="dietrich",
            primary_major="information-systems",
            year=1,
            completed_courses=["21-127", "36-200", "15-112", "66-136", "73-102"],
        )
        goal = app.PlanningGoal(type="additional_major", program="artificial-intelligence")
        constraints = app.PlanningConstraints(
            start_semester="spring", planning_year=1, target_completion_year=4, max_units=52,
        )
        response = TestClient(app.app).post("/api/recommend-courses", json={
            "student": student.model_dump(),
            "goals": [goal.model_dump()],
            "constraints": constraints.model_dump(),
        })
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["advisory_only"])
        self.assertTrue(payload["validation"]["duplicate_free"])
        self.assertTrue(payload["recommendations"])


if __name__ == "__main__":
    unittest.main()
