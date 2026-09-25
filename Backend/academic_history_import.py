"""Academic-history document extraction and catalog validation.

This module reads facts from an uploaded document. It deliberately does not
interpret CMU degree requirements; downstream engines continue to own policy.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import requests

SUPPORTED_MEDIA_TYPES = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpeg",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
VALID_STATUSES = {"completed", "in_progress", "planned"}
VALID_SEMESTERS = {"fall", "spring", "summer"}


class AcademicHistoryImportError(ValueError):
    """Safe, user-facing import failure."""


@dataclass(frozen=True)
class AcademicHistoryFile:
    filename: str
    content_type: str
    content: bytes


class AcademicHistoryExtractor(ABC):
    """Provider-neutral extraction interface."""

    @abstractmethod
    def extract(self, document: AcademicHistoryFile) -> dict[str, Any]:
        """Return raw semesters/courses without applying academic policy."""


class MockAcademicHistoryExtractor(AcademicHistoryExtractor):
    """Deterministic extractor used by tests and local fixture development."""

    def __init__(self, result: dict[str, Any]):
        self.result = result

    def extract(self, document: AcademicHistoryFile) -> dict[str, Any]:
        return self.result


def sniff_media_type(content: bytes) -> str | None:
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def validate_upload(document: AcademicHistoryFile) -> str:
    if not document.content:
        raise AcademicHistoryImportError("The uploaded file is empty.")
    if len(document.content) > MAX_UPLOAD_BYTES:
        raise AcademicHistoryImportError("Each file must be 10 MB or smaller.")
    detected = sniff_media_type(document.content)
    if detected is None:
        raise AcademicHistoryImportError("Upload a valid PDF, PNG, JPG, or JPEG file.")
    declared = (document.content_type or "").split(";", 1)[0].strip().lower()
    if declared and declared not in SUPPORTED_MEDIA_TYPES:
        raise AcademicHistoryImportError("This file type is not supported.")
    if declared and detected != declared:
        raise AcademicHistoryImportError("The file contents do not match its reported type.")
    if detected.startswith("image/"):
        try:
            from PIL import Image
            with Image.open(io.BytesIO(document.content)) as image:
                image.verify()
        except ImportError as error:
            raise AcademicHistoryImportError(
                "Image validation support is not installed on the server."
            ) from error
        except Exception as error:
            raise AcademicHistoryImportError("This image is corrupt or unreadable.") from error
    return detected


def normalize_course_id(value: str) -> str | None:
    """Normalize only unambiguous five-digit CMU course identifiers."""
    compact = re.sub(r"[^0-9]", "", str(value or ""))
    if len(compact) != 5:
        return None
    return f"{compact[:2]}-{compact[2:]}"


def normalize_status(value: str | None) -> str | None:
    normalized = re.sub(r"[^a-z]", "_", str(value or "").strip().lower()).strip("_")
    aliases = {
        "complete": "completed",
        "completed": "completed",
        "passed": "completed",
        "current": "in_progress",
        "currently_taking": "in_progress",
        "in_progress": "in_progress",
        "registered": "planned",
        "planned": "planned",
        "future": "planned",
    }
    return aliases.get(normalized)


def normalize_semester(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    aliases = {"autumn": "fall", "fa": "fall", "sp": "spring", "su": "summer"}
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in VALID_SEMESTERS else None


def _status_from_heading(heading: str) -> str | None:
    lowered = heading.lower()
    if any(token in lowered for token in ("in progress", "currently taking", "current")):
        return "in_progress"
    if any(token in lowered for token in ("planned", "registered", "future")):
        return "planned"
    if any(token in lowered for token in ("completed", "complete", "taken", "grade")):
        return "completed"
    return None


def parse_academic_history_text(text: str) -> dict[str, Any]:
    """Conservatively parse course facts from native PDF text."""
    records: list[dict[str, Any]] = []
    semester = None
    year = None
    status = None
    term_pattern = re.compile(
        r"\b(Fall|Autumn|Spring|Summer)\s+(20\d{2})(?:\s*[-—:]?\s*(Completed|In Progress|Currently Taking|Planned|Registered))?",
        re.IGNORECASE,
    )
    course_pattern = re.compile(r"(?<!\d)(\d{2})[\s-]?(\d{3})(?!\d)")
    for line in text.splitlines():
        clean = " ".join(line.split())
        if not clean:
            continue
        term_match = term_pattern.search(clean)
        if term_match:
            semester = normalize_semester(term_match.group(1))
            year = int(term_match.group(2))
            status = normalize_status(term_match.group(3)) or _status_from_heading(clean)
        for match in course_pattern.finditer(clean):
            raw_id = match.group(0)
            trailing = clean[match.end():].strip(" :-—")
            grade_match = re.search(r"\b(A[+-]?|B[+-]?|C[+-]?|D|P|S|W)\b", trailing)
            record_status = status or ("completed" if grade_match else None)
            records.append({
                "course_id": raw_id,
                "course_name": re.sub(r"\s{2,}.*$", "", trailing) or None,
                "semester": semester,
                "year": year,
                "status": record_status,
                "grade": grade_match.group(1) if grade_match else None,
                "confidence": 0.88 if semester and status else 0.68,
            })
    return {"courses": records, "warnings": []}


class NativePdfAcademicHistoryExtractor(AcademicHistoryExtractor):
    def extract(self, document: AcademicHistoryFile) -> dict[str, Any]:
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(document.content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError as error:
            raise AcademicHistoryImportError(
                "PDF support is not installed on the server."
            ) from error
        except Exception as error:
            raise AcademicHistoryImportError("This PDF could not be read.") from error
        if not text.strip():
            return {"courses": [], "warnings": ["PDF_NO_NATIVE_TEXT"]}
        result = parse_academic_history_text(text)
        result["native_text_found"] = True
        return result


class LocalOllamaVisionAcademicHistoryExtractor(AcademicHistoryExtractor):
    """Private vision extraction restricted to the local Ollama service."""

    endpoint = "http://127.0.0.1:11434/api/chat"

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get(
            "ACADEMIC_HISTORY_OLLAMA_MODEL", "qwen2.5vl:3b"
        )

    @staticmethod
    def _images(document: AcademicHistoryFile) -> list[bytes]:
        if document.content_type != "application/pdf":
            return [document.content]
        try:
            import fitz
            pdf = fitz.open(stream=document.content, filetype="pdf")
            return [
                page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).tobytes("png")
                for page in list(pdf)[:12]
            ]
        except ImportError as error:
            raise AcademicHistoryImportError(
                "Scanned-PDF rendering support is not installed on the server."
            ) from error
        except Exception as error:
            raise AcademicHistoryImportError("This scanned PDF could not be rendered.") from error

    def extract(self, document: AcademicHistoryFile) -> dict[str, Any]:
        images = [base64.b64encode(image).decode("ascii") for image in self._images(document)]
        prompt = (
            "Extract only academic course facts from these CMU academic-record pages. "
            "Do not infer requirements or include student identity. Return one JSON object "
            "with a courses array. Each course must contain course_id, course_name, semester, "
            "year, status, grade, confidence. status is completed, in_progress, planned, or "
            "null. Preserve ambiguous IDs exactly as shown; never guess missing digits."
        )
        try:
            response = requests.post(
                self.endpoint,
                json={
                    "model": self.model,
                    "stream": False,
                    "format": "json",
                    "messages": [{"role": "user", "content": prompt, "images": images}],
                    "options": {"temperature": 0},
                },
                timeout=90,
            )
            response.raise_for_status()
            result = json.loads(response.json()["message"]["content"])
        except requests.ConnectionError as error:
            raise AcademicHistoryImportError(
                "Private image extraction is not running. Start Ollama and install the "
                f"{self.model} vision model, or use a text-based PDF."
            ) from error
        except requests.Timeout as error:
            raise AcademicHistoryImportError(
                "Private image extraction timed out. Try fewer or clearer pages."
            ) from error
        except requests.HTTPError as error:
            raise AcademicHistoryImportError(
                f"The local Ollama vision model '{self.model}' is unavailable."
            ) from error
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise AcademicHistoryImportError(
                "The local vision model returned malformed course data."
            ) from error
        if not isinstance(result.get("courses"), list):
            raise AcademicHistoryImportError(
                "The local vision model did not return a course list."
            )
        return result


def default_extractor_for(document: AcademicHistoryFile) -> AcademicHistoryExtractor:
    media_type = validate_upload(document)
    normalized = AcademicHistoryFile(document.filename, media_type, document.content)
    if media_type == "application/pdf":
        return NativePdfAcademicHistoryExtractor()
    return LocalOllamaVisionAcademicHistoryExtractor()


def validate_extracted_courses(raw_result: dict[str, Any], catalog: list[dict]) -> dict[str, Any]:
    catalog_by_id = {course["id"]: course for course in catalog}
    validated = []
    warnings = list(raw_result.get("warnings", []))
    seen = set()
    for index, raw in enumerate(raw_result.get("courses", [])):
        if not isinstance(raw, dict):
            warnings.append({
                "record": index + 1,
                "message": "One malformed extracted record was skipped.",
            })
            continue
        original_id = str(raw.get("course_id") or raw.get("id") or "").strip()
        normalized_id = normalize_course_id(original_id)
        canonical = catalog_by_id.get(normalized_id) if normalized_id else None
        status = normalize_status(raw.get("status"))
        semester = normalize_semester(raw.get("semester"))
        raw_year = raw.get("year")
        try:
            year = int(raw_year) if raw_year not in (None, "") else None
        except (TypeError, ValueError):
            year = None
        issues = []
        if normalized_id is None:
            issues.append("ambiguous_course_id")
        elif canonical is None:
            issues.append("unknown_course")
        if status is None:
            issues.append("status_needs_review")
        if semester is None or year is None:
            issues.append("term_needs_review")
        dedupe_key = (normalized_id or original_id, semester, year, status)
        if dedupe_key in seen:
            issues.append("duplicate_in_upload")
        seen.add(dedupe_key)
        try:
            confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.5))))
        except (TypeError, ValueError):
            confidence = 0.5
            issues.append("confidence_needs_review")
        validated.append({
            "record_id": f"import-{index + 1}",
            "course_id": normalized_id or original_id,
            "course_name": canonical.get("name") if canonical else None,
            "units": canonical.get("units") if canonical else None,
            "semester": semester,
            "year": year,
            "status": status,
            "grade": raw.get("grade"),
            "confidence": confidence,
            "catalog_validated": canonical is not None,
            "needs_review": bool(issues),
            "issues": issues,
            "source": "academic_history_import",
        })
    return {
        "courses": validated,
        "warnings": warnings,
        "recognized_count": len(validated),
        "review_count": sum(item["needs_review"] for item in validated),
    }


def extract_academic_history(
    document: AcademicHistoryFile,
    catalog: list[dict],
    extractor: AcademicHistoryExtractor | None = None,
) -> dict[str, Any]:
    media_type = validate_upload(document)
    normalized_document = AcademicHistoryFile(
        document.filename, media_type, document.content
    )
    selected = extractor or default_extractor_for(normalized_document)
    raw_result = selected.extract(normalized_document)
    if (
        extractor is None
        and media_type == "application/pdf"
        and not raw_result.get("courses")
        and "PDF_NO_NATIVE_TEXT" in raw_result.get("warnings", [])
    ):
        raw_result = LocalOllamaVisionAcademicHistoryExtractor().extract(
            normalized_document
        )
    return validate_extracted_courses(raw_result, catalog)


def merge_academic_history(student_state: dict, records: list[dict], catalog: list[dict]) -> dict:
    """Merge confirmed records into the existing canonical student state."""
    catalog_ids = {course["id"] for course in catalog}
    merged = dict(student_state)
    history_by_term: dict[tuple, dict] = {
        (record["course_id"], record.get("semester"), record.get("year")): dict(record)
        for record in student_state.get("academic_history", [])
        if record.get("course_id")
    }
    status_lists = {
        "completed": list(student_state.get("completed_courses", [])),
        "in_progress": list(student_state.get("in_progress_courses", [])),
        "planned": list(student_state.get("planned_courses", [])),
    }
    priorities = {"planned": 1, "in_progress": 2, "completed": 3}
    imported = 0
    duplicates = 0
    for record in records:
        course_id = normalize_course_id(record.get("course_id", ""))
        status = normalize_status(record.get("status"))
        if course_id not in catalog_ids or status not in VALID_STATUSES:
            raise AcademicHistoryImportError(
                f"Review {record.get('course_id') or 'the unknown course'} before importing."
            )
        normalized = {
            "course_id": course_id,
            "semester": normalize_semester(record.get("semester")),
            "year": int(record["year"]) if record.get("year") not in (None, "") else None,
            "status": status,
            "grade": record.get("grade"),
            "source": "academic_history_import",
        }
        existing_status = next(
            (key for key, values in status_lists.items() if course_id in values), None
        )
        if existing_status and priorities[existing_status] >= priorities[status]:
            duplicates += 1
            history_key = (course_id, normalized["semester"], normalized["year"])
            if history_key not in history_by_term:
                history_by_term[history_key] = normalized | {"status": existing_status}
            continue
        for values in status_lists.values():
            while course_id in values:
                values.remove(course_id)
        status_lists[status].append(course_id)
        history_by_term[(course_id, normalized["semester"], normalized["year"])] = normalized
        imported += 1
    merged["completed_courses"] = list(dict.fromkeys(status_lists["completed"]))
    merged["in_progress_courses"] = list(dict.fromkeys(status_lists["in_progress"]))
    merged["planned_courses"] = list(dict.fromkeys(status_lists["planned"]))
    merged["academic_history"] = list(history_by_term.values())
    return {"student": merged, "imported_count": imported, "duplicate_count": duplicates}
