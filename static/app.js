// #region 0. APP OVERVIEW
// ============================================================
// APP.JS — Main controller for the CMU Course Advisor frontend
//
// This file is responsible for:
//
// 1. Keeping track of the user's current selections
// 2. Moving between screens
// 3. Rendering temporary SCS program choices
// 4. Sending plan requests to the FastAPI backend
// 5. Rendering planner results
//
// IMPORTANT:
//
// We are intentionally keeping the current SCS program list here
// only as a TEMPORARY frontend placeholder.
//
// Later, this should move to:
//
//     Data/programs.json
//
// and be loaded through:
//
//     GET /api/programs
//
// VS Code:
// Sections wrapped in "#region" / "#endregion" can be folded.
// Click the small arrow in the gutter next to each region.
// ============================================================
// #endregion



// #region 1. SCREEN REFERENCES
// ============================================================
// Each constant points to one major screen in index.html.
// 它是在 JS 里给 HTML 的几个主要页面取“快捷名字”

// index.html
//    ↓ 浏览器加载
// DOM
//    ↓
// document.getElementById("step2b")
// Current flow:
//
// Step 1  → Current student information
// Step 2  → Goal type
// Step 2B → School + program explorer
// Step 3  → Completed courses / planning inputs
// Results → Generated paths
// ============================================================

const step1 = document.getElementById("step1");
const step2 = document.getElementById("step2");
const step2b = document.getElementById("step2b");
const step3 = document.getElementById("step3");
let refreshRequirementDecisionProgress = () => {};
let refreshGenEdProgress = () => {};
let refreshDegreeRequirementTree = () => {};
let requirementReplanTimer = null;
const results = document.getElementById("results");

// #endregion


// #region 2. GLOBAL APP STATE
// ============================================================
// These variables describe what the user has selected.
//
// Example:
//
// selectedGoalType = "transfer"
// selectedSchool   = "scs"
// selectedProgram  = "computer-science"
//
// Later we can replace this with one appState object,
// for example:
//
// const appState = {
//     goalType: null,
//     school: null,
//     program: null
// };
//
// For now, separate variables are easier to understand.
// ============================================================

const appState = {
    student: {
        college: "dietrich",
        primary_major: "stats-ml",
        year: 1,
        enrollment_status: "enrolled",
        current_term: "fall",
        completed_courses: [],
        completed_requirement_ids: []
    },
    goals: [],
    constraints: {
        start_semester: "spring",
        max_units: 52,
        first_semester_max_units: 52,
        semester_unit_limits: [],
        planning_year: 1,
        target_completion_year: 4
    },
    selection: {
        goalType: null,
        school: null,
        program: null,
        programType: null
    },
    plannerKey: null,
    latestProgramProfile: null,
    latestCourseCatalog: {},
    latestSecondaryPathType: null,
    latestPlan: null,
    genedSelections: {}
};

// #endregion

// #region SAVED PATHS
const SAVED_PATHS_KEY = "cmu-path.saved-paths.v1";

function readSavedPaths() {
    try {
        return JSON.parse(localStorage.getItem(SAVED_PATHS_KEY) || "[]");
    } catch {
        return [];
    }
}

function capturePath(container) {
    return Array.from(container.querySelectorAll(".semester-card")).map(card => ({
        semester: card.querySelector(".semester-name")?.textContent.trim(),
        total: card.querySelector(".semester-total")?.textContent.trim(),
        courses: Array.from(card.querySelectorAll(".planner-course-block"))
            .filter(block => Number(block.dataset.units || 0) > 0)
            .map(block => ({
                id: block.dataset.courseId || block.querySelector("strong")?.textContent.trim(),
                units: Number(block.dataset.units || 0)
            }))
    }));
}

const CAREER_DIRECTIONS = {
    "stats-ml": "Data science, statistics, ML engineering, quantitative analysis, research",
    "mechanical-engineering": "Mechanical design, manufacturing, energy, robotics and systems engineering",
    "computer-science": "Software engineering, systems, product engineering, research",
    "artificial-intelligence": "ML engineering, applied AI, data science, AI research",
    "robotics": "Robotics software, autonomy, controls, perception, hardware systems",
    "human-computer-interaction": "UX engineering, product design, user research, product management",
    "computational-biology": "Bioinformatics, computational research, health technology",
    "information-systems": "Product, consulting, data and business technology"
};

function scorePath(pathData) {
    const semesters = pathData?.path || [];
    const highTerms = semesters.filter(term =>
        term.workload?.warning_level === "high"
        || term.high_intensity_count >= 2
    ).length;
    const avgUnits = semesters.length
        ? semesters.reduce((sum, term) => sum + Number(term.total_units || 0), 0) / semesters.length
        : 0;
    const avgFreeUnits = semesters.length
        ? semesters.reduce((sum, term) => sum + Number(term.free_choice_units || 0), 0) / semesters.length
        : 0;
    const pressure = highTerms > 1 || avgUnits > 48 ? "High" : highTerms || avgUnits > 42 ? "Moderate" : "Manageable";
    const freedom = avgFreeUnits >= 9 ? "High" : avgFreeUnits >= 4 ? "Moderate" : "Limited";
    const rating = Math.max(1, Math.min(5,
        5 - Math.min(2, highTerms) - (avgUnits > 50 ? 1 : 0) + (avgFreeUnits >= 9 ? 0.5 : 0)
    ));
    return { semesters: semesters.length, highTerms, avgUnits, avgFreeUnits, pressure, freedom, rating };
}

function renderPathIntelligence(fastest, secondary) {
    const goal = appState.goals[0] || {};
    const career = CAREER_DIRECTIONS[goal.program] || "Career direction depends on the courses and experiences chosen within this path.";
    const candidates = [
        { key: "fastest", label: "Fastest path", data: fastest },
        {
            key: "secondary",
            label: appState.latestSecondaryPathType === "minor_foundation" ? "Minor foundation" : "Lower-workload path",
            data: secondary
        }
    ].map(item => ({...item, score: scorePath(item.data)}));
    const best = [...candidates].sort((a, b) => b.score.rating - a.score.rating)[0]?.key;
    document.getElementById("pathComparisonGrid").innerHTML = candidates.map(item => `
        <article class="path-score-card ${item.key === best ? "recommended" : ""}">
            <h3>${item.label}</h3>
            <div class="path-rating">${item.score.rating.toFixed(1)} / 5</div>
            <p><strong>Career direction:</strong> ${career}</p>
            <p><strong>Academic pressure:</strong> ${item.score.pressure} · ${item.score.highTerms} high-pressure term${item.score.highTerms === 1 ? "" : "s"}</p>
            <p><strong>Extracurricular freedom:</strong> ${item.score.freedom} · ~${item.score.avgFreeUnits.toFixed(0)} open units per term</p>
            <p><strong>Recommendation:</strong> ${item.key === best ? "Best current balance under your inputs" : "Useful alternative when its tradeoff matches your priority"}</p>
        </article>
    `).join("");
    document.getElementById("rateMyPath").innerHTML = `
        <h3>Rate My Path</h3>
        <p>This first version uses course load, high-intensity combinations, open units, timing, and your selected goal. It stores structured context so an AI adviser can replace or enrich the explanation later.</p>
        <button class="secondary-button" id="rateCurrentPathButton" type="button">Rate my edited fastest path</button>
        <strong id="editedPathRating"></strong>
    `;
    document.getElementById("rateCurrentPathButton").addEventListener("click", () => {
        const cards = Array.from(fastestResults.querySelectorAll(".semester-card"));
        const totals = cards.map(card => Number.parseFloat(card.querySelector(".semester-total")?.textContent) || 0);
        const warnings = cards.filter(card => card.querySelector(".workload-high, .prerequisite-order-warning, .term-warning")).length;
        const average = totals.length ? totals.reduce((sum, value) => sum + value, 0) / totals.length : 0;
        const rating = Math.max(1, Math.min(5, 5 - Math.min(2, warnings) - (average > 50 ? 1 : 0)));
        document.getElementById("editedPathRating").textContent = ` Current edited path: ${rating.toFixed(1)} / 5`;
    });
}

function showPlannerError(message) {
    const dialog = document.getElementById("plannerDialog");
    document.getElementById("plannerDialogMessage").textContent = message;
    dialog.classList.remove("hidden");
    document.getElementById("plannerDialogOk").focus();
}

document.getElementById("plannerDialogOk").addEventListener("click", () => {
    document.getElementById("plannerDialog").classList.add("hidden");
    document.querySelectorAll(".planner-validation-message").forEach(message => {
        message.hidden = true;
        message.textContent = "";
    });
});

function renderSavedPaths() {
    const saved = readSavedPaths();
    document.getElementById("savedPathCount").textContent = saved.length;
    const list = document.getElementById("savedPathsList");
    list.innerHTML = saved.length ? saved.map(path => `
        <article class="saved-path-card" data-saved-path-id="${path.id}">
            <div>
                <strong>${path.name}</strong>
                <p>${path.semesterCount} semesters · ${path.goalType.replaceAll("_", " ")}</p>
                <small>Saved ${new Date(path.savedAt).toLocaleString()}</small>
            </div>
            <button class="secondary-button remove-saved-path" type="button">Remove</button>
        </article>
    `).join("") : "<p>No saved paths yet.</p>";
    list.querySelectorAll(".remove-saved-path").forEach(button => {
        button.addEventListener("click", event => {
            const id = event.target.closest("[data-saved-path-id]").dataset.savedPathId;
            localStorage.setItem(SAVED_PATHS_KEY, JSON.stringify(
                readSavedPaths().filter(path => path.id !== id)
            ));
            renderSavedPaths();
        });
    });
}

document.getElementById("savePathButton").addEventListener("click", () => {
    if (!appState.latestPlan) return;
    const goal = appState.goals[0];
    const paths = readSavedPaths();
    const snapshot = {
        id: globalThis.crypto?.randomUUID?.() || String(Date.now()),
        name: document.getElementById("goalName").textContent.trim(),
        goalType: goal?.type || "academic_path",
        program: goal?.program,
        student: structuredClone(appState.student),
        constraints: structuredClone(appState.constraints),
        balanced: capturePath(fastestResults),
        semesterCount: fastestResults.querySelectorAll(".semester-card").length,
        evaluation: scorePath(appState.latestPlan.lower_workload || appState.latestPlan.fastest),
        ai_context: {
            version: "rules_v1",
            goal,
            comparison_dimensions: ["career", "academic_pressure", "extracurricular_freedom", "recommendation"]
        },
        savedAt: new Date().toISOString()
    };
    paths.unshift(snapshot);
    localStorage.setItem(SAVED_PATHS_KEY, JSON.stringify(paths));
    document.getElementById("savePathFeedback").textContent = "Saved to My Paths";
    renderSavedPaths();
});

document.getElementById("toggleSavedPaths").addEventListener("click", () => {
    document.getElementById("savedPathsPanel").classList.toggle("hidden");
});

renderSavedPaths();
// #endregion


// #region 3. DISPLAY NAME HELPERS
// ============================================================
// Backend IDs are machine-readable.
//
// Example:
//
// cs-transfer
//
// UI should show:
//
// Transfer to Computer Science
//
// Later, these display names should come from programs.json.
// ============================================================

const goalNames = {

    "cs-transfer":
        "Transfer to Computer Science",

    "robotics-transfer":
        "Transfer to Robotics",

    "robotics-additional-major":
        "Robotics Additional Major"

};

// #endregion


// #region 4. TEMPORARY SCS PROGRAM DATA
// ============================================================
// TEMPORARY ONLY.
//
// We are keeping these here so we can finish the frontend
// architecture before connecting programs.json.
//
// Later, delete this whole region and replace it with:
//
// const response = await fetch("/api/programs");
// const programData = await response.json();
//
// ============================================================

let temporarySCSPrograms = [

    {
        id: "computer-science",
        name: "Computer Science"
    },

    {
        id: "artificial-intelligence",
        name: "Artificial Intelligence"
    },

    {
        id: "robotics",
        name: "Robotics"
    },

    {
        id: "human-computer-interaction",
        name: "Human-Computer Interaction"
    },

    {
        id: "computational-biology",
        name: "Computational Biology"
    }

];

let programDirectory = [];

const currentMajorAliases = {
    "Statistics and Machine Learning": "stats-ml",
    "Computer Science": "computer-science",
    "Electrical and Computer Engineering": "electrical-and-computer-engineering"
};

function populateCurrentMajors() {
    const college = document.getElementById("college").value;
    const majorSelect = document.getElementById("major");
    const matches = programDirectory
        .filter(program =>
            program.program_type === "primary_major"
            && (
                program.home_colleges.includes(college)
                || program.affiliations.includes(college)
            )
        )
        .sort((a, b) => a.name.localeCompare(b.name));

    if (!matches.length) return;
    const previousValue = majorSelect.value;
    majorSelect.innerHTML = "";
    for (const program of matches) {
        const option = document.createElement("option");
        option.value = currentMajorAliases[program.name] || program.planning_id || program.id;
        option.textContent = `${program.name} (${program.credential})`;
        majorSelect.appendChild(option);
    }
    if ([...majorSelect.options].some(option => option.value === previousValue)) {
        majorSelect.value = previousValue;
    }
}

async function loadProgramRegistry() {
    try {
        const [programResponse, directoryResponse] = await Promise.all([
            fetch("/api/programs"),
            fetch("/api/program-directory")
        ]);
        if (programResponse.ok) temporarySCSPrograms = await programResponse.json();
        if (directoryResponse.ok) {
            const payload = await directoryResponse.json();
            programDirectory = payload.programs;
            populateCurrentMajors();
        }
    } catch (error) {
        console.warn("Using bundled program fallback:", error);
    }
}

loadProgramRegistry();
document.getElementById("college").addEventListener("change", populateCurrentMajors);

// #endregion


// #region 4B. TEMPORARY COURSE SELECTION DATA
// ============================================================
// Determines what appears on Step 3.
//
// IMPORTANT:
//
// CS Transfer courses belong ONLY to:
//
// Transfer
// → School of Computer Science
// → Computer Science
//
// They are NOT the default course list anymore.
//
// Stats & ML is currently used for:
// Explore My Current Major
//
// Later:
// this data moves to requirements.json / courses.json.
// ============================================================

const step3CourseData = {


    // --------------------------------------------------------
    // SCS → Computer Science → Transfer
    // --------------------------------------------------------

    "cs-transfer": {

        eyebrow:
            "SCS · COMPUTER SCIENCE · TRANSFER",

        title:
            "What have you already completed?",

        description:
            "Select the courses relevant to the Computer Science transfer path.",


        courses: [

            {
                id: "21-120",
                name:
                    "Differential and Integral Calculus"
            },

            {
                id: "15-112",
                name:
                    "Fundamentals of Programming and Computer Science"
            },

            {
                id: "21-127",
                name:
                    "Concepts of Mathematics"
            },

            {
                id: "15-122",
                name:
                    "Principles of Imperative Computation"
            },

            {
                id: "15-150",
                name:
                    "Principles of Functional Programming"
            },

            {
                id: "15-210",
                name:
                    "Parallel and Sequential Data Structures and Algorithms"
            },

            {
                id: "15-213",
                name:
                    "Introduction to Computer Systems"
            },

            {
                id: "15-251",
                name:
                    "Great Ideas in Theoretical Computer Science"
            }

        ],

        plannerReady:
            true

    },



    "robotics-transfer": {

        eyebrow:
            "SCS · ROBOTICS · INTERNAL TRANSFER",

        title:
            "Review the Robotics transfer requirements",

        description:
            "Select courses you have completed. QPA and application requirements depend on whether you are currently in SCS.",

        courses: [
            { id: "36-225", name: "Probability option" },
            { id: "21-325", name: "Probability option" },
            { id: "36-218", name: "Probability option" },
            { id: "15-259", name: "Probability option" },
            { id: "21-127", name: "Concepts of Mathematics" },
            { id: "15-122", name: "Principles of Imperative Computation" },
            { id: "15-213", name: "Introduction to Computer Systems" },
            { id: "15-251", name: "Great Ideas in Theoretical Computer Science" },
            { id: "16-299", name: "Sophomore-level RI option" },
            { id: "16-280", name: "Sophomore-level RI option" },
            { id: "16-281", name: "Sophomore-level RI option" },
            { id: "16-211", name: "Sophomore-level RI option" },
            { id: "16-220", name: "Sophomore-level RI option" }
        ],

        plannerReady:
            false,

        plannerNote:
            "The verified Robotics requirements are available, but path generation is paused until one-of course groups and the SCS/non-SCS policy choice are supported."

    },


    "robotics-additional-major": {

        eyebrow:
            "SCS · ROBOTICS · ADDITIONAL MAJOR",

        title:
            "Explore the Robotics additional major",

        description:
            "Your current-college baseline is available below. Verified path requirements are not configured yet.",

        courses: [],

        plannerReady:
            false,

        plannerNote:
            "The Robotics additional-major goal is connected, but its verified requirement planner is not configured yet."

    },


    // --------------------------------------------------------
    // EXPLORE CURRENT MAJOR → STATISTICS & ML
    //
    // This is currently a FRONTEND FRAMEWORK PLACEHOLDER.
    //
    // We should populate the exact major requirements from
    // our verified Stats & ML requirements data next.
    // --------------------------------------------------------

    "stats-ml-major": {

        eyebrow:
            "DIETRICH · STATISTICS & MACHINE LEARNING",

        title:
            "Explore Statistics & Machine Learning",

        description:
            "Start from the official Stats/ML sample curriculum, then replace approved alternatives where needed.",


        courses: [
            {id: "21-120", name: "Differential and Integral Calculus"},
            {id: "36-200", name: "Reasoning with Data"},
            {id: "15-112", name: "Fundamentals of Programming and Computer Science"},
            {id: "36-202", name: "Methods for Statistics & Data Science"},
            {id: "21-127", name: "Concepts of Mathematics"},
            {id: "21-256", name: "Multivariate Analysis"},
            {id: "36-235", name: "Probability and Statistical Inference I"},
            {id: "15-122", name: "Principles of Imperative Computation"},
            {id: "36-236", name: "Probability and Statistical Inference II"},
            {id: "21-241", name: "Matrices and Linear Transformations"},
            {id: "36-350", name: "Statistical Computing"},
            {id: "10-301", name: "Introduction to Machine Learning"},
            {id: "36-401", name: "Modern Regression"},
            {id: "36-402", name: "Advanced Methods for Data Analysis"},
            {id: "15-351", name: "Algorithms and Advanced Data Structures"}
        ],


        plannerReady: true,
        plannerNote: "Official 2026–27 sample path. Calculus, multivariable calculus, linear algebra, data analysis, probability, computing, and ML alternatives remain customizable."

    }

};

