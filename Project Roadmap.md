# CMU AI Academic Planner

## 1. Product Vision

Build an AI-powered academic planning system that helps CMU students answer three fundamental questions:

1. **Where am I now?**
2. **Where do I want to go?**
3. **What is the best path from here to there?**

The product should go beyond traditional degree planning.

Traditional tools primarily answer:

> "What do I need to graduate?"

This product should answer:

> "Given my current situation and goals, what should I do next, why should I do it, and what are the tradeoffs?"

The long-term goal is to build an **AI operating system for navigating university**.

---

# 2. Core Product Philosophy

The fundamental unit of the product is NOT a course.

The fundamental unit is a **Goal**.

Courses, majors, minors, research, projects, internships, clubs, and other activities are actions or milestones that help a student achieve a goal.

Core structure:

```text
Student
   ↓
Goal
   ↓
Possible Paths
   ↓
Path Comparison
   ↓
Chosen Path
   ↓
Milestones
   ↓
Actions
   ↓
Progress
   ↓
Checkpoint
   ↓
Re-plan
```

Core product loop:

```text
Discover
→ Compare
→ Decide
→ Plan
→ Execute
→ Checkpoint
→ Re-plan
```

---

# 3. Primary User Problems

## Problem A — Optimizing an Existing Major

Some students are already satisfied with their major.

Their question is not:

> "What courses do I need to graduate?"

Instead:

> "How do I build the strongest possible profile from my current major?"

Examples:

- How should I prepare for ML engineering?
- How should I prepare for robotics?
- Which electives should I prioritize?
- Should I pursue research?
- Should I add a minor or additional major?
- Which projects would complement my coursework?
- What should I accomplish by sophomore/junior year?
- What skills am I currently missing?

The system should help students build a strong academic and career profile.

---

## Problem B — Exploring a Major Transfer / Alternative Path

Many CMU students consider changing majors or transferring schools.

The important question is not simply:

> "Can I transfer?"

The real questions are:

> "How difficult is this path?"

> "What will I have to sacrifice?"

> "What is the opportunity cost?"

> "Are there alternative paths that achieve almost the same goal?"

The system should compare paths such as:

```text
Path A
Transfer to Computer Science

Path B
Stay in current major + Robotics Additional Major

Path C
Stay in current major + CS coursework/minor

Path D
Alternative major with similar career outcome
```

Each path should include:

- Feasibility
- Required courses
- Remaining requirements
- Earliest completion
- Critical prerequisites
- Estimated workload
- Academic risk
- Opportunity cost
- Flexibility
- Career alignment
- Alternative options

The product should help the student understand:

> "What do I gain and what do I give up by choosing this path?"

---

# 4. Execution Mode

Once a student chooses a path, the product transitions from **decision support** to **execution support**.

Example:

```text
GOAL
Transfer to Computer Science

Overall Plan Completion
████████░░░░░░ 43%

Prerequisites       50%
Academic Benchmark  70%
Application Prep    20%
Relevant Experience 30%
```

The percentage must represent measurable plan completion rather than an invented probability of success.

Each goal should contain milestones.

Example:

```text
Goal:
Transfer to Computer Science

Milestone 1
Complete mathematical foundation

✓ 21-127

Milestone 2
Complete programming foundation

✓ 15-112
✓ 15-122
○ 15-150

Milestone 3
Complete advanced transfer coursework

○ 15-210
○ 15-213
○ 15-251

Milestone 4
Prepare transfer application

○ Verify eligibility
○ Review academic performance
○ Prepare application materials
```

---

# 5. Checkpoints

The system should periodically evaluate whether the student remains on track.

Examples:

### On Track

> You are currently on track for your selected path.

### Warning

> Delaying 15-150 may delay completion of your transfer prerequisites because it unlocks multiple downstream courses.

### Path Changed

> Your current schedule changes the earliest feasible completion date of this path.

### Better Alternative Found

> Based on your updated goals, another path may now provide better career alignment with lower opportunity cost.

The system should continuously update recommendations when the student's situation changes.

---

# 6. Core Technical Principle

AI should NOT be the source of truth.

Architecture:

