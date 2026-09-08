import unittest

from Scripts.data_pipeline.scrape_major_curricula import parse_curriculum_html, validate_curriculum


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


if __name__ == "__main__":
    unittest.main()
