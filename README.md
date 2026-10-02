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
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# Git Bash / WSL:         source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open http://localhost:8000/healthz — it should return
`{"status": "ok", "service": "job-tracker"}`. (Local dev serves on port 8000;
the Docker setup below exposes 8090.)

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
