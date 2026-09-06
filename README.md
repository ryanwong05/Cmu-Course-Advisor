# CMU Course Advisor

An academic path-planning tool that helps Carnegie Mellon students compare programs, understand tradeoffs, and build feasible semester-by-semester plans around their goals.

Traditional degree-audit tools answer **“What do I need to graduate?”** CMU Course Advisor is being built to answer a broader question:

> Given where I am now and where I want to go, what should I do next—and why?

## Project status

This repository is an actively developed prototype. The current application supports structured planning for selected CMU academic paths, while broader catalog coverage and the AI explanation layer are still in progress.

Current capabilities include:

- capturing a student's college, major, year, completed coursework, and planning constraints;
- comparing internal-transfer, additional-major, and minor paths for selected SCS programs;
- generating semester-by-semester plans from verified requirements and prerequisites;
- identifying critical prerequisite chains and potential scheduling delays;
- estimating semester workload using available course metrics;
- accounting for baseline college requirements, unit limits, and overlapping coursework; and
- presenting alternative paths such as fastest completion and lower-workload options.

The planning engine is deterministic: official and structured academic data—not an LLM—is intended to remain the source of truth. AI will be used for interpreting goals and explaining verified results.

## Product direction

The long-term product loop is:

```text
Discover → Compare → Decide → Plan → Execute → Checkpoint → Re-plan
```

The goal is to develop a system that can compare paths such as:

- transferring into another program;
- remaining in a current major while adding a minor or additional major;
- choosing coursework that supports a target field such as AI or robotics; and
- balancing completion time, workload, flexibility, and opportunity cost.

## Architecture

```text
CMU official data
        ↓
Raw and scraped datasets
        ↓
Cleaning and validation pipeline
        ↓
Processed course knowledge base
        ↓
Deterministic planning engine
        ↓
FastAPI backend
        ↓
Web frontend
```

Repository layout:

```text
app.py                 Stable ASGI entry point
Backend/               FastAPI application and backend services
Engine/                Requirements, availability, workload, and path logic
Data/raw/               Unmodified source datasets
Data/scraped/           Direct outputs from CMU source collection
Data/processed/         Validated datasets used by the application
Data/reference/         Department mappings and other reference data
Data/legacy/            Imported legacy database retained for migration
Scripts/                Scraping and data-ingestion utilities
static/                 Current browser application
tests/                  Planning and scraper tests
```

## Data model

The project is integrating three complementary sources of course information:

1. **Course catalog data** — course descriptions, units, departments, and prerequisites.
2. **Schedule of Classes data** — term-specific offerings, sections, times, and locations.
3. **Faculty Course Evaluation data** — historical workload and course/instructor ratings where available.

Raw source files are preserved separately from processed application data so that cleaning is reproducible and future CMU updates can be incorporated without overwriting source history.

## Running locally

Requirements:

- Python 3.10 or newer
- dependencies listed in `requirements.txt`

Create and activate a virtual environment, then install the dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

Start the application:

```bash
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000` in a browser.

## API endpoints

The current backend exposes:

- `GET /api/programs`
- `GET /api/programs/{program_id}/{goal_type}`
- `POST /api/program-comparison`
- `GET /api/baseline`
- `POST /api/baseline`
- `POST /api/plan`

FastAPI's interactive API documentation is available at `http://127.0.0.1:8000/docs` while the server is running.

## Tests

Run the current test suite with:

```bash
python -m unittest discover -s tests -v
```

## Roadmap

- normalize the imported course, section, and FCE datasets into a stable schema;
- attach explicit academic terms and years to course offerings;
- refresh Schedule of Classes data from CMU sources;
- add current catalog descriptions and prerequisite expressions;
- expand verified degree, major, minor, and transfer requirements;
- improve ranking and path comparison using workload and historical outcomes;
- add an AI layer for natural-language constraints and grounded explanations; and
- add persistent student plans, checkpoints, and re-planning.

## Authorship and acknowledgments

**Creator and lead developer:** [Ryan Wong](https://github.com/ryanwong05)

Special thanks to **[Stephen Xu](https://github.com/StDoses72)** for providing the initial CMU course schedule and Faculty Course Evaluation datasets, along with foundational data-ingestion and SQLite tooling. These contributions established an important data foundation for the project.

The academic-planning product, planning engine, application architecture, backend integration, and frontend experience are developed and maintained by Ryan Wong unless otherwise indicated in the repository history.

## Disclaimer

CMU Course Advisor is an independent student project and is not affiliated with or endorsed by Carnegie Mellon University. Academic requirements, course offerings, prerequisites, policies, and schedules can change. Students should verify important decisions using current university sources and consult their academic advisor.

## License

A project license has not yet been selected. Before making the repository public, add a license that is compatible with the permissions and attribution requirements of all incorporated code and datasets.
