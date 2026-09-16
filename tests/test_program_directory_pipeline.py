import unittest
from unittest.mock import patch

from Scripts.data_pipeline.scrape_program_directory import (
    load_planning_capabilities,
    planning_identity,
)
from Scripts.data_pipeline.audit_program_coverage import transfer_policy_coverage


class ProgramDirectoryPipelineTests(unittest.TestCase):
    def test_planning_identity_uses_verified_capabilities(self):
        capabilities = {
            "robotics": {"primary_major", "additional_major"},
        }

        self.assertEqual(
            planning_identity("Robotics", "additional_major", capabilities, {}),
            ("robotics", "planning_ready"),
        )
        self.assertEqual(
            planning_identity("Robotics", "minor", capabilities, {}),
            (None, "directory_only"),
        )

    def test_planning_identity_applies_data_driven_aliases(self):
        capabilities = {"stats-ml": {"primary_major"}}
        aliases = {"statistics-and-machine-learning": "stats-ml"}

        self.assertEqual(
            planning_identity(
                "Statistics and Machine Learning",
                "primary_major",
                capabilities,
                aliases,
            ),
            ("stats-ml", "planning_ready"),
        )

    def test_capabilities_are_derived_from_live_data_sources(self):
        profiles = {
            "programs": {
                "robotics": {
                    "additional_major": {"minimum_courses": 6},
                    "minor": {"minimum_courses": 6},
                }
            }
        }
        requirements = {
            "mechanical-engineering-major": {"planner_status": "ready"},
            "logic-and-computation-transfer": {"planner_status": "ready"},
            "economics-additional-major": {"planner_status": "ready"},
        }

        with patch(
            "Scripts.data_pipeline.scrape_program_directory.load_json",
            side_effect=[profiles, requirements],
        ):
            capabilities = load_planning_capabilities()

        self.assertEqual(
            capabilities["robotics"],
            {"additional_major", "minor"},
        )
        self.assertEqual(
            capabilities["mechanical-engineering"],
            {"primary_major"},
        )
        self.assertEqual(
            capabilities["logic-and-computation"],
            {"primary_major"},
        )
        self.assertEqual(
            capabilities["economics"],
            {"additional_major"},
        )

    def test_transfer_coverage_is_separate_from_curriculum_coverage(self):
        programs = [
            {"id": "statistics--b-s", "name": "Statistics", "program_type": "primary_major"},
            {"id": "robotics--b-s", "name": "Robotics", "program_type": "primary_major"},
            {"id": "history--b-a", "name": "History", "program_type": "primary_major"},
            {"id": "history--minor", "name": "History", "program_type": "minor"},
        ]

        def fake_load(path, default):
            if path.name == "transfer_requirements.json":
                return {"eligibility_profiles": {"stats": {}}}
            if path.name == "program_profiles.json":
                return {"programs": {"robotics": {"internal_transfer": {"minimum_courses": 1}}}}
            if path.name == "program_id_aliases.json":
                return {"aliases": {"statistics": "stats"}}
            return default

        with patch(
            "Scripts.data_pipeline.audit_program_coverage.load_json",
            side_effect=fake_load,
        ):
            result = transfer_policy_coverage(programs)

        self.assertEqual(result["catalog_primary_major_count"], 3)
        self.assertEqual(result["published_transfer_profile_count"], 2)
        self.assertEqual(result["coverage_percent"], 66.7)


if __name__ == "__main__":
    unittest.main()
