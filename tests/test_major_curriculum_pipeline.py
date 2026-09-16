import unittest

from Scripts.data_pipeline.scrape_major_curricula import (
    choose_count,
    parse_curriculum_html,
    shared_credit_signals,
    validate_curriculum,
)
from Scripts.data_pipeline.build_major_template_candidates import build_candidate


class MajorCurriculumPipelineTests(unittest.TestCase):
    def test_extracts_fixed_courses_and_choose_groups(self):
        html = """
        <main><h2>Curriculum</h2><h3>Technical Core</h3>
        <p>Complete all of the following courses:</p>
        <table><tr><td>15-112</td><td>Programming</td><td>12</td></tr>
        <tr><td>15-122</td><td>Imperative Computation</td><td>12</td></tr></table>
        <h3>Mathematics</h3><p>Complete one of the following courses:</p>
        <table><tr><td>21-120</td><td>Calculus</td><td>10</td></tr>
        <tr><td>21-127</td><td>Concepts</td><td>12</td></tr></table>
        <h3>Sample Schedule</h3><table><tr><td>99-999</td><td>Ignore</td><td>9</td></tr></table>
        </main>
        """
        program = {"id":"example--b-s","name":"Example","credential":"B.S.","source_url":"https://example.test"}
        result = parse_curriculum_html(html, program)
        self.assertEqual([item["id"] for item in result["fixed_courses"]], ["15-112", "15-122"])
        self.assertEqual(result["requirement_groups"][0]["choose"], 1)
        self.assertEqual(result["requirement_groups"][0]["options"], ["21-120", "21-127"])
        self.assertNotIn("99-999", str(result))

    def test_validation_separates_candidates_from_promotion(self):
        curriculum = {
            "fixed_courses": [{"id": "15-112"}],
            "requirement_groups": [{"id": "math", "choose": 1, "options": ["21-120"]}],
            "extraction": {
                "status": "high_confidence_candidate",
                "warnings": [],
            },
        }
        result = validate_curriculum(curriculum, {"15-112", "21-120"})
        self.assertTrue(result["promotion_ready"])
        self.assertEqual(result["blockers"], [])

    def test_implausible_unit_total_blocks_promotion(self):
        curriculum = {
            "fixed_courses": [{"id": "15-112", "units": 400}],
            "requirement_groups": [],
            "extraction": {"status": "high_confidence_candidate", "warnings": []},
        }
        result = validate_curriculum(curriculum, {"15-112"})
        self.assertFalse(result["promotion_ready"])
        self.assertTrue(any("implausible" in item for item in result["blockers"]))

    def test_unresolved_selection_rule_blocks_automatic_promotion(self):
        curriculum = {
            "fixed_courses": [{"id": "15-112", "units": 12}],
            "requirement_groups": [{
                "id": "electives", "choose": 1, "units": 9,
                "options": ["15-122", "15-150"],
                "selection_rule": {"type": "unresolved", "count": 1},
            }],
            "extraction": {"status": "high_confidence_candidate", "warnings": []},
        }
        result = validate_curriculum(curriculum, {"15-112", "15-122", "15-150"})
        self.assertFalse(result["promotion_ready"])
        self.assertTrue(any("unresolved selection" in item for item in result["blockers"]))

    def test_unit_requirement_is_not_misread_as_choice_count(self):
        self.assertIsNone(choose_count("Students select 18 units, typically two courses."))
        self.assertEqual(choose_count("Overview (one of the following)"), 1)
        self.assertEqual(choose_count("Survey courses (choose two)"), 2)

    def test_ignores_prerequisite_ids_outside_course_code_cell(self):
        html = """
        <main><h2>Curriculum</h2><h3>Required Courses</h3>
        <table><tr><td class="codecol">15-122</td>
        <td>Programming (prerequisite: 15-112)</td><td class="hourscol">12</td></tr></table>
        </main>
        """
        program = {
            "id": "example--minor", "name": "Example", "credential": "Minor",
            "program_type": "minor", "source_url": "https://example.test",
        }
        result = parse_curriculum_html(html, program)
        self.assertEqual([item["id"] for item in result["fixed_courses"]], ["15-122"])
        extracted_ids = [item["id"] for item in result["fixed_courses"]]
        extracted_ids += [
            option
            for group in result["requirement_groups"]
            for option in group["options"]
        ]
        self.assertNotIn("15-112", extracted_ids)
        self.assertEqual(result["program_type"], "minor")

    def test_infers_choice_count_from_uniform_courses_and_explicit_units(self):
        html = """
        <main><h2>Curriculum</h2><h3>Methods Electives</h3>
        <p>Select 18 units from the following courses.</p>
        <table>
        <tr><td class="codecol">36-200</td><td>Reasoning</td><td class="hourscol">9</td></tr>
        <tr><td class="codecol">36-202</td><td>Methods</td><td class="hourscol">9</td></tr>
        <tr><td class="codecol">36-220</td><td>Data</td><td class="hourscol">9</td></tr>
        </table></main>
        """
        program = {"id":"example--minor","name":"Example","credential":"Minor","source_url":"https://example.test"}
        result = parse_curriculum_html(html, program)
        self.assertEqual(result["requirement_groups"][0]["choose"], 2)
        self.assertEqual(result["requirement_groups"][0]["units"], 18)
        self.assertEqual(
            result["requirement_groups"][0]["selection_rule"],
            {"type": "minimum_units", "minimum_units": 18.0, "course_count_estimate": 2},
        )

    def test_ignores_nested_sample_course_sequence(self):
        html = """
        <main><h2>Program Requirements</h2><h3>Roadmap: Sample Course Sequence</h3>
        <h4>First Year</h4><table><tr><td class="codecol">99-999</td>
        <td>Example only</td><td class="hourscol">9</td></tr></table></main>
        """
        program = {"id":"example--b-s","name":"Example","credential":"B.S.","source_url":"https://example.test"}
        result = parse_curriculum_html(html, program)
        self.assertNotIn("99-999", str(result))

    def test_candidate_preserves_program_type_and_selection_rule(self):
        curriculum = {
            "catalog_year": "2026-2027",
            "program_id": "example--minor",
            "planning_id": "example",
            "name": "Example",
            "credential": "Minor",
            "program_type": "minor",
            "source_url": "https://example.test",
            "source_hash": "hash",
            "fixed_courses": [{"id": "15-112", "units": 12}],
            "requirement_groups": [{
                "id": "electives", "name": "Electives", "choose": 2,
                "units": 18, "options": ["15-122", "15-150"],
                "selection_rule": {"type": "minimum_units", "minimum_units": 18},
            }],
            "extraction": {"confidence": 0.9},
            "validation": {"promotion_ready": True},
        }
        candidate = build_candidate(curriculum)
        self.assertEqual(candidate["program_type"], "minor")
        self.assertEqual(
            candidate["requirement_groups"][0]["selection_rule"],
            {"type": "minimum_units", "minimum_units": 18},
        )

    def test_required_rows_with_or_lines_become_substitution_groups(self):
        html = """
        <main><h2>Curriculum</h2><h3>Required Courses</h3><table>
        <tr><td class="codecol">21-120</td><td>Calculus</td><td class="hourscol">10</td></tr>
        <tr><td class="codecol">or 21-111 &amp; 21-112</td><td>Calculus sequence</td><td class="hourscol">20</td></tr>
        <tr><td class="codecol">21-122</td><td>Integration</td><td class="hourscol">10</td></tr>
        </table></main>
        """
        program = {"id":"example--b-s","name":"Example","credential":"B.S.","source_url":"https://example.test"}
        result = parse_curriculum_html(html, program)
        self.assertEqual([item["id"] for item in result["fixed_courses"]], ["21-122"])
        self.assertEqual(
            result["requirement_groups"][0]["options"],
            ["21-120", "21-111 + 21-112"],
        )
        self.assertEqual(result["requirement_groups"][0]["relationship"], "substitution")

    def test_crosslisted_required_course_is_one_choice_not_two_fixed_courses(self):
        html = """
        <main><h2>Curriculum</h2><h3>Required Courses</h3><table>
        <tr><td class="codecol">03-360/02-319</td><td>Genomics</td><td class="hourscol">9</td></tr>
        </table></main>
        """
        program = {"id":"example--minor","name":"Example","credential":"Minor","source_url":"https://example.test"}
        result = parse_curriculum_html(html, program)
        self.assertEqual(result["fixed_courses"], [])
        self.assertEqual(result["requirement_groups"][0]["options"], ["03-360", "02-319"])

    def test_category_tables_share_one_heading_level_minimum_unit_rule(self):
        html = """
        <main><h2>Curriculum</h2><h3>Electives 18 units</h3>
        <p>Category A</p><table>
        <tr><td class="codecol">36-200</td><td>A</td><td class="hourscol">9</td></tr>
        <tr><td class="codecol">36-202</td><td>B</td><td class="hourscol">9</td></tr></table>
        <p>Category B</p><table>
        <tr><td class="codecol">36-220</td><td>C</td><td class="hourscol">9</td></tr>
        <tr><td class="codecol">36-230</td><td>D</td><td class="hourscol">9</td></tr></table>
        </main>
        """
        program = {"id":"example--minor","name":"Example","credential":"Minor","source_url":"https://example.test"}
        result = parse_curriculum_html(html, program)
        self.assertEqual(len(result["requirement_groups"]), 1)
        group = result["requirement_groups"][0]
        self.assertEqual(group["choose"], 2)
        self.assertEqual(group["options"], ["36-200", "36-202", "36-220", "36-230"])
        self.assertEqual(group["selection_rule"]["minimum_units"], 18.0)

    def test_multiple_tracks_without_selection_rule_are_blocked(self):
        html = """
        <main><h2>Curriculum</h2>
        <h3>Alpha Track Core Courses</h3><table>
        <tr><td class="codecol">15-210</td><td>Alpha</td><td class="hourscol">12</td></tr></table>
        <h3>Beta Track Core Courses</h3><table>
        <tr><td class="codecol">15-213</td><td>Beta</td><td class="hourscol">12</td></tr></table>
        </main>
        """
        program = {"id":"example--b-s","name":"Example","credential":"B.S.","source_url":"https://example.test"}
        result = parse_curriculum_html(html, program)
        validation = validate_curriculum(result, {"15-210", "15-213"})
        self.assertEqual(result["track_rule"]["type"], "unresolved")
        self.assertTrue(any("track-selection" in blocker for blocker in validation["blockers"]))

    def test_shared_credit_is_extracted_as_reviewable_policy_signal(self):
        signals = shared_credit_signals(
            "Students may double-count at most two courses with another minor. "
            "Unlimited double counting is permitted with general education requirements."
        )
        self.assertTrue(signals["present"])
        self.assertEqual(signals["course_limit_candidates"], [2])
        self.assertTrue(signals["unlimited_exception_present"])


if __name__ == "__main__":
    unittest.main()
