# DQA Monitoring — backend

Small FastAPI service that turns the `dbt_reports` / `dqa_pipeline` BigQuery
datasets into the few endpoints the dashboard needs. No database of its own —
it queries BigQuery (with a short TTL cache) or, in mock mode, an in-memory
generated dataset.

## Run it

```bash
cd backend
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for interactive API docs.

## Pointing it at real BigQuery

1. `gcloud auth application-default login` (one-time; opens a browser).
2. In `.env`, set `USE_MOCK_DATA=false` (this is already the default).
3. Confirm `GCP_PROJECT_ID` / `BQ_REPORTS_DATASET` / `BQ_RAW_DATASET` in `.env`
   match your environment (defaults are `langx-production` / `dbt_reports` /
   `dqa_pipeline`, matching the existing `data-pipeline` dbt project).

If you'd rather run against generated fake data (no GCP access needed, e.g.
for a demo or working offline), set `USE_MOCK_DATA=true` instead.

## Endpoints

| Endpoint | Backs |
|---|---|
| `GET /api/overview?date_from&date_to` | Overview page: business session KPIs (from `v_dialogs_business_*`) + DQA KPIs, charts |
| `GET /api/issues?date_from&date_to&type=&severity=&search=&page=&page_size=` | Issues feed, unified from 4 sources - see `app/data/issues.py` |
| `GET /api/dialogs?...` | Paginated/sortable dialog table |
| `GET /api/dialogs/{dialog_id}` | Single dialog: metadata, CEFR sub-scores, transcript, latency telemetry |

## Adding a new issue source

Issues are normalized from whatever dbt report model detects them into one
shape: `{id, type, severity, occurred_at, dialog_id, uid, scenario_id, title,
description, details}`. To add one:

1. Write (or point at an existing) dbt model that flags the problem.
2. In `app/data/issues.py`, add a `_fetch_x(settings, date_from, date_to)`
   function that queries it and returns the normalized shape.
3. Append it to `fetch_real_issues`.
4. Optionally add matching mock generation in `app/data/mock_store.py` so it
   shows up in `USE_MOCK_DATA=true` mode too.

## Caching

`app/cache.py` is a tiny in-process TTL cache (`CACHE_TTL_SECONDS`, default
300s) wrapping the BigQuery-hitting functions. dbt refreshes `dbt_reports`
hourly, so there's no point re-querying more often than that — raise the TTL
if you want fewer BigQuery jobs, lower it if you want fresher data sooner
after a manual dbt run.
