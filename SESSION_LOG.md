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

## Session 1 — 2026-10-01
- What was done:
  - Pinned `sqlalchemy==2.1.1` in `requirements.txt`.
  - Added `app/models.py`: `Base(DeclarativeBase)`, a naive-UTC `utc_now()` helper (§7), and the two tables from PLAN.md §4 — `applications` (all fields incl. PDF path/file-name columns; `status` mirrored with a DB-level CHECK constraint built from `config.STATUSES`) and `status_events` (`from_status` nullable for the creation event, `to_status`, `changed_at`; FK to applications with `ondelete="CASCADE"` + index). `Application.events` relationship uses `cascade="all, delete-orphan"` and is ordered by `(changed_at, id)`.
  - Added `app/db.py`: `db_file(data_dir)`, `create_db_engine(data_dir)` (creates the directory if missing; builds a cross-platform SQLite URL via `Path.as_posix()`), per-connection pragmas through an event listener — `journal_mode=WAL` (§7 crash-safety), `busy_timeout=5000`, and **`foreign_keys=ON`** (SQLite ignores FK constraints by default; this is what makes the ON DELETE CASCADE actually fire) — plus `make_session_factory(engine)` with `expire_on_commit=False`, a lazily-created app-wide engine/factory (`get_db_engine()` / `get_session_factory()`) so importing app modules has no disk side effects, an `open_session()` context manager for request-scoped sessions, and idempotent `init_db()`.
  - Wired `init_db()` into startup: `app/main.py` now builds `FastAPI(..., lifespan=lifespan)` where the lifespan calls `init_db()`. Static-file mounting stays deferred to S3 (comment left in place).
  - Added `app/repo.py`, the only layer that writes rows (§4 rules):
    - `create_application(session, *, company, job_title, applied_on, ...)` — always starts at "received" and writes exactly one `NULL → received` event in the same transaction; an explicit non-"received" status input raises loudly.
    - `update_application(session, application_id, **fields)` — omitted key = unchanged, `None` clears nullable columns (required columns raise), a changed status appends exactly one from/to event and mirrors into `applications.status`, setting the same status appends nothing, `updated_at` always bumps; unknown fields → TypeError, invalid statuses / clearing required columns → ValueError, all validated before any write.
    - `get_application`, `list_applications` (shared filter predicate: company exact match, statuses set on current status, inclusive applied_on range, empty = all; ordered newest first by applied_on then id), `get_status_events(application_id)` oldest-first, `get_status_events_for_filter(...)` returning full event histories of only the filtered applications in deterministic `(application_id, changed_at, id)` order — ready for S2 timelines, S4 Sankey and S5 events.csv.
    - `delete_application` → True/False; events cascade (ORM delete-orphan + DB FK CASCADE backstop). PDF file removal is deliberately NOT here (S2's concern).
  - Added `tests/test_data.py`: 21 tests against throwaway SQLite databases under pytest `tmp_path` covering creation fields/defaults, the single initial event, full lifecycle chains, no-op status updates, non-status edits + updated_at bump, validation-before-write, DB-level CHECK rejection via raw ORM insert, cascade delete with orphan check, all filter-predicate cases incl. inclusive date bounds and combined filters, events-for-filter ordering, WAL journal mode, and per-connection `foreign_keys=ON`.
  - README: fixed the Windows Git Bash venv activation path (it's `.venv/Scripts/activate`, not `bin`) and added a short Project status section.
- Commits: 4c2d69c "Add SQLAlchemy models for applications and status_events" (Type: feature, includes the sqlalchemy==2.1.1 pin), de94b83 "Add DB engine, session factory and init_db wired into app lifespan" (Type: feature), 0075f82 "Add repository functions enforcing status event rules" (Type: feature), f5ab72e "Add temp-database test suite for the data layer" (Type: feature); this log entry is the session's final commit.
- Test/build status: `pytest` → 22 passed, 1 warning (pre-existing Starlette/httpx deprecation notice from S0, not a failure). `docker build -t job-tracker .` passes with the new requirements. No stray directories created by tests/imports — verified no repo-local `data/` and no drive-root `/app/data` after runs.
- Open issues: none
- Notes for next session (S2): sessions are passed explicitly to every repo function — request handlers should use `with open_session() as s:` from `app.db`. `create_application` accepts-but-rejects a non-"received" status (the create form may simply not pass it). Uploads per §7: store PDFs under `<DATA_DIR>/uploads/<id>/{resume,application}.pdf`, keep the original file name in the resume_file_name/application_file_name columns, enforce MAX_UPLOAD_MB and content-type validation at the API layer; when a new file replaces an old one (and on delete) remove the stale files from disk — repo functions never touch the filesystem. `updated_at`/event timestamps are naive UTC; render as plain dates per §7.
