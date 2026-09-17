# DQA Monitoring app

Observability dashboard for the DQA data pipeline: replaces the Looker Studio
"sessions overview" report and adds a unified **Issues** feed that Looker
Studio couldn't really do — CEFR score drift, system repetition loops,
self-answered questions, and per-dialog quality flags, all in one filterable
list that links straight to the dialog.

```
dqa_monitoring/
├── backend/    FastAPI - queries BigQuery, small REST API. See backend/README.md
├── frontend/   React + Vite + Tailwind + Recharts. See frontend/README.md
└── docker-compose.yml
```

## Quickest way to look at it (no GCP setup needed)

```bash
cd backend && uv sync && cp .env.example .env
# edit .env: set USE_MOCK_DATA=true
uv run uvicorn app.main:app --reload --port 8000 &

cd ../frontend && npm install && npm run dev
```

Open http://localhost:5173 - fully interactive with realistic generated data.

## Running against real data

1. `gcloud auth application-default login`
2. `backend/.env`: leave `USE_MOCK_DATA=false` (the default) - it reads
   `langx-production.dbt_reports` / `.dqa_pipeline` directly.
3. Same two run commands as above.

See `backend/README.md` for the full env var list and `frontend/README.md`
for the page-by-page tour.

## What feeds this, and one thing worth knowing

Sessions/business KPIs come from `dbt_reports.v_dialogs_business_daily_dashboard`
and `.._monthly_dashboard`; dialogue-quality data (turns, latency, CEFR,
network) comes from the existing `dqa_dbt` report models
(`rpt_practice_vs_evaluation`, `rpt_dialogs_with_cefr_and_dqa`,
`rpt_user_score_drift`, `rpt_system_loops_weekly`, `rpt_system_self_answers`)
in `../data-pipeline/dqa_dbt`.

`v_dialogs_business_base` (which the two dashboard views above roll up) used
to be a hand-created BigQuery **view** that re-ran a live Cloud SQL join +
JSON parsing on every single read - a plain `COUNT(*)` took 6-7s. It's now a
dbt-managed **table**, refreshed hourly alongside the rest of `dbt_reports`
(see `../data-pipeline/dqa_dbt/dqa_dbt/models/report/v_dialogs_business_base.sql`)
so every reader - this dashboard, Looker Studio, ad-hoc queries - hits a
static snapshot instead. That dbt project needs a `dbt run` (and,
before that, the same `gcloud auth application-default login` above) for the
new table to actually exist in BigQuery.

## Adding a new report / issue type

- A new **chart or KPI**: add a query function in `backend/app/data/`, return
  it from `get_overview`, render it in `frontend/src/pages/Overview.tsx` with
  the existing `ChartCard`/`StatTile`/`TimeSeriesChart` components.
- A new **issue source** (another dbt model that flags a problem): see
  "Adding a new issue source" in `backend/README.md`.

## Deploying

Both halves are plain containers (`backend/Dockerfile`, `frontend/Dockerfile`)
with no built-in assumption about where they run - `docker-compose up` runs
both locally; the same images deploy to Cloud Run, Render, Fly.io, or
anywhere else that runs a container, with real BigQuery access via a service
account (`BigQuery Data Viewer` + `BigQuery Job User` roles are enough - this
app only reads). No login/auth is built into the frontend itself; put it
behind whatever access control your hosting choice offers if it needs to be
reachable outside your own machine.