```text
CMU Official Data
        ↓
Structured Knowledge Base
        ↓
Feasibility Engine
        ↓
Path Generator
        ↓
Optimization Engine
        ↓
AI Explanation Layer
        ↓
User
```

The LLM should primarily:

1. Understand natural-language goals.
2. Convert goals into structured information.
3. Explain planning-engine results.
4. Compare tradeoffs in understandable language.
5. Answer questions using verified system data.

The LLM should NOT invent:

- prerequisites
- degree requirements
- transfer requirements
- course availability
- unit requirements
- academic policies

These should come from structured and verified data.

---

# 7. Data Sources

Initial data should come from publicly available official CMU sources.

Potential sources include:

- CMU Undergraduate Catalog
- CMU Schedule of Classes
- Department websites
- Major requirements
- Minor requirements
- Additional major requirements
- Internal transfer policies
- AP / IB credit policies
- Academic policies
- Department advising documentation

Do NOT depend on scraping private student information from:

- SIO
- private Stellic accounts
- other authenticated student systems

Each important rule should eventually contain metadata such as:

```text
source
source_url
academic_year
last_verified
confidence
```

This allows the product to explain where information came from.

---

# 8. Structured Data

Initial project structure:

```text
data/
├── courses.json
├── programs.json
└── requirements.json
```

## courses.json

Stores course information.

Example:

```json
{
  "id": "15-150",
  "name": "Principles of Functional Programming",
  "units": 10,
  "prerequisites": ["21-127"]
}
```

Future fields may include:

```text
semester_offered
corequisites
department
difficulty
workload
tags
source
last_verified
```

---

## programs.json

Stores supported academic programs and paths.

Examples:

```text
Computer Science Internal Transfer
Statistics & Machine Learning
Robotics Additional Major
Computer Science Minor
ECE
```

---

## requirements.json

Stores requirements associated with each program.

Example:

```json
{
  "cs-transfer": {
    "required_courses": [
      "15-122",
      "15-150",
      "15-210",
      "15-213",
      "15-251",
      "21-127"
    ]
  }
}
```

---

# 9. Core Data Model

The long-term system should contain six major objects:

```text
Student
Course
Program
Goal
Path
Milestone
```

## Student

Possible fields:

```text
current_major
college
year
completed_courses
current_courses
grades
AP_IB_credit
interests
career_goals
academic_goals
GPA_priority
workload_preference
graduation_target
```

---

## Course

Represents a CMU course and its constraints.

---

## Program

Represents:

- major
- minor
- additional major
- transfer target
- academic pathway

---

## Goal

Represents what the student wants to achieve.

Examples:

```text
Transfer to CS
Build a strong robotics profile
Prepare for ML engineering
Explore ECE
Graduate in four years
Protect GPA
Prepare for research
```

---

## Path

A possible route from the student's current state to a goal.

A path should eventually contain:

```text
required_actions
required_courses
estimated_semesters
critical_path
risk
opportunity_cost
goal_alignment
flexibility
```

---

## Milestone

A measurable checkpoint along a path.

Example:

```text
Complete CS mathematical foundations
Complete transfer prerequisites
Develop robotics experience
Obtain research experience
```

---

# 10. Planning Engine

The planning engine is the core technical advantage of the product.

It should eventually answer:

### Requirement Checking

> What requirements has the student completed?

Current function:

```python
check_requirements()
```

---

### Course Availability

> What courses can the student currently take based on prerequisites?

Current function:

```python
get_available_courses()
```

---

### Dependency Analysis

> Which courses unlock important downstream courses?

Current functions:

```python
count_downstream_courses()
get_course_priority()
```

---

### Critical Path

> Which courses must be completed early to avoid delaying the goal?

Future functionality:

```python
find_critical_path()
```

---

### Delay Analysis

> If I postpone this course, how much could my path be delayed?

Functions:

```python
semesters_to_finish()
calculate_delay_if_skipped()
```

Future versions should account for:

- Fall/Spring course availability
- unit limits
- workload
- scheduling conflicts
- prerequisite alternatives

---

# 11. Feasibility Engine

The first major engine should answer:

> "Is this path actually possible?"

Inputs:

