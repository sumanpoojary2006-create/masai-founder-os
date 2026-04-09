# Masai Founder OS

Masai Founder OS is a deployable AI operations system for a Masai-style education company. It is built around one CEO agent, real department queues, a persistent SQLite database, and a live multi-page web dashboard.

This is no longer a static demo. The app now:

- stores company records in SQLite
- stores tasks, task events, and company memory in SQLite
- mutates real records when departments complete work
- recovers unfinished work after a restart
- exposes live operational state through the web UI and JSON API

## What "Actual Working AI Company" Means Here

The system models a real operating loop:

1. A founder submits work from the dashboard.
2. The CEO agent classifies and routes it to the correct team.
3. The task enters a live queue with priority and backlog ordering.
4. Department workers pick up tasks based on capacity.
5. The department agent generates an execution response with OpenRouter.
6. The backend applies a real database-side action to company records.
7. The CEO closes the loop and stores the final outcome in memory.

Examples of real data changes:

- `Sales` updates lead follow-up status and notes.
- `Ops` updates cohort readiness and operating notes.
- `Curriculum` updates module review status and quality notes.
- `Accounts` updates payment and refund workflow state.
- `Tech` updates incident ownership and status.

## Departments

- `Sales`
- `Ops`
- `Curriculum`
- `Accounts`
- `Tech`

Each department has:

- worker capacity
- live backlog queue
- active workload tracking
- completion and failure metrics
- average cycle-time tracking

## Database Model

The SQLite database includes real business records and operational logs:

- `leads`
- `cohorts`
- `students`
- `payments`
- `curriculum_modules`
- `tech_incidents`
- `tasks`
- `task_events`
- `memory_entries`

The app seeds realistic Masai-style starter data on first boot so the system has real records to operate on immediately.

## Live Task States

- `triage`
- `queued`
- `in_progress`
- `ceo_review`
- `completed`
- `failed`

## Website Pages

- `/` for the founder overview and live company snapshot
- `/teams` for department-by-department workload and database records
- `/workflow` for task lifecycle visibility
- `/dashboard` for the full operating console, live queue management, and task details

## Project Structure

```text
.
├── .github/workflows/python-check.yml
├── .gitignore
├── Dockerfile
├── render.yaml
├── AI_Company_Simulator_Colab.ipynb
└── ai_company/
    ├── main.py
    ├── webapp.py
    ├── config.py
    ├── llm.py
    ├── requirements.txt
    ├── agents/
    │   ├── manager.py
    │   ├── sales.py
    │   ├── ops.py
    │   ├── curriculum.py
    │   ├── accounts.py
    │   └── tech.py
    ├── core/
    │   ├── company.py
    │   ├── database.py
    │   ├── memory.py
    │   └── router.py
    ├── utils/
    │   └── prompts.py
    └── web/
        ├── index.html
        ├── teams.html
        ├── workflow.html
        ├── dashboard.html
        ├── styles.css
        ├── overview.js
        └── app.js
```

## Local Setup

### 1. Install Python

Use Python 3.10+.

### 2. Install dependencies

From inside the `ai_company` folder:

```bash
pip install -r requirements.txt
```

### 3. Save your API key once

You do not need to export the key on every run anymore.

At the repository root, copy [`.env.example`](/Users/inno/Desktop/MINI%20COMPANY/.env.example) to a new file called `.env.local`:

```bash
cp .env.example .env.local
```

Then open `.env.local` and replace:

```text
OPENROUTER_API_KEY=replace_with_your_openrouter_key
```

with your real key.

The app now auto-loads `.env.local` on startup.

Important:

- keep `.env.local` on your machine only
- do not commit or share it
- if you change the key, restart the server

### 4. Start the app

From inside the `ai_company` folder:

