import unittest
from copy import deepcopy

import app
from Engine.student_state import (
    course_ids_from_semester,
    derive_academic_state,
    planning_boundary_after_locked_semesters,
)


def scheduled_course_ids(path):
    return [
        course_id
        for semester in path
        for course_id in course_ids_from_semester(semester)
    ]


class AcademicStateTests(unittest.TestCase):
    def ece_transfer_request(self, *, post_transfer=False):
        return app.PlanningRequest(
            student=app.StudentState(
                college="dietrich",
                primary_major="stats-ml",
                year=1,
                completed_courses=[],
            ),
            goals=[app.PlanningGoal(
                type="internal_transfer",
                college="engineering",
                program="electrical-and-computer-engineering",
                include_post_transfer_plan=post_transfer,
            )],
            constraints=app.PlanningConstraints(target_completion_year=4),
        )

    def test_derived_state_distinguishes_completed_in_progress_and_planned(self):
        locked = [{
            "semester": "spring",
            "academic_year": 2,
            "courses": ["18-100"],
            "program_requirements": [{
                "id": "math-choice",
                "default_option": "21-120",
            }],
            "baseline_requirements": [{
                "id": "communication",
                "selected_course_id": "76-101",
            }],
        }]
        state = derive_academic_state({
            "completed_courses": ["15-122"],
            "in_progress_courses": ["21-127"],
            "planned_courses": ["36-200"],
            "completed_requirement_ids": ["data-analysis"],
            "locked_semesters": locked,
        }, app.expand_completed_courses)

        self.assertEqual(state["reported_completed_courses"], ["15-122"])
        self.assertIn("15-112", state["completed_courses"])
        self.assertEqual(state["in_progress_courses"], ["21-127"])
        self.assertEqual(
            set(state["planned_courses"]),
            {"36-200", "18-100", "21-120", "76-101"},
        )
        self.assertEqual(state["completed_requirement_ids"], ["data-analysis"])
        self.assertEqual(state["planned_requirement_ids"], ["communication"])

    def test_post_transfer_plan_preserves_history_and_starts_after_boundary(self):
        initial_request = self.ece_transfer_request()
        initial_result = app.create_plan(initial_request)
        locked = deepcopy(initial_result["fastest"]["path"])
        self.assertTrue(locked)

        continuation_request = self.ece_transfer_request(post_transfer=True)
        continuation_request.student.locked_semesters = locked
        continuation_result = app.create_plan(continuation_request)
        continuation = continuation_result["fastest"]

        self.assertEqual(
            continuation["path"][:len(locked)],
            locked,
        )
        boundary = planning_boundary_after_locked_semesters(locked)
        first_future = continuation["path"][len(locked)]
        self.assertEqual(first_future["semester"], boundary["semester"])
        self.assertEqual(first_future["academic_year"], boundary["academic_year"])
        self.assertEqual(
            continuation_result["transfer_planning"]["locked_semester_count"],
            len(locked),
        )
        self.assertEqual(
            continuation_result["transfer_planning"]["effective_term"],
            boundary,
        )

    def test_custom_transfer_boundary_preserves_two_terms_and_replans_after_them(self):
        request = self.ece_transfer_request(post_transfer=True)
        locked = [
            {
                "semester_number": 1,
                "semester": "fall",
                "academic_year": 1,
                "courses": ["21-120"],
                "program_requirements": [],
                "baseline_requirements": [],
            },
            {
                "semester_number": 2,
                "semester": "spring",
                "academic_year": 1,
                "courses": ["18-100"],
                "program_requirements": [],
                "baseline_requirements": [],
            },
        ]
        request.student.locked_semesters = deepcopy(locked)

        result = app.create_plan(request)

        self.assertEqual(result["fastest"]["path"][:2], locked)
        first_future = result["fastest"]["path"][2]
        self.assertEqual(first_future["semester"], "fall")
        self.assertEqual(first_future["academic_year"], 2)

    def test_exact_completed_course_is_recognized_by_transfer_planner(self):
        request = app.PlanningRequest(
            student=app.StudentState(
                college="dietrich",
                primary_major="linguistics",
                year=1,
                completed_courses=["21-127"],
            ),
            goals=[app.PlanningGoal(
                type="internal_transfer",
                college="scs",
                program="computer-science",
            )],
        )

        result = app.create_plan(request)

        self.assertNotIn("21-127", scheduled_course_ids(result["fastest"]["path"]))
        profile = app.get_program_profile("computer-science", "internal_transfer")
        self.assertIn("21-127", {course["id"] for course in profile["fixed_courses"]})

    def test_locked_target_credit_is_not_scheduled_again(self):
        initial_result = app.create_plan(self.ece_transfer_request())
        locked = deepcopy(initial_result["fastest"]["path"])
        locked_ids = set(scheduled_course_ids(locked))

        continuation_request = self.ece_transfer_request(post_transfer=True)
        continuation_request.student.locked_semesters = locked
        continuation = app.create_plan(continuation_request)["fastest"]
        all_ids = scheduled_course_ids(continuation["path"])
        future_ids = scheduled_course_ids(continuation["path"][len(locked):])

        self.assertTrue({"18-100", "21-120"}.issubset(locked_ids))
        self.assertTrue(locked_ids.isdisjoint(future_ids))
        self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_completion_implication_prevents_replanning_prerequisite(self):
        request = self.ece_transfer_request(post_transfer=True)
        request.student.locked_semesters = [{
            "semester_number": 1,
            "semester": "spring",
            "academic_year": 1,
            "courses": ["15-122"],
            "program_requirements": [],
            "baseline_requirements": [],
        }]
        result = app.create_plan(request)["fastest"]
        future_ids = scheduled_course_ids(result["path"][1:])

        self.assertNotIn("15-122", future_ids)
        self.assertNotIn("15-112", future_ids)

    def test_post_transfer_choices_are_valid_and_catalog_metadata_is_explicit(self):
        initial_result = app.create_plan(self.ece_transfer_request())
        locked = deepcopy(initial_result["fastest"]["path"])
        request = self.ece_transfer_request(post_transfer=True)
        request.student.locked_semesters = locked
        result = app.create_plan(request)
        future = result["fastest"]["path"][len(locked):]

        for semester in future:
            for requirement in semester.get("program_requirements", []):
                default = requirement.get("default_option")
                if default:
                    self.assertIn(default, requirement["options"])

        for course_id in scheduled_course_ids(result["fastest"]["path"]):
            metadata = result["course_catalog"][course_id]
            self.assertTrue(metadata["name"])
            self.assertIsNotNone(metadata["units"])
            self.assertIsInstance(metadata["offered"], list)
            self.assertGreaterEqual(metadata["minimum_year"], 1)
            self.assertIsInstance(metadata["prerequisites"], list)
            self.assertIn(
                metadata["metadata_status"],
                {"available", "catalog_zero_unit"},
            )
            if metadata["units"] == 0:
                self.assertEqual(metadata["metadata_status"], "catalog_zero_unit")
                self.assertTrue(metadata["source"])

        self.assertTrue(result["fastest"]["goal_complete"])
        self.assertFalse(result["fastest"]["remaining_program_requirements"])

    def test_initial_transfer_mode_remains_an_eligibility_plan(self):
        result = app.create_plan(self.ece_transfer_request())
        scheduled = set(scheduled_course_ids(result["fastest"]["path"]))

        self.assertEqual(result["transfer_planning"]["mode"], "eligibility")
        self.assertEqual(result["transfer_planning"]["locked_semester_count"], 0)
        self.assertIsNone(result["transfer_planning"]["effective_term"])
        self.assertIn("18-100", scheduled)
        self.assertIn("21-120", scheduled)
        self.assertTrue({"15-110", "15-112"}.intersection(scheduled))
        self.assertTrue({"33-121", "33-141", "33-151"}.intersection(scheduled))


if __name__ == "__main__":
    unittest.main()
