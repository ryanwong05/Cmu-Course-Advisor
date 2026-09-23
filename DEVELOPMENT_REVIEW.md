# Development Review: Starting-Plan UX

## 1. What changed

- The first screen now starts with a compact academic dashboard: current degree, selected goal, next planned semester, and current path.
- Students can create a starting plan without opening every course-history and requirement control. Those controls remain available in an optional disclosure panel.
- Degree and goal audits now keep `completed`, `planned`, and `unresolved` counts separate.
- Collapsed major and GenEd summaries expose unresolved work immediately. GenEd names unresolved categories, including Experiential Learning Activity.
- Course cards include a deterministic **Why here?** explanation based on requirement labels, prerequisites, offerings, and scheduled downstream courses.
- A strategy/reaction section shows the current Balanced path. Future strategies and reactions are visibly disabled instead of pretending to replan.
- The editable schedule rejects a second scheduled instance when a selected course or bundle component is already present elsewhere.

## 2. New user flow

1. The student sees the big picture first.
2. They update their current college, major, and planning semester only if needed.
3. They choose a goal.
4. The app offers to create a starting plan immediately.
5. Completed-course and manual requirement controls are optional refinements, not a mandatory construction workflow.
6. Results show high-level status first, then expandable requirement detail, then the editable semester path.

The planner still uses the same APIs and deterministic planning engine. This change rearranges the experience around the existing capabilities rather than replacing them.

## 3. Data flow

```text
Student form / completed-course selections
        ↓
StudentState + PlanningGoal + PlanningConstraints
        ↓
POST /api/plan
        ↓
requirements + baseline + deterministic planner
        ↓
semester course instances + requirement slots + degree audits
        ↓
dashboard / summaries / expandable details / editable path
```

`Engine/degree_audit.py` derives three distinct values from the same verified curriculum:

- **Completed**: satisfied by reported completed courses.
- **Planned**: not completed, but covered by a concrete future course in the generated path.
- **Unresolved**: neither completed nor covered by the current path.

These additive response fields do not rename or remove legacy API fields.

## 4. Important architectural decisions

- No LLM is involved in progress, prerequisites, unit totals, deduplication, or placement explanations.
- No new CMU academic policies or fake courses were added.
- Existing Pydantic models, API routes, planner keys, and response structures remain compatible.
- The dashboard shows honest empty states when no reliable plan exists.
- Explore First, Goal-focused, and natural-language reactions are UI scaffolding only. They are disabled until the engine has corresponding structured constraints.
- Unit limits and workload remain separate. Existing semester cards continue to show actual units, the configured limit, estimated hours, and intensity warnings independently.

## 5. Course instance vs requirement fulfillment

A scheduled course should appear once. A requirement may refer to that course, but it should not create another scheduled instance.

The planner already deduplicates fixed courses and supports explicitly policy-limited cross-scope overlap. This iteration adds a conservative frontend guard for manual choices: if another visible block already contains the same course—or a component of the same multi-course bundle—the second selection is rejected.

This guard does **not** assume that a course may double-count. The current response schema still lacks a first-class `requirement_fulfillments` collection pointing to course-instance IDs. A future safe extension should add that relation only when the policy data explicitly permits overlap.

## 6. Completed vs Planned vs Unresolved

- Completed is academic history and is never inferred from a future semester.
- Planned is a concrete future placement in the generated plan.
- Unresolved means the planner has no current fulfillment.

The degree audit cards, collapsed degree tree, and GenEd panel use these labels consistently. The GenEd progress bar is labelled as **covered** (completed or planned), not completed.

## 7. What to test manually

1. Open the homepage with no existing plan; verify all four dashboard cards use honest empty states.
2. Choose a current major and goal, then create a plan without opening optional controls.
3. Return to the homepage and verify **View my path** restores the generated results.
4. Generate an Information Systems + AI Additional Major plan and verify completed, planned, and unresolved counts are distinct.
5. Leave Experiential Learning unresolved and verify its name appears in the collapsed GenEd summary.
6. Open **Why here?** on a fixed course and a choice course; verify the text cites only known requirements, prerequisites, offerings, or downstream scheduled courses.
7. Try selecting the same course in two editable requirement blocks; verify the second instance is rejected.
8. Verify a semester above its configured unit limit still displays an explicit over-limit warning.
9. Check mobile width: dashboard and strategy cards should collapse to one column.

## 8. What to build next

1. Add a policy-backed `requirement_fulfillments` structure that references stable scheduled course-instance IDs.
2. Persist Student State and the last generated plan so the dashboard survives a new browser session.
3. Add explicit structured constraints for Explore First and Goal-focused strategies.
4. Convert reactions such as “Too hard” into validated planner constraints and produce a real alternative plan.
5. Expand verified prerequisite, offering, GenEd approval, and double-count policy coverage.
6. Split the large frontend controller into small state, API, planner-editor, and results-rendering modules once behavior is covered by browser-level tests.