// #endregion


// #region 5. SCREEN NAVIGATION
// ============================================================
// showScreen()
//
// Purpose:
//
// Hide all screens,
// then reveal the screen we want.
//
// This prevents us from repeating the same hide/show logic
// throughout the file.
// ============================================================

function showScreen(screen) {

    step1.classList.add("hidden");
    step2.classList.add("hidden");
    step2b.classList.add("hidden");
    step3.classList.add("hidden");
    results.classList.add("hidden");


    screen.classList.remove("hidden");


    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });

}

function renderResultsRequirementProgress() {
    const panel = document.getElementById("resultsRequirementPanel");
    const progress = appState.requirementDecisionProgress;
    if (!progress) {
        panel.innerHTML = "";
        panel.classList.add("hidden");
        return;
    }
    panel.classList.remove("hidden");
    panel.innerHTML = `
        <div class="results-progress-copy">
            <span><strong>Requirement choices</strong><small>${progress.complete} of ${progress.total} decisions complete</small></span>
            <button class="secondary-button edit-requirements-button" type="button">Edit choices</button>
        </div>
        <div class="decision-progress-track" role="progressbar" aria-label="Requirement choice completion" aria-valuemin="0" aria-valuemax="${progress.total}" aria-valuenow="${progress.complete}"><span style="width:${progress.percent}%"></span></div>`;
    panel.querySelector(".edit-requirements-button").addEventListener("click", () => showScreen(step3));
}

function renderTransferReadiness(data) {
    const panel = document.getElementById("transferReadinessPanel");
    const transfer = data.transfer_planning;
    if (!transfer?.policy) {
        panel.classList.add("hidden");
        panel.innerHTML = "";
        return;
    }
    const policy = transfer.policy;
    const gpaRules = [
        policy.minimum_overall_gpa ? `Overall QPA ≥ ${policy.minimum_overall_gpa}` : null,
        policy.minimum_core_gpa ? `Required-course QPA ≥ ${policy.minimum_core_gpa}` : null,
        policy.minimum_grade ? `Minimum course grade: ${policy.minimum_grade}` : null
    ].filter(Boolean);
    const completedIds = new Set(appState.student.completed_courses || []);
    const scheduledIds = new Set(
        (data.fastest?.path || []).flatMap(semester => [
            ...(semester.courses || []),
            ...(semester.program_requirements || []).flatMap(requirement =>
                (requirement.default_option || "").split(" + ").filter(Boolean)
            )
        ])
    );
    const courseCatalog = data.course_catalog || {};
    const courseStatus = ids => {
        if (ids.some(id => completedIds.has(id))) return {label: "✓ Completed", className: "is-complete"};
        if (ids.some(id => scheduledIds.has(id))) return {label: "Scheduled", className: "is-scheduled"};
        return {label: "Still needed", className: "is-needed"};
    };
    const fixedRequirements = (policy.required_course_ids || []).map(courseId => ({
        ids: [courseId],
        courseLabel: `${courseId} · ${courseCatalog[courseId]?.name || "Required course"}`,
        ruleLabel: "Required"
    }));
    const choiceRequirements = (policy.requirement_groups || []).map(group => ({
        ids: (group.options || []).flatMap(option => option.split(" + ")),
        courseLabel: (group.options || []).join(" OR "),
        ruleLabel: group.name
    }));
    const transferRequirements = [...fixedRequirements, ...choiceRequirements];
    const completedCount = transferRequirements.filter(requirement =>
        requirement.ids.some(id => completedIds.has(id))
    ).length;
    const scheduledCount = transferRequirements.filter(requirement =>
        !requirement.ids.some(id => completedIds.has(id))
        && requirement.ids.some(id => scheduledIds.has(id))
    ).length;
    const requirementRows = transferRequirements.map(requirement => {
        const status = courseStatus(requirement.ids);
        return `<li><span><strong>${requirement.courseLabel}</strong><small>${requirement.ruleLabel}</small></span><span class="transfer-course-status ${status.className}">${status.label}</span></li>`;
    }).join("");
    const preparationRows = (policy.preparation_courses || []).map(courseId => {
        const status = courseStatus([courseId]);
        return `<li><span><strong>${courseId} · ${courseCatalog[courseId]?.name || "Preparation course"}</strong><small>Preparation prerequisite; not one of the admission-course requirements</small></span><span class="transfer-course-status ${status.className}">${status.label}</span></li>`;
    }).join("");
    const applicationRequirements = (policy.application_requirements || []).map((requirement, index) => `
        <li>
            <span class="transfer-action-number">${index + 1}</span>
            <span><strong>${requirement.name}</strong><small>${requirement.detail}</small></span>
        </li>`).join("");
    panel.classList.remove("hidden");
    panel.innerHTML = `
        <div class="transfer-readiness-heading">
            <div><p class="eyebrow">YOUR #1 PRIORITY · TRANSFER CHECKPOINT</p><h2>${transfer.mode === "eligibility" ? "Path to become eligible to apply" : "Post-transfer degree plan"}</h2><p class="transfer-heading-note">Complete this checkpoint before treating the destination major as confirmed.</p></div>
            <span class="rules-badge">${completedCount} completed · ${scheduledCount} scheduled · ${Math.max(0, transferRequirements.length - completedCount - scheduledCount)} needed</span>
        </div>
        <div class="transfer-policy-grid">
            <div><strong>Academic threshold</strong><span>${gpaRules.join(" · ") || "Good academic standing"}</span></div>
            <div><strong>Capacity / slots</strong><span>${policy.capacity_limited ? "Admission depends on available space; completing courses does not guarantee transfer." : "No published capacity restriction found."}</span></div>
            <div><strong>Application timing</strong><span>${policy.application_timing || "Confirm the current deadline with the program."}</span></div>
            <div><strong>Admission outlook</strong><span>Not estimated yet—course completion alone is insufficient without your grades, statement/interview factors, and current capacity.</span></div>
        </div>
        <div class="transfer-course-checklist">
            <div class="transfer-course-checklist-heading"><strong>Courses required before you apply</strong><span>${transferRequirements.length} official requirements · ${policy.policy_status === "official_verified" ? "verified" : "advisor check"}</span></div>
            ${requirementRows ? `<ul>${requirementRows}</ul>` : "<p>No course-only automatic admission requirement is published for this program. Confirm the individual review with an advisor.</p>"}
            ${preparationRows ? `<div class="transfer-preparation-label">Preparation</div><ul>${preparationRows}</ul>` : ""}
        </div>
        ${applicationRequirements ? `<div class="transfer-application-actions"><div class="transfer-course-checklist-heading"><strong>Application materials & actions</strong><span>Required beyond coursework</span></div><ol>${applicationRequirements}</ol></div>` : ""}
        <p class="transfer-policy-note">${policy.eligibility || "Confirm all criteria with the destination program."} ${policy.source_url ? `<a href="${policy.source_url}" target="_blank" rel="noopener">View official policy</a>` : ""}</p>
        ${transfer.mode === "eligibility" && transfer.post_transfer_plan_available ? '<button class="secondary-button plan-after-transfer-button" type="button">Plan courses after I transfer →</button>' : ""}`;
    panel.querySelector(".plan-after-transfer-button")?.addEventListener("click", () => {
        appState.selection.includePostTransferPlan = true;
        updatePlanningGoal();
        document.getElementById("generateButton").click();
    });
}

function prepareTransferAdvisor(data) {
    const panel = document.getElementById("aiTransferAdvisor");
    const button = document.getElementById("analyzeTransferButton");
    const status = document.getElementById("aiTransferAdvisorStatus");
    const output = document.getElementById("aiTransferAdvisorOutput");
    const isTransferPlan = appState.goals[0]?.type === "internal_transfer" && data.transfer_planning;

    panel.classList.toggle("hidden", !isTransferPlan);
    button.disabled = false;
    button.textContent = "Analyze with AI";
    status.classList.remove("is-error");
    status.textContent = isTransferPlan
        ? "Uses only the verified policy and course-plan data shown by this app."
        : "";
    output.replaceChildren();
    output.classList.add("hidden");
}

function addAdvisorTextCard(container, title, value, className = "") {
    const card = document.createElement("section");
    card.className = `ai-advisor-card ${className}`.trim();
    const heading = document.createElement("h3");
    heading.textContent = title;
    const paragraph = document.createElement("p");
    paragraph.textContent = value;
    card.append(heading, paragraph);
    container.appendChild(card);
}

function addAdvisorListCard(container, title, values, ordered = false) {
    const card = document.createElement("section");
    card.className = "ai-advisor-card";
    const heading = document.createElement("h3");
    heading.textContent = title;
    const list = document.createElement(ordered ? "ol" : "ul");
    values.forEach(value => {
        const item = document.createElement("li");
        item.textContent = value;
        list.appendChild(item);
    });
    card.append(heading, list);
    container.appendChild(card);
}

function renderTransferAdvice(advice) {
    const output = document.getElementById("aiTransferAdvisorOutput");
    output.replaceChildren();
    addAdvisorTextCard(output, "Summary", advice.summary, "ai-advisor-summary");
    addAdvisorTextCard(output, "Recommendation", advice.recommendation);
    addAdvisorTextCard(output, "Feasibility", advice.feasibility);
    addAdvisorTextCard(output, "Opportunity cost", advice.opportunity_cost);
    addAdvisorTextCard(output, "Backup strength", advice.backup_strength);
    addAdvisorListCard(output, "Key risks", advice.key_risks);
    addAdvisorListCard(output, "Next steps", advice.next_steps, true);
    output.classList.remove("hidden");
}

document.getElementById("analyzeTransferButton").addEventListener("click", async () => {
    const button = document.getElementById("analyzeTransferButton");
    const status = document.getElementById("aiTransferAdvisorStatus");
    const output = document.getElementById("aiTransferAdvisorOutput");
    button.disabled = true;
    button.textContent = "Analyzing…";
    status.classList.remove("is-error");
    status.textContent = "Reviewing the verified transfer plan…";
    output.classList.add("hidden");

    try {
        const response = await fetch("/api/transfer-advice", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(buildPlanningRequest())
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || "AI analysis is unavailable right now.");
        renderTransferAdvice(payload);
        status.textContent = "Analysis complete. Confirm important decisions with your academic advisor.";
    } catch (error) {
        status.classList.add("is-error");
        status.textContent = error.message || "AI analysis is unavailable right now.";
    } finally {
        button.disabled = false;
        button.textContent = "Analyze again";
    }
});


// ------------------------------------------------------------
// STEP 1 → STEP 2
// ------------------------------------------------------------

document
    .getElementById("step1Next")
    .addEventListener("click", () => {

        appState.student = {
            college: document.getElementById("college").value,
            primary_major: document.getElementById("major").value,
            year: Number(document.getElementById("year").value),
            enrollment_status: document.getElementById("enrollmentStatus").value,
            current_term: document.getElementById("currentTerm").value,
            completed_courses: appState.student.completed_courses,
            completed_requirement_ids: appState.student.completed_requirement_ids
        };

        const [status, currentYear, currentTerm, planYear, planTerm] =
            document.getElementById("planningStart").value.split("|");
        appState.student.enrollment_status = status;
        appState.student.year = Number(currentYear);
        appState.student.current_term = currentTerm;
        document.getElementById("enrollmentStatus").value = status;
        document.getElementById("year").value = currentYear;
        document.getElementById("currentTerm").value = currentTerm;
        document.getElementById("planningYear").value = planYear;
        document.getElementById("semester").value = planTerm;

        showScreen(step2);

    });


// ------------------------------------------------------------
// STEP 2 → STEP 1
// ------------------------------------------------------------

document
    .getElementById("step2Back")
    .addEventListener("click", () => {

        showScreen(step1);

    });


// ------------------------------------------------------------
// STEP 2B → STEP 2
// ------------------------------------------------------------

document
    .getElementById("step2bBack")
    .addEventListener("click", () => {

        showScreen(step2);

    });


// ------------------------------------------------------------
// STEP 3 → STEP 2
// ------------------------------------------------------------
//
// NOTE:
//
// Later this should probably be context-aware.
//
// Example:
//
// Transfer → SCS → CS → Step 3
//
// pressing Back should ideally return to SCS → CS,
// not all the way back to Step 2.
//
// We can improve that later.
// ------------------------------------------------------------

document
    .getElementById("step3Back")
    .addEventListener("click", () => {

        // Course history is reached from the program picker for transfer,
        // additional-major, and minor paths.  Preserve that selection instead
        // of sending the student back to the beginning of goal selection.
        if (["transfer", "add-program"].includes(appState.selection.goalType)) {
            showScreen(step2b);
        } else {
            showScreen(step2);
        }

    });


// ------------------------------------------------------------
// RESULTS → START OVER
// ------------------------------------------------------------

document
    .getElementById("restartButton")
    .addEventListener("click", () => {

        showScreen(step3);

    });

// #endregion


// #region 6. STEP 2 — GOAL TYPE SELECTION
// ============================================================
// STEP 2
//
// Clicking a goal card only SELECTS it.
// The page changes only after the user clicks Continue.
// ============================================================


// Get all four goal cards
const goalTypeCards =
    document.querySelectorAll(
        ".goal-card[data-goal-type]"
    );


// Continue button on Step 2
const step2Next =
    document.getElementById(
        "step2Next"
    );


// ------------------------------------------------------------
// SELECT A GOAL CARD
// ------------------------------------------------------------

goalTypeCards.forEach(card => {

    card.addEventListener("click", () => {

        // Remove selection from every card
        goalTypeCards.forEach(otherCard => {
            otherCard.classList.remove("selected");
        });


        // Highlight the card that was clicked
        card.classList.add("selected");


        // Save the user's choice
        appState.selection.goalType =
            card.dataset.goalType;


        // Enable Continue
        step2Next.disabled = false;


        console.log(
            "Selected goal type:",
            appState.selection.goalType
        );

    });

});


// ------------------------------------------------------------
// CONTINUE FROM STEP 2
// ------------------------------------------------------------

step2Next.addEventListener("click", async () => {

    // Safety check
    if (!appState.selection.goalType) {
        return;
    }


    // --------------------------------------------------------
    // EXPLORE CURRENT MAJOR
    //
    // We already know the student's major from Step 1,
    // so no school/program selection is needed.
    // --------------------------------------------------------

    if (appState.selection.goalType === "explore-current") {

        await prepareCurrentMajorStep();

        return;
    }


    // --------------------------------------------------------
    // TRANSFER MAJOR
    // --------------------------------------------------------

    if (appState.selection.goalType === "transfer") {

        resetProgramExplorer();

        updateExplorerCopy();

        showScreen(step2b);

        return;
    }


    // --------------------------------------------------------
    // ADDITIONAL MAJOR / MINOR
    // --------------------------------------------------------

    if (appState.selection.goalType === "add-program") {

        resetProgramExplorer();

        updateExplorerCopy();

        showScreen(step2b);

        return;
    }


    // --------------------------------------------------------
    // UNDECIDED
    //
    // Temporary behavior:
    // use the program explorer.
    //
    // Later this will have its own discovery page.
    // --------------------------------------------------------

    if (appState.selection.goalType === "undecided") {

        resetProgramExplorer();

        updateExplorerCopy();

        showScreen(step2b);

    }

});

// ------------------------------------------------------------
// UPDATE PROGRAM EXPLORER TEXT
//
// Changes the Step 2B title and description depending on
// what the user selected on Step 2.
// ------------------------------------------------------------

function updateExplorerCopy() {

    const title =
        document.getElementById(
            "explorerTitle"
        );

    const description =
        document.getElementById(
            "explorerDescription"
        );


    // --------------------------------------------------------
    // TRANSFER MAJOR
    // --------------------------------------------------------

    if (appState.selection.goalType === "transfer") {

        title.textContent =
            "Where are you considering transferring?";

        description.textContent =
            "Choose a school, then choose a major.";

    }


    // --------------------------------------------------------
    // ADDITIONAL MAJOR / MINOR
    // --------------------------------------------------------

    else if (appState.selection.goalType === "add-program") {

        title.textContent =
            "What would you like to add?";

        description.textContent =
            "Choose a school, then explore its additional majors and minors.";

    }


    // --------------------------------------------------------
    // UNDECIDED
    // --------------------------------------------------------

    else if (appState.selection.goalType === "undecided") {

        title.textContent =
            "Explore academic options";

        description.textContent =
            "Browse schools and programs to discover possible academic paths.";

    }

}

// #endregion


// #region 7. STEP 2B — SCHOOL SELECTION
// ============================================================
// School selection now uses ONE dropdown.
//
// This gives the page more space and lets program cards
// become the main visual focus.
//
// Future benefit:
// Adding more CMU schools will not make the page huge.
// ============================================================

const schoolSelect =
    document.getElementById(
        "schoolSelect"
    );


schoolSelect.addEventListener(
    "change",
    () => {

        appState.selection.school =
            schoolSelect.value;


        // Changing school invalidates old program choice.
        appState.selection.program =
            null;


        // Disable Continue until program selected.
        document
            .getElementById(
                "step2bNext"
            )
            .disabled = true;


        const programSection =
            document.getElementById(
                "programSection"
            );


        const programOptions =
            document.getElementById(
                "programOptions"
            );


        // Clear previous programs.
        programOptions.innerHTML =
            "";


        // No school selected.
        if (!appState.selection.school) {

            programSection
                .classList
                .add("hidden");

            return;

        }


        renderProgramsForSchool(appState.selection.school);


        console.log(
            "Selected school:",
            appState.selection.school
        );

    }
);

// #endregion


