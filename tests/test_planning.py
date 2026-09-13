import json
import os
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

import app
import Backend.application as application
from Engine.availability import prerequisites_satisfied
from Engine.planning import generate_semester_path


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
        scs_programs = [program for program in app.programs if program["college"] == "scs"]
        self.assertEqual(len(scs_programs), 5)
        for program in scs_programs:
            self.assertEqual(
                set(program["available_goal_types"]),
                {"internal_transfer", "additional_major", "minor"},
            )

    def test_bcsa_transfer_is_verified_and_plannable(self):
        directory_entry = next(
            item for item in app.program_directory
            if item["id"] == "computer-science-and-arts--b-c-s-a"
        )
        self.assertEqual(directory_entry["planning_id"], "computer-science-and-arts")
        self.assertEqual(directory_entry["planning_status"], "planning_ready")
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "intercollege",
            "program": "computer-science-and-arts",
        })
        baseline = app.create_baseline(request)
        self.assertEqual(baseline["planner_status"], "ready_with_requirement_slots")
        result = app.create_plan(request)
        self.assertEqual(result["program_profile"]["minimum_units"], 380)
        self.assertTrue(result["fastest"]["path"])
        self.assertEqual(result["primary_baseline"]["status"], "replaced_by_transfer")
        self.assertTrue(all(
            semester["primary_major_reserved_units"] == 0
            for semester in result["fastest"]["path"]
        ))
        slot_names = {
            slot["name"]
            for semester in result["fastest"]["path"]
            for slot in semester.get("program_requirements", [])
        } | {
            slot["name"]
            for slot in result["fastest"]["remaining_program_requirements"]
        }
        self.assertIn("Selected CFA concentration", slot_names)

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

    def test_semesters_use_academic_year_names_and_six_blocks_max(self):
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
        self.assertTrue(all(len(semester["course_blocks"]) <= 6 for semester in path))

    def test_fall_elective_catalog_contains_07_280(self):
        result = app.list_electives(term="fall", category="free-elective")
        course = next(item for item in result["courses"] if item["id"] == "07-280")
        self.assertEqual(course["units"], 12)
        self.assertGreater(course["sections"], 0)
        self.assertIn("Offered Fall 2026", course["description"])

    def test_elective_catalog_excludes_graduate_courses(self):
        result = app.list_electives(term="fall", category="free-elective")
        self.assertTrue(result["courses"])
        self.assertTrue(all(course["level"] < 600 for course in result["courses"]))

    def test_communication_and_humanities_have_real_scheduled_candidates(self):
        for category in ("communication", "humanities"):
            result = app.list_electives(term="fall", category=category)
            self.assertTrue(result["courses"])
            self.assertTrue(all(course["sections"] > 0 for course in result["courses"]))

    def test_communication_uses_only_official_full_course_or_two_mini_paths(self):
        result = app.list_electives(term="fall", category="communication")
        ids = {course["id"] for course in result["courses"]}
        self.assertIn("76-101", ids)
        self.assertIn("76-106 + 76-107", ids)
        self.assertNotIn("76-106", ids)
        self.assertTrue(all(course["units"] == 9 for course in result["courses"]))

    def test_target_completion_year_controls_planning_horizon(self):
        request = self.shared_request({
            "type": "additional_major",
            "college": "scs",
            "program": "artificial-intelligence",
        })
        request.constraints.start_semester = "spring"
        request.constraints.planning_year = 1
        request.constraints.target_completion_year = 4
        result = app.create_plan(request)
        self.assertEqual(result["target_completion_year"], 4)
        self.assertLessEqual(len(result["fastest"]["path"]), 7)

    def test_junior_deadline_includes_junior_spring(self):
        request = self.shared_request({
            "type": "additional_major",
            "college": "scs",
            "program": "computer-science",
        })
        request.student.college = "intercollege"
        request.student.primary_major = "bxa"
        request.constraints.start_semester = "spring"
        request.constraints.planning_year = 1
        request.constraints.target_completion_year = 3
        path = app.create_plan(request)["fastest"]["path"]
        self.assertEqual(len(path), 5)
        self.assertEqual(
            (path[-1]["academic_year_name"], path[-1]["semester"]),
            ("Junior", "spring"),
        )

    def test_target_year_does_not_silently_cap_user_limit_at_42(self):
        request = self.shared_request({
            "type": "additional_major",
            "college": "scs",
            "program": "artificial-intelligence",
        })
        request.constraints.max_units = 52
        request.constraints.target_completion_year = 4
        result = app.create_plan(request)
        self.assertTrue(all(
            semester["unit_limit"] == 52
            for semester in result["fastest"]["path"]
        ))

    def test_verified_meche_major_uses_real_curriculum_with_robotics(self):
        request = self.shared_request({
            "type": "additional_major", "college": "scs", "program": "robotics"
        })
        request.student.college = "engineering"
        request.student.primary_major = "mechanical-engineering"
        request.constraints.start_semester = "fall"
        request.constraints.planning_year = 1
        request.constraints.target_completion_year = 4
        result = app.create_plan(request)
        self.assertEqual(result["primary_baseline"]["units"], 0)
        self.assertEqual(
            result["degree_audits"]["primary_degree"]["status"],
            "verified_curriculum",
        )
        blocks = [
            block for semester in result["fastest"]["path"]
            for block in semester["course_blocks"]
        ]
        self.assertFalse(any(block.get("estimated") for block in blocks))
        self.assertTrue(any(block["id"] == "24-101" for block in blocks))
        self.assertTrue(any(block["id"] == "16-450" for block in blocks))
        self.assertTrue(result["fastest"]["goal_complete"])
        self.assertEqual(result["fastest"]["remaining_program_requirements"], [])
        self.assertGreaterEqual(sum(
            block.get("kind") in {"current_major", "shared", "current_major_choice"}
            for block in blocks
        ), 20)

    def test_meche_completion_profile_exposes_real_courses(self):
        profile = app.get_primary_major_profile("mechanical-engineering")
        ids = {course["id"] for course in profile["fixed_courses"]}
        self.assertTrue({"24-101", "24-261", "24-370", "24-452"}.issubset(ids))
        self.assertEqual(profile["minimum_degree_units"], 382)

    def test_robotics_additional_major_has_all_ten_requirements(self):
        profile = app.program_profiles["programs"]["robotics"]["additional_major"]
        self.assertEqual(profile["minimum_courses"], 10)
        self.assertEqual(
            1 + sum(group["choose"] for group in profile["requirement_groups"]),
            10,
        )

    def test_verified_stats_ml_curriculum_uses_real_requirements_without_reserve(self):
        request = self.shared_request({
            "type": "additional_major", "college": "scs", "program": "robotics"
        })
        result = app.create_plan(request)
        self.assertEqual(result["primary_baseline"]["status"], "verified_curriculum")
        self.assertTrue(all(
            semester["primary_major_reserved_units"] == 0
            for semester in result["fastest"]["path"]
        ))
        self.assertTrue(any(
            semester["current_major_courses"]
            for semester in result["fastest"]["path"]
        ))
        self.assertTrue(any(
            item.get("scope") == "primary_major"
            for semester in result["fastest"]["path"]
            for item in semester["program_requirements"]
        ))

    def test_stats_ml_official_math_and_core_courses_are_hydrated(self):
        course_ids = {course["id"] for course in app.courses}
        self.assertTrue({
            "21-256", "21-241", "36-235", "36-236", "36-350",
            "36-402", "10-301", "15-351",
        }.issubset(course_ids))
        self.assertEqual(app.requirements["stats-ml-major"]["planner_status"], "ready")
        regression = next(course for course in app.courses if course["id"] == "36-401")
        self.assertEqual(set(regression["offered"]), {"fall", "spring"})

    def test_stats_ml_math_picker_is_limited_to_official_groups(self):
        result = app.list_electives(term="spring", category="stats-ml-math")
        self.assertTrue(result["courses"])
        self.assertTrue(all(
            course["id"] in app.STATS_ML_MATH_GROUPS
            and course["requirement_group"]
            for course in result["courses"]
        ))

    def test_stats_ml_verified_template_has_all_official_curriculum_sections(self):
        curriculum = app.requirements["stats-ml-major"]
        self.assertEqual(curriculum["curriculum_status"], "verified")
        self.assertEqual(curriculum["minimum_degree_units"], 360)
        self.assertEqual(
            {group["id"] for group in curriculum["requirement_groups"]},
            {
                "calculus", "multivariable", "linear-algebra",
                "beginning-data", "intermediate-data", "advanced-data",
                "programming", "algorithms", "intro-ml", "advanced-ml",
            },
        )

    def test_stats_ml_defaults_are_distinct_and_offered_in_their_terms(self):
        request = self.shared_request({
            "type": "current_major", "program": "stats-ml"
        })
        request.constraints.start_semester = "fall"
        request.constraints.target_completion_year = 4
        result = app.create_plan(request)["fastest"]
        defaults = []
        catalog = {course["id"]: course for course in app.courses}
        for semester in result["path"]:
            for item in semester["program_requirements"]:
                if item.get("scope") != "primary_major":
                    continue
                default = item.get("default_option")
                defaults.append(default)
                for course_id in default.split(" + "):
                    self.assertIn(semester["semester"], catalog[course_id]["offered"])
        self.assertEqual(len(defaults), len(set(defaults)))
        self.assertFalse(result["remaining_current_major"])
        self.assertFalse(result["remaining_primary_requirements"])
        self.assertTrue(result["primary_major_complete"])

    def test_every_scheduled_course_gets_a_five_level_intensity(self):
        result = app.list_electives(term="fall", category="humanities")
        self.assertTrue(result["courses"])
        self.assertTrue(all(
            1 <= course["intensity"]["tier"] <= 5
            and course["intensity"]["label"]
            for course in result["courses"]
        ))

    def test_information_systems_minor_is_verified_and_plannable(self):
        profile = app.get_program_profile("information-systems", "minor")
        self.assertEqual(
            {course["id"] for course in profile["fixed_courses"]},
            {"67-240", "67-250", "67-262"},
        )
        self.assertEqual(sum(
            group.get("choose", 1) for group in profile["requirement_groups"]
        ), 4)
        request = self.shared_request({
            "type": "minor",
            "college": "dietrich",
            "program": "information-systems",
            "include_post_transfer_plan": True,
        })
        request.constraints.target_completion_year = 4
        result = app.create_plan(request)["fastest"]
        self.assertTrue(result["goal_complete"])
        self.assertFalse(result["remaining_program_requirements"])

    def test_information_systems_bs_is_verified_and_plannable(self):
        directory_entry = next(
            item for item in app.program_directory
            if item["id"] == "information-systems--b-s"
        )
        self.assertEqual(directory_entry["planning_status"], "planning_ready")
        self.assertEqual(directory_entry["home_colleges"], ["dietrich"])
        self.assertIn("heinz", directory_entry["affiliations"])
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "dietrich",
            "program": "information-systems",
            "include_post_transfer_plan": True,
        })
        baseline = app.create_baseline(request)
        self.assertEqual(baseline["planner_status"], "ready_with_requirement_slots")
        request.constraints.target_completion_year = 4
        result = app.create_plan(request)["fastest"]
        scheduled = {
            course_id
            for semester in result["path"]
            for course_id in semester["goal_courses"]
        }
        fixed_slots = {
            item["id"]
            for semester in result["path"]
            for item in semester["program_requirements"]
        }
        self.assertTrue({"67-250", "67-262"}.issubset(scheduled))
        # Once a catalog/schedule row is available, the course should be a
        # real scheduled block instead of a placeholder requirement slot.
        self.assertIn("67-272", scheduled)
        self.assertTrue(any(
            item["name"].startswith("IS breadth")
            for semester in result["path"]
            for item in semester["program_requirements"]
        ))

    def test_all_supported_cross_program_paths_preserve_planning_invariants(self):
        supported_goals = [
            ("internal_transfer", "computer-science"),
            ("internal_transfer", "information-systems"),
            *[
                (goal_type, program["id"])
                for program in app.programs
                for goal_type in ("additional_major", "minor")
            ],
        ]
        course_by_id = {course["id"]: course for course in app.courses}

        for primary_major in ("stats-ml", "mechanical-engineering"):
            for start_semester in ("fall", "spring"):
                for goal_type, program_id in supported_goals:
                    with self.subTest(
                        primary_major=primary_major,
                        start_semester=start_semester,
                        goal_type=goal_type,
                        program_id=program_id,
                    ):
                        request = self.shared_request({
                            "type": goal_type,
                            "college": "scs",
                            "program": program_id,
                        })
                        request.student.primary_major = primary_major
                        request.constraints.start_semester = start_semester
                        request.constraints.target_completion_year = 4
                        result = app.create_plan(request)

                        for path_name in ("fastest", "lower_workload"):
                            completed = set(app.expand_completed_courses([]))
                            for semester in result[path_name]["path"]:
                                scheduled = list(semester["courses"])
                                for requirement in semester["program_requirements"]:
                                    default = requirement.get("default_option")
                                    if default:
                                        scheduled.extend(default.split(" + "))

                                self.assertEqual(len(scheduled), len(set(scheduled)))
                                self.assertFalse(completed.intersection(scheduled))
                                for course_id in scheduled:
                                    course = course_by_id.get(course_id)
                                    if course is None:
                                        continue
                                    if course.get("offered"):
                                        self.assertIn(
                                            semester["semester"], course["offered"]
                                        )
                                    self.assertTrue(
                                        prerequisites_satisfied(course, completed),
                                        f"{course_id} has unmet prerequisites in "
                                        f"{primary_major} + {program_id}",
                                    )
                                if semester["unit_limit"] is not None:
                                    self.assertLessEqual(
                                        semester["total_units"], semester["unit_limit"]
                                    )
                                self.assertLessEqual(
                                    semester["high_intensity_count"], 2
                                )
                                completed.update(scheduled)

    def test_primary_and_selected_goal_have_separate_audits(self):
        request = self.shared_request({
            "type": "minor", "college": "scs", "program": "robotics"
        })
        result = app.create_plan(request)
        self.assertEqual(
            set(result["degree_audits"]),
            {"primary_degree", "selected_goal"},
        )
        self.assertEqual(result["degree_audits"]["selected_goal"]["type"], "minor")

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

    def test_stats_ml_ai_additional_major_contains_full_required_path(self):
        request = self.shared_request({
            "type": "additional_major",
            "college": "scs",
            "program": "artificial-intelligence",
        })
        request.student.completed_courses = [
            "21-120", "21-127", "21-259", "36-200", "36-202", "15-112",
        ]
        request.constraints.start_semester = "spring"
        request.constraints.planning_year = 1
        request.constraints.target_completion_year = 4
        request.constraints.max_units = 52
        result = app.create_plan(request)

        self.assertEqual(result["secondary_path_type"], "minor_foundation")
        full_blocks = [
            block
            for semester in result["fastest"]["path"]
            for block in semester["course_blocks"]
        ]
        fixed_ids = {block["id"] for block in full_blocks if block["locked"]}
        self.assertTrue({"15-150", "21-241"}.issubset(fixed_ids))

        cluster_names = {
            block["name"]
            for block in full_blocks
            if block["name"].startswith("AI cluster:")
        }
        self.assertEqual(cluster_names, {
            "AI cluster: Cognition and Action",
            "AI cluster: Machine Learning",
            "AI cluster: Perception and Language",
            "AI cluster: Human-AI Interaction",
        })
        self.assertTrue(all(
            block["options"]
            for block in full_blocks
            if block["name"].startswith("AI cluster:")
        ))

    def test_robotics_additional_major_uses_official_ten_course_structure(self):
        profile = app.program_profiles["programs"]["robotics"]["additional_major"]
        self.assertEqual(profile["minimum_courses"], 10)
        self.assertEqual(
            1 + sum(group.get("choose", 1) for group in profile["requirement_groups"]),
            10,
        )
        goal = app.PlanningGoal(
            type="additional_major", college="scs", program="robotics"
        )
        inputs = app.planning_inputs_for_profile(goal, [])
        self.assertNotIn("15-112", inputs["required_courses"])
        self.assertEqual(len(inputs["program_requirement_slots"]), 9)

    def test_robotics_capstone_is_reserved_for_senior_spring(self):
        request = self.shared_request({
            "type": "additional_major", "college": "scs", "program": "robotics"
        })
        request.constraints.start_semester = "spring"
        request.constraints.planning_year = 1
        request.constraints.target_completion_year = 4
        path = app.create_plan(request)["fastest"]["path"]
        capstone_terms = [
            (semester["academic_year"], semester["semester"])
            for semester in path
            if any(
                block["id"].startswith("capstone-")
                for block in semester["course_blocks"]
            )
        ]
        self.assertEqual(capstone_terms, [(4, "spring")])

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
            + first["baseline_units"]
            + first["program_requirement_units"]
            + first["primary_major_reserved_units"],
        )
        self.assertLessEqual(first["total_units"], 52)

    def test_internal_transfer_does_not_schedule_former_major_requirements(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        path = app.create_plan(request)["fastest"]["path"]
        primary_slots = {
            item.get("id")
            for semester in path
            for item in semester["program_requirements"]
            if item.get("scope") == "primary_major"
        }
        self.assertEqual(primary_slots, set())

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

    def test_fixed_course_satisfies_overlapping_minor_choice_group(self):
        goal = app.PlanningGoal(
            type="additional_major",
            college="scs",
            program="computer-science",
        )
        inputs = app.planning_inputs_for_profile(goal, [])
        system_theory_slots = [
            slot for slot in inputs["program_requirement_slots"]
            if slot["id"].startswith("upper-core-")
        ]
        self.assertEqual(system_theory_slots, [])

    def test_21_127_uses_programming_prerequisite_without_forcing_calculus(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
            "include_post_transfer_plan": True,
        })
        path = app.create_plan(request)["fastest"]["path"]
        concepts_semester = next(
            semester["semester_number"]
            for semester in path
            if "21-127" in semester["courses"]
        )
        programming_semester = next(
            semester["semester_number"]
            for semester in path
            if "15-112" in semester["courses"]
        )
        self.assertGreater(concepts_semester, programming_semester)
        self.assertFalse(any(
            item.get("default_option") == "21-120"
            for semester in path
            for item in semester["program_requirements"]
        ))

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

    def test_21_241_has_recommended_preparation_not_hard_prerequisite(self):
        course = next(item for item in app.courses if item["id"] == "21-241")
        self.assertEqual(course["prerequisites"], [])
        self.assertEqual(course["recommended_preparation"], ["21-127"])
        self.assertTrue(prerequisites_satisfied(course, []))

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
            "include_post_transfer_plan": True,
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
            "include_post_transfer_plan": True,
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

    def test_lower_workload_path_prefers_one_high_intensity_course_per_term(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        path = app.create_plan(request)["lower_workload"]["path"]
        self.assertTrue(all(
            semester["high_intensity_count"] <= 1
            for semester in path
        ))

    def test_two_high_intensity_courses_produce_warning(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
            "include_post_transfer_plan": True,
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

    def test_course_catalog_exposes_timing_and_prerequisite_confidence(self):
        request = self.shared_request({
            "type": "current_major", "program": "stats-ml"
        })
        result = app.create_plan(request)
        linear_algebra = result["course_catalog"]["21-241"]
        self.assertEqual(linear_algebra["minimum_year"], 1)
        self.assertEqual(linear_algebra["recommended_preparation"], ["21-127"])
        self.assertEqual(
            linear_algebra["prerequisite_data_status"],
            "verified_no_hard_prerequisite",
        )
        unknown = next(
            course for course in app.courses
            if course.get("source") == "processed_schedule_sqlite"
            and course["id"] not in app.STATS_ML_PREREQUISITES
        )
        self.assertEqual(
            result["course_catalog"][unknown["id"]]["prerequisite_data_status"],
            "catalog_not_imported",
        )

    def test_stats_ml_prefers_21_241_for_linear_algebra(self):
        request = self.shared_request({
            "type": "current_major", "program": "stats-ml"
        })
        request.student.completed_courses = ["21-120", "15-112", "36-200"]
        request.constraints.start_semester = "fall"
        request.constraints.target_completion_year = 4
        path = app.create_plan(request)["fastest"]["path"]
        linear_algebra = next(
            item
            for semester in path
            for item in semester["program_requirements"]
            if item["name"] == "Linear algebra"
        )
        self.assertEqual(linear_algebra["default_option"], "21-241")

    def test_planner_never_places_a_course_before_minimum_year(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        path = app.create_plan(request)["fastest"]["path"]
        catalog = {course["id"]: course for course in app.courses}
        for semester in path:
            for course_id in semester["courses"]:
                self.assertGreaterEqual(
                    semester["academic_year"],
                    catalog[course_id].get("minimum_year", 1),
                )

    def test_priority_uses_metadata_for_each_available_course(self):
        courses = [
            {
                "id": "99-002",
                "name": "Ordinary option",
                "units": 9,
                "offered": ["fall"],
                "prerequisites": [],
                "minimum_year": 1,
            },
            {
                "id": "99-001",
                "name": "Prepared option",
                "units": 9,
                "offered": ["fall"],
                "prerequisites": [],
                "minimum_year": 1,
                "recommended_preparation": ["99-000"],
            },
        ]
        path = generate_semester_path(
            completed_courses=["99-000"],
            courses=courses,
            program_id="metadata-priority",
            requirements={
                "metadata-priority": {
                    "required_courses": ["99-002", "99-001"]
                }
            },
            start_semester="fall",
            num_semesters=1,
            max_units=9,
            first_semester_max_units=9,
        )

        self.assertEqual(path["path"][0]["courses"], ["99-001"])

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

    def test_transfer_audit_separates_scheduled_from_academic_completion(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        request.student.completed_courses = ["15-112", "21-127", "36-200"]
        result = app.create_plan(request)
        audit = result["degree_audits"]["selected_goal"]
        self.assertNotEqual(audit["status"], "not_verified")
        self.assertIn("all_requirements_scheduled", audit)
        self.assertIn("requirements_remaining_to_complete", audit)
        self.assertTrue(result["program_profile"]["eligibility"])

    def test_infeasible_deadline_returns_structured_warning(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "engineering",
            "program": "electrical-and-computer-engineering",
            "include_post_transfer_plan": True,
        })
        request.constraints.target_completion_year = 2
        result = app.create_plan(request)
        codes = {warning["code"] for warning in result["planning_warnings"]}
        self.assertIn("TARGET_DEADLINE_NOT_MET", codes)
        self.assertIn("ELIGIBILITY_CHECKPOINT", codes)

    def test_transfer_replaces_unverified_former_major_instead_of_reserving_it(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        request.student.primary_major = "economics--b-a"
        result = app.create_plan(request)
        codes = {warning["code"] for warning in result["planning_warnings"]}
        self.assertNotIn("PRIMARY_CURRICULUM_ESTIMATED", codes)
        self.assertEqual(result["primary_baseline"]["status"], "replaced_by_transfer")
        self.assertTrue(all(
            semester["primary_major_reserved_units"] == 0
            for semester in result["fastest"]["path"]
        ))

    def test_ece_transfer_defaults_to_official_eligibility_courses(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "engineering",
            "program": "electrical-and-computer-engineering",
        })
        result = app.create_plan(request)
        scheduled = {
            course_id
            for semester in result["fastest"]["path"]
            for course_id in semester["courses"]
        } | {
            item["default_option"]
            for semester in result["fastest"]["path"]
            for item in semester["program_requirements"]
            if item.get("default_option")
        }
        self.assertEqual(result["transfer_planning"]["mode"], "eligibility")
        self.assertIn("18-100", scheduled)
        self.assertIn("21-120", scheduled)
        self.assertTrue({"15-110", "15-112"}.intersection(scheduled))
        self.assertTrue({"33-121", "33-141", "33-151"}.intersection(scheduled))

    def test_completed_transfer_checkpoint_returns_success_instead_of_409(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "dietrich",
            "program": "information-systems",
        })
        request.student.completed_courses = ["15-112"]
        result = app.create_plan(request)
        self.assertTrue(result["fastest"]["goal_complete"])
        self.assertEqual(result["fastest"]["remaining_program_requirements"], [])

    def test_cs_transfer_checkpoint_lists_the_six_official_admission_courses(self):
        detail = app.get_program_profile("computer-science", "internal_transfer")
        course_ids = [course["id"] for course in detail["fixed_courses"]]

        self.assertEqual(
            course_ids,
            ["21-127", "15-122", "15-150", "15-210", "15-213", "15-251"],
        )
        self.assertNotIn("15-112", course_ids)
        self.assertEqual(detail["transfer_eligibility"]["preparation_courses"], ["15-112"])

    def test_is_transfer_checkpoint_preserves_programming_requirement_after_completion(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "dietrich",
            "program": "information-systems",
        })
        request.student.completed_courses = ["15-112"]
        result = app.create_plan(request)
        groups = result["transfer_planning"]["policy"]["requirement_groups"]

        self.assertEqual(groups[0]["options"], ["15-112", "02-120"])
        self.assertTrue(result["fastest"]["goal_complete"])
        action_names = {
            item["name"]
            for item in result["transfer_planning"]["policy"]["application_requirements"]
        }
        self.assertIn("Personal statement", action_names)
        self.assertIn("IS academic advisor interview", action_names)

    def test_is_ready_student_keeps_one_current_major_term_then_applies(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "dietrich",
            "program": "information-systems",
        })
        request.student.completed_courses = ["15-112"]
        request.student.year = 1
        request.constraints.planning_year = 1
        request.constraints.start_semester = "spring"
        request.constraints.target_completion_year = 2
        result = app.create_plan(request)
        path = result["fastest"]["path"]

        self.assertEqual(len(path), 1)
        self.assertTrue(path[0]["courses"])
        self.assertTrue(any(
            block.get("kind") in {"current_major", "shared"}
            for block in path[0]["course_blocks"]
        ))
        self.assertEqual(
            path[0]["milestones"][0]["name"],
            "Apply for internal transfer",
        )
        self.assertIn(
            "last day of classes",
            path[0]["milestones"][0]["description"],
        )
        self.assertEqual(
            result["transfer_planning"]["application_term"],
            {"semester": "spring", "academic_year": 1, "academic_year_name": "Freshman"},
        )

    def test_is_post_transfer_plan_is_opt_in(self):
        eligibility_request = self.shared_request({
            "type": "internal_transfer",
            "college": "dietrich",
            "program": "information-systems",
        })
        degree_request = self.shared_request({
            "type": "internal_transfer",
            "college": "dietrich",
            "program": "information-systems",
            "include_post_transfer_plan": True,
        })
        eligibility = app.create_plan(eligibility_request)
        degree = app.create_plan(degree_request)
        self.assertEqual(eligibility["transfer_planning"]["mode"], "eligibility")
        self.assertEqual(degree["transfer_planning"]["mode"], "post_transfer_degree")
        self.assertLess(
            eligibility["program_profile"]["minimum_courses"],
            degree["program_profile"]["minimum_courses"],
        )

    def test_new_regression_goal_profiles_are_plannable(self):
        scenarios = [
            ("internal_transfer", "stats-ml"),
            ("internal_transfer", "mechanical-engineering"),
            ("additional_major", "economics"),
            ("minor", "business-administration"),
        ]
        for goal_type, program in scenarios:
            request = self.shared_request({
                "type": goal_type,
                "program": program,
            })
            result = app.create_plan(request)
            self.assertTrue(result["fastest"]["path"], program)
            self.assertIsNotNone(result["program_profile"], program)

    def test_scs_student_gets_explicit_machine_learning_minor_ineligibility(self):
        request = self.shared_request({
            "type": "minor",
            "program": "machine-learning",
        })
        request.student.college = "scs"
        request.student.primary_major = "computer-science"
        with self.assertRaises(HTTPException) as context:
            app.create_plan(request)
        self.assertEqual(context.exception.status_code, 409)
        self.assertIn("only to students outside SCS", context.exception.detail)

    def test_directory_automatically_exposes_every_configured_profile(self):
        directory = app.list_program_directory()["programs"]
        expected = {
            ("economics", "additional_major"),
            ("business-administration", "minor"),
            ("machine-learning", "minor"),
        }
        available = {
            (item.get("planning_id"), item["program_type"])
            for item in directory
            if item.get("planning_status") == "planning_ready"
        }
        self.assertTrue(expected.issubset(available))

    def test_all_six_scs_transfer_programs_are_planning_ready(self):
        expected = {
            "artificial-intelligence",
            "computational-biology",
            "computer-science",
            "computer-science-and-arts",
            "human-computer-interaction",
            "robotics",
        }
        directory = app.list_program_directory(
            college="scs", program_type="primary_major"
        )["programs"]
        ready = {
            item.get("planning_id")
            for item in directory
            if item.get("planning_status") == "planning_ready"
        }
        self.assertEqual(ready, expected)

    def test_new_scs_transfer_profiles_generate_real_choice_slots(self):
        expected_groups = {
            "artificial-intelligence": {"SCS core course", "Probability"},
            "computational-biology": {
                "Algorithms course", "Introduction to Computational Biology"
            },
            "human-computer-interaction": {
                "SCS core course", "HCI implementation course"
            },
            "robotics": {"Probability", "Robotics course"},
        }
        for program, group_names in expected_groups.items():
            with self.subTest(program=program):
                request = self.shared_request({
                    "type": "internal_transfer",
                    "college": "scs",
                    "program": program,
                })
                baseline = app.create_baseline(request)
                self.assertEqual(
                    baseline["planner_status"], "ready_with_requirement_slots"
                )
                result = app.create_plan(request)
                self.assertTrue(result["fastest"]["path"])
                profile = result["program_profile"]
                self.assertEqual(profile["minimum_courses"], 6)
                self.assertEqual(
                    {group["name"] for group in profile["requirement_groups"]},
                    group_names,
                )

    def test_every_ready_primary_major_has_a_current_major_audit(self):
        directory = app.list_program_directory(program_type="primary_major")["programs"]
        for item in directory:
            if item.get("current_major_planning_status") != "planning_ready":
                continue
            profile = app.get_primary_major_profile(item["planning_id"])
            self.assertTrue(profile["fixed_courses"] or profile["requirement_groups"])

    def test_popular_current_major_audits_are_verified_and_structured(self):
        expected_groups = {
            "computer-science": {
                "probability", "artificial-intelligence", "domains",
                "logic-languages", "software-systems", "scs-electives",
            },
            "electrical-and-computer-engineering": {
                "probability", "math-science", "ece-foundations",
                "ece-coverage", "ece-advanced", "ece-capstone",
            },
            "information-systems": {
                "mathematics", "programming", "data-structures", "hci-core",
                "professional-communication", "quantitative-analysis",
                "innovation", "concentration",
            },
        }
        for planning_id, required_group_ids in expected_groups.items():
            profile = app.get_primary_major_profile(planning_id)
            self.assertEqual(profile["curriculum_status"], "verified")
            self.assertGreater(profile["minimum_degree_units"], 0)
            groups = {group["id"]: group for group in profile["requirement_groups"]}
            self.assertTrue(required_group_ids.issubset(groups))
            self.assertTrue(all(group["options"] for group in groups.values()))

    def test_popular_current_majors_generate_without_placeholder_slots(self):
        colleges = {
            "computer-science": "scs",
            "electrical-and-computer-engineering": "engineering",
            "information-systems": "dietrich",
        }
        for planning_id, college in colleges.items():
            request = app.PlanningRequest(
                student=app.StudentState(
                    college=college,
                    primary_major=planning_id,
                    year=1,
                    completed_courses=[],
                ),
                goals=[app.PlanningGoal(type="current_major", program=planning_id)],
            )
            result = app.create_plan(request)
            slots = [
                slot
                for semester in result["fastest"]["path"]
                for slot in semester.get("program_requirements", [])
            ] + result["fastest"]["remaining_program_requirements"]
            self.assertTrue(slots)
            self.assertTrue(all(
                not option.startswith("Approved ")
                for slot in slots
                for option in slot.get("options", [])
            ))

    def test_transfer_advice_sends_only_verified_server_context(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        expected = {
            "recommendation": "Continue with advisor confirmation.",
            "feasibility": "The generated plan places the supplied requirements.",
            "opportunity_cost": "The plan uses units that could otherwise be electives.",
            "backup_strength": "The current major remains represented in the plan.",
            "key_risks": ["Admission is capacity limited."],
            "next_steps": ["Confirm the current application timing."],
            "summary": "A plausible course plan, not an admission guarantee.",
        }
        response = Mock()
        response.json.return_value = {
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(expected)}],
            }]
        }
        response.raise_for_status.return_value = None

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch.object(application.requests, "post", return_value=response) as post:
                self.assertEqual(app.transfer_advice(request), expected)

        url = post.call_args.args[0]
        options = post.call_args.kwargs
        sent_context = json.loads(options["json"]["input"])
        self.assertEqual(url, "https://api.openai.com/v1/responses")
        self.assertEqual(options["headers"]["Authorization"], "Bearer test-key")
        self.assertFalse(options["json"]["store"])
        self.assertEqual(options["json"]["text"]["format"]["type"], "json_schema")
        self.assertIn("verified_policy", sent_context)
        self.assertIn("generated_plan", sent_context)
        self.assertNotIn("test-key", options["json"]["input"])
        self.assertNotIn("tools", options["json"])

    def test_transfer_advice_requires_server_api_key(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                app.transfer_advice(request)
        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
