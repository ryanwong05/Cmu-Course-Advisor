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
    latestPlan: null
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
    `).join("") : "<p>No saved paths yet. Save a recommendation to compare it later.</p>";
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
        fastest: capturePath(fastestResults),
        lowerWorkload: capturePath(lowerWorkloadResults),
        semesterCount: fastestResults.querySelectorAll(".semester-card").length,
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
    "Electrical and Computer Engineering": "ece"
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
        option.value = currentMajorAliases[program.name] || program.id;
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

step2Next.addEventListener("click", () => {

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

        prepareCurrentMajorStep();

        showScreen(step3);

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
        button.innerHTML = `
            <strong>${program.name}</strong>
            <span class="program-upgrade-label">${program.credential}</span>
            <small>${program.planning_status === "planning_ready"
                ? "Verified planning available"
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
            const ready = program.planning_status === "planning_ready";
            document.getElementById("step2bNext").disabled = !ready;
            helper.textContent = ready
                ? "Verified planning is available for this path."
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
            program
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
            if (goal && ["additional_major", "minor"].includes(goal.type)) {
                const response = await fetch(
                    `/api/programs/${goal.program}/${goal.type}`
                );
                if (!response.ok) {
                    console.error("Program profile could not be loaded");
                    return;
                }
                const detail = await response.json();
                const currentMajorHistory = appState.student.primary_major === "stats-ml"
                    ? step3CourseData["stats-ml-major"].courses.map(course => ({
                        ...course,
                        is_current_major: true
                    }))
                    : [];
                const historyById = new Map();
                [...currentMajorHistory, ...detail.fixed_courses].forEach(course => {
                    historyById.set(course.id, {...historyById.get(course.id), ...course});
                });
                const historyCourses = [...historyById.values()];
                step3CourseData[appState.plannerKey] = {
                    eyebrow: `SCS · ${detail.program_name.toUpperCase()} · ${goal.type === "minor" ? "MINOR" : "ADDITIONAL MAJOR"}`,
                    title: "Which current-major and goal courses have you completed?",
                    description: `Select completed courses from your current major and this goal. Anything left unchecked may be placed in your future plan.`,
                    courses: historyCourses,
                    choiceGroups: detail.requirement_groups,
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

function prepareCurrentMajorStep() {

    const currentMajor =
        document.getElementById(
            "major"
        ).value;


    // --------------------------------------------------------
    // Statistics & Machine Learning
    // --------------------------------------------------------

    if (
        currentMajor === "stats-ml"
    ) {

        updatePlanningGoal();
        appState.plannerKey =
            "stats-ml-major";


        renderCourseSelection(
            "stats-ml-major"
        );

        loadBaseline();


        return;

    }


    // --------------------------------------------------------
    // Other majors are not implemented yet.
    // --------------------------------------------------------

    console.warn(
        "Current-major explorer not implemented yet:",
        currentMajor
    );

}



// ------------------------------------------------------------
// RENDER STEP 3
// ------------------------------------------------------------

function renderCourseSelection(
    pathKey
) {

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


    const foundationOrder = ["21-120", "21-122", "15-112", "36-200"];
    const earlyCoreOrder = ["21-127", "15-122", "36-202", "36-235", "21-241"];
    const rank = course => {
        if (foundationOrder.includes(course.id)) return [0, foundationOrder.indexOf(course.id)];
        if (earlyCoreOrder.includes(course.id)) return [1, earlyCoreOrder.indexOf(course.id)];
        if (course.is_current_major) return [2, 0];
        if (course.program_tier === "minor_foundation") return [3, 0];
        if (course.program_tier === "additional_major") return [4, 0];
        return [2, 0];
    };
    const groupNames = [
        "First-year foundations",
        "Early major core",
        "Later current-major coursework",
        "Minor foundation",
        "Additional-major extension"
    ];
    const groupedCourses = data.courses
        .slice()
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
            "course-option";


        label.innerHTML = `

            <input
                type="checkbox"
                value="${course.id}"
            >

            <span>

                <strong>
                    ${course.id}
                </strong>

                ${course.name}

                ${course.program_tier ? `<small class="course-tier-badge ${course.program_tier === "minor_foundation" ? "minor-foundation" : ""}">${course.is_current_major ? "Also counts toward " : ""}${course.program_tier === "minor_foundation" ? "Minor foundation" : "Additional-major extension"}</small>` : ""}

            </span>

        `;


            list.appendChild(label);
        }
        section.appendChild(list);
        courseList.appendChild(section);
    });

    // Choice groups belong in the semester builder on Results.  Keeping them
    // off this history screen prevents a long catalog dump before planning.


    // --------------------------------------------------------
    // No requirement data yet.
    // --------------------------------------------------------

    if (
        data.courses.length === 0
    ) {

        courseList.innerHTML = `

            <div class="empty-course-state">

                <strong>
                    Statistics & Machine Learning
                </strong>

                <p>
                    The major explorer is connected.
                    Next we'll populate its verified
                    requirement groups and course history.
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
            "Generate my path →";


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
    const kindLabels = {
        goal: "Goal program",
        current_major: "Current major",
        shared: "Current + goal",
        baseline: "GenEd requirement",
        program_choice: "Program choice"
    };

    const fixedBlock = (block, number) => `
        <div class="planner-course-block fixed-block ${block.program_tier === "additional_major" ? "additional-major-block" : block.program_tier === "minor_foundation" ? "minor-foundation-block" : ""} ${block.estimated ? "primary-baseline-block" : ""}" data-units="${block.units}" data-course-id="${block.id}" draggable="true">
            <span class="block-number">${number}</span>
            <span class="block-main">
                <small>${block.estimated ? "Estimated primary-major workload" : block.program_tier === "additional_major" ? "Additional Major extension" : (kindLabels[block.kind] || "Minor foundation")}</small>
                <strong>${block.id}</strong>
                <span>${block.name}</span>
            </span>
            <strong class="block-units">${block.units}u</strong>
        </div>`;

    const choiceBlock = (block, number) => {
        const options = block.options || [];
        const isBaseline = block.kind === "baseline";
        return `
            <div class="planner-course-block choice-block ${block.program_tier === "additional_major" ? "additional-major-block" : "minor-foundation-block"}" data-units="${block.units}" draggable="true">
                <span class="block-number">${number}</span>
                <span class="block-main">
                    <select class="block-category" aria-label="Block ${number} category">
                        <option selected>${block.name}</option>
                    </select>
                    <select class="block-course" aria-label="Block ${number} course">
                        <option value="" data-units="${block.units}">${isBaseline
                            ? "Choose an approved course in SIO"
                            : "Choose a course"}</option>
                        ${options.map(option => `<option value="${option}" data-units="${appState.latestCourseCatalog[option]?.units || block.units}">${option}${appState.latestCourseCatalog[option]?.name ? ` · ${appState.latestCourseCatalog[option].name}` : ""}</option>`).join("")}
                    </select>
                    <small class="course-description" aria-live="polite"></small>
                </span>
                <strong class="block-units">${block.units}u</strong>
            </div>`;
    };

    const emptyBlock = number => `
        <div class="planner-course-block choice-block empty-block collapsed" data-units="0" draggable="true">
            <span class="block-number">${number}</span>
            <span class="block-main">
                <button type="button" class="add-elective-button">+ Add elective</button>
                <div class="elective-controls" hidden>
                <select class="block-category" aria-label="Block ${number} category">
                    <option value="">Choose a category</option>
                    ${appState.student.primary_major === "stats-ml" ? '<option value="stats-ml-math">Stats/ML math requirement</option>' : ""}
                    <option value="math">Mathematics</option>
                    <option value="humanities">Humanities</option>
                    <option value="social-sciences">Social Sciences</option>
                    <option value="communication">Communication</option>
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
        const blocks = (semester.course_blocks || []).slice(0, 6);
        const blocksHtml = blocks.map((block, index) =>
            block.locked ? fixedBlock(block, index + 1) : choiceBlock(block, index + 1)
        );
        // Keep five visible semester slots. Unused positions stay compact as
        // "+ Add elective" cards instead of looking like missing requirements.
        while (blocksHtml.length < 5) {
            blocksHtml.push(emptyBlock(blocksHtml.length + 1));
        }

        card.innerHTML = `
            <div class="semester-name">${semester.academic_year_name || "Year"} ${semester.semester}</div>
            <div class="five-course-blocks">${blocksHtml.join("")}</div>
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
                return {
                    hours: metrics?.hours_per_week ?? units / 3,
                    workload: metrics?.workload,
                    difficulty: metrics?.difficulty,
                    stress: metrics?.stress,
                    high: metrics?.intensity === "high_intensity",
                    courseId: block.dataset.courseId
                };
            }).filter(load => load.hours > 0);
            const rated = loads.filter(load => Number.isFinite(load.workload));
            const hours = Math.round(loads.reduce((sum, load) => sum + load.hours, 0));
            const highCourses = loads.filter(load => load.high).map(load => load.courseId);
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
            const response = await fetch(`/api/electives?term=${encodeURIComponent(term)}&category=${encodeURIComponent(category)}`);
            if (!response.ok) throw new Error("Elective catalog unavailable");
            return response.json();
        };
        const setCourseOptions = (courseSelect, electiveData) => {
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
            const currentMajorPrefixes = appState.student.primary_major === "stats-ml"
                ? ["10", "15", "21", "36"] : [];
            const relatedPrefixes = new Set([...goalPrefixes, ...currentMajorPrefixes]);
            const poorRecommendation = /independent study|practicum|reading and research/i;
            const hasAdvancedMath = [...alreadyScheduled, ...appState.student.completed_courses]
                .some(id => /^21-(1[2-9]\d|[2-5]\d\d)$/.test(id));
            const available = electiveData.courses.filter(course => !alreadyScheduled.has(course.id));
            const recommended = available.filter(course =>
                relatedPrefixes.has(course.id.slice(0, 2))
                && course.level >= 100
                && !poorRecommendation.test(course.name)
                && !(hasAdvancedMath && ["21-090", "21-102", "21-108"].includes(course.id))
            );
            const recommendedIds = new Set(recommended.map(course => course.id));
            const other = available.filter(course => !recommendedIds.has(course.id));
            const optionHtml = (course, recommendedCourse = false) =>
                `<option value="${course.id}" data-units="${course.units}" data-term="${course.term}" data-description="${recommendedCourse ? "Recommended for your current and goal programs · " : ""}${course.description}">${recommendedCourse ? "★ " : ""}${course.requirement_group ? `[${course.requirement_group}] ` : ""}${course.id} · ${course.name}</option>`;
            courseSelect.innerHTML = '<option value="" data-units="0">Choose a scheduled undergraduate course</option>' +
                (recommended.length ? `<optgroup label="Recommended for your plan">${recommended.map(course => optionHtml(course, true)).join("")}</optgroup>` : "") +
                `<optgroup label="Other undergraduate courses">${other.map(course => optionHtml(course)).join("")}</optgroup>`;
            courseSelect.disabled = false;
        };

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
                option.dataset.description = course.description;
            });
        }).catch(() => {});

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
                        setCourseOptions(courseSelect, await fetchElectives(event.target.value || "free-elective", cardTerm));
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
                block.dataset.units = option?.dataset.units || block.dataset.units || 0;
                block.dataset.courseId = option?.value || "";
                block.dataset.offeredTerm = option?.dataset.term || "";
                block.querySelector(".block-units").textContent = `${block.dataset.units}u`;
                const description = block.querySelector(".course-description");
                if (description) description.textContent = option?.dataset.description || "";
                updateTotal();
            });
        });
        updateTotal();
        container.appendChild(card);
    }

    let draggedBlock = null;
    const swapBlocks = (source, target) => {
        if (!source || !target || source === target) return;
        if (source.closest(".semester-card") === target.closest(".semester-card")) return;
        const sourceParent = source.parentNode;
        const targetParent = target.parentNode;
        const marker = document.createComment("planner-swap");
        sourceParent.replaceChild(marker, source);
        targetParent.replaceChild(source, target);
        marker.parentNode.replaceChild(target, marker);
        refreshCards();
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
        container.querySelectorAll(".fixed-block[data-course-id]").forEach(block => {
            const courseId = block.dataset.courseId;
            const detail = appState.latestCourseCatalog[courseId] || {};
            const semesterIndex = cards.indexOf(block.closest(".semester-card"));
            const expression = detail.prerequisite_expression;
            const prerequisites = expression?.options?.map(option => option.course_id)
                || detail.prerequisites || [];
            const satisfied = prerequisite => completed.has(prerequisite)
                || (scheduledBefore(prerequisite) >= 0 && scheduledBefore(prerequisite) < semesterIndex);
            const valid = expression?.type === "any_of"
                ? prerequisites.some(satisfied)
                : prerequisites.every(satisfied);
            block.classList.toggle("prerequisite-order-warning", prerequisites.length > 0 && !valid);
            block.title = prerequisites.length > 0 && !valid
                ? `Check prerequisite order: ${prerequisites.join(" or ")}`
                : "Drag to another semester";
        });
        container.querySelectorAll(".empty-block[data-course-id]").forEach(block => {
            const cardTerm = block.closest(".semester-card")
                .querySelector(".semester-name").textContent.toLowerCase().endsWith("fall")
                ? "fall" : "spring";
            const wrongTerm = block.dataset.offeredTerm && block.dataset.offeredTerm !== cardTerm;
            block.classList.toggle("elective-term-warning", wrongTerm);
            const description = block.querySelector(".course-description");
            if (wrongTerm && description) {
                description.textContent = `Not offered in ${cardTerm}. Re-select a course for this semester.`;
            }
        });
    };

    container.querySelectorAll(".planner-course-block").forEach(block => {
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

    // Pointer fallback makes cross-semester rearranging reliable in browsers
    // whose native HTML drag-and-drop is inconsistent. The numbered circle is
    // the drag handle so selects remain easy to use.
    let pointerDraggedBlock = null;
    container.querySelectorAll(".block-number").forEach(handle => {
        handle.addEventListener("mousedown", event => {
            event.preventDefault();
            pointerDraggedBlock = event.currentTarget.closest(".planner-course-block");
            pointerDraggedBlock.classList.add("dragging");
        });
    });
    document.addEventListener("mouseup", event => {
        if (!pointerDraggedBlock) return;
        const target = event.target.closest?.(".planner-course-block");
        pointerDraggedBlock.classList.remove("dragging");
        if (target && container.contains(target)) {
            swapBlocks(pointerDraggedBlock, target);
        }
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
                    '#courseList .course-option input[type="checkbox"]:checked:not(#noCompletedCourses)'
                );


            const completedCourses =
                Array
                    .from(
                        checkedCourses
                    )
                    .map(
                        input =>
                            input.value
                    );

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


                console.error(
                    "Backend error:",
                    errorText
                );


                return;

            }

            // #endregion



            // #region 10E. PARSE RESPONSE
            // ------------------------------------------------

            const data =
                await response.json();

            appState.latestPlan = data;

            renderDegreeAudits(data.degree_audits, data.primary_baseline);

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

            renderPath(
                data.fastest,
                fastestResults
            );


            renderPath(
                data.lower_workload,
                lowerWorkloadResults
            );

            // #endregion



            // #region 10G. PATH SUMMARIES
            // ------------------------------------------------

            document
                .getElementById(
                    "fastestSummary"
                )
                .textContent =
                data.fastest.path.length
                    ? `${data.fastest.path[0].academic_year_name} ${data.fastest.path[0].semester} → ${data.fastest.path.at(-1).academic_year_name} ${data.fastest.path.at(-1).semester}`
                    : "No semesters needed";


            document
                .getElementById(
                    "lowerWorkloadSummary"
                )
                .textContent =
                data.lower_workload.path.length
                    ? `${data.lower_workload.path[0].academic_year_name} ${data.lower_workload.path[0].semester} → ${data.lower_workload.path.at(-1).academic_year_name} ${data.lower_workload.path.at(-1).semester}`
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


function renderDegreeAudits(audits, baseline) {
    const container = document.getElementById("degreeAuditGrid");
    if (!audits) {
        container.innerHTML = "";
        return;
    }
    const primary = audits.primary_degree;
    const goal = audits.selected_goal;
    const goalPercent = goal.total_requirements
        ? Math.min(100, Math.round(goal.requirements_placed / goal.total_requirements * 100))
        : 0;
    container.innerHTML = `
        <article class="degree-audit-card primary-audit-card">
            <p class="eyebrow">PRIMARY DEGREE</p>
            <h3>${primary.program}</h3>
            <strong>${primary.future_semesters_planned} future semesters have a baseline</strong>
            <div class="audit-progress"><span style="width:${Math.min(100, (primary.completed_semesters + primary.future_semesters_planned) / primary.total_semesters * 100)}%"></span></div>
            <p>${primary.planned_primary_units} primary-major units represented in this planning horizon.</p>
            <small>${primary.message}</small>
        </article>
        <article class="degree-audit-card goal-audit-card">
            <p class="eyebrow">${goal.type.replaceAll("_", " ")}</p>
            <h3>${goal.program}</h3>
            <strong>${goal.requirements_placed ?? 0} / ${goal.total_requirements ?? "—"} requirements placed</strong>
            <div class="audit-progress"><span style="width:${goalPercent}%"></span></div>
            <p>${goal.requirements_remaining ?? "—"} requirements remaining.</p>
            <small>${goal.message}</small>
        </article>
        ${baseline?.status === "estimated_template" ? `<p class="audit-disclaimer"><strong>Estimated baseline:</strong> ${baseline.note}</p>` : ""}
    `;
}


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

    if (
        data.fastest.goal_complete
    ) {

        goalStatus.textContent =
            "Course Path Mapped ✓";

    }


    // --------------------------------------------------------
    // Courses still remaining
    // --------------------------------------------------------

    else {
        const remainingCourses = data.fastest.remaining.length;
        const remainingSlots =
            (data.fastest.remaining_program_requirements ?? []).length;
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
    document.getElementById("fastestPathTitle").textContent =
        `🎯 Target-paced ${pathType} Path · by ${["", "Freshman", "Sophomore", "Junior", "Senior"][targetYear]}`;
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
