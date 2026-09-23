import unittest
from unittest.mock import patch
from pathlib import Path

from Scripts.data_pipeline.scrape_program_directory import (
    annotate_program_availability,
    load_planning_capabilities,
    merge_reviewed_inventory_entries,
    planning_identity,
)
from Scripts.data_pipeline.audit_program_coverage import transfer_policy_coverage


class ProgramDirectoryPipelineTests(unittest.TestCase):
    def test_frontend_uses_canonical_directory_without_program_allowlist(self):
        app_js = Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn("payload.canonical_programs", app_js)
        self.assertIn("program.available_as", app_js)
        self.assertNotIn("temporarySCSPrograms", app_js)

    def test_availability_is_derived_from_one_canonical_inventory(self):
        programs = annotate_program_availability([
            {"id": "sample--b-s", "name": "Sample", "program_type": "primary_major"},
            {"id": "sample--additional", "name": "Sample", "program_type": "additional_major"},
            {"id": "sample--minor", "name": "Sample", "program_type": "minor"},
        ])

        self.assertEqual(
            programs[0]["available_as"],
            ["additional_major", "minor", "primary_major"],
        )
        self.assertTrue(all(
            program["canonical_program_id"] == "sample" for program in programs
        ))

    def test_reviewed_discovery_entry_does_not_imply_planner_support(self):
        base = [{
            "id": "sample--b-s",
            "name": "Sample",
            "program_type": "primary_major",
            "home_colleges": ["mcs"],
            "affiliations": ["mcs"],
            "interdisciplinary": False,
            "source_url": "https://example.test/sample/",
        }]
        review = {
            "catalog_year": "2026-2027",
            "reviewed_entries": [{
                "id": "sample--additional-major",
                "name": "Sample",
                "credential": "Additional Major",
                "program_type": "additional_major",
                "inherits_from": "sample--b-s",
                "requirements_source_program_id": "sample--b-s",
                "evidence_heading": "Additional Major",
            }],
        }

        merged = merge_reviewed_inventory_entries(base, review, {}, {})
        added = merged[-1]
        self.assertEqual(added["planning_status"], "directory_only")
        self.assertIsNone(added["planning_id"])
        self.assertEqual(added["home_colleges"], ["mcs"])

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
