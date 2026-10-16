# Program Coverage Audit

> Audit date: 2026-10-15; implementation status updated 2026-10-16. Catalog year: 2026–2027. This file is generated from the current repository data and actual local planner executions; it does not treat directory discovery as planning support.

## Method and coverage levels

- **Level 0:** absent from the project inventory (none in the canonical 213-entry inventory; this says nothing about programs missing from CMU's official catalog).
- **Level 1:** discoverable but no non-empty structured requirement extraction.
- **Level 2:** structured extracted requirements exist, but the corresponding product flow is not connected to the planner.
- **Level 3:** the correct planner endpoint executes, but this audit did not obtain a complete Senior Spring plan.
- **Level 4:** the correct planner endpoint executed and the representative plan reported `goal_complete=true`.

Execution baseline: freshman, no completed courses, 52-unit semester limit, target Senior Spring. Primary majors used their own college and curriculum. Additional majors and minors were combined with Stats/ML. Internal-transfer targets were tested separately from Stats/ML. A Level 4 result proves only this representative scenario, not every student, catalog year, elective selection, or admission outcome.

## Executive counts

| Layer | Count | Percent of 213 directory entries |
|---|---:|---:|
| Discoverable | 213 | 100.0% |
| Non-empty structured extraction | 209 | 98.1% |
| Entry-specific planner flow executes | 21 | 9.9% |
| Representative directory flow completes | 16 | 7.5% |
| Internal-transfer targets separately executable | 10 of 71 primary majors | 14.1% of primary majors |
| Internal-transfer representative flow completes | 9 of 10 configured targets | 90.0% of configured targets |

The raw `program_directory.json` contains 25 `planning_ready` entries, while the runtime API can label 26 entries broadly planning-ready after adding transfer capability. Both numbers overstate entry-specific planning: five SCS/intercollege primary-major entries are transfer-ready but not current-major-ready. The scoped API flag `planner_ready` is the correct field for the entry's own program type and yields 21 executable entries.

## Coverage by program type

| Program type | Directory | Executable | Level 4 | Executable % | Level 4 % |
|---|---:|---:|---:|---:|---:|
| Primary major | 71 | 7 | 7 | 9.9% | 9.9% |
| Additional major | 36 | 6 | 2 | 16.7% | 5.6% |
| Minor | 105 | 8 | 7 | 7.6% | 6.7% |
| Additional degree | 1 | 0 | 0 | 0.0% | 0.0% |

## Coverage by college

Multi-college programs are counted in every listed home college, so college totals are memberships rather than deduplicated rows.

| College | Directory memberships | Executable | Level 4 | Executable % | Level 4 % |
|---|---:|---:|---:|---:|---:|
| College of Fine Arts | 26 | 0 | 0 | 0.0% | 0.0% |
| Dietrich College | 87 | 4 | 4 | 4.6% | 4.6% |
| College of Engineering | 22 | 2 | 2 | 9.1% | 9.1% |
| Intercollege | 21 | 0 | 0 | 0.0% | 0.0% |
| Mellon College of Science | 25 | 1 | 1 | 4.0% | 4.0% |
| CMU-Q | 1 | 0 | 0 | 0.0% | 0.0% |
| School of Computer Science | 20 | 12 | 8 | 60.0% | 40.0% |
| Tepper School of Business | 14 | 2 | 1 | 14.3% | 7.1% |

## Planner-ready and verified programs

**Level 4 directory flows (16):** Statistics and Machine Learning B.S.; Mathematical Sciences B.S.; Mechanical Engineering B.S.; Electrical and Computer Engineering B.S.; Information Systems B.S.; Logic and Computation B.S.; Computer Science B.S.; HCI additional major; Robotics additional major; AI, Business Administration, CS, HCI, IS, Machine Learning, and Robotics minors.

**Executed but incomplete (5):** AI additional major, Computational Biology additional major, Computational Biology minor, Computer Science additional major, and Economics additional major.

**Broadly marked planning-ready but wrong for the entry's own flow (5):** AI B.S., Computational Biology B.S., BCSA, HCI B.S., and Robotics B.S. Their runtime API correctly exposes `current_major_planning_status=directory_only`, but the broad `planning_status=planning_ready` is inherited from transfer capability and should not be used as a generic readiness flag.

## Internal-transfer coverage

| Target | Catalog year | Requirements | Planner | Verified |
|---|---|---|---|---|
| Artificial Intelligence | 2026-2027 | Published profile loaded | Executed | Pass |
| Computational Biology | 2026-2027 | Published profile loaded | Executed | Pass |
| Computer Science | 2026-2027 | Published profile loaded | Executed | Pass |
| Computer Science and Arts | 2026-2027 | Published profile loaded | Executed | Incomplete: BCSA Mathematics, BCSA Probability, BCSA Science & Engineering breadth, BCSA Science & Engineering breadth, Institutions or Cognition breadth, Additional Dietrich or CFA breadth, Additional Dietrich or CFA breadth, BCSA Applications or CS electives, BCSA Applications or CS electives, BCSA Applications or CS electives, BCSA Applications or CS electives, BCSA Applications or CS electives, Selected CFA concentration, Selected CFA concentration, Selected CFA concentration, Selected CFA concentration, Selected CFA concentration, Selected CFA concentration, Selected CFA concentration, Selected CFA concentration, Selected CFA concentration, Selected CFA concentration, Selected CFA concentration, Selected CFA concentration, 15-251 |
| Electrical and Computer Engineering | 2026-2027 | Published profile loaded | Executed | Pass |
| Human-Computer Interaction | 2026-2027 | Published profile loaded | Executed | Pass |
| Information Systems | 2026-2027 | Published profile loaded | Executed | Pass |
| Mechanical Engineering | 2026-2027 | Published profile loaded | Executed | Pass |
| Robotics | 2026-2027 | Published profile loaded | Executed | Pass |
| Statistics and Machine Learning | 2026-2027 | Published profile loaded | Executed | Pass |

BCSA is an important boundary case: its transfer/admission profile executes, but the post-transfer degree plan still has many unresolved breadth, application/elective, and selected-CFA-concentration slots. It is Level 3, not Level 4.

## Complete 213-entry matrix

| College | Program | Type | Catalog year | Requirements | Planner | Verified | Level |
|---|---|---|---|---|---|---|---:|
| College of Fine Arts | Architectural Design Fabrication | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Fine Arts | Architectural Representation and Visualization | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Fine Arts | Architectural Technology | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Fine Arts | Architecture | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Fine Arts | Architecture | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Fine Arts | Architecture | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Fine Arts | Architecture History | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Fine Arts | Art | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Fine Arts | Art | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Fine Arts | Building Science | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Fine Arts | Collaborative Piano | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Fine Arts | Composition | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Fine Arts | Computational Design | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Fine Arts | Conducting | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Fine Arts | Design | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Fine Arts | Design | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Fine Arts | Drama | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Fine Arts | Drama | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Fine Arts | Electronic Music | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Fine Arts | Music | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Fine Arts | Music Education | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Fine Arts | Music Performance | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Fine Arts | Music Technology | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Fine Arts | Music and Technology | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Fine Arts | Photography | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Fine Arts | The History of the Arts | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | African and African American Studies | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | American Politics and Law | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Anthropology | Additional major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Anthropology | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Anthropology | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Arabic Studies | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Behavioral Economics | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Behavioral Economics | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Behavioral Economics | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Chinese Studies | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Cognitive Neuroscience | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Cognitive Science | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Cognitive Science | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Creative Writing | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Creative Writing | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Cybersecurity and International Conflict | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Decision Making and Intelligent Systems | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Decision Science | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Decision Science | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Decision Science | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Economics and Politics | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Economics and Statistics | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Economics and Statistics | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Ethics | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Ethics, History and Public Policy | Additional major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Ethics, History and Public Policy | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Film and Visual Media | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Film and Visual Media | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Gender Studies | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | German Studies | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Global Cultures and Emerging Technologies | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Global French Studies | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Health Humanities | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Hispanic Studies | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | History | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | History | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | History | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Humanities Analytics | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Information Systems | Minor | 2026-2027 | Structured · promotion candidate | Executed | Pass | 4 |
| Dietrich College | Information Systems | Primary major | 2026-2027 | Structured · promotion candidate | Executed | Pass | 4 |
| Dietrich College | International Relations and Political Science | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | International Relations and Political Science | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Japanese Studies | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Languages and Cultures | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Linguistics | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Linguistics | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Literature and Culture | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Literature and Culture | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Logic and Computation | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Logic and Computation | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Logic and Computation | Primary major | 2026-2027 | Structured · promotion candidate | Executed | Pass | 4 |
| Dietrich College | Medical Decision Making | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Military Strategy and International Relations | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Philosophy | Additional major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Philosophy | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Philosophy | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Policy and Management | Additional major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Policy and Management | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Policy and Management | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Political Science, Security, and Technology | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Political Science, Security, and Technology | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Politics and Public Policy | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Professional Writing | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Professional Writing | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Psychology | Additional major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Psychology | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Psychology | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Psychology and Biological Sciences | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Rationality, Uncertainty, and Choice: Formal Methods | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Religious Studies | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Russian Studies | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Science, Technology and Society | Additional major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Science, Technology and Society | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Science, Technology and Society | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Societal and Human Impacts of Future Technologies | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Sociology | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Statistics and Data Science | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Statistics and Data Science | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Statistics and Data Science | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Statistics and Data Science (Mathematical Sciences Track) | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Statistics and Data Science (Mathematical Sciences Track) | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Statistics and Data Science (Neuroscience Track) | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Statistics and Data Science (Neuroscience Track) | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Statistics and Machine Learning | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Dietrich College | Statistics and Machine Learning | Primary major | 2026-2027 | Structured · promotion candidate | Executed | Pass | 4 |
| Dietrich College | Technical Writing | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Dietrich College | Technical Writing | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Engineering | Additive Manufacturing | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Engineering | Audio Engineering | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Engineering | Biomedical Engineering | Additional major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Engineering | Biomedical Engineering | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Engineering | Biomedical Technology | Additional major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Engineering | Chemical Engineering | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Engineering | Civil Engineering | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Engineering | Colloids, Polymers and Surfaces | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Engineering | Electrical and Computer Engineering | Primary major | 2026-2027 | Structured · promotion candidate | Executed | Pass | 4 |
| College of Engineering | Electronic Materials | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Engineering | Engineering Design, Innovation, and Entrepreneurship | Additional major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Engineering | Engineering Studies | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Engineering | Engineering and Public Policy | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Engineering | Environmental Engineering | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Engineering | Global Engineering | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Engineering | Information Security, Privacy and Policy | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Engineering | Materials Science and Engineering | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Engineering | Materials Science and Engineering | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| College of Engineering | Mechanical Behavior of Materials | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Engineering | Mechanical Engineering | Primary major | 2026-2027 | Structured · needs review | Executed | Pass | 4 |
| College of Engineering | Science, Technology, and Public Policy | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| College of Engineering | Technology and Policy | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | Animation and Special Effects | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | Computer Science and Arts | Primary major | 2026-2027 | Empty extraction | Not connected | Not executed | 1 |
| Intercollege | Design for Learning | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | Engineering Studies and Arts | Primary major | 2026-2027 | Empty extraction | Not connected | Not executed | 1 |
| Intercollege | Engineering and Arts | Additional major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | Environmental and Sustainability Studies | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Intercollege | Environmental and Sustainability Studies | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | Game Design | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | General Studies | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | Health Care Policy and Management | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | Humanities and Arts | Primary major | 2026-2027 | Empty extraction | Not connected | Not executed | 1 |
| Intercollege | Immersive Technologies in Arts and Culture | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | Innovation and Entrepreneurship | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Intercollege | Intelligent Environments | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | Media Design | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | Neural Computation | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | Neuroscience | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | Physical Computing | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | Science and Arts | Primary major | 2026-2027 | Empty extraction | Not connected | Not executed | 1 |
| Intercollege | Soft Technologies | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Intercollege | Sonic Arts | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Biological Sciences | Additional major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Biological Sciences | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Mellon College of Science | Biological Sciences | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Biological Sciences | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Biological Sciences and Psychology | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Mellon College of Science | Chemistry | Additional major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Chemistry | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Chemistry | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Mellon College of Science | Chemistry | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Chemistry/Biological Chemistry Track | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Mellon College of Science, Tepper School of Business | Computational Finance | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Mellon College of Science, Tepper School of Business | Computational Finance | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Mellon College of Science, Tepper School of Business | Computational Finance | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Mellon College of Science | Discrete Mathematics and Logic | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Mathematical Sciences | Additional major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Mathematical Sciences | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Mellon College of Science | Mathematical Sciences | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Mellon College of Science | Mathematical Sciences | Primary major | 2026-2027 | Structured · needs review | Executed | Pass | 4 |
| Mellon College of Science | Mathematical Sciences and Economics | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Neuroscience | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Physics | Additional major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Physics | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Physics | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Physics | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Mellon College of Science | Scientific Computing | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| CMU-Q | Tech Entrepreneurship | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| School of Computer Science | Artificial Intelligence | Additional major | 2026-2027 | Structured · needs review | Executed | Incomplete: AI cluster: Perception and Language, AI cluster: Human-AI Interaction, Ethics, Human Cognition, 07-380 | 3 |
| School of Computer Science | Artificial Intelligence | Minor | 2026-2027 | Structured · needs review | Executed | Pass | 4 |
| School of Computer Science | Artificial Intelligence | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| School of Computer Science | Computational Biology | Additional major | 2026-2027 | Structured · promotion candidate | Executed | Incomplete: Introduction to Computational Biology, Modern Biology, Computational biology laboratory, Algorithms, Machine learning, 300-level Computational Biology electives, 300-level Computational Biology electives, 300-level Biology elective, 03-320, 02-512 | 3 |
| School of Computer Science | Computational Biology | Minor | 2026-2027 | Structured · needs review | Executed | Incomplete: 300-level Computational Biology electives | 3 |
| School of Computer Science | Computational Biology | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| School of Computer Science | Computer Science | Additional degree | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| School of Computer Science | Computer Science | Additional major | 2026-2027 | Structured · promotion candidate | Executed | Incomplete: Artificial Intelligence elective, Domains elective, Logic and Languages elective, Systems elective, Technical Communication | 3 |
| School of Computer Science | Computer Science | Minor | 2026-2027 | Structured · promotion candidate | Executed | Pass | 4 |
| School of Computer Science | Computer Science | Primary major | 2026-2027 | Structured · promotion candidate | Executed | Pass | 4 |
| School of Computer Science | Human Computer Interaction | Minor | 2026-2027 | Structured · promotion candidate | Executed | Pass | 4 |
| School of Computer Science | Human-Computer Interaction | Additional major | 2026-2027 | Structured · promotion candidate | Executed | Pass | 4 |
| School of Computer Science | Human-Computer Interaction | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| School of Computer Science | Language Technologies | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| School of Computer Science | Machine Learning | Minor | 2026-2027 | Structured · needs review | Executed | Pass | 4 |
| School of Computer Science | Robotics | Additional major | 2026-2027 | Structured · promotion candidate | Executed | Pass | 4 |
| School of Computer Science | Robotics | Minor | 2026-2027 | Structured · needs review | Executed | Pass | 4 |
| School of Computer Science | Robotics | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| School of Computer Science | Societal Computing | Minor | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| School of Computer Science | Software Engineering | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Tepper School of Business | Business Administration | Additional major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Tepper School of Business | Business Administration | Minor | 2026-2027 | Structured · promotion candidate | Executed | Pass | 4 |
| Tepper School of Business | Business Administration | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Tepper School of Business | Business Analytics and Optimization | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Tepper School of Business | Economics | Additional major | 2026-2027 | Structured · promotion candidate | Executed | Incomplete: 300-level Economics elective, 300-level Economics elective, 300-level Economics elective, 300-level Economics elective, 300-level Economics elective, Economics capstone | 3 |
| Tepper School of Business | Economics | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Tepper School of Business | Economics | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Tepper School of Business | Economics | Primary major | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Tepper School of Business | Economics and Mathematical Sciences | Primary major | 2026-2027 | Structured · needs review | Not connected | Not executed | 2 |
| Tepper School of Business | Financial Management | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |
| Tepper School of Business | Product Management | Minor | 2026-2027 | Structured · promotion candidate | Not connected | Not executed | 2 |

## Missing or incomplete academic data

1. **Four empty intercollege/BXA extractions:** BCSA, BESA, BHA, and BSA have registry records but no fixed courses or requirement groups. BCSA has a manually curated transfer profile, but not a verified current-major curriculum.
2. **188 raw directory entries are not marked ready.** Most have scraper output, but still require academic-policy review, explicit selection rules, unit minima, track handling, double-count policies, and regression tests before promotion.
3. **Prerequisites are the largest cross-cutting gap.** In the 21 executable directory scenarios, most plans emitted `PREREQUISITE_DATA_INCOMPLETE`; the schedule catalog and requirement extraction are broader than verified prerequisite coverage.
4. **Additional-major policy is not inferred safely from primary-major tables.** Thirty additional-major forms remain directory-only even when they inherit a primary curriculum page; unique-course, double-count, declaration, and admission rules must be modeled explicitly.
5. **Course offering data is term-specific, not a long-range guarantee.** A present Fall/Spring listing cannot prove that a course will be offered in every future academic year.
6. **Catalog-year distinctions are nominal.** All current inventory rows are 2026–2027; there is no student-specific historical catalog selection or migration logic.

## Exact failures found during execution

- **Computer Science primary major:** six required courses remained because the fixed-course scheduler does not insert 15-112 and 21-127 as missing preparation for current-major sequences.
- **AI additional major:** four choice requirements remained in the uniform Stats/ML scenario; the planner reported eligible options but exhausted the horizon/capacity.
- **Computational Biology additional major:** eight choice slots remained.
- **Computational Biology minor:** its third 300-level elective remained; the expanded candidate set contains only two distinct 02-3xx courses, so `choose=3` cannot be fulfilled without broader verified data.
- **Computer Science additional major:** five upper-level choice slots remained.
- **Economics additional major:** five 300-level electives and the capstone remained under the representative 52-unit Stats/ML combination.

## Evidence and commands

- Directory capability derivation: `Backend/application.py:650-715`.
- Primary-major and goal request dispatch: `Backend/application.py:1304-1505`.
- Requirement registry: `Data/processed/program_curriculum_registry.json`.
- Program inventory: `Data/processed/program_directory.json`.
- Existing generated report: `Data/processed/program_coverage_report.json` (useful for extraction statistics, but its broad planning-ready number is not entry-flow verification).
- Audit execution: local calls to `app.create_plan()` for every entry with `planner_ready=true`, plus every primary-major entry with `transfer_planning_status=planning_ready`.
