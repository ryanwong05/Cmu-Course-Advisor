import unittest

from Backend import application as app
from Backend.catalog_drafts import (
    build_catalog_draft_profile,
    mark_catalog_draft_unresolved,
)


class CatalogDraftPlanningTests(unittest.TestCase):
    def test_draft_schedule_data_does_not_extend_verified_course_graph(self):
        verified_ids = {course["id"] for course in app.courses}
        draft_ids = {course["id"] for course in app.catalog_draft_courses}
        self.assertTrue(verified_ids < draft_ids)
        self.assertEqual(verified_ids, set(app.course_metrics))
        self.assertEqual(draft_ids, set(app.catalog_draft_course_metrics))

    def test_all_directory_entries_have_verified_or_draft_access(self):
        directory = app.list_program_directory()["programs"]
        self.assertEqual(len(directory), 213)
        self.assertTrue(all(
            item.get("planner_ready") or item.get("draft_planning_available")
            for item in directory
        ))
        self.assertTrue(all(
            item.get("transfer_planning_status") == "planning_ready"
            or item.get("transfer_draft_available")
            for item in directory if item["program_type"] == "primary_major"
        ))

    def test_shared_planning_id_does_not_promote_unreviewed_minor(self):
        item = next(
            item for item in app.list_program_directory()["programs"]
            if item["id"] == "computational-biology--minor"
        )
        self.assertFalse(item["planner_ready"])
        self.assertTrue(item["draft_planning_available"])
        profile = app.profile_for_goal(app.PlanningGoal(
            type="minor", program=item["id"],
        ))
        self.assertEqual(profile["policy_status"], "catalog_extracted_unverified")

    def test_shared_page_inheritance_is_tentative_and_source_bound(self):
        entry = next(
            item for item in app.program_directory
            if item["id"] == "cognitive-science--additional-major"
        )
        curriculum = app.program_curriculum_registry[
            entry["requirements_source_program_id"]
        ]
        evidence = app.shared_credential_evidence[entry["id"]]
        profile = build_catalog_draft_profile(
            entry, curriculum,
            {course["id"] for course in app.catalog_draft_courses},
            "additional_major", evidence,
        )
        self.assertTrue(profile["required_course_ids"])
        self.assertEqual(profile["policy_status"], "catalog_extracted_unverified")
        self.assertTrue(any(
            item["reason"] == "credential_rules_not_separately_parsed"
            for item in profile["draft_unresolved_requirements"]
        ))

        stale_evidence = {**evidence, "parent_source_hash": "outdated"}
        stale = build_catalog_draft_profile(
            entry, curriculum,
            {course["id"] for course in app.catalog_draft_courses},
            "additional_major", stale_evidence,
        )
        self.assertEqual(stale["required_course_ids"], [])
        self.assertEqual(stale["requirement_groups"], [])

    def test_unsafe_catalog_group_stays_unresolved(self):
        entry = {
            "id": "example--minor", "credential": "Minor",
            "source_url": "https://example.test/minor",
        }
        curriculum = {
            "catalog_year": "2026-2027",
            "fixed_courses": [{"id": "15-112"}, {"id": "99-999"}],
            "requirement_groups": [{
                "id": "electives", "name": "Electives", "choose": 2,
                "units": 18, "options": ["15-122"],
                "selection_rule": {"type": "unresolved"},
            }],
            "extraction": {"status": "needs_review"},
        }
        profile = build_catalog_draft_profile(
            entry, curriculum, {"15-112", "15-122"}, "minor",
        )
        self.assertEqual(profile["required_course_ids"], ["15-112"])
        self.assertEqual(profile["requirement_groups"], [])
        reasons = {item["reason"] for item in profile["draft_unresolved_requirements"]}
        self.assertIn("course_schedule_data_missing", reasons)
        self.assertIn("catalog_choice_rule_pending", reasons)
        self.assertIn("catalog_policy_unverified", reasons)

        result = {"goal_complete": True, "remaining_program_requirements": [], "unscheduled_requirements": []}
        mark_catalog_draft_unresolved(result, profile)
        self.assertFalse(result["goal_complete"])
        self.assertEqual(
            len(result["unscheduled_requirements"]),
            len(profile["draft_unresolved_requirements"]),
        )

    def test_draft_plan_does_not_claim_verified_completion_or_transfer_eligibility(self):
        student = app.StudentState(college="dietrich", primary_major="stats-ml", year=1)
        constraints = app.PlanningConstraints(target_completion_year=4)
        cases = [
            ("minor", "additive-manufacturing--minor"),
            ("additional_major", "biomedical-engineering--additional-major"),
            ("additional_degree", "computer-science--dual-degree"),
            ("internal_transfer", "history--b-a"),
            ("current_major", "history--b-a"),
        ]
        for goal_type, program in cases:
            with self.subTest(goal_type=goal_type, program=program):
                result = app.create_plan(app.PlanningRequest(
                    student=student,
                    goals=[app.PlanningGoal(type=goal_type, program=program)],
                    constraints=constraints,
                ))
                self.assertEqual(
                    result["program_profile"]["policy_status"],
                    "catalog_extracted_unverified",
                )
                self.assertFalse(result["fastest"]["goal_complete"])
                self.assertFalse(result["degree_audits"]["selected_goal"]["requirements_verified"])
                self.assertTrue(any(
                    item["reason"] == "catalog_policy_unverified"
                    for item in result["fastest"]["unscheduled_requirements"]
                ))
                self.assertTrue(any(
                    warning["code"] == "CATALOG_DRAFT_NOT_VERIFIED"
                    for warning in result["planning_warnings"]
                ))
                if goal_type == "internal_transfer":
                    self.assertEqual(result["transfer_planning"]["mode"], "catalog_exploration")
                    self.assertIsNone(result["transfer_planning"]["application_term"])
                    self.assertIsNone(result["transfer_planning"]["policy"])

    def test_every_directory_program_and_transfer_target_has_a_safe_plan(self):
        """Catalog-wide smoke check; a draft must never masquerade as an audit."""
        constraints = app.PlanningConstraints(target_completion_year=4)
        for entry in app.list_program_directory()["programs"]:
            goal_type = (
                "current_major" if entry["program_type"] == "primary_major"
                else entry["program_type"]
            )
            cases = [goal_type]
            if goal_type == "current_major":
                cases.append("internal_transfer")
            for case_type in cases:
                with self.subTest(program=entry["id"], goal_type=case_type):
                    ready = (
                        entry.get("transfer_planning_status") == "planning_ready"
                        if case_type == "internal_transfer"
                        else entry["planner_ready"]
                    )
                    goal_program = (
                        entry.get("planning_id") or entry["id"]
                        if ready else entry["id"]
                    )
                    student = app.StudentState(
                        college=(entry.get("home_colleges") or ["dietrich"])[0]
                        if case_type == "current_major" else "dietrich",
                        primary_major=goal_program
                        if case_type == "current_major" else "stats-ml",
                        year=1,
                    )
                    result = app.create_plan(app.PlanningRequest(
                        student=student,
                        goals=[app.PlanningGoal(type=case_type, program=goal_program)],
                        constraints=constraints,
                    ))
                    path = result["fastest"]["path"]
                    scheduled_ids = [
                        course_id for term in path for course_id in term["courses"]
                    ]
                    self.assertEqual(len(scheduled_ids), len(set(scheduled_ids)))
                    self.assertTrue(all(term["units"] <= constraints.max_units for term in path))
                    self.assertTrue(all(
                        item.get("reason")
                        for item in result["fastest"]["unscheduled_requirements"]
                    ))
                    if (result["program_profile"] or {}).get("policy_status") == "catalog_extracted_unverified":
                        self.assertFalse(result["fastest"]["goal_complete"])
                        self.assertFalse(
                            result["degree_audits"]["selected_goal"]["requirements_verified"]
                        )


if __name__ == "__main__":
    unittest.main()
