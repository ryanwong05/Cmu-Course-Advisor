import unittest
from pathlib import Path

from Scripts.scrape_cmu import (
    extract_dietrich_requirement_section,
    parse_robotics_policies,
)


FIXTURE = Path(__file__).parent / "fixtures" / "robotics_transfer.txt"


class RoboticsScraperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policies = parse_robotics_policies(FIXTURE.read_text(encoding="utf-8"))

    def test_policies_are_split_by_audience(self):
        self.assertEqual(
            [policy["audience"] for policy in self.policies],
            ["scs_students", "non_scs_students"],
        )

    def test_each_audience_has_six_requirement_groups(self):
        self.assertEqual([len(item["requirements"]) for item in self.policies], [6, 6])

    def test_non_scs_qpa_is_linked_to_requirements(self):
        qpa = self.policies[1]["qpa_requirements"]
        self.assertEqual(qpa["overall"], 3.0)
        self.assertEqual(qpa["course_group"]["minimum"], 3.6)
        self.assertEqual(
            qpa["course_group"]["applies_to"]["type"],
            "requirement_groups",
        )
        self.assertEqual(
            len(qpa["course_group"]["applies_to"]["requirement_ids"]),
            6,
        )

    def test_final_dietrich_section_stops_before_repeated_page_content(self):
        text = (
            "\nExperiential Learning Activity\n1 unit\n"
            "Must be completed after first semester\n"
            "Total General Education\n115 units\n"
            "Foundations\n36-200, Reasoning with Data\n"
        )
        section = extract_dietrich_requirement_section(
            text,
            "Experiential Learning Activity",
        )
        self.assertNotIn("36-200", section)


if __name__ == "__main__":
    unittest.main()
