# Session Log

Chronological log of sessions that have touched this repo. Each session ends by appending an entry here — what changed, open issues, notes for the next session — before its final commit (see `PLAN.md` §9).

## Session -1 — Initial architecture brief (2026-07-08)
**Role:** Architecture definition only; no application code was written.

**Changed:**
- Initialized this git repo at `coding-projects/job-tracker` (per-project convention, sibling to `pricehawk`).
- Added `prompts/` with the verbatim original request (`session--1.md`) plus a README documenting session conventions and run protocol.
- Established `.gitignore` and commit conventions with the mandatory trailing `Type:` footer (mirrored from pricehawk §10).
- Wrote `PLAN.md`: single-container FastAPI + SQLite architecture, data model with append-only status history (Sankey source of truth), API/page design, dashboard spec (waiting queue, Sankey, pie chart, whole-dashboard filters), PDF upload & persistence rules, docker-compose deployment to a Raspberry Pi over the LAN, testing gates, and a 7-session build plan (§11).

**Open issues:** None blocking; see `PLAN.md` §13.

**Notes for next session:** Start at Session 0 per the protocol in `PLAN.md` §11.

## Session -0.5 — Create build-session prompts (2026-07-09)
**Role:** Prompt creation only; no application code was written.

**Changed:**
- Wrote self-contained prompt files `prompts/session-0.md` … `prompts/session-6.md`, one per build session in PLAN.md §11, mirroring the pricehawk prompts format (start-here checks, where-we-are context, deliverables keyed to PLAN sections, hard rules, definition of done, commit order, finish protocol).
- Appended this session's verbatim request to `prompts/session--1.md` (its own file name would have been awkward under the integer convention).
- Updated the index in `prompts/README.md` with all build sessions.

**Open issues:** None blocking; see PLAN.md §13 for known constraints and risks.

**Notes for next session:** All prompts now exist. Start at **Session 0** — read `PLAN.md`, then `prompts/session-0.md`.

## Session 0 — 2026-10-01
- What was done:
  - Created `app/` package: `config.py` (DATA_DIR env-overridable, default `/app/data`; MAX_UPLOAD_MB=15; STATUSES/WAITING_STATUSES per §4.1; STATUS_COLORS for dashboard badges) and `main.py` with a `create_app()` factory exposing GET /healthz → {"status":"ok","service":"job-tracker"}.
  - Pinned `requirements.txt` (fastapi==0.142.2, uvicorn[standard]==0.54.0, jinja2==3.1.6, httpx==0.28.1, pytest==9.1.1) and added a TestClient smoke test for /healthz (`tests/test_health.py`).
  - Added `Dockerfile` (python:3.12-slim multi-arch, pinned pip install in its own layer, DATA_DIR=/app/data, EXPOSE 8000, urllib-based HEALTHCHECK since slim has no curl) and `docker-compose.yml` (${PORT:-8090}:8000, ./data:/app/data bind mount, restart: unless-stopped, healthcheck interval 30s / timeout 5s / retries 3).
  - Added README stub: project summary linking PLAN.md plus local-development (venv + uvicorn --reload), run-tests (pytest) and Docker (compose up --build → localhost:8090/healthz) quickstarts, with a note that runtime data lives in ./data.
- Commits: 07e0139 "Scaffold FastAPI app with /healthz and config module" (Type: chore), a705b78 "Pin dependencies and add health smoke test" (Type: test), 0b6c150 "Add Docker skeleton with stdlib healthcheck" (Type: chore), 1a8f57a "Add README stub with quickstart and Docker instructions" (Type: docs); this log entry is the session's final commit.
- Test/build status: pytest 1 passed; docker build ok — `docker compose up --build` reached healthy and http://localhost:8090/healthz returned {"status":"ok","service":"job-tracker"} (stack torn down afterwards).
- Open issues: none
- Notes for next session (S1): config variable names/defaults live in app/config.py — DATA_DIR (env-overridable, default "/app/data"; use ./data locally), MAX_UPLOAD_MB=15, STATUSES/WAITING_STATUSES/STATUS_COLORS. Build the DB init as a lifespan context manager on the FastAPI(...) call inside create_app() and mount static files at the bottom of that factory — both spots are marked with S1/S3 comments in app/main.py. Docker healthcheck is a Python-stdlib urllib one-liner; keep this approach when hardening in S6 (compose quirk: its test list needs the ["CMD", ...] prefix, while the bare JSON array form only works inside the Dockerfile HEALTHCHECK instruction).