```text
Student state
+
Program requirements
+
Prerequisite graph
+
Semester availability
+
Unit constraints
+
Graduation timeline
```

Output:

```text
Feasible: Yes / No

Remaining requirements
Required semesters
Critical courses
Blocking requirements
Potential problems
```

---

# 12. Optimization Engine

After generating feasible paths, the system should rank them based on the student's priorities.

Example priorities:

```text
Career alignment
Transfer goal
GPA protection
Workload
Graduation time
Robotics preparation
CS depth
Research preparation
Flexibility
Personal interest
```

Conceptually:

```text
All Possible Paths
        ↓
Remove Infeasible Paths
        ↓
Score Remaining Paths
        ↓
Rank Paths
        ↓
Explain Tradeoffs
```

Different students should receive different recommendations.

There should NOT be one universally "best" academic path.

---

# 13. Hard Constraints vs Soft Constraints

The system should distinguish between:

## Hard Constraints

Objective rules.

Examples:

```text
Course prerequisite
Required course
Minimum units
Major requirement
Transfer eligibility requirement
Course availability
```

Violating a hard constraint makes a path infeasible.

---

## Soft Constraints

Preferences or recommendations.

Examples:

```text
Avoid extremely heavy semesters
Protect GPA
Prefer robotics courses
Prefer morning classes
Avoid stacking multiple difficult courses
Maintain flexibility
Prioritize research preparation
```

Soft constraints affect path ranking rather than feasibility.

---

# 14. Opportunity Cost

Opportunity cost is a core differentiator of the product.

The system should eventually quantify questions such as:

> If I pursue CS transfer, what other courses or opportunities do I delay?

> If I take 15-150 instead of 18-100, what paths become easier or harder?

> If I add an additional major, how much flexibility do I lose?

Potential metrics:

```text
Additional units
Additional semesters
Delayed courses
Lost elective slots
Workload increase
GPA risk
Reduced exploration flexibility
Alternative goals affected
```

---

# 15. AI Layer

The AI layer sits ABOVE the planning engine.

Example user input:

> I'm a StatsML freshman interested in robotics and ML. I'm considering transferring to CS, but I care about GPA and don't want more than 50 units.

AI converts this into:

```json
{
  "current_major": "Statistics & Machine Learning",
  "goals": [
    "explore_cs_transfer",
    "robotics",
    "machine_learning"
  ],
  "constraints": {
    "max_units": 50,
    "gpa_priority": "high"
  }
}
```

The planning engine then performs the actual calculations.

The AI receives structured results and explains them.

---

# 16. MVP Scope

The first version should NOT support all of CMU.

Start with a small closed system.

Initial target users:

> CMU freshmen/sophomores exploring CS, StatsML, Robotics, and related pathways.

Initial supported paths may include:

```text
StatsML
CS Internal Transfer
Robotics Additional Major
CS-related alternative paths
```

Initial course database:

Approximately 20–40 relevant courses.

The goal is accuracy and usefulness, NOT coverage.

---

# 17. MVP User Flow

```text
Landing Page
      ↓
Create Student Profile
      ↓
Choose / Describe Goal
      ↓
Generate Possible Paths
      ↓
Compare Paths
      ↓
Choose Path
      ↓
Generate Roadmap
      ↓
Track Milestones
      ↓
Checkpoint
```

---

# 18. MVP Success Criterion

The MVP is successful if a real CMU student can:

1. Enter their current academic situation.
2. Describe what they want to achieve.
3. Receive multiple realistic paths.
4. Understand the tradeoffs between those paths.
5. Choose one.
6. Receive a concrete roadmap.
7. Understand what they should do next.

The desired reaction is:

> "This helped me make a decision I was actually confused about."

Not:

> "This is a cool chatbot."

---

# 19. What NOT to Build Yet

Do NOT build these in v0.1:

- Every CMU major
- Every CMU course
- Exact transfer probability
- Automatic SIO integration
- Private Stellic scraping
- Social network
- Advisor marketplace
- Full career platform
- Mobile app
- Perfect schedule optimization
- ML prediction model
- Student historical outcome dataset

First prove that:

```text
Student
→ Goal
→ Paths
→ Comparison
→ Decision
→ Roadmap
```