// #region 8. STEP 2B — PROGRAM SELECTION
// ============================================================
// After choosing SCS, we dynamically create:
//
// Computer Science
// Artificial Intelligence
// Robotics
// Human-Computer Interaction
// Computational Biology
//
// Later:
//
// this should be generic:
//
// selectedSchool
//      ↓
// programs.json
//      ↓
// render available programs
//
// ============================================================

function renderTemporarySCSPrograms() {

    const programSection =
        document.getElementById(
            "programSection"
        );

    const programOptions =
        document.getElementById(
            "programOptions"
        );


    // --------------------------------------------------------
    // Remove old program cards before rendering again
    // --------------------------------------------------------

    programOptions.innerHTML = "";


    // --------------------------------------------------------
    // Create one button per program
    // --------------------------------------------------------

    for (
        const program
        of temporarySCSPrograms
    ) {

        const button =
            document.createElement(
                "button"
            );


        button.className =
            "program-card";


        button.dataset.program =
            program.id;


        button.innerHTML = `<strong>${program.name}</strong>`;

        if (appState.selection.goalType === "add-program") {
            const route = document.createElement("span");
            route.className = "program-upgrade-label";
            route.textContent = "Minor foundation → Additional Major";
            button.appendChild(route);
        }


        // ----------------------------------------------------
        // PROGRAM CLICK EVENT
        // ----------------------------------------------------

        button.addEventListener(
            "click",
            event => {

                // --------------------------------------------
                // Clear previous program selection
                // --------------------------------------------

                document
                    .querySelectorAll(
                        ".program-card"
                    )
                    .forEach(otherCard => {

                        otherCard
                            .classList
                            .remove(
                                "selected"
                            );

                    });


                // --------------------------------------------
                // Highlight current program
                // --------------------------------------------

                button.classList.add(
                    "selected"
                );


                // --------------------------------------------
                // Save program
                // --------------------------------------------

                appState.selection.program =
                    program.id;

                if (appState.selection.goalType === "add-program") {
                    appState.selection.programType = "additional_major";
                    renderProgramComparison(program.id);
                }


                console.log(
                    "Selected program:",
                    appState.selection.program
                );


                // --------------------------------------------
                // Convert new frontend selection into
                // old backend planner goal
                // --------------------------------------------

                updatePlanningGoal();


                // --------------------------------------------
                // Allow user to continue
                // --------------------------------------------

                document
                    .getElementById(
                        "step2bNext"
                    )
                    .disabled = false;

            }
        );


        programOptions.appendChild(
            button
        );

    }


    // --------------------------------------------------------
    // Reveal program section
    // --------------------------------------------------------

    programSection.classList.remove(
        "hidden"
    );

}


function renderProgramsForSchool(school) {
    if (!programDirectory.length) {
        if (school === "scs") renderTemporarySCSPrograms();
        return;
    }

    const programSection = document.getElementById("programSection");
    const programOptions = document.getElementById("programOptions");
    const helper = programSection.querySelector(".program-helper");
    const schoolLabel = programSection.querySelector(".eyebrow");
    const allowedTypes = appState.selection.goalType === "transfer"
        ? ["primary_major"]
        : ["additional_major", "minor"];
    const matches = programDirectory
        .filter(program =>
            allowedTypes.includes(program.program_type)
            && (
                program.home_colleges.includes(school)
                || program.affiliations.includes(school)
            )
        )
        .sort((a, b) => a.name.localeCompare(b.name));

    programOptions.innerHTML = "";
    schoolLabel.textContent = school.replaceAll("-", " ").toUpperCase();
    helper.textContent = `${matches.length} programs in the 2026–27 directory`;

    for (const program of matches) {
        const button = document.createElement("button");
        button.className = "program-card";
        button.dataset.program = program.id;
        const planningId = program.planning_id || program.id;
        // The API derives readiness from the real profile/curriculum data.
        // Do not maintain a second browser-side program allowlist.
        const readyForSelectedGoal = appState.selection.goalType === "transfer"
            ? program.transfer_planning_status === "planning_ready"
            : program.planning_status === "planning_ready";
        button.disabled = !readyForSelectedGoal;
        button.setAttribute("aria-disabled", String(!readyForSelectedGoal));
        button.innerHTML = `
            <strong>${program.name}</strong>
            <span class="program-upgrade-label">${program.credential}</span>
            <small>${readyForSelectedGoal
                ? "Verified planning available"
                : appState.selection.goalType === "transfer"
                    ? "Transfer planning coming soon"
                    : "Directory only · requirements coming soon"}</small>
        `;
        button.addEventListener("click", () => {
            document.querySelectorAll(".program-card").forEach(card => {
                card.classList.remove("selected");
            });
            button.classList.add("selected");
            appState.selection.program = program.planning_id || program.id;
            appState.selection.programType = program.program_type === "minor"
                ? "minor"
                : program.program_type === "additional_major"
                    ? "additional_major"
                    : null;
            updatePlanningGoal();
            const ready = readyForSelectedGoal;
            document.getElementById("step2bNext").disabled = !ready;
            helper.textContent = ready
                ? "Verified planning is available for this path."
                : appState.selection.goalType === "transfer"
                    ? "This major is listed, but its transfer planner is not verified yet."
                    : "This program is listed, but its planning requirements have not been verified yet.";
            if (ready && appState.selection.goalType === "add-program") {
                renderProgramComparison(appState.selection.program);
            } else {
                document.getElementById("programComparison").classList.add("hidden");
            }
        });
        programOptions.appendChild(button);
    }

    if (!matches.length) {
        programOptions.innerHTML = "<p>No matching programs are listed for this path.</p>";
    }
    programSection.classList.remove("hidden");
}



// ------------------------------------------------------------
// RESET PROGRAM EXPLORER
//
// Why?
//
// Imagine:
//
// 1. User chooses Transfer → SCS → CS
// 2. Goes back
// 3. Chooses Additional Major / Minor
//
// We do NOT want CS to remain selected.
//
// This function resets those old choices.
// ------------------------------------------------------------

function resetProgramExplorer() {

    appState.selection.school = null;
    appState.selection.program = null;
    appState.selection.programType = null;


    // Reset school dropdown.
    const schoolSelect =
        document.getElementById(
            "schoolSelect"
        );

    schoolSelect.value =
        "";


    // Hide program section.
    const programSection =
        document.getElementById(
            "programSection"
        );


    const programOptions =
        document.getElementById(
            "programOptions"
        );


    programOptions.innerHTML =
            "";

    const comparison = document.getElementById("programComparison");
    comparison.innerHTML = "";
    comparison.classList.add("hidden");


    programSection
        .classList
        .add("hidden");


    // Disable Continue.
    document
        .getElementById(
            "step2bNext"
        )
        .disabled = true;

}



// ------------------------------------------------------------
// TEMPORARY BACKEND GOAL MAPPING
//
// NEW frontend architecture:
//
// goalType
// +
// school
// +
// program
//
// Example:
//
// transfer
// + scs
// + computer-science
//
// OLD backend architecture:
//
// "cs-transfer"
//
// This function temporarily connects the two systems.
//
// Eventually:
//
// DELETE THIS FUNCTION.
//
// Backend should directly accept:
//
// {
//     goal_type: "transfer",
//     school: "scs",
//     program: "computer-science"
// }
//
// ------------------------------------------------------------

function updatePlanningGoal() {
    const { goalType, school, program } = appState.selection;

    if (goalType === "explore-current") {
        appState.goals = [{
            type: "current_major",
            program: appState.student.primary_major
        }];
        return;
    }

    if (goalType === "transfer") {
        appState.goals = [{
            type: "internal_transfer",
            college: school,
            program,
            include_post_transfer_plan: Boolean(appState.selection.includePostTransferPlan)
        }];
        return;
    }

    if (goalType === "add-program") {
        appState.goals = [{
            type: appState.selection.programType || "additional_major",
            college: school,
            program
        }];
    }
}


function plannerKeyForGoal(goal) {
    const keys = {
        "current_major:stats-ml": "stats-ml-major",
        "internal_transfer:computer-science": "cs-transfer",
        "internal_transfer:robotics": "robotics-transfer",
        "additional_major:robotics": "robotics-additional-major"
    };
    if (keys[`${goal.type}:${goal.program}`]) {
        return keys[`${goal.type}:${goal.program}`];
    }
    const suffix = {
        internal_transfer: "transfer",
        additional_major: "additional-major",
        minor: "minor"
    }[goal.type];
    return suffix ? `${goal.program}-${suffix}` : null;
}

async function renderProgramComparison(programId) {
    const container = document.getElementById("programComparison");
    container.classList.remove("hidden");
    container.innerHTML = "Loading opportunity-cost comparison…";
    const response = await fetch("/api/program-comparison", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            student: appState.student,
            programs: [programId],
            goal_types: ["additional_major", "minor"]
        })
    });
    if (!response.ok) {
        container.textContent = "Comparison could not be loaded.";
        return;
    }
    const data = await response.json();
    const minor = data.comparisons.find(item => item.goal_type === "minor");
    const major = data.comparisons.find(item => item.goal_type === "additional_major");
    container.innerHTML = `
        <p class="eyebrow">ONE UPGRADE PATH · ${data.catalog_year}</p>
        <article class="comparison-card upgrade-comparison-card">
            <h3>Minor foundation → Additional Major</h3>
            <p><strong>Foundation:</strong> ${minor?.minimum_courses ?? "—"}+ courses · ≈${minor?.minimum_units ?? "—"}+ units</p>
            <p class="major-extension-copy"><strong>Green extension:</strong> approximately ${Math.max(0, (major?.minimum_courses || 0) - (minor?.minimum_courses || 0))} additional courses and ${Math.max(0, (major?.minimum_units || 0) - (minor?.minimum_units || 0))} additional units at the published minimum.</p>
            <p>${major?.potential_overlap_courses.length
                ? `${major.potential_overlap_courses.join(", ")} may overlap with your currently verified curriculum.`
                : "No overlap is confirmed from the currently verified subset."}</p>
            <p><strong>Minor eligibility:</strong> ${minor?.eligibility || "Review with the program advisor."}</p>
        </article>
        <p class="history-helper">Catalog minimums are not a promised graduation plan. Elective choices and advisor decisions can increase the cost.</p>
    `;
}


function buildPlanningRequest() {
    appState.constraints = {
        start_semester: document.getElementById("semester").value,
        max_units: Number(document.getElementById("units").value),
        first_semester_max_units: 52,
        semester_unit_limits: [],
        planning_year: Number(document.getElementById("planningYear").value),
        target_completion_year: Number(document.getElementById("targetCompletionYear").value)
    };

    return {
        student: appState.student,
        goals: appState.goals,
        constraints: appState.constraints
    };
}


async function loadBaseline() {
    const baselineSummary = document.getElementById("baselineSummary");
    baselineSummary.textContent = "Loading your current-college baseline…";

    const response = await fetch("/api/baseline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPlanningRequest())
    });

    if (!response.ok) {
        baselineSummary.textContent = "Baseline could not be loaded.";
        return;
    }

    const data = await response.json();
    appState.baselineRequirements = data.baseline.requirements;
    appState.plannerKey = data.planner_key;
    const genedHistory = document.getElementById("genedHistory");
    genedHistory.innerHTML = data.baseline.requirements.map(requirement => `
        <label class="course-option gened-option">
            <input type="checkbox" value="${requirement.id}"
                ${appState.student.completed_requirement_ids.includes(requirement.id) ? "checked" : ""}>
            <span>
                <strong>${requirement.name}</strong>
                ${requirement.units} ${requirement.units === 1 ? "unit" : "units"} · ${requirement.timeline.source_text}
            </span>
        </label>
    `).join("");
    const decisionPage = document.querySelector(".requirement-decision-page");
    const baselineSection = genedHistory.closest(".history-section");
    if (decisionPage && baselineSection) {
        baselineSection.classList.add("hidden");
        const auditList = decisionPage.querySelector(".requirement-audit-list");
        const nowList = decisionPage.querySelector(".choose-now-group .decision-list");
        const laterList = decisionPage.querySelector(".decide-later-group .decision-list");
        auditList.querySelectorAll(".baseline-audit-row").forEach(row => row.remove());
        decisionPage.querySelectorAll(".baseline-decision-requirement").forEach(row => row.remove());
        data.baseline.requirements.forEach(requirement => {
            const completed = appState.student.completed_requirement_ids.includes(requirement.id);
            const row = document.createElement("div");
            row.className = `requirement-audit-row baseline-audit-row${completed ? " audit-complete" : ""}`;
            row.dataset.requirementId = requirement.id;
            row.innerHTML = `<label><input type="checkbox" class="baseline-audit-toggle" ${completed ? "checked" : ""}><span><strong>${requirement.name}</strong><small>${requirement.units} ${requirement.units === 1 ? "unit" : "units"} · ${requirement.timeline.source_text}</small></span></label><span class="audit-row-status">${completed ? "Completed" : "Choose in plan"}</span>`;
            const matchingDecision = requirement.id === "data-analysis"
                ? Array.from(decisionPage.querySelectorAll(".decision-requirement")).find(panel =>
                    panel.querySelector('input[value="36-200"]')
                    || /beginning data analysis/i.test(panel.querySelector(".decision-summary-name")?.textContent || "")
                )
                : null;
            const syncRequirement = checked => {
                const source = genedHistory.querySelector(`input[value="${requirement.id}"]`);
                if (source) source.checked = checked;
                row.querySelector("input").checked = checked;
                row.classList.toggle("audit-complete", checked);
                row.querySelector(".audit-row-status").textContent = checked ? "Completed" : "Choose in plan";
                const baselineCard = decisionPage.querySelector(`.baseline-decision-requirement[data-requirement-id="${requirement.id}"]`);
                if (baselineCard) {
                    baselineCard.querySelector("input").checked = checked;
                    baselineCard.classList.toggle("decision-complete", checked);
                    baselineCard.querySelector(".decision-status-text").textContent = checked ? "✓ Completed" : "Choose in plan";
                }
                refreshDegreeRequirementTree();
            };
            if (matchingDecision) {
                matchingDecision.dataset.baselineRequirementId = requirement.id;
                matchingDecision.querySelector(".decision-summary-name").insertAdjacentHTML(
                    "beforeend", '<small class="shared-requirement-badge">Also satisfies GenEd: Data Analysis</small>'
                );
                matchingDecision.querySelectorAll('.requirement-choice-option input[type="checkbox"]').forEach(input => {
                    input.addEventListener("change", () => {
                        const satisfied = Boolean(matchingDecision.querySelector('input[value="36-200"]:checked'));
                        syncRequirement(satisfied);
                        refreshGenEdProgress();
                    });
                });
            } else {
                const decision = document.createElement("details");
                decision.className = `completed-choice-checklist decision-requirement baseline-decision-requirement${completed ? " decision-complete" : ""}`;
                decision.dataset.requirementId = requirement.id;
                const detailText = (requirement.source_text || "").split("\n")
                    .find(line => line.length > 60 && line !== requirement.name)
                    || "Choose an approved option; the same selection will appear in your generated plan.";
                decision.innerHTML = `<summary><strong class="decision-summary-name">${requirement.name}</strong><span class="decision-summary-rule">Choose one approved option</span><span class="decision-status-text">${completed ? "✓ Completed" : appState.genedSelections[requirement.id] ? "✓ Selected" : "Choose in plan"}</span><small class="decision-deadline">${requirement.timeline.source_text}</small></summary><div class="decision-expanded"><p>${detailText}</p><div class="gened-plan-choice-slot" aria-live="polite"></div><label class="baseline-completed-toggle"><input type="checkbox" ${completed ? "checked" : ""}> I already completed this requirement</label></div>`;
                const deadlineYear = requirement.timeline.year || (requirement.timeline.type === "after_semester" ? 4 : 1);
                const moveToChooseNow = ["humanities", "social-sciences", "experiential-learning"].includes(requirement.id);
                (moveToChooseNow || deadlineYear <= Math.max(1, appState.student.year) ? nowList : laterList).appendChild(decision);
                decision.querySelector("input").addEventListener("change", event => {
                    syncRequirement(event.target.checked);
                    refreshRequirementDecisionProgress();
                    refreshGenEdProgress();
                });
                const category = {
                    communication: "communication",
                    humanities: "humanities",
                    "social-sciences": "social-sciences"
                }[requirement.id];
                const slot = decision.querySelector(".gened-plan-choice-slot");
                if (requirement.id === "experiential-learning") {
                    slot.innerHTML = `<label>Planned activity<select class="gened-plan-choice"><option value="">Choose later</option><option>Internship or work-based project</option><option>Undergraduate research</option><option>Community-engaged learning</option><option>Study abroad</option></select></label>`;
                } else if (category) {
                    slot.innerHTML = `<label>Course choice<input type="search" class="gened-option-search" placeholder="Search course number or title"><select class="gened-plan-choice"><option value="">Loading scheduled courses…</option></select></label>`;
                    Promise.all(["fall", "spring"].map(term => fetch(`/api/electives?term=${term}&category=${category}&primary_major=${encodeURIComponent(appState.student.primary_major)}&goal_program=${encodeURIComponent(appState.goals[0]?.program || "")}`).then(response => response.json())))
                        .then(responses => {
                            const courses = new Map(
                                responses
                                    .flatMap(response => response.courses || [])
                                    .filter(course => Number(course.units || 0) >= Number(requirement.units || 0))
                                    .map(course => [course.id, course])
                            );
                            const select = slot.querySelector(".gened-plan-choice");
                            const groupedCourses = Array.from(courses.values()).reduce((groups, course) => {
                                const label = course.display_group || "Other scheduled courses";
                                if (!groups.has(label)) groups.set(label, []);
                                groups.get(label).push(course);
                                return groups;
                            }, new Map());
                            select.innerHTML = '<option value="">Choose a scheduled course</option>'
                                + Array.from(groupedCourses.entries()).map(([label, groupCourses]) =>
                                    `<optgroup label="${label}">${groupCourses.map(course => `<option value="${course.id}">${course.id} · ${course.name}</option>`).join("")}</optgroup>`
                                ).join("");
                            select.value = appState.genedSelections[requirement.id] || "";
                            const search = slot.querySelector(".gened-option-search");
                            search.addEventListener("input", () => {
                                const query = search.value.trim().toLowerCase();
                                Array.from(select.options).slice(1).forEach(option => option.hidden = !option.textContent.toLowerCase().includes(query));
                            });
                        });
                }
                slot.querySelector(".gened-plan-choice")?.addEventListener("change", event => {
                    if (event.target.value) appState.genedSelections[requirement.id] = event.target.value;
                    else delete appState.genedSelections[requirement.id];
                    decision.classList.toggle("decision-complete", Boolean(event.target.value) || decision.querySelector('.baseline-completed-toggle input').checked);
                    decision.querySelector(".decision-status-text").textContent = event.target.value ? "✓ Selected" : decision.querySelector('.baseline-completed-toggle input').checked ? "✓ Completed" : "Choose in plan";
                    refreshRequirementDecisionProgress();
                    refreshGenEdProgress();
                    refreshDegreeRequirementTree();
                    applyGenEdSelectionsToPath();
                });
            }
            row.querySelector("input").addEventListener("change", event => {
                syncRequirement(event.target.checked);
                if (matchingDecision) {
                    const linked = matchingDecision.querySelector('input[value="36-200"]');
                    if (linked) linked.checked = event.target.checked;
                }
                refreshRequirementDecisionProgress();
                refreshGenEdProgress();
                if (!results.classList.contains("hidden")) {
                    window.clearTimeout(requirementReplanTimer);
                    requirementReplanTimer = window.setTimeout(() => document.getElementById("generateButton").click(), 350);
                }
            });
            auditList.appendChild(row);
        });
        [decisionPage.querySelector(".choose-now-group"), decisionPage.querySelector(".decide-later-group")].forEach(group => {
            group?.classList.toggle("hidden", !group.querySelector(".decision-requirement"));
        });
        refreshRequirementDecisionProgress();
    } else if (baselineSection) {
        baselineSection.classList.remove("hidden");
    }
    baselineSummary.textContent =
        `${data.baseline.college} baseline · ` +
        `${data.baseline.total_units} remaining units will be scheduled with your goal`;
}



