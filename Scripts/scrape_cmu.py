import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = (PROJECT_ROOT / "Data" / "scraped_programs.json")
COLLEGE_OUTPUT_PATH = (PROJECT_ROOT/ "Data"/ "scraped_college_requirements.json")

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

COLLEGE_SOURCES = [
    {
        "id": "dietrich",
        "college": "Dietrich College",
        "catalog_year": "2026-2027",
        "requirement_type": "general_education",
        "url": "https://www.cmu.edu/dietrich/gened/curriculum/index.html",
    }
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

# =========================
# Dietrich GenEd Parser
# =========================

DIETRICH_REQUIREMENT_CATEGORIES = [
    {
        "id": "communication",
        "name": "Communication",
        "group": "foundations",
    },
    {
        "id": "data-analysis",
        "name": "Data Analysis",
        "group": "foundations",
    },
    {
        "id": "computational-thinking",
        "name": "Computational Thinking",
        "group": "foundations",
    },
    {
        "id": "contextual-thinking",
        "name": "Contextual Thinking",
        "group": "foundations",
    },
    {
        "id": "intercultural-global-inquiry",
        "name": "Intercultural and Global Inquiry",
        "group": "foundations",
    },
    {
        "id": "scientific-inquiry",
        "name": "Scientific Inquiry",
        "group": "foundations",
    },

    {
        "id": "humanities",
        "name": "Humanities",
        "group": "disciplinary_perspectives",
    },
    {
        "id": "social-sciences",
        "name": "Social Sciences",
        "group": "disciplinary_perspectives",
    },
    {
        "id": "logic-mathematical-reasoning",
        "name": "Logic/Mathematical Reasoning",
        "group": "disciplinary_perspectives",
    },
    {
        "id": "arts",
        "name": "The Arts",
        "group": "disciplinary_perspectives",
    },
    {
        "id": "additional-disciplines",
        "name": "Additional Disciplines: Business, Design, or Engineering",
        "group": "disciplinary_perspectives",
    },

    {
        "id": "grand-challenge-seminar",
        "name": "Grand Challenge Seminar",
        "group": "special_seminars",
    },
    {
        "id": "justice-injustice",
        "name": "Perspectives on Justice and Injustice",
        "group": "special_seminars",
    },

    {
        "id": "experiential-learning",
        "name": "Experiential Learning Activity",
        "group": "experiential_learning",
    },
]


def extract_units(text):
    """
    Find something like:
        9 units
        6 units
        1 unit

    Returns an int or None.
    """
    match = re.search(
        r"\b(\d+)\s+units?\b",
        text,
        re.IGNORECASE,
    )

    if match:
        return int(match.group(1))

    return None


def extract_timeline(text):
    """
    Convert Dietrich timeline text into a structured form
    that the planner can eventually understand.
    """

    lower_text = text.lower()

    if "required in year 1 or 2" in lower_text:
        return {
            "type": "complete_by",
            "year": 2,
            "source_text": "Required in Year 1 or 2",
        }

    if "required in year 1" in lower_text:
        return {
            "type": "complete_by",
            "year": 1,
            "source_text": "Required in Year 1",
        }

    if "year 1, 2, or 3" in lower_text:
        return {
            "type": "complete_by",
            "year": 3,
            "source_text": "Can be completed in Year 1, 2, or 3",
        }

    if "anytime in a student" in lower_text:
        return {
            "type": "complete_by",
            "year": 4,
            "source_text": "Can be completed anytime",
        }

    if "after first semester" in lower_text:
        return {
            "type": "after_semester",
            "semester": 1,
            "source_text": "Must be completed after first semester",
        }

    return {
        "type": "unknown",
        "source_text": None,
    }


# def extract_dietrich_requirement_section(
#     text,
#     current_name,
#     next_name=None,
# ):
#     """
#     Grab the text belonging to one Dietrich GenEd category.

#     Example:
#         Data Analysis
#         ...description...
#         9 units
#         Required in Year 1
#         36-200
#     """

#     start = text.find(current_name)

#     if start == -1:
#         return None

#     if next_name:
#         end = text.find(next_name, start + len(current_name))

#         if end == -1:
#             end = len(text)
#     else:
#         end = len(text)

#     return text[start:end].strip()

def extract_dietrich_requirement_section(
    text,
    current_name,
    next_name=None,
):
    start_marker = f"\n{current_name}\n"
    start = text.find(start_marker)

    if start == -1:
        return None

    start += 1

    if next_name:
        next_marker = f"\n{next_name}\n"
        end = text.find(next_marker,start + len(current_name),)

        if end == -1:
            end = len(text)
    else:
        end_candidates = [
            text.find(marker, start + len(current_name))
            for marker in ("\nTotal General Education\n", "\nRelated Links\n")
        ]
        valid_ends = [candidate for candidate in end_candidates if candidate != -1]
        end = min(valid_ends) if valid_ends else len(text)

    return text[start:end].strip()

def parse_dietrich_requirements(text):
    requirements = []

    for index, category in enumerate(
        DIETRICH_REQUIREMENT_CATEGORIES
    ):
        current_name = category["name"]

        if index + 1 < len(DIETRICH_REQUIREMENT_CATEGORIES):
            next_name = (
                DIETRICH_REQUIREMENT_CATEGORIES[index + 1]["name"]
            )
        else:
            next_name = None

        section = extract_dietrich_requirement_section(
            text,
            current_name,
            next_name,
        )

        if section is None:
            print(
                f"Warning: Dietrich requirement not found: "
                f"{current_name}"
            )
            continue

        courses = extract_course_numbers(section)

        requirement = {
            "id": category["id"],
            "name": category["name"],
            "group": category["group"],
            "type": "category",
            "units": extract_units(section),
            "timeline": extract_timeline(section),
            "courses": courses,
            "source_text": section,
        }

        # Special case:
        # Dietrich says choose one course from
        # Business, Design, or Engineering.
        if category["id"] == "additional-disciplines":
            requirement["type"] = "choose_one_discipline"
            requirement["options"] = [
                "Business",
                "Design",
                "Engineering",
            ]

        requirements.append(requirement)

    return requirements

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


def scrape_college(source):
    text = html_to_text(
        fetch_page(source["url"])
    )

    result = {
        "id": source["id"],
        "college": source["college"],
        "catalog_year": source["catalog_year"],
        "requirement_type": source["requirement_type"],
        "source_url": source["url"],
    }

    if source["id"] == "dietrich":
        result["requirements"] = (
            parse_dietrich_requirements(text)
        )
    else:
        result["requirements"] = []

    return result

def main():
    program_results = [
        scrape_program(source)
        for source in PROGRAM_SOURCES
    ]

    save_results(
        program_results,
        DEFAULT_OUTPUT_PATH
    )

    college_results = [
        scrape_college(source)
        for source in COLLEGE_SOURCES
    ]

    save_results(
        college_results,
        COLLEGE_OUTPUT_PATH
    )

    print(
        f"Saved {len(program_results)} program(s) "
        f"to {DEFAULT_OUTPUT_PATH}"
    )

    print(
        f"Saved {len(college_results)} college(s) "
        f"to {COLLEGE_OUTPUT_PATH}"
    )

if __name__ == "__main__":
    main()
