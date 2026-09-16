# Planner Quality Issue: Freshman Sequencing and Unit-Cap Pressure

**Status:** Recorded; implementation pending  
**Date recorded:** 2026-09-16  
**Priority:** High  
**Change type:** Conservative planner-quality fix, not an architecture rewrite

## Problem summary

For an Information Systems student starting in Freshman Fall with few or no completed courses and pursuing the Robotics Additional Major, the planner currently selects mostly reasonable requirement categories but produces an unrealistic semester sequence.

The generated plan can place advanced current-major courses too early, including courses such as `17-313`, `67-250`, `67-272`, and `95-422`, while also trying to fill semesters close to the configured 52-unit maximum.

This is primarily a scheduling and sequencing problem, not a requirement-parsing problem. The listed courses are examples of the symptom and must not become program-specific hardcoded exceptions.

## Reproduction scenario

- Current major: Information Systems
- Planning start: Freshman Fall
- Completed courses: few or none
- Goal type: Additional Major
- Goal program: Robotics
- Unit limit: approximately 52 units per semester

## Current incorrect behavior

- Advanced courses can be scheduled before a realistic prerequisite chain has been completed.
- Freshman semesters can contain courses that assume later class standing or prior major preparation.
- The scheduler appears to reward filling nearly all available units too strongly.
- A semester with 51 or 52 units may be preferred even when a lighter plan would be more realistic and academically better sequenced.
- Current-major progress and additional-major progress may be mixed without enough attention to introductory-to-advanced progression.

## Expected behavior

The scheduler should prioritize, in order:

1. Requirement and prerequisite validity.
2. Realistic course sequencing and class standing.
3. Progress toward both the primary major and the selected goal.
4. Balanced workload across semesters.
5. Unit utilization only after the preceding goals are satisfied.

Unused capacity is acceptable. The planner must not force a semester toward the maximum solely because additional units remain available.

## Required planner behavior

### Prerequisites

- Enforce prerequisite ordering before placing a course.
- Respect multi-step prerequisite chains, not only direct prerequisites.
- Use existing prerequisite helpers and structured course data where available.
- Do not add Information Systems- or Robotics-specific scheduling exceptions.

### Co-requisites

- Keep prerequisites and co-requisites as distinct relationships.
- Permit a co-requisite in the same semester only when the verified data allows it.
- Do not treat a prerequisite as a co-requisite merely to make a schedule fit.

### Freshman and class-standing sequencing

- Prefer explicit minimum-year or class-standing metadata when available.
- Where explicit metadata is missing, use conservative and program-independent sequencing heuristics.
- Introductory and foundational courses should normally precede advanced major courses.
- Any heuristic must remain generic and deterministic, rather than being a list of manually classified courses.

### Primary-major and goal balance

- An Additional Major plan must continue making credible progress in the student's primary major.
- Goal-program courses should be introduced when their prerequisite chains and expected level permit them.
- Neither program should crowd out the other merely because its courses score well for unit utilization.

### Capacity and scoring

- Validity and sequencing must dominate capacity utilization in the scoring objective.
- Remaining unit capacity should be a weak preference, not a requirement.
- The scheduler should not prefer an advanced or poorly sequenced course simply because it fills the semester closer to 52 units.

## Scope boundaries

This fix must preserve:

- Existing API endpoints and response schemas.
- Existing Pydantic models and frontend integration.
- Legacy planner keys and compatibility behavior.
- Current requirement parsing and requirement-category selection.
- Existing Transfer Major, Additional Major, Minor, comparison, and current-major flows.
- The current Robotics requirement categories unless a separate verified-data issue is found.

This work must not:

- Rewrite the planner architecture.
- Add manual semester plans for every major.
- Hardcode special behavior for Information Systems, Robotics, or individual example courses.
- Invent missing CMU prerequisites, co-requisites, class-standing rules, or policies.
- Force every semester to use all available units.

## Investigation checklist

Before changing planner behavior, trace:

1. How course candidates are generated for each semester.
2. Where prerequisite and co-requisite eligibility is evaluated.
3. Whether prerequisite validation considers the full earlier-course history.
4. How course level, minimum year, and class standing affect eligibility or score.
5. How primary-major and goal-program progress are weighted.
6. How workload and unit capacity affect candidate scoring.
7. Whether a capacity reward can outweigh sequencing penalties.
8. Whether courses rejected in one semester are reconsidered correctly later.

Reuse existing helpers before introducing new logic. Any new helper should be small, generic, and independently testable.

## Regression tests required

Add a targeted regression test for the exact scenario:

- Information Systems current major
- Freshman Fall start
- no or minimal completed coursework
- Robotics Additional Major

The test should verify that:

- prerequisite chains are respected;
- advanced current-major courses do not appear in unrealistic freshman positions;
- primary-major and Robotics progress both remain present;
- the result is deterministic;
- semesters are not filled to the unit cap at the expense of sequencing;
- the public response structure is unchanged.

If practical, add a second generic regression scenario using a different primary major or goal to prove the fix is not program-specific.

## Acceptance criteria

- The reproduction scenario produces a realistic freshman plan.
- Direct and transitive prerequisites are ordered correctly.
- Co-requisites remain distinct from prerequisites.
- Advanced coursework is delayed until its preparation is present.
- The planner may leave units unused when that improves validity or sequencing.
- Primary-major progress remains visible in an Additional Major plan.
- No hardcoded IS, Robotics, or course-specific scheduling branch is introduced.
- Existing API contracts and frontend behavior remain unchanged.
- Targeted planner tests pass.
- The complete test suite passes.
- `git diff --check` reports no formatting errors.

## Data dependencies to verify

The implementation may be limited by incomplete verified data. Before using heuristics, audit the availability and coverage of:

- prerequisite relationships;
- co-requisite relationships;
- minimum-year or class-standing restrictions;
- semester offering data;
- course level and numbering metadata;
- units and workload estimates.

Any missing policy data should be reported explicitly. It must not be silently replaced with invented academic rules.

## Future implementation report

When the fix is implemented, report:

- the confirmed root cause;
- files changed;
- exact scheduling/scoring behavior changed;
- prerequisite and co-requisite handling;
- freshman-sequencing behavior;
- capacity-utilization behavior;
- regression tests added;
- full test results;
- remaining limitations caused by missing data.