// ------------------------------------------------------------
// STEP 2B → STEP 3
// ------------------------------------------------------------

document
    .getElementById(
        "step2bNext"
    )
    .addEventListener(
        "click",
        async () => {


            updatePlanningGoal();
            appState.plannerKey = plannerKeyForGoal(appState.goals[0]);

            const goal = appState.goals[0];
            if (goal && ["internal_transfer", "additional_major", "minor"].includes(goal.type)) {
                const response = await fetch(
                    `/api/programs/${goal.program}/${goal.type}`
                );
                if (!response.ok) {
                    console.error("Program profile could not be loaded");
                    return;
                }
                const detail = await response.json();
                let currentMajorHistory = [];
                let currentMajorChoiceGroups = [];
                const primaryResponse = await fetch(
                    `/api/primary-majors/${encodeURIComponent(appState.student.primary_major)}`
                );
                if (primaryResponse.ok) {
                    const primaryDetail = await primaryResponse.json();
                    currentMajorHistory = primaryDetail.fixed_courses;
                    currentMajorChoiceGroups = primaryDetail.requirement_groups;
                }
                if (goal.type === "internal_transfer") {
                    const goalOptionSets = detail.requirement_groups.map(group =>
                        new Set((group.options || []).flatMap(option => option.split(" + ")))
                    );
                    currentMajorChoiceGroups = currentMajorChoiceGroups.filter(group => {
                        const currentOptions = new Set(
                            (group.options || []).flatMap(option => option.split(" + "))
                        );
                        return !goalOptionSets.some(goalOptions =>
                            currentOptions.size === goalOptions.size
                            && Array.from(currentOptions).every(option => goalOptions.has(option))
                        );
                    });
                }
                const historyById = new Map();
                [...currentMajorHistory, ...detail.fixed_courses].forEach(course => {
                    historyById.set(course.id, {...historyById.get(course.id), ...course});
                });
                const historyCourses = [...historyById.values()];
                step3CourseData[appState.plannerKey] = {
                    eyebrow: `${(goal.college || "CMU").toUpperCase()} · ${detail.program_name.toUpperCase()} · ${goal.type === "minor" ? "MINOR" : goal.type === "internal_transfer" ? "B.S. TRANSFER" : "ADDITIONAL MAJOR"}`,
                    title: "Which current-major and goal courses have you completed?",
                    description: `Select completed courses from your current major and this goal. Anything left unchecked may be placed in your future plan.`,
                    courses: historyCourses,
                    choiceGroups: [
                        ...currentMajorChoiceGroups.map(group => ({...group, history_scope: "current_major"})),
                        ...detail.requirement_groups.map(group => ({...group, history_scope: "goal"}))
                    ],
                    plannerNote: `Catalog ${detail.catalog_year}: ${detail.requirement_groups.map(group => `${group.name} (${group.options.join(" / ")})`).join("; ") || "all listed requirements are fixed courses"}.`,
                    plannerReady: true
                };
                renderCourseSelection(appState.plannerKey);
                showScreen(step3);
                loadBaseline();
                return;
            }

            if (step3CourseData[appState.plannerKey]) {
                renderCourseSelection(appState.plannerKey);
                showScreen(step3);
                loadBaseline();
                return;
            }



            // ------------------------------------------------
            // OTHER PROGRAMS
            //
            // UI works, but requirements are not connected yet.
            // ------------------------------------------------

            console.log(
                "Selected future program:",
                {
                    goalType:
                        appState.selection.goalType,

                    school:
                        appState.selection.school,

                    program:
                        appState.selection.program
                }
            );


            // For now we do NOT accidentally show
            // the Computer Science transfer courses.
            //
            // We'll create program-specific pages next.

        }
    );

// #endregion


// #region 8B. STEP 3 PREPARATION
// ============================================================
// These functions decide WHAT Step 3 represents.
//
// Step 3 is no longer "the CS transfer page".
//
// It is a reusable academic-history screen.
// ============================================================



// ------------------------------------------------------------
// EXPLORE CURRENT MAJOR
// ------------------------------------------------------------

async function prepareCurrentMajorStep() {

    const currentMajor =
        document.getElementById(
            "major"
        ).value;


    updatePlanningGoal();
    appState.plannerKey = `${currentMajor}-major`;
    const response = await fetch(`/api/primary-majors/${encodeURIComponent(currentMajor)}`);
    if (!response.ok) {
        const selectedName = document.getElementById("major").selectedOptions[0]?.textContent || currentMajor;
        step3CourseData[appState.plannerKey] = {
            eyebrow: "CURRENT MAJOR · DATA REVIEW",
            title: `Explore ${selectedName}`,
            description: "This major is in the CMU directory, but its requirement audit has not passed verification yet.",
            courses: [],
            choiceGroups: [],
            plannerNote: "We will not invent a course path while the curriculum is unverified.",
            plannerReady: false
        };
        renderCourseSelection(appState.plannerKey);
        showScreen(step3);
        return false;
    }
    const detail = await response.json();
    const selectedName = document.getElementById("major").selectedOptions[0]?.textContent || currentMajor;
    step3CourseData[appState.plannerKey] = {
        eyebrow: `CURRENT MAJOR · ${detail.catalog_year}`,
        title: `What have you completed for ${selectedName}?`,
        description: "Select completed fixed courses and requirement choices. Remaining verified requirements will be scheduled into your path.",
        courses: detail.fixed_courses,
        choiceGroups: detail.requirement_groups.map(group => ({...group, history_scope: "current_major"})),
        plannerNote: detail.notes.join(" "),
        plannerReady: true
    };
    renderCourseSelection(appState.plannerKey);
    showScreen(step3);
    await loadBaseline();
    return true;

}



// ------------------------------------------------------------
// RENDER STEP 3
// ------------------------------------------------------------

