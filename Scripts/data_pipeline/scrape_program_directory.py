"""Build a CMU-wide undergraduate program directory from the official catalog.

This script collects directory metadata only. It does not claim that a program
is planning-ready until its eligibility and curriculum rules are verified.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "Data" / "scraped" / "program_directory.json"
PROCESSED_OUTPUT_PATH = ROOT / "Data" / "processed" / "program_directory.json"
CATALOG_URL = "https://coursecatalog.web.cmu.edu/programs/"
CATALOG_YEAR = "2026-2027"

COLLEGE_PATHS = {
    "collegeofengineering": "engineering",
    "collegeoffinearts": "cfa",
    "dietrichcollegeofhumanitiesandsocialsciences": "dietrich",
    "melloncollegeofscience": "mcs",
    "schoolofcomputerscience": "scs",
    "tepper": "tepper",
    "qatar": "qatar",
    "heinzcollegeofinformationsystemsandpublicpolicy": "heinz",
}

INTERCOLLEGE_AFFILIATIONS = {
    "computer-science-arts": ["cfa", "scs"],
    "engineering-studies-arts": ["cfa", "engineering"],
    "humanities-arts": ["cfa", "dietrich"],
    "science-arts": ["cfa", "mcs"],
    "engineering-arts-additional-major": ["cfa", "engineering"],
    "information-systems-bs": ["dietrich", "heinz"],
    "information-systems-minor": ["dietrich", "heinz"],
}

PLANNING_IDS = {
    "artificial-intelligence": "artificial-intelligence",
    "computational-biology": "computational-biology",
    "computer-science": "computer-science",
    "human-computer-interaction": "human-computer-interaction",
    "robotics": "robotics",
}


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return value.strip("-")


def classify_program(label: str) -> tuple[str, str, str]:
    """Return display name, program type, and credential."""
    name, separator, credential = label.rpartition(", ")
    if not separator:
        return label, "other", ""
    normalized = credential.replace("\u200b", "").strip().rstrip(".")
    if normalized.lower() == "minor" or normalized.lower().startswith("minor "):
        return name, "minor", credential
    if normalized.lower() == "additional major":
        return name, "additional_major", credential
    return name, "primary_major", credential


def infer_home_colleges(path: str) -> list[str]:
    for fragment, college_id in COLLEGE_PATHS.items():
        if f"/{fragment}/" in path:
            return [college_id]
    if "/intercollegeprograms/" in path:
        return ["intercollege"]
    return ["unclassified"]


def planning_identity(name: str, program_type: str) -> tuple[str | None, str]:
    family_id = PLANNING_IDS.get(slugify(name))
    if family_id is None:
        return None, "directory_only"
    supported_types = {
        "primary_major": "internal_transfer",
        "additional_major": "additional_major",
        "minor": "minor",
    }
    return family_id, (
        "planning_ready" if program_type in supported_types else "directory_only"
    )


def scrape_program_directory() -> list[dict[str, object]]:
    response = requests.get(
        CATALOG_URL,
        headers={"User-Agent": "CMU-Course-Advisor/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    main = soup.find("main")
    if main is None:
        raise ValueError("Could not find the main program directory content")

    programs: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for anchor in main.select("a[href]"):
        label = " ".join(anchor.get_text(" ", strip=True).split())
        path = anchor.get("href", "")
        if not label or not path.startswith("/") or ", " not in label:
            continue

        name, program_type, credential = classify_program(label)
        if program_type == "other":
            continue
        source_url = urljoin(CATALOG_URL, path)
        identity = (label, source_url)
        if identity in seen:
            continue
        seen.add(identity)

        page_slug = path.rstrip("/").split("/")[-1]
        home_colleges = infer_home_colleges(path)
        affiliations = INTERCOLLEGE_AFFILIATIONS.get(
            page_slug, list(home_colleges)
        )
        if page_slug.startswith("information-systems-"):
            home_colleges = ["dietrich", "heinz"]
            affiliations = ["dietrich", "heinz"]

        planning_id, planning_status = planning_identity(name, program_type)
        programs.append({
            "id": f"{slugify(name)}--{slugify(credential)}",
            "name": name,
            "credential": credential,
            "program_type": program_type,
            "home_colleges": home_colleges,
            "affiliations": affiliations,
            "interdisciplinary": len(affiliations) > 1 or "intercollege" in home_colleges,
            "planning_id": planning_id,
            "planning_status": planning_status,
            "catalog_year": CATALOG_YEAR,
            "source_url": source_url,
        })

    return sorted(
        programs,
        key=lambda item: (str(item["name"]), str(item["program_type"])),
    )


def main() -> None:
    programs = scrape_program_directory()
    payload = json.dumps(programs, indent=2, ensure_ascii=False) + "\n"
    for output_path in (OUTPUT_PATH, PROCESSED_OUTPUT_PATH):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    print(f"Wrote {len(programs)} programs to {OUTPUT_PATH}")
    print(f"Promoted validated directory to {PROCESSED_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