is genuinely useful.

---

# 20. Development Roadmap

## Phase 1 — Rule Engine

Build:

```text
courses.json
programs.json
requirements.json
```

Implement:

```python
check_requirements()
get_available_courses()
count_downstream_courses()
get_course_priority()
semesters_to_finish()
calculate_delay_if_skipped()
```

Goal:

The system understands basic prerequisite and requirement relationships.

---

## Phase 2 — Course Graph

Represent courses as a dependency graph.

Build:

```python
find_dependencies()
find_downstream_courses()
find_critical_path()
```

Goal:

Understand which courses control future academic options.

---

## Phase 3 — Semester Planning

Add:

```text
Fall/Spring availability
Units
Maximum semester workload
Course conflicts
```

Generate feasible semester-by-semester plans.

---

## Phase 4 — Path Generation

Given:

```text
Student State + Goal
```

generate multiple feasible academic paths.

---

## Phase 5 — Path Comparison

Compare:

```text
Time
Units
Difficulty
Risk
Opportunity cost
Goal alignment
Flexibility
```

---

## Phase 6 — AI Integration

Add LLM capabilities for:

```text
Natural-language goal understanding
Path explanation
Tradeoff explanation
Conversational questions
Recommendation explanations
```

AI does NOT replace the planning engine.

---

## Phase 7 — Frontend

Core pages:

```text
Profile
Goals
Path Comparison
Roadmap
Progress
```

---

## Phase 8 — Real User Testing

Test with CMU students who are:

```text
Considering internal transfer
Choosing between majors
Planning CS/robotics pathways
Unsure about course selection
```

Observe:

- What questions they ask
- What information they trust
- Which comparisons matter
- What recommendations are useful
- Where the engine fails

Use this feedback to determine the next features.

---

# 21. Long-Term Vision

Eventually the system could expand from:

```text
CMU Course Planning
```

to:

```text
CMU Academic Planning
```

to:

```text
CMU Student Goal Planning
```

and eventually:

```text
University Planning Platform
```

The long-term product could help students navigate:

```text
Courses
Majors
Transfers
Minors
Additional majors
Research
Projects
Internships
Career preparation
Graduation
```

But expansion should happen only after the core planning engine works.

---

# 22. North Star

The product should always be able to answer:

> Where are you now?

> Where do you want to go?

> What paths can get you there?

> What are the tradeoffs?

> Which path best fits your priorities?

> What should you do next?

> Are you still on track?

If a feature does not help answer one of these questions, it is probably not a priority.

---

# 23. Placeholder and Incomplete Feature Registry

This registry records behavior that appears in the product but is not yet a
complete, authoritative implementation. A placeholder must never silently
become a permanent academic rule.

## Status Vocabulary

Use one of these statuses in data, code comments, tests, and this registry:

```text
verified       Backed by a current authoritative source and tested.
partial        Real implementation, but only some programs or cases are covered.
placeholder    Temporary behavior used to support the current prototype.
estimated      Derived from incomplete or non-authoritative evidence.
not_configured The option is visible, but the planner cannot generate it yet.
blocked        Cannot be completed until a named data source or policy is obtained.
```

Every `placeholder`, `partial`, or `estimated` feature should record:

```text
Current behavior
Why it exists
What it cannot claim
Replacement data or logic
User-facing disclosure
```

## Current Registry

### P-001 — Supported Academic Goals

- **Status:** `partial`
- **Current behavior:** The interface can show several SCS programs, but only
  configured requirement keys can generate a plan.
- **Cannot claim:** That every visible major, minor, additional major, or
  transfer path is supported.
- **Replacement:** Add verified program requirements, prerequisites, policies,
  and tests one program at a time.
- **Disclosure:** Show `Not configured yet` instead of generating an inferred
  plan.

### P-002 — Current-Major Curriculum

- **Status:** `partial`
- **Current behavior:** The planner can reserve the Stats/ML calculus foundation
  (`21-120`) as a current-major course. The baseline also contains selected
  Dietrich GenEd slots, but the rest of the current-major curriculum is not yet
  loaded.
- **Cannot claim:** That a transfer plan leaves enough space to make normal
  progress in the student's current major.