function renderCourseSelection(
    pathKey
) {

    document.querySelector("#resultsRequirementPanel .requirement-decision-page")?.remove();
    const data =
        step3CourseData[pathKey];


    if (!data) {

        console.error(
            "No Step 3 data found for:",
            pathKey
        );

        return;

    }


    const eyebrow =
        document.getElementById(
            "step3Eyebrow"
        );


    const title =
        document.getElementById(
            "step3Title"
        );


    const description =
        document.getElementById(
            "step3Description"
        );


    const courseList =
        document.getElementById(
            "courseList"
        );


    const generateButton =
        document.getElementById(
            "generateButton"
        );


    const plannerNote =
        document.getElementById(
            "plannerNote"
        );

    // --------------------------------------------------------
    // Update page copy.
    // --------------------------------------------------------

    eyebrow.textContent =
        data.eyebrow;


    title.textContent =
        data.title;


    description.textContent =
        data.description;


    // --------------------------------------------------------
    // Clear old course list.
    // --------------------------------------------------------

    courseList.innerHTML =
        "";

    if (pathKey === "cs-transfer") {
        const noneLabel = document.createElement("label");
        noneLabel.className = "course-option no-courses-option";
        noneLabel.innerHTML = `
            <input type="checkbox" id="noCompletedCourses">
            <span>
                <strong>No college courses completed yet</strong>
                Best for incoming freshmen.
            </span>
        `;
        courseList.appendChild(noneLabel);
        noneLabel.querySelector("input").addEventListener("change", event => {
            courseList
                .querySelectorAll('input[type="checkbox"]:not(#noCompletedCourses)')
                .forEach(input => {
                    input.checked = false;
                    input.disabled = event.target.checked;
                });
        });
    }

    const choiceGroups = data.choiceGroups || [];
    const renderedHistoryIds = new Set();
    let auditFixedContainer = courseList;
    if (choiceGroups.length) {
        const courseNames = new Map(data.courses.map(course => [course.id, course.name]));
        const normalizedGroups = new Map();
        const normalizedGroup = group => {
            const label = `${group.id || ""} ${group.name || ""}`.toLowerCase();
            if (/multivariable/.test(label)) return {key: "multivariable-calculus", name: "Multivariable calculus"};
            if (/pre.?calculus|\bcalculus\b/.test(label)) {
                return {key: "calculus-foundation", name: "Calculus & precalculus foundation"};
            }
            if (/linear algebra/.test(label)) return {key: "linear-algebra", name: "Linear algebra"};
            return {key: group.id || group.name, name: group.name};
        };

        choiceGroups.forEach(group => {
            const normalized = normalizedGroup(group);
            const concreteIds = (group.options || []).flatMap(option => option.split(" + "))
                .map(id => id.trim()).filter(id => /^\d{2}-\d{3}$/.test(id));
            const inferredMinimumYear = concreteIds.length
                ? Math.min(...concreteIds.map(id => Number(id.split("-")[1][0]) >= 3 ? 3 : Number(id.split("-")[1][0]) >= 2 ? 2 : 1))
                : 1;
            const groupMinimumYear = group.minimum_year || inferredMinimumYear;
            const entry = normalizedGroups.get(normalized.key) || {
                key: normalized.key,
                name: normalized.name,
                minimumYear: groupMinimumYear,
                choose: group.choose || 1,
                options: new Map(),
                scopes: new Set()
            };
            entry.minimumYear = Math.min(entry.minimumYear, groupMinimumYear);
            entry.choose = Math.max(entry.choose, group.choose || 1);
            entry.scopes.add(group.history_scope === "current_major" ? "Current major" : "Goal program");
            (group.options || []).forEach(option => {
                const ids = option.split(" + ").map(id => id.trim());
                if (!ids.every(id => /^\d{2}-\d{3}$/.test(id))) return;
                entry.options.set(option, {
                    value: option,
                    ids,
                    name: ids.map(id => courseNames.get(id)).filter(Boolean).join(" + ") || entry.name
                });
            });
            normalizedGroups.set(normalized.key, entry);
        });

        title.textContent = "Finish your course choices";
        description.textContent = "Only decisions that still affect your plan are shown here. Your progress will carry into the generated plan.";
        const decisionSection = document.createElement("section");
        decisionSection.className = "requirement-decision-page";
        decisionSection.innerHTML = `
            <div class="decision-progress" aria-live="polite">
                <div><strong class="decision-progress-label"></strong><span class="decision-progress-percent"></span></div>
                <div class="decision-progress-track" role="progressbar" aria-valuemin="0"><span></span></div>
            </div>
            <div class="requirement-tabs" role="tablist" aria-label="Requirement views">
                <button type="button" role="tab" aria-selected="true" aria-controls="needsChoicePanel" id="needsChoiceTab">Needs your choice <span class="needs-choice-count"></span></button>
                <button type="button" role="tab" aria-selected="false" aria-controls="allRequirementsPanel" id="allRequirementsTab">All requirements</button>
            </div>
            <div id="needsChoicePanel" role="tabpanel" aria-labelledby="needsChoiceTab">
                <section class="urgency-group choose-now-group"><div class="urgency-heading"><h3>Choose now</h3><p>Choices needed for the next stage of your generated path.</p></div><div class="decision-list"></div></section>
                <details class="urgency-group decide-later-group"><summary class="urgency-heading"><span><strong>Decide later</strong><small>These remain required, but their verified timing allows you to decide later.</small></span></summary><div class="decision-list"></div></details>
            </div>
            <div id="allRequirementsPanel" class="hidden" role="tabpanel" aria-labelledby="allRequirementsTab">
                <div class="requirement-audit-list"></div>
            </div>`;
        courseList.appendChild(decisionSection);
        const nowList = decisionSection.querySelector(".choose-now-group .decision-list");
        const laterList = decisionSection.querySelector(".decide-later-group .decision-list");
        const auditList = decisionSection.querySelector(".requirement-audit-list");
        auditFixedContainer = auditList;
        const yearNames = ["", "freshman", "sophomore", "junior", "senior"];
        const allGroups = Array.from(normalizedGroups.values());
        // A requirement with no real alternative (or where every option must
        // be completed) is an audit item, not a user decision.
        const groups = allGroups.filter(group => group.choose > 0 && group.options.size > group.choose);
        const panelsByGroup = new Map();

        const ruleText = group => {
            if (group.choose >= group.options.size) return "Complete all";
            if (group.choose === 1) return "Choose any one";
            return `Choose ${group.choose} of ${group.options.size}`;
        };
        const deadlineText = group => group.minimumYear > 1
            ? `Needed starting ${yearNames[group.minimumYear] || `Year ${group.minimumYear}`}`
            : "Needed for your early plan";
        groups.forEach(group => {
            const groupPanel = document.createElement("details");
            groupPanel.className = "completed-choice-checklist decision-requirement";
            groupPanel.dataset.minimumYear = group.minimumYear;
            groupPanel.dataset.choose = group.choose;
            groupPanel.innerHTML = `
                <summary>
                    <strong class="decision-summary-name">${group.name}</strong>
                    <span class="decision-summary-rule">${ruleText(group)}</span>
                    <span class="decision-status-text">${group.options.size} options</span>
                    <small class="decision-deadline">${deadlineText(group)}</small>
                </summary>
                <div class="decision-expanded">
                    <p>${ruleText(group)} from the verified ${Array.from(group.scopes).join(" and ").toLowerCase()} requirement options.</p>
                    ${group.options.size >= 10 ? `<div class="requirement-option-tools"><label>Search within ${group.name}<input type="search" class="requirement-option-search" placeholder="Search course number or name"></label><label>Show<select class="requirement-option-filter"><option value="all">All options</option><option value="selected">Selected only</option><option value="unselected">Unselected only</option></select></label></div>` : ""}
                    <div class="completed-choice-options"></div>
                </div>`;
            const optionList = groupPanel.querySelector(".completed-choice-options");
            group.options.forEach(option => {
                option.ids.forEach(id => renderedHistoryIds.add(id));
                const label = document.createElement("label");
                label.className = "course-option requirement-choice-option";
                label.dataset.searchText = `${option.value} ${option.name}`.toLowerCase();
                label.innerHTML = `
                    <input type="checkbox" value="${option.value}" ${option.ids.every(id => appState.student.completed_courses.includes(id)) ? "checked" : ""}>
                    <span>
                        <strong>${option.value}</strong>
                        ${option.name}
                    </span>`;
                optionList.appendChild(label);
            });

            // Keep required math courses visible beside the Mathematics choice
            // without treating them as substitutes for its choose-one rule.
            if (group.key === "mathematics") {
                const requiredMathCourses = ["21-122", "21-241"]
                    .map(id => data.courses.find(course => course.id === id))
                    .filter(Boolean)
                    .filter(course => !group.options.has(course.id));
                if (requiredMathCourses.length) {
                    const requiredSection = document.createElement("section");
                    requiredSection.className = "required-math-courses";
                    requiredSection.innerHTML = `
                        <div class="required-math-courses-heading">
                            <strong>Required math courses</strong>
                            <small>Mark these if already completed. They do not replace the choose-one requirement above.</small>
                        </div>
                        <div class="completed-choice-options required-math-course-options"></div>`;
                    const requiredList = requiredSection.querySelector(".required-math-course-options");
                    requiredMathCourses.forEach(course => {
                        renderedHistoryIds.add(course.id);
                        const label = document.createElement("label");
                        label.className = "course-option required-math-course-option";
                        label.innerHTML = `
                            <input type="checkbox" value="${course.id}" ${appState.student.completed_courses.includes(course.id) ? "checked" : ""}>
                            <span>
                                <strong>${course.id}</strong>
                                ${course.name}
                                <small class="required-math-course-status">${appState.student.completed_courses.includes(course.id) ? "Completed" : "Required · Auto-planned"}</small>
                            </span>`;
                        requiredList.appendChild(label);
                    });
                    groupPanel.querySelector(".decision-expanded").appendChild(requiredSection);
                }
            }
            const isNow = group.minimumYear <= Math.min(appState.student.year, appState.constraints.target_completion_year || 4);
            (isNow ? nowList : laterList).appendChild(groupPanel);
            panelsByGroup.set(group, groupPanel);

            const auditRow = document.createElement("div");
            auditRow.className = "requirement-audit-row";
            auditRow.dataset.groupName = group.name;
            auditRow.innerHTML = `<span><strong>${group.name}</strong><small>${ruleText(group)} · ${deadlineText(group)}</small></span><span class="audit-row-status">Remaining</span>`;
            auditList.appendChild(auditRow);

            const applyFilter = () => {
                const search = groupPanel.querySelector(".requirement-option-search")?.value.trim().toLowerCase() || "";
                const filter = groupPanel.querySelector(".requirement-option-filter")?.value || "all";
                optionList.querySelectorAll(".course-option").forEach(option => {
                    const checked = option.querySelector("input").checked;
                    option.hidden = !option.dataset.searchText.includes(search)
                        || (filter === "selected" && !checked)
                        || (filter === "unselected" && checked);
                });
            };
            groupPanel.querySelector(".requirement-option-search")?.addEventListener("input", applyFilter);
            groupPanel.querySelector(".requirement-option-filter")?.addEventListener("change", applyFilter);
        });
        allGroups.filter(group => !groups.includes(group)).forEach(group => {
            const row = document.createElement("div");
            row.className = "requirement-audit-row audit-auto-resolved";
            row.innerHTML = `<span><strong>${group.name}</strong><small>${group.options.size ? ruleText(group) : "Planner-managed requirement"} · ${deadlineText(group)}</small></span><span class="audit-row-status">Auto-resolved</span>`;
            auditList.appendChild(row);
        });
        [decisionSection.querySelector(".choose-now-group"), decisionSection.querySelector(".decide-later-group")].forEach(group => {
            if (!group.querySelector(".decision-requirement")) group.classList.add("hidden");
        });

        const updateDecisionProgress = () => {
            let complete = 0;
            let total = 0;
            groups.forEach(group => {
                const panel = panelsByGroup.get(group);
                // Read this requirement group's own controls. The earlier global
                // course-id set could drift out of sync when GenEd asynchronously
                // linked 36-200 to Beginning Data Analysis.
                const selected = panel
                    ? panel.querySelectorAll('.requirement-choice-option input[type="checkbox"]:checked').length
                    : 0;
                const done = selected >= group.choose;
                total += group.choose;
                complete += Math.min(selected, group.choose);
                panel?.classList.toggle("decision-complete", done);
                if (panel) panel.querySelector(".decision-status-text").textContent = done ? "✓ Selected" : `${group.options.size} options`;
                const auditRow = Array.from(auditList.querySelectorAll(".requirement-audit-row"))
                    .find(item => item.dataset.groupName === group.name);
                if (auditRow) {
                    auditRow.classList.toggle("audit-complete", done);
                    auditRow.querySelector(".audit-row-status").textContent = done ? "Completed" : "Remaining";
                }
            });
            decisionSection.querySelectorAll(".baseline-decision-requirement").forEach(panel => {
                const requirementId = panel.dataset.requirementId;
                const done = panel.querySelector('.baseline-completed-toggle input[type="checkbox"]')?.checked
                    || Boolean(appState.genedSelections[requirementId]);
                total += 1;
                complete += done ? 1 : 0;
                panel.classList.toggle("decision-complete", done);
                panel.querySelector(".decision-status-text").textContent = appState.genedSelections[requirementId]
                    ? "✓ Selected" : done ? "✓ Completed" : "Choose in plan";
            });
            const remaining = Math.max(0, total - complete);
            const percent = total ? Math.round(complete / total * 100) : 100;
            decisionSection.querySelector(".decision-progress-label").textContent = `${complete} of ${total} decisions complete`;
            decisionSection.querySelector(".decision-progress-percent").textContent = `${percent}%`;
            const progress = decisionSection.querySelector(".decision-progress-track");
            progress.setAttribute("aria-valuemax", total);
            progress.setAttribute("aria-valuenow", complete);
            progress.querySelector("span").style.width = `${percent}%`;
            decisionSection.querySelector(".needs-choice-count").textContent = remaining;
            appState.requirementDecisionProgress = {complete, total, percent};
            if (!results.classList.contains("hidden")) renderResultsRequirementProgress();
        };
        refreshRequirementDecisionProgress = updateDecisionProgress;
        decisionSection.addEventListener("change", event => {
            if (event.target.matches('.requirement-choice-option input[type="checkbox"]')) {
                updateDecisionProgress();
                if (!results.classList.contains("hidden")) {
                    window.clearTimeout(requirementReplanTimer);
                    requirementReplanTimer = window.setTimeout(() => {
                        document.getElementById("generateButton").click();
                    }, 350);
                }
            }
            if (event.target.matches('.required-math-course-option input[type="checkbox"]')) {
                const status = event.target.closest(".required-math-course-option")
                    .querySelector(".required-math-course-status");
                status.textContent = event.target.checked ? "Completed" : "Required · Auto-planned";
                if (!results.classList.contains("hidden")) {
                    window.clearTimeout(requirementReplanTimer);
                    requirementReplanTimer = window.setTimeout(() => {
                        document.getElementById("generateButton").click();
                    }, 350);
                }
            }
        });
        const tabs = Array.from(decisionSection.querySelectorAll('[role="tab"]'));
        tabs.forEach((tab, index) => {
            tab.addEventListener("click", () => {
                tabs.forEach(item => item.setAttribute("aria-selected", String(item === tab)));
                decisionSection.querySelector("#needsChoicePanel").classList.toggle("hidden", tab.id !== "needsChoiceTab");
                decisionSection.querySelector("#allRequirementsPanel").classList.toggle("hidden", tab.id !== "allRequirementsTab");
            });
            tab.addEventListener("keydown", event => {
                if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
                event.preventDefault();
                tabs[(index + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length].click();
                tabs[(index + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length].focus();
            });
        });
        updateDecisionProgress();
    }


    const foundationOrder = ["21-120", "21-122", "15-112", "36-200"];
    const earlyCoreOrder = ["21-127", "15-122", "36-202", "36-235", "21-241"];
    const rank = course => {
        if (foundationOrder.includes(course.id)) return [0, foundationOrder.indexOf(course.id)];
        if (earlyCoreOrder.includes(course.id)) return [1, earlyCoreOrder.indexOf(course.id)];
        if (course.is_current_major) return [2, 0];
        if (course.program_tier === "transfer_goal") return [3, 0];
        if (course.program_tier === "minor_foundation") return [4, 0];
        if (course.program_tier === "additional_major") return [5, 0];
        return [2, 0];
    };
    const groupNames = [
        "First-year foundations",
        "Early major core",
        "Later current-major coursework",
        "Target B.S. requirements",
        "Minor foundation",
        "Additional-major extension"
    ];
    const uniqueCourses = Array.from(data.courses.reduce((courses, course) => {
        if (!courses.has(course.id)) courses.set(course.id, {...course});
        else {
            const existing = courses.get(course.id);
            existing.is_current_major ||= course.is_current_major;
            existing.program_tier ||= course.program_tier;
        }
        return courses;
    }, new Map()).values()).filter(course => !renderedHistoryIds.has(course.id));
    const groupedCourses = uniqueCourses
        .sort((a, b) => rank(a)[0] - rank(b)[0] || rank(a)[1] - rank(b)[1])
        .reduce((groups, course) => {
            const group = rank(course)[0];
            (groups[group] ||= []).push(course);
            return groups;
        }, {});

    Object.entries(groupedCourses).forEach(([groupIndex, groupCourses]) => {
        const section = document.createElement("section");
        section.className = "history-course-group";
        const collapseLater = Number(groupIndex) >= 2 && appState.student.year === 1;
        const list = document.createElement(collapseLater ? "details" : "div");
        if (collapseLater) {
            list.innerHTML = `<summary>${groupNames[groupIndex]} (${groupCourses.length})</summary>`;
        } else {
            section.innerHTML = `<h3>${groupNames[groupIndex]}</h3>`;
        }

        for (const course of groupCourses) {

        const label =
            document.createElement(
                "label"
            );


        label.className =
            `course-option${choiceGroups.length ? " audit-course-option" : ""}`;


        label.innerHTML = `

            <input
                type="checkbox"
                value="${course.id}"
                ${appState.student.completed_courses.includes(course.id) ? "checked" : ""}
            >

            <span>

                <strong>
                    ${course.id}
                </strong>

                ${course.name}

                ${course.program_tier ? `<small class="course-tier-badge ${course.program_tier === "minor_foundation" ? "minor-foundation" : ""}">${course.is_current_major ? "Also counts toward " : ""}${course.program_tier === "transfer_goal" ? "Target B.S. requirement" : course.program_tier === "minor_foundation" ? "Minor foundation" : "Additional-major extension"}</small>` : ""}

                ${choiceGroups.length ? `<small class="audit-course-status">${appState.student.completed_courses.includes(course.id) ? "Completed" : "Auto-planned"}</small>` : ""}

            </span>

        `;


            list.appendChild(label);
        }
        section.appendChild(list);
        auditFixedContainer.appendChild(section);
    });
    courseList.querySelectorAll(".audit-course-option input").forEach(input => {
        input.addEventListener("change", event => {
            const status = event.target.closest(".audit-course-option").querySelector(".audit-course-status");
            if (status) status.textContent = event.target.checked ? "Completed" : "Auto-planned";
        });
    });

    // Unfinished choice groups still become editable blocks on Results. The
    // compact selectors above exist only to record choices already completed.


    // --------------------------------------------------------
    // No requirement data yet.
    // --------------------------------------------------------

    if (
        data.courses.length === 0
    ) {

        courseList.innerHTML = `

            <div class="empty-course-state">

                <strong>
                    ${data.title}
                </strong>

                <p>
                    ${data.description}
                </p>

            </div>

        `;

    }


    // --------------------------------------------------------
    // Planner availability.
    // --------------------------------------------------------

    if (
        data.plannerReady
    ) {

        generateButton.disabled =
            false;


        generateButton.textContent =
            "Continue to my plan →";


        plannerNote
            .classList
            .add("hidden");

    }


    else {

        generateButton.disabled =
            true;


        generateButton.textContent =
            "Planner coming next";


        plannerNote.textContent =
            data.plannerNote
            ?? "This major is connected to the new interface, but its requirement engine has not been populated yet.";


        plannerNote
            .classList
            .remove("hidden");

    }

}

// #endregion


// #region 9. PATH RENDERING
// ============================================================
// Converts backend semester data into visual semester cards.
//
// Expected backend structure:
//
// {
//     semester_number: 1,
//     semester: "spring",
//     courses: [
//         "15-150",
//         "15-213"
//     ],
//     units: 22,
//
//     workload: {
//         hours_per_week: 25,
//         average_workload: 4.3,
//         average_difficulty: 4.2,
//         average_stress: 4.2
//     }
// }
//
// ============================================================

function renderPath(
    pathData,
    container
) {
    container.innerHTML = "";
    const validationMessage = document.createElement("div");
    validationMessage.className = "planner-validation-message";
    validationMessage.hidden = true;
    validationMessage.setAttribute("role", "status");
    container.appendChild(validationMessage);
    const kindLabels = {
        goal: "Goal program",
        current_major: "Current major",
        shared: "Current + goal",
        baseline: "GenEd requirement",
        program_choice: "Program choice",
        current_major_choice: "Current major requirement"
    };

    const intensityClass = intensity => intensity ? `intensity-tier-${intensity.tier}` : "";
    const intensityBadge = intensity => intensity
        ? `<span class="course-intensity-badge">Workload rating · ${intensity.label}</span>`
        : "";
    const intensityData = intensity => intensity
        ? `data-intensity-tier="${intensity.tier}" data-hours="${intensity.hours_per_week}" data-workload="${intensity.workload}" data-difficulty="${intensity.difficulty}"`
        : "";
    const baselineCategoryNames = {
        "Communication": "communication",
        "Humanities": "humanities",
        "Social Sciences": "social-sciences",
        "Data Analysis": "data-analysis"
    };
    const baselineRequirementForCategory = category =>
        (appState.baselineRequirements || []).find(requirement =>
            baselineCategoryNames[requirement.name] === category
        );

    const fixedBlock = (block, number) => {
        const intensity = appState.latestCourseCatalog[block.id]?.intensity;
        const minimumYear = appState.latestCourseCatalog[block.id]?.minimum_year || block.minimum_year || 1;
        return `
        <div class="planner-course-block fixed-block has-selected-course ${block.program_tier === "additional_major" ? "additional-major-block" : block.program_tier === "minor_foundation" ? "minor-foundation-block" : ""} ${block.estimated ? "primary-baseline-block" : ""} ${intensityClass(intensity)}" data-units="${block.units}" data-course-id="${block.id}" data-minimum-year="${minimumYear}" ${intensityData(intensity)} draggable="true">
            <span class="block-number">${number}</span>
            <span class="block-main">
                <small>${block.estimated
                    ? "Reserved for remaining primary-major requirements"
                    : block.program_tier === "transfer_preparation"
                        ? "Preparation · unlocks transfer requirements"
                        : block.program_tier === "additional_major"
                            ? "Additional Major extension"
                            : (kindLabels[block.kind] || "Minor foundation")}</small>
                ${block.estimated ? "" : `<strong>${block.id}</strong>`}
                <span>${block.name}</span>
                ${intensityBadge(intensity)}
            </span>
            <strong class="block-units">${block.units}u</strong>
        </div>`;
    };

    const choiceBlock = (block, number) => {
        const options = block.options || [];
        const isBaseline = block.kind === "baseline";
        const baselineCategory = isBaseline ? baselineCategoryNames[block.name] || "" : "";
        const defaultIntensity = appState.latestCourseCatalog[block.default_option]?.intensity;
        const minimumYear = appState.latestCourseCatalog[block.default_option]?.minimum_year || block.minimum_year || 1;
        return `
            <div class="planner-course-block choice-block ${block.default_option ? "has-selected-course choice-resolved" : ""} ${block.program_tier === "additional_major" ? "additional-major-block" : block.program_tier === "minor_foundation" ? "minor-foundation-block" : ""} ${intensityClass(defaultIntensity)}" data-units="${block.units}" data-course-id="${block.default_option || ""}" data-minimum-year="${minimumYear}" ${intensityData(defaultIntensity)} data-baseline-category="${baselineCategory}" draggable="true">
                <span class="block-number">${number}</span>
                <span class="block-main">
                    <span class="choice-course-summary">
                        <span class="choice-summary-heading">
                            <small class="choice-summary-kind">${kindLabels[block.kind] || block.name}</small>
                            <button type="button" class="change-course-button" aria-label="Change ${block.default_option || block.name}">Change</button>
                        </span>
                        <strong class="choice-summary-id">${block.default_option || ""}</strong>
                        <span class="choice-summary-name">${appState.latestCourseCatalog[block.default_option]?.name || block.name}</span>
                    </span>
                    <span class="choice-edit-controls">
                        <select class="block-category" aria-label="Block ${number} category">
                            <option selected>${block.name}</option>
                        </select>
                        <select class="block-course" aria-label="Block ${number} course">
                            <option value="" data-units="${block.units}" ${block.default_option ? "" : "selected"}>${isBaseline
                                ? "Choose an approved course in SIO"
                                : "Choose a course"}</option>
                            ${options.map(option => {
                                const course = appState.latestCourseCatalog[option];
                                const intensity = course?.intensity;
                                return `<option value="${option}" data-units="${course?.units || block.units}" data-minimum-year="${course?.minimum_year || block.minimum_year || 1}" data-intensity-tier="${intensity?.tier || ""}" data-hours="${intensity?.hours_per_week || ""}" data-workload="${intensity?.workload || ""}" data-difficulty="${intensity?.difficulty || ""}" data-intensity-label="${intensity?.label || ""}" ${option === block.default_option ? "selected" : ""}>${option}${course?.name ? ` · ${course.name}` : ""}${intensity ? ` · ${intensity.label}` : ""}</option>`;
                            }).join("")}
                        </select>
                        <small class="course-description" aria-live="polite"></small>
                    </span>
                    <span class="course-intensity-slot">${intensityBadge(defaultIntensity)}</span>
                </span>
                <strong class="block-units">${block.units}u</strong>
            </div>`;
    };

    const emptyBlock = number => `
        <div class="planner-course-block choice-block empty-block collapsed" data-units="0" draggable="true">
            <span class="block-number">${number}</span>
            <span class="block-main">
                <span class="choice-course-summary">
                    <span class="choice-summary-heading">
                        <small class="choice-summary-kind">Course choice</small>
                        <button type="button" class="change-course-button" aria-label="Change selected course">Change</button>
                    </span>
                    <strong class="choice-summary-id"></strong>
                    <span class="choice-summary-name">Course choice</span>
                </span>
                <button type="button" class="add-elective-button">+ Add elective</button>
                <div class="elective-controls choice-edit-controls" hidden>
                <select class="block-category" aria-label="Block ${number} category">
                    <option value="">Choose a category</option>
                    ${appState.student.primary_major === "stats-ml" ? '<option value="stats-ml-math">Stats/ML math requirement</option>' : ""}
                    <option value="math">Mathematics</option>
                    <option value="humanities">Humanities</option>
                    <option value="social-sciences">Social Sciences</option>
                    <option value="communication">Communication</option>
                    <option value="general-education">General education</option>
                    <option value="data-analysis">Data Analysis</option>
                    <option value="current-major">Current major course</option>
                    <option value="goal-program">Goal program course</option>
                    <option value="free-elective">Free elective</option>
                </select>
                <select class="block-course" aria-label="Block ${number} course" disabled>
                    <option value="" data-units="0">Select a category first</option>
                </select>
                <small class="course-description" aria-live="polite"></small>
                </div>
            </span>
            <strong class="block-units">0u</strong>
        </div>`;

    for (const semester of pathData.path) {
        const card = document.createElement("div");
        card.className = "semester-card semester-builder";
        card.dataset.academicYear = semester.academic_year;
        card.dataset.semesterTerm = semester.semester.toLowerCase();
        const blocks = (semester.course_blocks || []).slice(0, 6);
        const blocksHtml = blocks.map((block, index) =>
            block.locked ? fixedBlock(block, index + 1) : choiceBlock(block, index + 1)
        );
        // Keep five visible semester slots. Unused positions stay compact as
        // "+ Add elective" cards instead of looking like missing requirements.
        while (blocksHtml.length < 5) {
            blocksHtml.push(emptyBlock(blocksHtml.length + 1));
        }
        const milestonesHtml = (semester.milestones || []).map(milestone => `
            <div class="semester-milestone transfer-application-milestone" role="note">
                <span class="milestone-icon">→</span>
                <span><strong>${milestone.name}</strong><small>${milestone.description}</small></span>
            </div>`).join("");

        card.innerHTML = `
            <div class="semester-name">${semester.academic_year_name || "Year"} ${semester.semester}</div>
            <div class="five-course-blocks">${blocksHtml.join("")}</div>
            ${milestonesHtml}
            <div class="units semester-total">${semester.total_units ?? semester.units} total units</div>
            <div class="free-choice semester-remaining"></div>
            <div class="semester-metrics"></div>`;

        const updateTotal = () => {
            const total = Array.from(card.querySelectorAll(".planner-course-block"))
                .reduce((sum, block) => sum + Number(block.dataset.units || 0), 0);
            card.querySelector(".semester-total").textContent = `${total} total units`;
            const limit = semester.unit_limit;
            const remaining = card.querySelector(".semester-remaining");
            remaining.classList.toggle("over-unit-limit", limit !== null && total > limit);
            remaining.textContent = limit === null
                ? "No planner hard limit; confirm overload with your advisor."
                : total > limit
                    ? `${total - limit} units over this semester's limit`
                    : `${limit - total} units still available`;

            const blocks = Array.from(card.querySelectorAll(".planner-course-block"));
            const loads = blocks.map(block => {
                const units = Number(block.dataset.units || 0);
                const metrics = appState.latestCourseCatalog[block.dataset.courseId]?.metrics;
                const intensity = appState.latestCourseCatalog[block.dataset.courseId]?.intensity;
                return {
                    hours: Number(block.dataset.hours) || intensity?.hours_per_week || metrics?.hours_per_week || units / 3,
                    workload: Number(block.dataset.workload) || intensity?.workload || metrics?.workload,
                    difficulty: Number(block.dataset.difficulty) || intensity?.difficulty || metrics?.difficulty,
                    stress: metrics?.stress,
                    high: Number(block.dataset.intensityTier) >= 5 || metrics?.intensity === "high_intensity",
                    tier: Number(block.dataset.intensityTier) || intensity?.tier || 0,
                    label: block.querySelector(".course-intensity-badge")?.textContent.replace("Workload rating · ", "") || intensity?.label || "",
                    courseId: block.dataset.courseId
                };
            }).filter(load => load.hours > 0);
            const rated = loads.filter(load => Number.isFinite(load.workload));
            const hours = Math.round(loads.reduce((sum, load) => sum + load.hours, 0));
            const highCourses = loads.filter(load => load.high).map(load => load.courseId);
            const heaviest = loads.filter(load => load.courseId).sort((a, b) => b.tier - a.tier).slice(0, 3);
            const level = highCourses.length >= 2 || hours >= 35
                ? "high"
                : highCourses.length === 1 || hours >= 22
                    ? "medium"
                    : "easy";
            const average = key => rated.length
                ? (rated.reduce((sum, load) => sum + load[key], 0) / rated.length).toFixed(1)
                : "—";
            const term = card.querySelector(".semester-name").textContent.toLowerCase().endsWith("fall")
                ? "fall" : "spring";
            const wrongTerm = blocks
                .map(block => block.dataset.courseId)
                .filter(Boolean)
                .filter(courseId => {
                    const offered = appState.latestCourseCatalog[courseId]?.offered || [];
                    return offered.length && !offered.includes(term);
                });
            const primaryEstimate = blocks
                .filter(block => block.classList.contains("primary-baseline-block"))
                .reduce((sum, block) => sum + Number(block.dataset.units || 0), 0);
            card.querySelector(".semester-metrics").innerHTML = `
                <div class="workload-level workload-${level}">${level[0].toUpperCase() + level.slice(1)} workload</div>
                ${primaryEstimate ? `<div class="baseline-workload-note">Includes ${primaryEstimate} estimated primary-major units.</div>` : ""}
                ${highCourses.length >= 2 ? `<div class="workload-warning">High-intensity combination: ${highCourses.join(", ")}</div>` : ""}
                ${wrongTerm.length ? `<div class="term-warning">Not listed for ${term}: ${wrongTerm.join(", ")}</div>` : ""}
                ${heaviest.length ? `<div class="semester-course-weight"><strong>Course load:</strong> ${heaviest.map(load => `${load.courseId} ${load.label}`).join(" · ")}</div>` : ""}
                <div>~${hours} hrs/week</div>
                <div>Workload ${average("workload")} / 5</div>
                <div>Difficulty ${average("difficulty")} / 5</div>
                <div>Stress ${average("stress")} / 5</div>`;
        };
        card.updatePlannerTotal = updateTotal;

        card.querySelectorAll(".add-elective-button").forEach(button => {
            button.addEventListener("click", event => {
                const block = event.target.closest(".empty-block");
                block.classList.remove("collapsed");
                event.target.hidden = true;
                block.querySelector(".elective-controls").hidden = false;
                block.querySelector(".block-category").focus();
            });
        });
        const semesterTerm = semester.semester.toLowerCase();
        const fetchElectives = async (category, term = semesterTerm) => {
            const query = new URLSearchParams({
                term,
                category,
                primary_major: appState.student.primary_major || "",
                goal_program: appState.goals[0]?.program || ""
            });
            const response = await fetch(`/api/electives?${query}`);
            if (!response.ok) throw new Error("Elective catalog unavailable");
            return response.json();
        };
        const setCourseOptions = (courseSelect, electiveData, minimumUnits = 0) => {
            const alreadyScheduled = new Set(
                Array.from(container.querySelectorAll("[data-course-id]"))
                    .map(block => block.dataset.courseId)
                    .filter(Boolean)
            );
            const goalPrefixes = {
                "artificial-intelligence": ["02", "05", "07", "10", "11", "15", "16", "36", "85"],
                "computer-science": ["10", "11", "15", "17", "21"],
                "robotics": ["10", "15", "16", "18", "24"]
            }[appState.goals[0]?.program] || [];
            const currentMajorPrefixes = {
                "stats-ml": ["10", "15", "21", "36"],
                "mechanical-engineering": ["21", "24", "33", "36"],
                "electrical-and-computer-engineering": ["15", "18", "21", "33", "36"]
            }[appState.student.primary_major] || [];
            const relatedPrefixes = new Set([...goalPrefixes, ...currentMajorPrefixes]);
            const poorRecommendation = /independent study|practicum|reading and research/i;
            const hasAdvancedMath = [...alreadyScheduled, ...appState.student.completed_courses]
                .some(id => /^21-(1[2-9]\d|[2-5]\d\d)$/.test(id));
            const available = electiveData.courses.filter(course =>
                !alreadyScheduled.has(course.id)
                && Number(course.units || 0) >= minimumUnits
            );
            const recommended = available.filter(course =>
                relatedPrefixes.has(course.id.slice(0, 2))
                && course.level >= 100
                && !poorRecommendation.test(course.name)
                && !(hasAdvancedMath && ["21-090", "21-102", "21-108"].includes(course.id))
            );
            const recommendedIds = new Set(recommended.map(course => course.id));
            const other = available.filter(course => !recommendedIds.has(course.id));
            const optionHtml = (course, recommendedCourse = false) =>
                `<option value="${course.id}" data-units="${course.units}" data-term="${course.term}" data-minimum-year="${course.minimum_year || 1}" data-intensity-tier="${course.intensity?.tier || ""}" data-hours="${course.intensity?.hours_per_week || ""}" data-workload="${course.intensity?.workload || ""}" data-difficulty="${course.intensity?.difficulty || ""}" data-intensity-label="${course.intensity?.label || ""}" data-description="${recommendedCourse ? "Recommended for your current and goal programs · " : ""}${course.description}">${recommendedCourse ? "★ " : ""}${course.requirement_group ? `[${course.requirement_group}] ` : ""}${course.id} · ${course.name} ${course.intensity ? `· ${course.intensity.label}` : ""}</option>`;
            const grouped = available.some(course => course.display_group)
                ? Array.from(available.reduce((groups, course) => {
                    const label = course.display_group || "Other scheduled courses";
                    if (!groups.has(label)) groups.set(label, []);
                    groups.get(label).push(course);
                    return groups;
                }, new Map()).entries()).map(([label, groupCourses]) =>
                    `<optgroup label="${label}">${groupCourses.map(course => optionHtml(course, recommendedIds.has(course.id))).join("")}</optgroup>`
                ).join("")
                : (recommended.length ? `<optgroup label="Recommended for your plan">${recommended.map(course => optionHtml(course, true)).join("")}</optgroup>` : "")
                    + `<optgroup label="Other undergraduate courses">${other.map(course => optionHtml(course)).join("")}</optgroup>`;
            courseSelect.innerHTML = '<option value="" data-units="0">Choose a scheduled undergraduate course</option>' + grouped;
            courseSelect.disabled = false;
        };

        const syncChoiceSummary = block => {
            if (!block || block.classList.contains("empty-block")) return;
            const courseSelect = block.querySelector(".block-course");
            const option = courseSelect?.selectedOptions[0];
            const courseId = option?.value || "";
            const category = block.querySelector(".block-category")?.selectedOptions[0]?.textContent || "Course choice";
            const catalogCourse = appState.latestCourseCatalog[courseId];
            const optionParts = (option?.textContent || "").replace(/^★\s*/, "").split(" · ");
            const courseName = catalogCourse?.name || optionParts[1] || category;
            const kind = block.querySelector(".choice-summary-kind");
            const id = block.querySelector(".choice-summary-id");
            const name = block.querySelector(".choice-summary-name");
            if (kind) kind.textContent = category;
            if (id) id.textContent = courseId;
            if (name) name.textContent = courseName;
            block.classList.toggle("choice-resolved", Boolean(courseId));
            if (courseId) block.classList.remove("choice-editing");
        };

        // Turn supported GenEd placeholders into real, term-specific course
        // pickers. These are scheduled candidates; exact Dietrich category
        // approval remains an advisor/SIO check until the approved-course
        // rules are imported as structured data.
        card.querySelectorAll(".choice-block[data-baseline-category]").forEach(block => {
            const category = block.dataset.baselineCategory;
            if (!category) return;
            const courseSelect = block.querySelector(".block-course");
            courseSelect.disabled = true;
            courseSelect.innerHTML = '<option value="" data-units="9">Loading scheduled candidates…</option>';
            fetchElectives(category).then(electiveData => {
                setCourseOptions(courseSelect, electiveData, Number(block.dataset.units || 0));
                const placeholder = courseSelect.querySelector('option[value=""]');
                if (placeholder) {
                    placeholder.textContent = "Choose a scheduled candidate · confirm approval";
                    placeholder.dataset.units = block.dataset.units;
                }
                syncChoiceSummary(block);
                applyGenEdSelectionsToPath();
            }).catch(() => {
                courseSelect.innerHTML = '<option value="" data-units="9">Course list unavailable</option>';
            });
        });

        // Requirement-group options arrive as verified course IDs. Enrich them
        // from the actual semester schedule so students see titles, units, and
        // offering details rather than a wall of unexplained numbers.
        fetchElectives("free-elective").then(electiveData => {
            const scheduledById = new Map(
                electiveData.courses.map(course => [course.id, course])
            );
            card.querySelectorAll(".choice-block:not(.empty-block) .block-course option[value]").forEach(option => {
                const course = scheduledById.get(option.value);
                if (!course) return;
                option.textContent = `${course.id} · ${course.name}`;
                option.dataset.units = course.units;
                option.dataset.minimumYear = course.minimum_year || 1;
                option.dataset.description = course.description;
                option.dataset.intensityTier = course.intensity?.tier || "";
                option.dataset.hours = course.intensity?.hours_per_week || "";
                option.dataset.workload = course.intensity?.workload || "";
                option.dataset.difficulty = course.intensity?.difficulty || "";
                option.dataset.intensityLabel = course.intensity?.label || "";
                if (course.intensity) {
                    option.textContent += ` · ${course.intensity.label}`;
                }
            });
            card.querySelectorAll(".choice-block:not(.empty-block)").forEach(syncChoiceSummary);
        }).catch(() => {});

        card.querySelectorAll(".change-course-button").forEach(button => {
            button.addEventListener("click", event => {
                const block = event.target.closest(".choice-block");
                block.classList.add("choice-editing");
                block.querySelector(".block-course")?.focus();
            });
        });

        card.querySelectorAll(".empty-block .block-category").forEach(select => {
            select.addEventListener("change", async event => {
                const block = event.target.closest(".planner-course-block");
                const courseSelect = block.querySelector(".block-course");
                const goalOptions = (appState.latestProgramProfile?.requirement_groups || [])
                    .flatMap(group => group.options || [])
                    .filter(option => /^\d{2}-\d{3}$/.test(option));
                courseSelect.disabled = true;
                courseSelect.innerHTML = '<option value="" data-units="0">Loading scheduled courses…</option>';
                if (event.target.value === "goal-program" && goalOptions.length) {
                    courseSelect.innerHTML = '<option value="" data-units="0">Choose a course</option>' +
                        goalOptions.map(option => `<option value="${option}" data-units="${appState.latestCourseCatalog[option]?.units || 9}">${option}${appState.latestCourseCatalog[option]?.name ? ` · ${appState.latestCourseCatalog[option].name}` : ""}</option>`).join("");
                    courseSelect.disabled = false;
                } else if (event.target.value === "current-major") {
                    const statsMlCourses = [
                        "21-120", "36-200", "15-112", "36-202", "21-127",
                        "21-256", "36-235", "15-122", "36-236", "21-241",
                        "36-350", "10-301", "36-401", "36-402", "15-351"
                    ];
                    courseSelect.innerHTML = '<option value="" data-units="0">Choose an official Stats/ML course</option>' +
                        statsMlCourses.map(option => {
                            const course = appState.latestCourseCatalog[option];
                            return `<option value="${option}" data-units="${course?.units || 9}" data-description="Official Stats/ML curriculum course">${option}${course?.name ? ` · ${course.name}` : ""}</option>`;
                        }).join("");
                    courseSelect.disabled = false;
                } else {
                    try {
                        const cardTerm = block.closest(".semester-card")
                            .querySelector(".semester-name").textContent.toLowerCase().endsWith("fall")
                            ? "fall" : "spring";
                        const baselineRequirement = baselineRequirementForCategory(event.target.value);
                        setCourseOptions(
                            courseSelect,
                            await fetchElectives(event.target.value || "free-elective", cardTerm),
                            Number(baselineRequirement?.units || 0)
                        );
                    } catch (error) {
                        courseSelect.innerHTML = '<option value="" data-units="0">Could not load courses</option>';
                    }
                }
                courseSelect.dispatchEvent(new Event("change"));
            });
        });
        card.querySelectorAll(".block-course").forEach(select => {
            select.addEventListener("change", event => {
                const block = event.target.closest(".planner-course-block");
                const option = event.target.selectedOptions[0];
                const previousCourseId = block.dataset.courseId || "";
                block.dataset.units = option?.dataset.units || block.dataset.units || 0;
                block.dataset.courseId = option?.value || "";
                block.dataset.offeredTerm = option?.dataset.term || "";
                block.dataset.minimumYear = option?.dataset.minimumYear || 1;
                block.dataset.intensityTier = option?.dataset.intensityTier || "";
                block.dataset.hours = option?.dataset.hours || "";
                block.dataset.workload = option?.dataset.workload || "";
                block.dataset.difficulty = option?.dataset.difficulty || "";
                const selectedCategory = block.dataset.baselineCategory
                    || block.querySelector(".block-category")?.value
                    || "";
                const baselineRequirement = baselineRequirementForCategory(selectedCategory);
                if (baselineRequirement && option?.value) {
                    block.dataset.baselineCategory = selectedCategory;
                    appState.genedSelections[baselineRequirement.id] = option.value;
                    container.querySelectorAll(`.choice-block[data-baseline-category="${selectedCategory}"]`).forEach(candidate => {
                        candidate.hidden = candidate !== block;
                    });
                } else if (baselineRequirement && !option?.value) {
                    if (appState.genedSelections[baselineRequirement.id] === previousCourseId) {
                        delete appState.genedSelections[baselineRequirement.id];
                    }
                    container.querySelectorAll(`.choice-block[data-baseline-category="${selectedCategory}"]`).forEach(candidate => {
                        candidate.hidden = false;
                    });
                }
                block.classList.remove(...[1, 2, 3, 4, 5].map(tier => `intensity-tier-${tier}`));
                block.classList.toggle("has-selected-course", Boolean(option?.value));
                if (option?.value && block.classList.contains("empty-block")) {
                    block.classList.remove("empty-block", "collapsed");
                    block.querySelector(".add-elective-button").hidden = true;
                }
                if (block.dataset.intensityTier) block.classList.add(`intensity-tier-${block.dataset.intensityTier}`);
                const intensitySlot = block.querySelector(".course-intensity-slot");
                if (intensitySlot) intensitySlot.innerHTML = block.dataset.intensityTier
                    ? `<span class="course-intensity-badge">Workload rating · ${option?.dataset.intensityLabel}</span>`
                    : "";
                block.querySelector(".block-units").textContent = `${block.dataset.units}u`;
                const description = block.querySelector(".course-description");
                if (description) description.textContent = option?.dataset.description || "";
                syncChoiceSummary(block);
                refreshRequirementDecisionProgress();
                refreshGenEdProgress();
                refreshDegreeRequirementTree();
                updateTotal();
            });
        });
        card.querySelectorAll(".choice-block:not(.empty-block)").forEach(syncChoiceSummary);
        updateTotal();
        container.appendChild(card);
    }

    let draggedBlock = null;
    const swapDomBlocks = (source, target) => {
        const sourceParent = source.parentNode;
        const targetParent = target.parentNode;
        const marker = document.createComment("planner-swap");
        sourceParent.replaceChild(marker, source);
        targetParent.replaceChild(source, target);
        marker.parentNode.replaceChild(target, marker);
    };
    const swapBlocks = (source, target) => {
        if (!source || !target || source === target) return;
        if (source.closest(".semester-card") === target.closest(".semester-card")) return;
        const violationsBefore = new Set(refreshCards().map(item => item.key));
        const sourceLabel = source.dataset.courseId
            || source.querySelector(".block-category")?.selectedOptions[0]?.textContent
            || "this requirement";
        const sourceParent = source.parentNode;
        const targetParent = target.parentNode;
        const availableTargetSlot = targetParent.querySelector(".empty-block");
        if (availableTargetSlot) target = availableTargetSlot;
        const sourceCourseCount = sourceParent.querySelectorAll(".planner-course-block").length;
        const targetCourseCount = targetParent.querySelectorAll(".planner-course-block").length;
        // Prefer an existing + Add elective slot. Only insert a sixth card when
        // the source semester already has six, so moving never reduces another
        // semester below its five standard planner positions.
        const canInsert = !target.classList.contains("empty-block")
            && targetCourseCount < 6
            && sourceCourseCount > 5;
        let sourceMarker = null;
        if (canInsert) {
            sourceMarker = document.createComment("planner-source-position");
            source.parentNode.replaceChild(sourceMarker, source);
            targetParent.insertBefore(source, target);
        } else {
            swapDomBlocks(source, target);
        }
        const violationsAfter = refreshCards();
        const introduced = violationsAfter.filter(item => !violationsBefore.has(item.key));
        if (introduced.length) {
            if (canInsert) {
                sourceMarker.parentNode.replaceChild(source, sourceMarker);
            } else {
                swapDomBlocks(source, target);
            }
            refreshCards();
            const message = `Moving ${sourceLabel} there would break another path rule. ${introduced[0].message.replace(/^Cannot move /, "Affected course: ")}`;
            validationMessage.textContent = message;
            validationMessage.hidden = false;
            showPlannerError(message);
            return;
        }
        if (canInsert) sourceMarker.remove();
        validationMessage.hidden = true;
        validationMessage.textContent = "";
        refreshDegreeRequirementTree();
    };
    const refreshCards = () => {
        container.querySelectorAll(".semester-card").forEach(card => {
            card.querySelectorAll(".planner-course-block").forEach((block, index) => {
                block.querySelector(".block-number").textContent = index + 1;
            });
            card.updatePlannerTotal?.();
        });

        const completed = new Set(appState.student.completed_courses);
        const cards = Array.from(container.querySelectorAll(".semester-card"));
        const scheduledBefore = courseId => {
            const block = container.querySelector(`[data-course-id="${courseId}"]`);
            return block ? cards.indexOf(block.closest(".semester-card")) : -1;
        };
        const violations = [];
        container.querySelectorAll(".planner-course-block[data-course-id]").forEach(block => {
            const courseId = block.dataset.courseId;
            const detail = appState.latestCourseCatalog[courseId] || {};
            const semesterIndex = cards.indexOf(block.closest(".semester-card"));
            const academicYear = Number(block.closest(".semester-card").dataset.academicYear || 1);
            const semesterTerm = block.closest(".semester-card").dataset.semesterTerm;
            const minimumYear = Number(block.dataset.minimumYear || detail.minimum_year || 1);
            const expression = detail.prerequisite_expression;
            const prerequisites = expression?.options?.map(option => option.course_id)
                || detail.prerequisites || [];
            const satisfied = prerequisite => completed.has(prerequisite)
                || (scheduledBefore(prerequisite) >= 0 && scheduledBefore(prerequisite) < semesterIndex);
            const valid = expression?.type === "any_of"
                ? prerequisites.some(satisfied)
                : prerequisites.every(satisfied);
            block.classList.toggle("prerequisite-order-warning", prerequisites.length > 0 && !valid);
            if (prerequisites.length > 0 && !valid) {
                violations.push({
                    key: `${courseId}:${semesterIndex}`,
                    message: `Cannot move ${courseId} here: complete ${prerequisites.join(expression?.type === "any_of" ? " or " : " and ")} in an earlier semester.`
                });
            }
            const tooEarly = academicYear < minimumYear;
            block.classList.toggle("course-year-warning", tooEarly);
            if (tooEarly) {
                violations.push({
                    key: `${courseId}:${semesterIndex}:year`,
                    message: `Cannot move ${courseId} to Year ${academicYear}. This path's verified timing rule starts it in Year ${minimumYear}.`
                });
            }
            const offered = detail.offered || (block.dataset.offeredTerm ? [block.dataset.offeredTerm] : []);
            const wrongTerm = offered.length > 0 && !offered.includes(semesterTerm);
            block.classList.toggle("elective-term-warning", wrongTerm);
            if (wrongTerm) {
                violations.push({
                    key: `${courseId}:${semesterIndex}:term`,
                    message: `Cannot move ${courseId} to ${semesterTerm}. The current schedule data lists it for ${offered.join(" or ")}.`
                });
            }
            const description = block.querySelector(".course-description");
            if (wrongTerm && description) {
                description.textContent = `Not offered in ${semesterTerm}. Re-select a course for this semester.`;
            }
            const prerequisiteStatus = detail.prerequisite_data_status;
            block.title = tooEarly
                ? `Year ${minimumYear}+ course`
                : prerequisites.length > 0 && !valid
                    ? `Check prerequisite order: ${prerequisites.join(" or ")}`
                    : prerequisiteStatus?.startsWith("pending") || prerequisiteStatus === "catalog_not_imported"
                        ? "Prerequisite rule is not fully verified; confirm in the CMU catalog"
                        : "Drag to another semester";
        });
        return violations;
    };

    container.querySelectorAll(".planner-course-block").forEach(block => {
        // The numbered handle below owns pointer dragging. Disabling native
        // HTML dragging prevents Chrome from executing the same move twice.
        block.draggable = false;
        block.addEventListener("dragstart", event => {
            draggedBlock = event.currentTarget;
            draggedBlock.classList.add("dragging");
            event.dataTransfer.effectAllowed = "move";
        });
        block.addEventListener("dragend", () => {
            draggedBlock?.classList.remove("dragging");
            draggedBlock = null;
            refreshCards();
        });
        block.addEventListener("dragover", event => event.preventDefault());
        block.addEventListener("drop", event => {
            event.preventDefault();
            const target = event.currentTarget;
            swapBlocks(draggedBlock, target);
        });
    });

    let pointerDraggedBlock = null;
    const beginPointerDrag = (block, event) => {
        event.preventDefault();
        pointerDraggedBlock = block;
        pointerDraggedBlock.classList.add("dragging");
        document.body.classList.add("planner-drag-active");
    };
    container.querySelectorAll(".planner-course-block").forEach(block => {
        block.addEventListener("mousedown", event => {
            if (event.button !== 0) return;
            if (event.target.closest("button, select, input, label, a")) return;
            beginPointerDrag(event.currentTarget, event);
        });
    });
    container.querySelectorAll(".block-number").forEach(handle => {
        handle.addEventListener("mousedown", event => {
            event.stopPropagation();
            beginPointerDrag(event.currentTarget.closest(".planner-course-block"), event);
        });
    });
    document.addEventListener("mousemove", event => {
        if (!pointerDraggedBlock) return;
        container.querySelectorAll(".planner-course-block.drag-target").forEach(block => block.classList.remove("drag-target"));
        const target = document.elementFromPoint(event.clientX, event.clientY)?.closest(".planner-course-block");
        if (target && target !== pointerDraggedBlock && container.contains(target)) target.classList.add("drag-target");
    });
    document.addEventListener("mouseup", event => {
        if (!pointerDraggedBlock) return;
        const target = document.elementFromPoint(event.clientX, event.clientY)?.closest(".planner-course-block")
            || event.target.closest?.(".planner-course-block");
        pointerDraggedBlock.classList.remove("dragging");
        container.querySelectorAll(".planner-course-block.drag-target").forEach(block => block.classList.remove("drag-target"));
        document.body.classList.remove("planner-drag-active");
        if (target && container.contains(target)) swapBlocks(pointerDraggedBlock, target);
        pointerDraggedBlock = null;
    });
    refreshCards();
}



// ------------------------------------------------------------
// RESULT CONTAINERS
// ------------------------------------------------------------

const fastestResults =
    document.getElementById(
        "fastestResults"
    );


const lowerWorkloadResults =
    document.getElementById(
        "lowerWorkloadResults"
    );

// #endregion


// #region 10. GENERATE PATH — REQUEST
// ============================================================
// Runs when user clicks:
//
// "Generate my path"
//
// Flow:
//
// 1. Collect completed courses
// 2. Build request body
// 3. POST to FastAPI
// 4. Parse response
// 5. Render fastest path
// 6. Render lower-workload path
// 7. Render explanation
// 8. Render goal status
// 9. Show results
//
// ============================================================

document
    .getElementById(
        "generateButton"
    )
    .addEventListener(
        "click",
        async () => {


            // #region 10A. COLLECT COMPLETED COURSES
            // ------------------------------------------------

            const checkedCourses =
                document.querySelectorAll(
                    '.requirement-decision-page .course-option input[type="checkbox"]:checked:not(#noCompletedCourses)'
                );


            const completedCourses = [...new Set([
                ...Array.from(checkedCourses).flatMap(input => input.value.split(" + "))
            ])];

            appState.student.completed_courses =
                completedCourses;
            appState.student.completed_requirement_ids = Array.from(
                document.querySelectorAll('#genedHistory input[type="checkbox"]:checked')
            ).map(input => input.value);

            // #endregion



            // #region 10B. BUILD REQUEST BODY
            // ------------------------------------------------

            const requestBody = buildPlanningRequest();


            console.log(
                "Sending plan request:",
                requestBody
            );

            // #endregion



            // #region 10C. SEND REQUEST
            // ------------------------------------------------

            const response =
                await fetch(
                    "/api/plan",
                    {

                        method:
                            "POST",


                        headers: {

                            "Content-Type":
                                "application/json"

                        },


                        body:
                            JSON.stringify(
                                requestBody
                            )

                    }
                );

            // #endregion



            // #region 10D. HANDLE BACKEND ERRORS
            // ------------------------------------------------

            if (
                !response.ok
            ) {

                const errorText =
                    await response.text();

                let errorMessage = "We could not generate this plan. Please review your choices and try again.";

                try {
                    const errorPayload = JSON.parse(errorText);
                    if (typeof errorPayload.detail === "string" && errorPayload.detail.trim()) {
                        errorMessage = errorPayload.detail;
                    }
                } catch (error) {
                    if (errorText.trim()) {
                        errorMessage = errorText.trim();
                    }
                }


                console.error(
                    "Backend error:",
                    errorText
                );

                showPlannerError(errorMessage);


                return;

            }

            // #endregion



            // #region 10E. PARSE RESPONSE
            // ------------------------------------------------

            const data =
                await response.json();

            appState.latestPlan = data;

            appState.latestProgramProfile = data.program_profile;
            appState.latestCourseCatalog = data.course_catalog || {};
            appState.latestSecondaryPathType = data.secondary_path_type;
            const programPathNote = document.getElementById("programPathNote");
            if (data.minor_status) {
                const fixedCount = data.program_profile?.required_course_ids?.length || 0;
                const choiceCount = (data.program_profile?.requirement_groups || [])
                    .reduce((total, group) => total + (group.choose || 1), 0);
                programPathNote.classList.remove("hidden");
                programPathNote.classList.toggle("minor-unavailable", !data.minor_status.available);
                programPathNote.innerHTML = `
                    <strong>Minor foundation → Additional Major</strong>
                    <span><strong>${fixedCount + choiceCount} program requirements:</strong> ${fixedCount} fixed course${fixedCount === 1 ? "" : "s"} + ${choiceCount} course-choice slots.</span>
                    <span>Standard blocks form the minor foundation. Green blocks are additional courses required to continue to the major.</span>
                    <span>Drag a block onto another semester to swap their positions; totals and prerequisite warnings update immediately.</span>
                    ${data.minor_status.note ? `<span>${data.minor_status.note}</span>` : ""}
                `;
            } else {
                programPathNote.classList.add("hidden");
            }


            console.log(
                "Planner response:",
                data
            );

            // #endregion



            // #region 10F. RENDER PATHS
            // ------------------------------------------------

            // For an additional major, `lower_workload` is intentionally the
            // smaller minor-foundation preview, not a complete alternative
            // route to the additional major. The primary results panel must
            // therefore render `fastest`, which contains the full published
            // curriculum (including extension courses and cluster choices).
            // Rendering the foundation here previously made an AI additional
            // major look like the AI minor and hid 15-150, 21-241, and two of
            // the four required AI-cluster areas.
            const balancedPath = appState.goals[0]?.type === "internal_transfer"
                ? data.fastest
                : data.secondary_path_type === "minor_foundation"
                ? data.fastest
                : (data.lower_workload || data.fastest);
            renderPath(balancedPath, fastestResults);
            lowerWorkloadResults.innerHTML = "";
            renderDegreeAudits(data.degree_audits, data.primary_baseline, data.planning_warnings || []);
            renderTransferReadiness(data);
            prepareTransferAdvisor(data);
            renderDegreeRequirementTree();

            refreshRequirementDecisionProgress();
            renderResultsRequirementProgress();
            refreshGenEdProgress();

            const secondarySection = document.getElementById("secondaryPathSection");
            const compareMinorButton = document.getElementById("compareMinorPathButton");
            const comparePathsButton = document.getElementById("comparePathsButton");
            secondarySection.classList.add("hidden");
            compareMinorButton.classList.add("hidden");
            comparePathsButton.classList.add("hidden");
            programPathNote.classList.add("hidden");
            document.getElementById("pathIntelligence").classList.add("hidden");

            // #endregion



            // #region 10G. PATH SUMMARIES
            // ------------------------------------------------

            document
                .getElementById(
                    "fastestSummary"
                )
                .textContent =
                balancedPath.path.length
                    ? `${balancedPath.path[0].academic_year_name} ${balancedPath.path[0].semester} → ${balancedPath.path.at(-1).academic_year_name} ${balancedPath.path.at(-1).semester}`
                    : "No semesters needed";

            // #endregion



            // #region 10H. WHY THIS PATH?
            // ------------------------------------------------

            renderPathExplanation(
                data.explanation
            );

            // #endregion



            // #region 10I. GOAL STATUS
            // ------------------------------------------------

            renderGoalStatus(
                data
            );

            // #endregion



            // #region 10J. GOAL NAME
            // ------------------------------------------------

            renderGoalName();

            renderOverlapSummary(data.overlap_summary);

            // #endregion



            // #region 10K. SHOW RESULTS
            // ------------------------------------------------

            showScreen(
                results
            );
            refreshGenEdProgress();
            renderDegreeRequirementTree();

            // #endregion

        }
    );

// #endregion


// #region 11. RESULT HELPERS
// ============================================================
// Small rendering functions.
//
// These used to live inside the giant Generate button handler.
//
// Moving them here makes the request code much easier to read.
// ============================================================



// ------------------------------------------------------------
// 11A. WHY THIS PATH?
// ------------------------------------------------------------

function renderPathExplanation(
    explanation
) {

    const insightTitle =
        document.getElementById(
            "insightTitle"
        );


    const insightText =
        document.getElementById(
            "insightText"
        );


    // --------------------------------------------------------
    // Explanation exists
    // --------------------------------------------------------

    if (
        explanation
    ) {

        insightTitle.textContent =
            `Your critical next course is ${explanation.critical_course}.`;


        let text =
            `${explanation.critical_course} currently has the biggest impact on your path.`;


        // ----------------------------------------------------
        // Show courses directly unlocked
        // ----------------------------------------------------

        if (
            explanation.unlocks &&
            explanation.unlocks.length > 0
        ) {

            text +=
                ` It directly unlocks ${explanation.unlocks.join(", ")}.`;

        }


        // ----------------------------------------------------
        // Show delay impact
        // ----------------------------------------------------

        if (
            explanation.delay_if_skipped !== null &&
            explanation.delay_if_skipped > 0
        ) {

            text +=
                ` Delaying it may delay this path by ${explanation.delay_if_skipped} semester(s).`;

        }


        insightText.textContent =
            text;

    }


    // --------------------------------------------------------
    // No explanation
    // --------------------------------------------------------

    else {

        insightTitle.textContent =
            "No critical next course found.";


        insightText.textContent =
            "You may already have completed the key prerequisites for this path.";

    }

}


function renderOverlapSummary(summary) {
    const container = document.getElementById("overlapSummary");
    if (!summary || !summary.courses.length) {
        container.classList.add("hidden");
        return;
    }
    container.classList.remove("hidden");
    container.innerHTML = `
        <strong>${summary.courses.length} shared courses make this path more efficient</strong>
        <p>${summary.courses.join(", ")} advance both your current major and selected goal (${summary.units} units scheduled once).</p>
        <p class="history-helper">Based on the currently verified subset of your current-major curriculum.</p>
    `;
}


function renderDegreeAudits(audits, baseline, warnings = []) {
    const container = document.getElementById("degreeAuditGrid");
    if (!audits) {
        container.innerHTML = "";
        return;
    }
    const primary = audits.primary_degree;
    const goal = audits.selected_goal;
    const goalPercent = goal.total_requirements
        ? Math.min(100, Math.round((goal.total_requirements - (goal.requirements_remaining_to_complete ?? goal.requirements_remaining ?? 0)) / goal.total_requirements * 100))
        : 0;
    const programName = id => programDirectory.find(program =>
        program.planning_id === id || program.id === id
    )?.name || id.replaceAll("-", " ").replace(/\b\w/g, letter => letter.toUpperCase());
    const primaryRemaining = primary.requirements_remaining_to_graduate;
    const goalRemaining = goal.requirements_remaining_to_complete ?? goal.requirements_remaining;
    const placementSummary = Number.isFinite(goal.total_requirements) && Number.isFinite(goal.requirements_scheduled)
        ? `${goal.requirements_scheduled} of ${goal.total_requirements} published requirements are placed in this plan.`
        : "";
    container.innerHTML = `
        ${primary.status === "replaced_by_transfer" ? "" : `<article class="degree-audit-card degree-audit-row primary-audit-card">
            <div><p class="eyebrow">CURRENT BACHELOR'S DEGREE</p><h3>${programName(primary.program)}</h3></div>
            <div class="audit-remaining"><strong>${primaryRemaining == null ? "Curriculum audit in progress" : `${primaryRemaining} major requirements remaining`}</strong><small>${primary.minimum_degree_units ? `${primary.minimum_degree_units} total units required for the degree; GenEd and free electives are tracked separately.` : primary.message}</small></div>
        </article>`}
        <article class="degree-audit-card degree-audit-row goal-audit-card">
            <div><p class="eyebrow">${goal.type.replaceAll("_", " ")}</p><h3>${programName(goal.program)}</h3></div>
            <div class="audit-remaining"><strong>${goalRemaining == null ? "Curriculum audit in progress" : `${goalRemaining} requirements not yet completed`}</strong><div class="audit-progress" role="progressbar" aria-label="Goal requirements placed in plan" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${goalPercent}"><span style="width:${goalPercent}%"></span></div><small>${[placementSummary, goal.message].filter(Boolean).join(" ")}</small></div>
        </article>
        ${warnings.length ? `<section class="planning-warning-list" aria-label="Planning checks">
            ${warnings.map(warning => `<article class="planning-warning ${warning.severity || "warning"}">
                <strong>${warning.severity === "error" ? "Action required" : warning.severity === "info" ? "Eligibility checkpoint" : "Verify before enrolling"}</strong>
                <span>${warning.message}</span>
            </article>`).join("")}
        </section>` : ""}
        ${baseline?.status === "estimated_template" ? `<p class="audit-disclaimer"><strong>Estimated baseline:</strong> ${baseline.note}</p>` : ""}
    `;
}

function renderDegreeRequirementTree() {
    const container = document.getElementById("degreeRequirementTree");
    const plan = appState.latestPlan;
    if (!container || !plan || results.classList.contains("hidden")) {
        if (container) container.innerHTML = "";
        return;
    }

    const audits = plan.degree_audits || {};
    const primary = audits.primary_degree || {};
    const goal = audits.selected_goal || {};
    const isEligibilityPlan = plan.transfer_planning?.mode === "eligibility";
    const completedCourses = new Set(appState.student.completed_courses || []);
    const completedRequirements = new Set(appState.student.completed_requirement_ids || []);
    const planned = Array.from(fastestResults.querySelectorAll(".planner-course-block[data-course-id]"))
        .filter(block => block.dataset.courseId)
        .map(block => ({
            id: block.dataset.courseId,
            requirement: block.querySelector(".block-category")?.selectedOptions[0]?.textContent?.trim()
                || block.querySelector(".block-main > small")?.textContent?.trim()
                || ""
        }));
    const plannedIds = new Set(planned.flatMap(item => item.id.split(" + ")));
    const choiceGroups = step3CourseData[appState.plannerKey]?.choiceGroups || [];
    const programName = id => programDirectory.find(program =>
        program.planning_id === id || program.id === id
    )?.name || (id || "Academic program").replaceAll("-", " ").replace(/\b\w/g, letter => letter.toUpperCase());
    const rule = group => {
        const choose = group.choose || 1;
        const count = (group.options || []).length;
        return choose === 1 ? "fulfill one" : choose >= count && count ? "fulfill all" : `fulfill ${choose}`;
    };
    const plannedFor = group => {
        const options = (group.options || []).flatMap(option => option.split(" + "));
        const matches = [
            ...planned.filter(item => item.requirement.toLowerCase() === (group.name || "").toLowerCase()).map(item => item.id),
            ...options.filter(id => plannedIds.has(id) || completedCourses.has(id))
        ];
        return [...new Set(matches)];
    };
    const requirementLeaf = (name, ruleLabel, course, complete = Boolean(course)) => `
        <article class="degree-tree-leaf ${complete ? "fulfilled" : ""}">
            <span class="tree-status-icon">${course || complete ? "✓" : "○"}</span>
            <span><strong>${name}</strong><small>${ruleLabel}</small></span>
            <span class="tree-course-link">${complete && course ? `Satisfied by ${course}` : course ? `Planned: ${course}` : complete ? "Completed" : "Still needed"}</span>
        </article>`;
    const groupBranch = (label, groups, remaining) => `
        <details class="degree-tree-branch">
            <summary><span><strong>${label}</strong><small>${remaining == null ? "Verified requirements" : `${remaining} remaining`}</small></span><span class="tree-rule-badge">fulfill all</span></summary>
            <div class="degree-tree-children">
                ${groups.length ? groups.map(group => {
                    const courses = plannedFor(group);
                    const choose = group.choose || 1;
                    return requirementLeaf(group.name, rule(group), courses.join(", "), courses.length >= choose);
                }).join("") : '<p class="tree-empty-note">No unresolved course-choice categories.</p>'}
            </div>
        </details>`;

    const currentGroups = choiceGroups.filter(group => group.history_scope === "current_major");
    const goalGroups = choiceGroups.filter(group => group.history_scope !== "current_major");
    const genEdByGroup = (appState.baselineRequirements || []).reduce((groups, requirement) => {
        (groups[requirement.group || "general_education"] ||= []).push(requirement);
        return groups;
    }, {});
    const genEdBranches = Object.entries(genEdByGroup).map(([groupId, requirements]) => {
        const label = groupId.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
        return `<details class="degree-tree-branch gened-tree-branch">
            <summary><span><strong>${label}</strong><small>${requirements.length} categor${requirements.length === 1 ? "y" : "ies"}</small></span><span class="tree-rule-badge">fulfill all</span></summary>
            <div class="degree-tree-children">${requirements.map(requirement => {
                const linked = appState.genedSelections[requirement.id]
                    || planned.find(item => item.requirement.toLowerCase() === requirement.name.toLowerCase())?.id
                    || (requirement.courses || []).find(id => plannedIds.has(id) || completedCourses.has(id));
                return requirementLeaf(requirement.name, "fulfill one", linked, Boolean(linked) || completedRequirements.has(requirement.id));
            }).join("")}</div>
        </details>`;
    }).join("");

    container.innerHTML = `
        <div class="degree-tree-heading">
            <div><p class="eyebrow">DEGREE REQUIREMENTS</p><h2>How this plan fulfills your degree</h2><p>Open a branch to see every fulfill-all and fulfill-one rule. Course links update when you edit the plan.</p></div>
            <span class="rules-badge">Live plan audit</span>
        </div>
        ${isEligibilityPlan || goal.type !== "internal_transfer" ? `<details class="degree-tree-root">
            <summary><span><strong>${programName(primary.program)}</strong><small>Current bachelor's degree</small></span><span class="tree-rule-badge">fulfill all</span></summary>
            <div class="degree-tree-children">
                ${groupBranch("Major requirements", currentGroups, primary.requirements_remaining_to_graduate)}
                <details class="degree-tree-branch"><summary><span><strong>General Education</strong><small>${(appState.baselineRequirements || []).length} categories</small></span><span class="tree-rule-badge">fulfill all</span></summary><div class="degree-tree-children">${genEdBranches}</div></details>
            </div>
        </details>` : ""}
        <details class="degree-tree-root target-tree-root">
            <summary><span><strong>${programName(goal.program)}</strong><small>${(goal.type || "Selected goal").replaceAll("_", " ")}</small></span><span class="tree-rule-badge">fulfill all</span></summary>
            <div class="degree-tree-children">
                ${groupBranch("Target program requirements", goalGroups, goal.requirements_remaining_to_complete ?? goal.requirements_remaining)}
            </div>
        </details>`;
}
refreshDegreeRequirementTree = renderDegreeRequirementTree;

function renderGenEdProgress() {
    const panel = document.getElementById("genedProgressPanel");
    const wasOpen = panel.querySelector(".gened-progress-details")?.open ?? false;
    const requirements = appState.baselineRequirements || [];
    if (!requirements.length || results.classList.contains("hidden")) {
        panel.innerHTML = "";
        panel.classList.add("hidden");
        return;
    }
    const completed = new Set(appState.student.completed_requirement_ids || []);
    const plannedByName = new Map();
    document.querySelectorAll("#fastestResults .choice-block").forEach(block => {
        const name = block.querySelector(".block-category")?.selectedOptions[0]?.textContent?.trim();
        if (name && block.dataset.courseId) plannedByName.set(name, block.dataset.courseId);
    });
    const plannedCourseIds = new Set(Array.from(
        document.querySelectorAll("#fastestResults .planner-course-block[data-course-id]")
    ).flatMap(block => (block.dataset.courseId || "").split(" + ")).filter(Boolean));
    const plannedCourseFor = requirement => appState.genedSelections[requirement.id]
        || plannedByName.get(requirement.name)
        || (requirement.courses || []).find(id => plannedCourseIds.has(id));
    const satisfied = requirements.filter(requirement => completed.has(requirement.id) || Boolean(plannedCourseFor(requirement)));
    const percent = requirements.length ? Math.round(satisfied.length / requirements.length * 100) : 0;
    const ruleFor = requirement => requirement.name === "Communication"
        ? "Choose one approved full course OR one approved two-mini sequence"
        : requirement.name === "Experiential Learning Activity"
            ? "Complete one approved experiential activity"
            : `Choose one approved ${requirement.name.toLowerCase()} course`;
    const groupLabels = {
        foundations: "Foundations",
        disciplinary_perspectives: "Disciplinary Perspectives",
        special_seminars: "Special Seminars",
        experiential_learning: "Experiential Learning"
    };
    const grouped = requirements.reduce((result, requirement) => {
        (result[requirement.group || "other"] ||= []).push(requirement);
        return result;
    }, {});
    panel.classList.remove("hidden");
    panel.innerHTML = `
        <details class="gened-progress-details" ${wasOpen ? "open" : ""}>
            <summary><div class="gened-progress-heading">
                <div><p class="eyebrow">DIETRICH GENERAL EDUCATION</p><h2>GenEd progress</h2><p>115 units across Foundations, Disciplinary Perspectives, Special Seminars, and Experiential Learning.</p></div>
                <strong>${satisfied.length} / ${requirements.length}</strong>
            </div></summary>
            <div class="gened-progress-body">
            <div class="gened-progress-track" role="progressbar" aria-label="GenEd completion" aria-valuemin="0" aria-valuemax="${requirements.length}" aria-valuenow="${satisfied.length}"><span style="width:${percent}%"></span></div>
            <div class="gened-rule-key"><span><b>AND</b> Complete every category</span><span><b>OR</b> Choose one approved option inside a category</span></div>
            <div class="gened-category-list">
                ${Object.entries(grouped).map(([groupId, groupRequirements]) => `
                    <section class="gened-category-group">
                        <div class="gened-category-group-heading"><strong>${groupLabels[groupId] || groupId.replaceAll("_", " ")}</strong><span>${groupRequirements.filter(requirement => completed.has(requirement.id) || Boolean(plannedCourseFor(requirement))).length} / ${groupRequirements.length}</span></div>
                        ${groupRequirements.map((requirement, index) => {
                            const courseId = plannedCourseFor(requirement);
                            const done = completed.has(requirement.id) || Boolean(courseId);
                            return `${index ? '<div class="gened-and-connector">AND</div>' : ""}<article class="gened-category ${done ? "complete" : ""}">
                                <span><strong>${requirement.name}</strong><small>${ruleFor(requirement)} · ${requirement.timeline?.source_text || "Complete before graduation"}</small></span>
                                <span class="gened-category-status">${done ? `✓ ${courseId || "Completed"}` : "Choose in your path"}</span>
                            </article>`;
                        }).join("")}
                    </section>`).join("")}
            </div></div>
        </details>`;
}
refreshGenEdProgress = renderGenEdProgress;

function applyGenEdSelectionsToPath() {
    if (results.classList.contains("hidden")) return;
    const requirements = new Map((appState.baselineRequirements || []).map(item => [item.id, item]));
    Object.entries(appState.genedSelections || {}).forEach(([requirementId, courseId]) => {
        if (!/^\d{2}-\d{3}$/.test(courseId)) return;
        const requirement = requirements.get(requirementId);
        const block = Array.from(fastestResults.querySelectorAll(".choice-block")).find(candidate =>
            candidate.querySelector(".block-category")?.selectedOptions[0]?.textContent?.trim() === requirement?.name
        );
        const select = block?.querySelector(".block-course");
        if (!select || select.value === courseId || !Array.from(select.options).some(option => option.value === courseId)) return;
        select.value = courseId;
        select.dispatchEvent(new Event("change", { bubbles: true }));
    });
}

const comparisonActions = document.querySelector(".deferred-comparison-actions");
comparisonActions.after(document.getElementById("pathIntelligence"));
document.getElementById("comparePathsButton").addEventListener("click", event => {
    const intelligence = document.getElementById("pathIntelligence");
    const shouldOpen = intelligence.classList.contains("hidden");
    intelligence.classList.toggle("hidden", !shouldOpen);
    event.currentTarget.textContent = shouldOpen ? "Hide comparison" : "Compare paths";
});
document.getElementById("compareMinorPathButton").addEventListener("click", event => {
    const secondary = document.getElementById("secondaryPathSection");
    const intelligence = document.getElementById("pathIntelligence");
    const note = document.getElementById("programPathNote");
    const shouldOpen = secondary.classList.contains("hidden");
    secondary.classList.toggle("hidden", !shouldOpen);
    intelligence.classList.toggle("hidden", !shouldOpen);
    note.classList.toggle("hidden", !shouldOpen);
    event.currentTarget.textContent = shouldOpen ? "Hide minor path" : "Compare minor path";
});


// ------------------------------------------------------------
// 11B. GOAL STATUS
// ------------------------------------------------------------

function renderGoalStatus(
    data
) {

    const goalStatus =
        document.getElementById(
            "goalStatus"
        );


    // --------------------------------------------------------
    // Goal course path complete
    // --------------------------------------------------------

    const balancedPath = data.secondary_path_type === "minor_foundation"
        ? data.fastest
        : (data.lower_workload || data.fastest);
    if (
        balancedPath.goal_complete
    ) {

        goalStatus.textContent =
            data.transfer_planning?.mode === "eligibility"
                ? "Application checkpoint mapped ✓"
                : "Course Path Mapped ✓";

    }


    // --------------------------------------------------------
    // Courses still remaining
    // --------------------------------------------------------

    else {
        const remainingCourses = balancedPath.remaining.length;
        const remainingSlots =
            (balancedPath.remaining_program_requirements ?? []).length;
        goalStatus.textContent =
            `${remainingCourses} courses + ${remainingSlots} requirement slots remaining`;

    }

}



// ------------------------------------------------------------
// 11C. GOAL DISPLAY NAME
//
// Safe:
// If index.html does not contain:
//
// id="goalName"
//
// this function simply exits.
// ------------------------------------------------------------

function renderGoalName() {

    const goalNameElement =
        document.getElementById(
            "goalName"
        );


    if (
        !goalNameElement
    ) {

        return;

    }


    const goal = appState.goals[0];
    const programName = temporarySCSPrograms.find(
        program => program.id === goal.program
    )?.name ?? programDirectory.find(
        program => program.planning_id === goal.program
    )?.name ?? goal.program;
    const typeName = {
        current_major: "Current Major",
        internal_transfer: "Transfer to",
        additional_major: "Additional Major in",
        minor: "Minor in"
    }[goal.type] ?? goal.type;
    const fullGoalName = goal.type === "additional_major"
        ? `${programName}: Minor foundation → Additional Major`
        : (goalNames[appState.plannerKey] ?? `${typeName} ${programName}`);
    goalNameElement.textContent = fullGoalName;

    const pathType = goal.type === "additional_major"
        ? "Minor → Additional Major"
        : goal.type === "minor"
            ? "Minor"
            : typeName;
    const contextText = `${programName} · ${pathType}`;
    document.getElementById("fastestGoalContext").textContent = contextText;
    const secondaryIsMinor = appState.latestSecondaryPathType === "minor_foundation";
    document.getElementById("lowerWorkloadGoalContext").textContent = secondaryIsMinor
        ? `${programName} · Minor foundation`
        : contextText;
    const targetYear = appState.constraints.target_completion_year;
    const applicationTerm = appState.latestPlan?.transfer_planning?.application_term;
    document.getElementById("fastestPathTitle").textContent = applicationTerm
        ? `Transfer application plan · apply in ${applicationTerm.academic_year_name} ${applicationTerm.semester}`
        : `Balanced workload · by ${["", "Freshman", "Sophomore", "Junior", "Senior"][targetYear]}`;
    document.getElementById("lowerWorkloadTitle").textContent = secondaryIsMinor
        ? `◆ ${programName} Minor Foundation Path`
        : `⚖ Lower Workload ${pathType} Path`;

}

// #endregion


// #region 12. NEXT REFACTOR CHECKLIST
// ============================================================
// DOCUMENTATION ONLY.
//
// Nothing below here runs.
//
// This is a reminder of the architecture we want to move toward.
//
// ------------------------------------------------------------
//
// NEXT STEP 1
//
// Move:
//
// temporarySCSPrograms
//
// into:
//
// Data/programs.json
//
// ------------------------------------------------------------
//
// NEXT STEP 2
//
// Add backend endpoint:
//
// GET /api/programs
//
// ------------------------------------------------------------
//
// NEXT STEP 3
//
// Create:
//
// static/program-explorer.js
//
// Move:
//
// School Selection
// Program Selection
//
// out of app.js.
//
// ------------------------------------------------------------
//
// NEXT STEP 4
//
// Create:
//
// static/course-selection.js
//
// Step 3 should become:
//
// selected goal
//      ↓
// requirements.json
//      ↓
// dynamically generated relevant courses
//
// ------------------------------------------------------------
//
// NEXT STEP 5
//
// Create:
//
// static/results.js
//
// Move:
//
// renderPath()
// renderPathExplanation()
// renderGoalStatus()
//
// out of app.js.
//
// ------------------------------------------------------------
//
// NEXT STEP 6
//
// Remove legacy:
//
// selectedGoal
//
// Instead backend should understand:
//
// {
//     goal_type: "transfer",
//     school: "scs",
//     program: "computer-science"
// }
//
// ------------------------------------------------------------
//
// NEXT STEP 7
//
// Add:
//
// Additional Major
// vs
// Minor
//
// comparison page.
//
// ------------------------------------------------------------
//
// NEXT STEP 8
//
// Add:
//
// Undecided
//
// academic combinations / exploration page.
//
// ============================================================
// #endregion
