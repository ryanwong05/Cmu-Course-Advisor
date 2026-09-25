import io
import unittest

from PIL import Image

import app
from Backend.academic_history_import import (
    AcademicHistoryFile,
    AcademicHistoryImportError,
    LocalOllamaVisionAcademicHistoryExtractor,
    MockAcademicHistoryExtractor,
    extract_academic_history,
    merge_academic_history,
    normalize_course_id,
)
from Engine.availability import prerequisites_satisfied
from Engine.student_state import derive_academic_state


def scheduled_course_ids(result):
    return {
        course_id
        for semester in result["fastest"]["path"]
        for course_id in semester.get("courses", [])
    }


class AcademicHistoryImportTests(unittest.TestCase):
    def setUp(self):
        self.catalog = app.courses
        self.raw_courses = {
            "courses": [
                {
                    "course_id": "15-112",
                    "course_name": "OCR title is not trusted",
                    "semester": "fall",
                    "year": 2025,
                    "status": "completed",
                    "confidence": 0.95,
                },
                {
                    "course_id": "21 127",
                    "semester": "spring",
                    "year": 2026,
                    "status": "in progress",
                    "confidence": 0.9,
                },
                {
                    "course_id": "36200",
                    "semester": "fall",
                    "year": 2026,
                    "status": "planned",
                    "confidence": 0.9,
                },
            ]
        }

    def test_image_import_mock_produces_canonical_records(self):
        image = Image.new("RGB", (8, 8), "white")
        content = io.BytesIO()
        image.save(content, format="PNG")
        result = extract_academic_history(
            AcademicHistoryFile("sio.png", "image/png", content.getvalue()),
            self.catalog,
            MockAcademicHistoryExtractor(self.raw_courses),
        )
        self.assertEqual(
            [record["course_id"] for record in result["courses"]],
            ["15-112", "21-127", "36-200"],
        )
        self.assertEqual(
            result["courses"][0]["course_name"],
            next(course["name"] for course in self.catalog if course["id"] == "15-112"),
        )

    def test_pdf_import_mock_uses_same_canonical_structure(self):
        result = extract_academic_history(
            AcademicHistoryFile("sio.pdf", "application/pdf", b"%PDF-1.7\nfixture"),
            self.catalog,
            MockAcademicHistoryExtractor(self.raw_courses),
        )
        self.assertEqual(result["recognized_count"], 3)
        self.assertTrue(all(record["catalog_validated"] for record in result["courses"]))

    def test_normalization_accepts_only_unambiguous_five_digit_ids(self):
        self.assertEqual(normalize_course_id("15112"), "15-112")
        self.assertEqual(normalize_course_id("15 112"), "15-112")
        self.assertEqual(normalize_course_id("15-112"), "15-112")
        self.assertIsNone(normalize_course_id("36-20"))

    def test_unknown_course_is_flagged_and_cannot_be_committed(self):
        raw = {"courses": [{
            "course_id": "99-999",
            "semester": "fall",
            "year": 2026,
            "status": "completed",
        }]}
        result = extract_academic_history(
            AcademicHistoryFile("sio.pdf", "application/pdf", b"%PDF-1.7\nfixture"),
            self.catalog,
            MockAcademicHistoryExtractor(raw),
        )
        self.assertIn("unknown_course", result["courses"][0]["issues"])
        with self.assertRaises(AcademicHistoryImportError):
            merge_academic_history({}, result["courses"], self.catalog)

    def test_duplicate_existing_course_is_merged_once(self):
        merged = merge_academic_history(
            {"completed_courses": ["21-127"]},
            [{
                "course_id": "21-127",
                "semester": "fall",
                "year": 2025,
                "status": "completed",
            }],
            self.catalog,
        )
        self.assertEqual(merged["student"]["completed_courses"], ["21-127"])
        self.assertEqual(merged["duplicate_count"], 1)

    def test_statuses_remain_distinct_in_canonical_state(self):
        merged = merge_academic_history(
            {},
            [
                {"course_id": "15-112", "status": "completed"},
                {"course_id": "21-127", "status": "in_progress"},
                {"course_id": "36-200", "status": "planned"},
            ],
            self.catalog,
        )["student"]
        state = derive_academic_state(merged, app.expand_completed_courses)
        self.assertIn("15-112", state["completed_courses"])
        self.assertEqual(state["in_progress_courses"], ["21-127"])
        self.assertEqual(state["planned_courses"], ["36-200"])

    def test_manual_and_imported_source_have_identical_planning_effect(self):
        imported = merge_academic_history(
            {}, [{"course_id": "21-127", "status": "completed"}], self.catalog
        )["student"]
        manual_state = derive_academic_state(
            {"completed_courses": ["21-127"]}, app.expand_completed_courses
        )
        imported_state = derive_academic_state(imported, app.expand_completed_courses)
        self.assertEqual(manual_state["completed_courses"], imported_state["completed_courses"])

    def test_imported_course_updates_transfer_and_post_transfer_planning(self):
        merged_student = merge_academic_history(
            {
                "college": "dietrich",
                "primary_major": "linguistics",
                "year": 1,
                "enrollment_status": "enrolled",
                "current_term": "fall",
            },
            [{"course_id": "21-127", "status": "completed"}],
            self.catalog,
        )["student"]
        request = app.PlanningRequest(
            student=app.StudentState(**merged_student),
            goals=[app.PlanningGoal(
                type="internal_transfer",
                college="scs",
                program="computer-science",
            )],
        )
        result = app.create_plan(request)
        self.assertNotIn("21-127", scheduled_course_ids(result))

    def test_prerequisite_analysis_reuses_boolean_expression_engine(self):
        course = next(course for course in self.catalog if course["id"] == "21-127")
        self.assertTrue(prerequisites_satisfied(course, ["15-112"]))
        self.assertFalse(prerequisites_satisfied(course, []))
        analysis = app.prerequisite_analysis_for_student({
            "completed_courses": ["15-112"],
            "in_progress_courses": ["21-127"],
        })
        self.assertEqual(analysis[0]["status"], "satisfied")

    def test_result_does_not_contain_raw_document_bytes(self):
        marker = "PRIVATE_STUDENT_IDENTIFIER"
        result = extract_academic_history(
            AcademicHistoryFile("sio.pdf", "application/pdf", b"%PDF-1.7\n" + marker.encode()),
            self.catalog,
            MockAcademicHistoryExtractor({"courses": []}),
        )
        self.assertNotIn(marker, repr(result))

    def test_private_vision_provider_is_restricted_to_loopback(self):
        self.assertEqual(
            LocalOllamaVisionAcademicHistoryExtractor.endpoint,
            "http://127.0.0.1:11434/api/chat",
        )

    def test_malformed_partial_record_does_not_discard_valid_records(self):
        raw = {"courses": [self.raw_courses["courses"][0], "not-a-record"]}
        result = extract_academic_history(
            AcademicHistoryFile("sio.pdf", "application/pdf", b"%PDF-1.7\nfixture"),
            self.catalog,
            MockAcademicHistoryExtractor(raw),
        )
        self.assertEqual(result["recognized_count"], 1)
        self.assertTrue(result["warnings"])


if __name__ == "__main__":
    unittest.main()