- **Replacement:** First implement the verified Statistics & Machine Learning
  curriculum, including required groups, alternatives, prerequisites, and
  recommended timing. Then add other current majors incrementally.
- **Disclosure:** Label available units as unallocated space, not truly free
  elective units, until current-major requirements are loaded.

### P-003 — Dietrich GenEd Coverage

- **Status:** `partial`
- **Current behavior:** Planning currently loads the early baseline through
  Year 2 and schedules requirement slots rather than concrete courses.
- **Cannot claim:** That the displayed slots represent the complete 115-unit
  Dietrich GenEd curriculum or that a specific course satisfies a slot.
- **Replacement:** Model all categories, approved course options, timelines,
  cohort rules, and double-counting policies from official sources.
- **Disclosure:** Continue displaying these as requirement slots.

### P-004 — Experiential Learning

- **Status:** `partial`
- **Current behavior:** Represented as a one-unit slot after the first semester;
  the known scraper error mapping it to `36-200` has been removed.
- **Known gap:** It applies only to eligible cohorts (beginning with the Class
  of 2028), and its one unit should not consume the normal semester maximum.
- **Replacement:** Add entry year / graduation cohort and a
  `counts_toward_semester_limit` field.
- **Disclosure:** Do not present it as a conventional scheduled course.

### P-005 — Semester Unit Limits

- **Status:** `placeholder`
- **Current behavior:** `52` is the current user-facing default capacity.
- **Cannot claim:** That 52 is a universal official maximum for every student
  and every semester.
- **Replacement:** Separate official limit, preferred workload, approved
  overload, and per-semester overrides. Confirm policies by cohort and student
  standing.
- **Disclosure:** Describe 52 as a planner setting until policy data is verified.

### P-006 — Course Difficulty and Workload

- **Status:** `estimated`
- **Current behavior:** Every course currently supported by the planner has an
  explicit `standard`, `demanding`, or `high_intensity` tier. Three
  high-intensity courses are blocked from the same semester; two are allowed
  with a prominent warning. Results also display estimated workload,
  difficulty, stress, and weekly hours.
- **Cannot claim:** That a numerical score predicts how difficult the course
  will be for an individual student.
- **Replacement:** Store source-backed course workload plus broad intensity
  tiers (`standard`, `demanding`, `high_intensity`). Later personalize using
  preparation, prior courses, interests, and opt-in feedback.
- **Current policy:** Three high-intensity courses in one semester are blocked;
  two produce a prominent high-workload warning. This rule remains configurable
  until validated with advisors and student testing.
- **Data limitation:** ScottyLabs CMU Courses exposes FCE data only to signed-in
  users. Current values remain `estimated`; they must not be labeled as FCE
  observations until an authorized import includes semester range, respondent
  count, and retrieval date.
- **Disclosure:** Mark values as estimates and explain their inputs.

### P-007 — Placement, AP, IB, and Transfer Credit

- **Status:** `partial`
- **Current behavior:** Students check SIO and mark `21-120` as completed in the
  same course-history checklist used for other relevant courses. The planner
  does not ask how the credit or waiver was earned.
- **Cannot claim:** That selecting a course always grants units or satisfies all
  downstream degree rules.
- **Replacement:** Model separate outcomes:
  `completed_course`, `transfer_credit`, `placement_only`,
  `requirement_waiver`, and `not_completed`. Ask only about courses relevant to
  the selected current-major and goal pair.
- **Product decision:** Credit source and awarded-unit auditing stay in SIO;
  this product only needs the resulting course/requirement status.
- **Remaining priority cases:** Apply the same simple pattern to introductory
  programming, data analysis, and mathematical foundations.

### P-008 — Prerequisites and Course Availability

- **Status:** `partial`
- **Current behavior:** The supported CS path uses a limited prerequisite graph.
- **Cannot claim:** That every planned course is offered in the displayed term,
  has available seats, or includes every co-requisite and grade requirement.
- **Replacement:** Add verified prerequisites, co-requisites, Fall/Spring
  offering patterns, minimum grades, and later live availability where possible.
- **Disclosure:** Separate `academically eligible` from `confirmed available`.

