# Job Application Tracker

A single-user, LAN-hosted web app that keeps a living record of every job
application: what was applied for, when, with which documents (resume + full
application PDF), and how it progressed through the status lifecycle
(received → interviewing → offer/accepted/rejected/ghosted) — all viewable in
one dashboard with a waiting queue, Sankey funnel, status pie chart, filters,
and CSV export. The complete design lives in [PLAN.md](PLAN.md).

## Local development

```bash
python -m venv .venv
# Windows (PowerShell):    .venv\Scripts\Activate.ps1
# Windows (Git Bash):      source .venv/Scripts/activate
# WSL / Linux / macOS:     source .venv/bin/activate
pip install -r requirements.txt
# Point live state at ./data in the repo. Without it, DATA_DIR defaults to
# /app/data — fine inside Docker, but on a local Windows machine Python
# resolves that against your system drive (e.g. C:\app\data), not the repo.
set DATA_DIR=./data              # Git Bash / WSL / macOS
$env:DATA_DIR = "./data"         # PowerShell
uvicorn app.main:app --reload
```

Then open http://localhost:8000/healthz — it should return
`{"status": "ok", "service": "job-tracker"}`. (Local dev serves on port 8000;
the Docker setup below exposes 8090.)

## Project status

Session 1 delivered the data layer: SQLAlchemy models for `applications` and
the append-only `status_events` history (`app/models.py`), a SQLite engine
with WAL + foreign keys enabled (`app/db.py`, tables created at startup via a
FastAPI lifespan), and repository functions that enforce all of PLAN.md §4's
status-event rules (`app/repo.py`).

Session 2 adds the application API: server-rendered create/detail/update/
delete pages with multipart PDF uploads for resume + full application
(`app/routes/applications.py`, minimal placeholder templates in
`app/templates/` that Session 3 will rebuild as the dashboard), upload
validation and storage under `<DATA_DIR>/uploads/<id>/<kind>.pdf`
(`app/uploads.py`) — extension, magic bytes and a 15 MB cap are all checked
before anything touches disk — plus PDF downloads that serve stored files
under their original names. Every status change appends exactly one
`status_events` row; deleting an application removes its history rows and
both stored files.

Everything is covered by temp-database test suites (`tests/test_data.py`,
`tests/test_api.py`). The dashboard layout, charts, waiting queue, filters,
CSV/JSON export and static assets are the later sessions — see
[PLAN.md](PLAN.md) §11 for the plan and [SESSION_LOG.md](SESSION_LOG.md) for
what each session shipped.

## Run tests

```bash
pytest
```

## Docker

```bash
docker compose up --build
```

The container builds locally and reports **healthy** via its `/healthz`
healthcheck, then open http://localhost:8090/healthz. Set `PORT` in the
environment to override the host-side port (default 8090). The same file
works unchanged on Windows/WSL (Docker Desktop) and on a Raspberry Pi — all
paths are relative to the repo root (§2, §8 of PLAN.md).

## Runtime data

Live state (SQLite database + uploaded PDFs) lives in `./data` at the repo
root. It is gitignored but bind-mounted into the container at `/app/data`, so
it survives rebuilds and restarts — copying that directory is the backup
recipe (§2, §7 of PLAN.md).
