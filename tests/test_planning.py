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

    def test_stats_ml_student_without_calculus_credit_gets_calculus_choice(self):
        request = self.shared_request({
            "type": "internal_transfer",
            "college": "scs",
            "program": "computer-science",
        })
        path = app.create_plan(request)["fastest"]["path"]
        primary_choices = {
            item.get("default_option")
            for semester in path
            for item in semester["program_requirements"]
            if item.get("scope") == "primary_major"
        }
        self.assertIn("21-120", primary_choices)

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
            if any(
                item.get("default_option") == "21-120"
                for item in semester["program_requirements"]
            )
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