```bash
python webapp.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

If port `8000` is busy:

```bash
AI_COMPANY_PORT=8001 python webapp.py
```

## Environment Variables

- `OPENROUTER_API_KEY`: required for live AI task execution
- `DATABASE_URL`: hosted Postgres connection string for free cloud deployment
- `AI_COMPANY_HOST`: server bind host, defaults to `127.0.0.1`
- `AI_COMPANY_PORT`: server port, defaults to `8000`
- `AI_COMPANY_DB_PATH`: SQLite database path, defaults to `masai_founder_os.db`
- `AI_COMPANY_WORKFLOW_DELAY`: optional UI/demo pacing for workflow transitions

For local development, these can live in `.env.local`.
For Render and Docker, keep using platform environment variables.
If `DATABASE_URL` is set, the app uses hosted Postgres. If not, it falls back to local SQLite.

## Running with Docker

From the repository root:

```bash
docker build -t masai-founder-os .
docker run -p 8000:8000 \
  -e OPENROUTER_API_KEY="your_api_key_here" \
  -e DATABASE_URL="your_postgres_connection_string" \
  masai-founder-os
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Deploying on Render

This repository includes `render.yaml` and a `Dockerfile`.

### Deploy flow

1. Push this repository to GitHub.
2. Create a free Postgres database in Render.
3. Copy its external database URL.
4. In Render, create a new Blueprint deployment from the GitHub repo.
5. Render will read `render.yaml`.
6. Add `OPENROUTER_API_KEY` as a secret environment variable.
7. Add `DATABASE_URL` using the Render Postgres connection string.
8. Deploy and open the service URL.

This keeps the backend fully free for short-lived demos while preserving real company data in a hosted database.

## Deploying the Frontend on Vercel

Vercel is a good fit for the static frontend, but not for the current Python backend.

Why:

- Vercel Python runs as Functions, not as a long-lived threaded server.
- The backend here relies on background workers, in-process queues, and a persistent SQLite file.
- Vercel's own docs say SQLite is not supported there because local storage is ephemeral.

Useful references:

- [Vercel runtimes](https://vercel.com/docs/functions/runtimes)
- [Is SQLite supported in Vercel?](https://vercel.com/kb/guide/is-sqlite-supported-in-vercel)
- [Vercel rewrites](https://vercel.com/docs/edge-network/rewrites)

### Recommended split deployment

1. Deploy the real backend on Render using [`render.yaml`](/Users/inno/Desktop/MINI%20COMPANY/render.yaml).
2. Deploy the static frontend on Vercel using [`vercel.json`](/Users/inno/Desktop/MINI%20COMPANY/vercel.json).
3. Point the Vercel frontend at the backend URL by editing [`vercel-config.js`](/Users/inno/Desktop/MINI%20COMPANY/ai_company/web/vercel-config.js):

```js
window.MASAI_API_BASE_URL = "https://your-backend-host.onrender.com";
```

4. Commit that change and deploy to Vercel.

The backend now sends CORS headers, so the Vercel-hosted frontend can call it directly.

## GitHub Automation

The repository includes a GitHub Actions workflow:

- `.github/workflows/python-check.yml`

It installs dependencies and runs Python syntax compilation on every push and pull request.

## JSON API

Main runtime endpoints:

- `GET /health`
- `GET /api/state`
- `POST /api/tasks`
- `POST /api/tasks/<task_id>/priority`
- `POST /api/tasks/<task_id>/retry`

## Sample Founder Requests

- `Write a follow-up plan for webinar leads in Bangalore who have not applied yet.`
- `Prepare an ops checklist for the next full stack cohort launch.`
- `Review the backend APIs module because students are struggling in assessments.`
- `Handle a refund review for a learner who deferred after paying the full fee.`
- `Investigate why the student dashboard slows down during assignment submissions.`

## Notes

- The backend is Python standard library plus `requests`.
- SQLite gives the app real persistence without introducing extra services.
- Department outputs still depend on a valid OpenRouter key for live AI execution.
- If OpenRouter is unavailable, routing still falls back to heuristics, but department answer quality will degrade.

## Next Strong Upgrades

- add authentication and founder accounts
- add manual reassignment between departments
- add SLA breach alerts and escalations
- add audit exports and CSV download
- add placement and student success teams
