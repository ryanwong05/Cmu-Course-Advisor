const step1 = document.getElementById("step1");
const step2 = document.getElementById("step2");
const step3 = document.getElementById("step3");
const results = document.getElementById("results");

const semesterResults =
    document.getElementById("semesterResults");


function showScreen(screen) {

    step1.classList.add("hidden");
    step2.classList.add("hidden");
    step3.classList.add("hidden");
    results.classList.add("hidden");

    screen.classList.remove("hidden");

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}


document
    .getElementById("step1Next")
    .addEventListener("click", () => {

        showScreen(step2);

    });


document
    .getElementById("step2Back")
    .addEventListener("click", () => {

        showScreen(step1);

    });


document
    .getElementById("step2Next")
    .addEventListener("click", () => {

        showScreen(step3);

    });


document
    .getElementById("step3Back")
    .addEventListener("click", () => {

        showScreen(step2);

    });


document
    .getElementById("restartButton")
    .addEventListener("click", () => {

        showScreen(step1);

    });


document
    .getElementById("generateButton")
    .addEventListener("click", async () => {

        const checkedCourses =
            document.querySelectorAll(
                '.course-option input[type="checkbox"]:checked'
            );

        const completedCourses =
            Array.from(checkedCourses)
                .map(input => input.value);


        const requestBody = {

            completed_courses: completedCourses,

            goal: "cs-transfer",

            start_semester:
                document.getElementById("semester").value,

            max_units:
                Number(
                    document.getElementById("units").value
                )

        };


        const response =
            await fetch("/api/plan", {

                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body:
                    JSON.stringify(requestBody)

            });


        const data =
            await response.json();
        
        const insightTitle =
            document.getElementById("insightTitle");
        
        const insightText =
            document.getElementById("insightText");

        if (data.explanation) {

    const explanation = data.explanation;

    insightTitle.textContent =
        `Your critical next course is ${explanation.critical_course}.`;

    let text =
        `${explanation.critical_course} currently has the biggest impact on your path.`;


    if (
        explanation.unlocks &&
        explanation.unlocks.length > 0
    ) {

        text +=
            ` It directly unlocks ${explanation.unlocks.join(", ")}.`;

    }


    if (
        explanation.delay_if_skipped !== null &&
        explanation.delay_if_skipped > 0
    ) {

        text +=
            ` Delaying it may delay this path by ${explanation.delay_if_skipped} semester(s).`;

    }


    insightText.textContent = text;

}
else {

    insightTitle.textContent =
        "No critical next course found.";

    insightText.textContent =
        "You may already have completed the key prerequisites for this path.";

}


        semesterResults.innerHTML = "";


        for (const semester of data.path) {

            const card =
                document.createElement("div");

            card.className = "semester-card";


            const coursesHtml =
                semester.courses
                    .map(course => `
                        <div class="course">
                            ${course}
                        </div>
                    `)
                    .join("");


            card.innerHTML = `

                <div class="semester-name">
                    Semester ${semester.semester_number}
                    ·
                    ${semester.semester}
                </div>

                ${coursesHtml}

                <div class="units">
                    ${semester.units} goal units
                </div>

            `;


            semesterResults.appendChild(card);

        }


        const goalStatus =
            document.getElementById("goalStatus");


        if (data.goal_complete) {

            goalStatus.textContent =
                "Requirements mapped ✓";

        } else {

            goalStatus.textContent =
                `${data.remaining.length} courses remaining`;

        }


        showScreen(results);

    });