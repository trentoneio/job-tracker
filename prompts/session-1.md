# Session 1 Prompt — Data Layer (Models, DB Init, Repository)

**Project:** Job Application Tracker — single-user, LAN-hosted job application tracker.
**Repo root:** `C:\Users\Trenton\coding-projects\job-tracker`
**Shell paths:** may be Git Bash/MSYS2 (`/c/Users/Trenton/coding-projects/job-tracker`) or WSL (`/mnt/c/Users/Trenton/coding-projects/job-tracker`) — detect with `ls /c` vs `ls /mnt/c`.

You are starting fresh with **no memory of previous sessions**. The only prior state is this repository and this `prompts/` directory.

## Start here (do these first, in order)
1. `cd` into the repo root. Run:
   - `git log --oneline -25` — expected to end with Session 0 commits (FastAPI scaffold + config module, pinned deps + health test, Dockerfile/compose skeleton, README). If not, **stop and report**.
   - `git status` — must be clean.
   - Read `PLAN.md` in full (canonical requirements), then the tail of `SESSION_LOG.md`, then this file.
2. Baseline: create venv (`python -m venv .venv && source .venv/bin/activate`), install deps, run `pytest` — must be green **before** you change anything.

## Where we are
Session 0 is done: the repo has a runnable FastAPI skeleton (app factory + `/healthz`), config constants in `app/config.py` (including the status vocabulary per §4.1), pinned dependencies, working Dockerfile/compose on WSL, README stub, and SESSION_LOG entries for sessions -1 and 0. Your job is to build the persistence layer that everything else reads/writes — per **PLAN.md §2, §4, §7**.

## Your job this session (deliverables)

### 1. Dependencies
- Add **SQLAlchemy 2.x** (pinned) to `requirements.txt`. Nothing else new needed.

### 2. `app/db.py`
- Engine creation from the configured `DATA_DIR` (create the directory if missing); a session factory; an `init_db()` function that creates all tables.
- SQLite pragmas on connect: `journal_mode=WAL` and a sane `busy_timeout` (§7) — via a connect event listener so every connection gets them.
- Wire `init_db()` into the FastAPI lifespan in `app/main.py` so any app start guarantees tables exist (dev runs honor the env-overridden `DATA_DIR`, e.g. `./data`).

### 3. `app/models.py` — SQLAlchemy 2.0 style (`DeclarativeBase`, `Mapped[...]`)
Per **PLAN.md §4**, two tables:

**applications**
- `id` INTEGER PK; `company` TEXT NOT NULL; `job_title` TEXT NOT NULL; `reference_number` TEXT nullable; `applied_on` DATE NOT NULL;
- `status` TEXT NOT NULL, default `received`, with a CHECK constraint against the `STATUSES` set in `app/config.py`;
- `job_posting_url` TEXT nullable; `notes` TEXT nullable;
- `resume_pdf` / `application_pdf` TEXT nullable — relative paths under `data/uploads/<id>/` — **plus** columns storing the original file names (e.g. `resume_file_name`, `application_file_name`) used for display/download naming (§7); storage names stay stable, originals are metadata;
- `created_at`, `updated_at` TIMESTAMP UTC ISO-8601.

**status_events** (append-only history — the Sankey source of truth)
- `id` INTEGER PK; `application_id` FK → applications.id with ON DELETE CASCADE;
- `from_status` TEXT nullable (NULL on the initial event); `to_status` TEXT NOT NULL;
- `changed_at` TIMESTAMP UTC, default now; index on `application_id`.

Add a relationship where it helps (application ↔ its events).

### 4. `app/repo.py` — repository functions
Small function set that later sessions (API in S2, dashboard in S3, exports in S5) call instead of fiddling with sessions directly:
- `create_application(...) -> Application` — inserts the row **and** appends exactly one status event (`from_status NULL → to_status "received"`) in the same transaction (§4 rules). Creating always starts at `received`, regardless of inputs.
- `get_application(id)`, and a listing/filtering helper taking optional `company`, `statuses` (set/list), `date_from`, `date_to` — **all params optional; empty = all applications**. This one shared predicate is used by the dashboard render, both CSV endpoints (§5 "export what you're looking at"), and tests.
- `update_application(id, ...)` — edits fields; if `status` changed: append exactly one event AND update `applications.status` to mirror the latest event. No event when only non-status fields change. Always bumps `updated_at`.
- `delete_application(id)` — deletes the row and cascades its events (file cleanup is S2's job).
- `get_status_events(application_id)` ordered by `changed_at`, plus a way to fetch all events for the currently filtered set (for CSV export in S5 and Sankey computation in S4).

**Rules that must hold (§4):** creating an application writes exactly one event; every status change appends exactly one more and mirrors it on `applications.status`; events are never edited or deleted — the full lifecycle is reconstructable at any time.

### 5. Tests (`tests/test_data.py`)
- Use a temp SQLite file (fixture), not the real `DATA_DIR`.
- Cover: model CRUD; exactly-one-event-on-create; exactly-one-appended-per-status-change with correct from/to values; **no** event when only non-status fields change; status-mirror invariant after edits; cascade delete removes events; filter predicate behavior for no-filter, single company, multi-status set, and date range.

## Hard rules (apply to this and every session)
1. **Scope:** data layer only. No application HTTP routes, no uploads, no UI — those are S2/S3+. Small incidental fixes fine if committed separately with their own `Type:` footer.
2. **Gates before finishing:** `pytest` green (old + new tests); `docker build -t job-tracker .` passes **if Docker is available** (else note it in SESSION_LOG.md); `git status` clean.
3. **Commits:** one logical change per commit; imperative summary ≤ ~70 chars, optional body, blank line, then exactly one footer: `Type:` = one of `feature | fix | refactor | docs | chore | test | perf`.
4. **PLAN.md is canonical.** Fix errors via a separate minimal `Type: docs` commit and call them out in your report.
5. **Blockers:** stop if stuck; record under "Open issues" in SESSION_LOG.md with what you tried; leave the tree coherent — never end with unexplained half-work.
6. Never commit `.venv/`, `data/`, `.env`, or any `*.db` (covered by `.gitignore`).

## Definition of done (checklist)
- [ ] Starting the app initializes the DB automatically (lifespan hook works); WAL mode is active (`PRAGMA journal_mode` returns `wal`).
- [ ] Model CRUD + event rules covered by tests; pre-existing health test still passes.
- [ ] Docker build passes (if available); all commits carry `Type:` footers; SESSION_LOG updated.

## Suggested commit order (adapt as needed)
1. "Add SQLAlchemy models for applications and status_events" — Type: feature
2. "Add DB init with WAL pragma wired into app lifespan" — Type: feature
3. "Add repository functions enforcing event-append rules" — Type: feature
4. "Cover data layer with model/repo tests" — Type: test

## Finish protocol (mandatory)
1. Append a **Session 1** entry to `SESSION_LOG.md`:
   ```markdown
   ## Session 1 — <YYYY-MM-DD>
   - What was done: <bullets>
   - Commits: <hash> "message" (Type: x), ...
   - Test/build status: pytest N passed; docker build ok | skipped (reason)
   - Open issues: <none or bullets>
   - Notes for next session: <anything S2 should rely on, e.g. repo function signatures and the shared filter predicate's shape>
   ```
2. Commit the log update separately — `Type: docs`.
3. Report to the user: commits made, test/build results, any repo-function API decisions S2 should rely on, and confirmation that **Session 2** is ready (`prompts/session-2.md`).
