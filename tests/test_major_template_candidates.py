import unittest

from Scripts.data_pipeline.build_major_template_candidates import build_candidate


class MajorTemplateCandidateTests(unittest.TestCase):
    def test_candidate_is_never_marked_ready_or_verified(self):
        source = {
            "catalog_year": "2026-2027",
            "program_id": "example--b-s",
            "planning_id": "example",
            "name": "Example",
            "credential": "B.S.",
            "source_url": "https://example.test",
            "source_hash": "abc",
            "fixed_courses": [{"id": "15-112", "units": 12}],
            "requirement_groups": [{
                "id": "math", "name": "Math", "choose": 1,
                "units": 10, "options": ["21-120"],
            }],
            "extraction": {"confidence": 0.95},
            "validation": {"promotion_ready": True},
        }
        result = build_candidate(source)
        self.assertEqual(result["planner_status"], "review_required")
        self.assertEqual(result["curriculum_status"], "catalog_extracted_candidate")
        self.assertEqual(result["minimum_major_units_estimate"], 22)