### P-009 — Cross-Program Overlap and Double Counting

- **Status:** `partial`
- **Current behavior:** For the verified Stats/ML subset and CS transfer pair,
  the planner identifies `15-112`, `15-122`, and `21-127` as shared courses,
  schedules each once, counts its units once, prioritizes it within the combined
  path, and explains the overlap in Results.
- **Cannot claim:** That every shared course is legally double-countable under
  both programs' policies.
- **Replacement:** Map each course to requirement slots, distinguish
  `advances_both_paths` from `officially_double_countable`, and encode program
  policy limits. Prioritize shared courses before unique goal courses when safe.
- **Remaining work:** Expand the full Stats/ML curriculum and encode formal
  double-counting policies. Shared requirement membership does not by itself
  prove that a department permits double counting.

### P-010 — Math Course Recommendation

- **Status:** `placeholder`
- **Current behavior:** Results report space available for math but do not select
  a justified course.
- **Cannot claim:** That `21-241` is required for every Statistics & Machine
  Learning student.
- **Replacement:** Model alternative requirement groups such as
  `21-240 | 21-241 | 21-242`, prerequisites, student preparation, and preference
  for applied versus theoretical mathematics.
- **Disclosure:** Show a generic math slot until a choice is supported.

### P-011 — Free or Reserved Units

- **Status:** `placeholder`
- **Current behavior:** Remaining capacity is described as available for math or
  electives.
- **Cannot claim:** That this space is genuinely free before the complete
  current-major curriculum, GenEd curriculum, and graduation-unit requirement
  are included.
- **Replacement:** Divide space into current-major, GenEd, goal, shared,
  reserved/elective, and truly unallocated units.
- **Disclosure:** Use `unallocated units` instead of `free units` for now.

### P-012 — Plan Horizon and Completion

- **Status:** `placeholder`
- **Current behavior:** Fastest and lower-workload paths use fixed planning
  horizons.
- **Cannot claim:** That courses listed as remaining are impossible to schedule
  or that a goal is infeasible.
- **Replacement:** Derive the horizon from the student's starting term,
  graduation target, goal deadline, and remaining prerequisite chain.
- **Disclosure:** Explain when results are outside the currently displayed
  horizon.

### P-013 — Transfer Feasibility and GPA

- **Status:** `partial`
- **Current behavior:** The engine schedules required courses but does not model
  the required transfer-course QPA, overall QPA, application timing, seat
  availability, or committee review.
- **Cannot claim:** That completing a generated course path guarantees transfer.
- **Replacement:** Add verified thresholds, grade scenarios, application dates,
  and non-course milestones without inventing an admission probability.
- **Disclosure:** Call the result a course plan, not a transfer guarantee.

### P-014 — Standardized Course-Catalog Ingestion

- **Status:** `partial`
- **Current behavior:** Program and Dietrich GenEd pages have dedicated parsers;
  course prerequisites are still curated in `courses.json`. The prerequisite
  model now supports typed `any_of` and `all_of` expressions with minimum-grade
  metadata, but grades are not yet collected from students.
- **Cannot claim:** That every prerequisite was automatically discovered or
  that a raw scrape is safe to publish directly to the planner.
- **Replacement pipeline:**

```text
Official source registry
→ dated raw snapshot
→ source-specific extraction
→ normalized prerequisite expression (AND / OR / grade / co-requisite)
→ schema validation
→ regression fixtures
→ explicit human overrides with reasons
→ reviewed production dataset
```

- **Required provenance:** Store source URL, catalog year, retrieval date,
  parser version, source text, verification status, and any override reason.
- **Failure policy:** A parse ambiguity becomes `needs_review`; it must never be
  converted into an empty prerequisite list.
- **Change detection:** Re-scrapes produce a reviewable diff and do not replace
  production data automatically.

## Maintenance Rule

Whenever a new placeholder is introduced:

1. Add it to this registry in the same change.
2. Give it a stable ID and explicit status.
3. Add a user-facing disclosure if it can affect a recommendation.
4. Add at least one test that prevents the placeholder from being presented as
   verified fact.
5. Update or remove the entry when authoritative data replaces it.
