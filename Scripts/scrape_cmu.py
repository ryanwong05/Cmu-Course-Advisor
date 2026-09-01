import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "Data" / "scraped_programs.json"

PROGRAM_SOURCES = [
    {
        "id": "robotics-transfer",
        "college": "SCS",
        "program": "Robotics",
        "program_type": "primary_major",
        "change_type": "internal_transfer",
        "catalog_year": "2026-2027",
        "url": (
            "https://www.ri.cmu.edu/education/academic-programs/"
            "bachelor-of-science-in-robotics/transfer-guidelines/"
        ),
    },
    {
        "id": "cs-transfer",
        "college": "SCS",
        "program": "Computer Science",
        "program_type": "primary_major",
        "change_type": "internal_transfer",
        "catalog_year": "2026-2027",
        "url": (
            "https://csd.cmu.edu/"
            "guidelines-for-internal-transfer-or-dual-degree"
        ),
    },
]


def fetch_page(url):
    response = requests.get(
        url,
        headers={"User-Agent": "CMU Academic Advisor Project/0.1"},
        timeout=20,
    )
    response.raise_for_status()
    return response.text


def html_to_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def extract_courses_from_line(line):
    return re.findall(r"\b\d{2}-\d{3}\b", line)


def extract_course_numbers(text):
    return list(dict.fromkeys(re.findall(r"\b\d{2}-\d{3}\b", text)))


def clean_requirement_name(line):
    name = line.split(":", 1)[0] if ":" in line else line
    name = re.sub(r"\bone of\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\b\d{2}-\d{3}\b", "", name)
    name = re.sub(r"\s*(?:,|\bor\b|\band\b)\s*", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip(" ,.-")


def parse_requirements(text):
    requirements = []
    for line in (line.strip() for line in text.splitlines()):
        if not line:
            continue
        courses = extract_courses_from_line(line)
        if not courses:
            continue

        lower_line = line.lower()
        if "one of" in lower_line or " or " in lower_line:
            requirement_type = "one_of"
        elif len(courses) == 1:
            requirement_type = "required"
        elif " and " in lower_line:
            requirement_type = "all_of"
        else:
            requirement_type = "unknown"

        requirements.append(
            {
                "name": clean_requirement_name(line),
                "type": requirement_type,
                "courses": courses,
                "source_text": line,
            }
        )
    return requirements


def deduplicate_requirements(requirements):
    unique = []
    seen = set()
    for requirement in requirements:
        key = (requirement["type"], tuple(requirement["courses"]))
        if key not in seen:
            seen.add(key)
            unique.append(requirement)
    return unique


def extract_overall_qpa(text):
    patterns = [
        r"overall\s+(?:minimum\s+)?(?:of\s+)?(\d+(?:\.\d+)?)\s+QPA",
        r"maintain\s+at\s+least\s+(?:an?\s+)?(\d+(?:\.\d+)?)\s+QPA",
        r"minimum\s+(?:overall\s+)?QPA\s+(?:of\s+)?(\d+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def extract_course_group_qpa(text):
    match = re.search(
        r"at\s+least\s+(?:an?\s+)?(\d+(?:\.\d+)?)\s+"
        r"(?:cumulative\s+)?QPA\s+in\s+",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    tail = text[match.end() : match.end() + 500]
    explicit_courses = extract_course_numbers(tail.splitlines()[0])
    return {
        "minimum": float(match.group(1)),
        "courses": explicit_courses or None,
    }


def requirement_id(requirement, index):
    base = re.sub(r"[^a-z0-9]+", "-", requirement["name"].lower()).strip("-")
    return base or f"requirement-{index}"


def add_requirement_ids(requirements):
    return [
        {"id": requirement_id(requirement, index), **requirement}
        for index, requirement in enumerate(requirements, start=1)
    ]


def attach_qpa_to_requirements(course_group_qpa, requirements):
    if course_group_qpa is None:
        return None
    if course_group_qpa.get("courses"):
        applies_to = {
            "type": "explicit_courses",
            "courses": course_group_qpa["courses"],
        }
    else:
        applies_to = {
            "type": "requirement_groups",
            "requirement_ids": [item["id"] for item in requirements],
        }
    return {"minimum": course_group_qpa["minimum"], "applies_to": applies_to}


def extract_section(text, start_heading, end_headings):
    start = text.find(start_heading)
    if start == -1:
        return None
    section_start = start + len(start_heading)
    candidate_ends = []
    for heading in end_headings:
        position = text.find(heading, section_start)
        if position != -1:
            candidate_ends.append(position)
    section_end = min(candidate_ends) if candidate_ends else len(text)
    return text[section_start:section_end].strip()


def parse_policy(section_text, audience):
    requirements = add_requirement_ids(
        deduplicate_requirements(parse_requirements(section_text))
    )
    return {
        "audience": audience,
        "requirements": requirements,
        "qpa_requirements": {
            "overall": extract_overall_qpa(section_text),
            "course_group": attach_qpa_to_requirements(
                extract_course_group_qpa(section_text), requirements
            ),
        },
        "application_requirements": {
            "essay_required": "essay" in section_text.lower(),
            "advisor_consultation_required": (
                "advisor" in section_text.lower()
                or "director" in section_text.lower()
            ),
        },
        "transfer_guaranteed": False,
    }


def parse_robotics_policies(text):
    scs_section = extract_section(
        text,
        "Information for SCS Students",
        ["Information for Non-SCS Students"],
    )
    non_scs_section = extract_section(
        text,
        "Information for Non-SCS Students",
        ["Back to Academic Programs"],
    )
    if scs_section is None or non_scs_section is None:
        raise ValueError("Robotics transfer policy sections could not be located")
    return [
        parse_policy(scs_section, "scs_students"),
        parse_policy(non_scs_section, "non_scs_students"),
    ]


def scrape_program(source):
    text = html_to_text(fetch_page(source["url"]))
    result = {
        "id": source["id"],
        "college": source["college"],
        "program": source["program"],
        "program_type": source["program_type"],
        "change_type": source["change_type"],
        "catalog_year": source["catalog_year"],
        "source_url": source["url"],
    }
    if source["id"] == "robotics-transfer":
        result["policies"] = parse_robotics_policies(text)
    else:
        requirements = add_requirement_ids(
            deduplicate_requirements(parse_requirements(text))
        )
        result["policies"] = [
            {
                "audience": "all_applicants",
                "requirements": requirements,
                "qpa_requirements": {
                    "overall": extract_overall_qpa(text),
                    "course_group": attach_qpa_to_requirements(
                        extract_course_group_qpa(text), requirements
                    ),
                },
            }
        ]
    return result


def save_results(results, output_path=DEFAULT_OUTPUT_PATH):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main():
    results = [scrape_program(source) for source in PROGRAM_SOURCES]
    save_results(results)
    print(f"Saved {len(results)} program(s) to {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
