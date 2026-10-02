# Session 0 Prompt — Repo Scaffolding & Tooling

**Project:** Job Application Tracker — single-user, LAN-hosted webapp for tracking job applications (one Docker container on a Raspberry Pi; developed on Windows/WSL).
**Repo root:** `C:\Users\Trenton\coding-projects\job-tracker`
**Shell paths:** the shell for this session may be Git Bash/MSYS2 (`/c/Users/Trenton/coding-projects/job-tracker`) or WSL (`/mnt/c/Users/Trenton/coding-projects/job-tracker`). Detect with `ls /c` vs `ls /mnt/c`; use whichever exists.

You are starting fresh with **no memory of previous sessions**. The only prior state is this repository itself and this `prompts/` directory (which also holds the verbatim session -1 architecture brief at `session--1.md`).

## Start here (do these first, in order)
1. `cd` into the repo root. Run:
   - `git log --oneline -8` — expected history is exactly two commits: "Add project plan covering architecture through deployment" (Type: docs) on top of "Initialize repository with session prompt archive" (Type: chore). If it doesn't match, **stop and report** before doing anything.
   - `git status` — must be clean before you begin.
   - Read `PLAN.md` in full (it is the canonical requirements document), then read this file.
2. Confirm tooling available: Python 3.10+ (`python --version`), git, and whether Docker exists (`docker version`). Record availability in your final report.

## Where we are
This is the **first build session** (architecture was defined in session -1; no code has been written yet). The repo contains only `PLAN.md`, `SESSION_LOG.md` (one entry: session -1), `.gitignore`, and `prompts/`. You are creating the runnable skeleton that every later session builds on.

## Your job this session (deliverables)

### 1. Python package `app/`
- `app/__init__.py`
- `app/config.py` — load configuration from environment variables with defaults; a small plain module reading `os.getenv` is fine — no settings framework:
  - `DATA_DIR` — default `/app/data` (container use); must be overridable via env for local dev (e.g. `./data`).
  - `MAX_UPLOAD_MB` = 15 (§7 upload cap).
  - **Status vocabulary as one constant set** per §4.1: `STATUSES = ("received", "interviewing", "offer", "accepted", "rejected", "ghosted")` and `WAITING_STATUSES = ("received", "interviewing", "offer")`. Adding a status later must be a one-line change here plus a badge color (S3).
  - `STATUS_COLORS` — small mapping of each status to a badge color used by the dashboard (S3 consumes it; define it now so §4.1's "one line + a badge color" holds).
- `app/main.py` — FastAPI app factory: `def create_app() -> FastAPI`. For now one route: `GET /healthz` → JSON `{"status": "ok", "service": "job-tracker"}`. Design the factory so lifespan hooks (DB init in S1) and static-file mounting (S3) are easy to add later.

### 2. Dependencies & tests
- `requirements.txt` at repo root with **pinned** versions (`==`) of: fastapi, uvicorn[standard], jinja2, httpx, pytest. SQLAlchemy is added by S1; HTMX and ECharts arrive as vendored static files (S3/S4) — no further pip deps are expected for this project.
- `tests/test_health.py` — use FastAPI's `TestClient`; assert `/healthz` returns 200 and `"status": "ok"`.

### 3. Docker skeleton
- `Dockerfile`: base `python:3.12-slim` (multi-arch so the Pi builds native arm64); copy requirements first for layer caching, pinned `pip install`, copy `app/`, `ENV DATA_DIR=/app/data`, `EXPOSE 8000`, `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`. Include the healthcheck now — Python stdlib one-liner, since the slim image has no curl (§8):
  `["python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz')"]`
  with interval 30s / timeout 5s / retries 3 (in the compose file). S6 hardens this Dockerfile further (non-root user, final polish) but must keep this healthcheck approach.
- `docker-compose.yml` at repo root: service `job-tracker`, `build: .`, ports `"${PORT:-8090}:8000"`, volume `./data:/app/data`, `restart: unless-stopped`, and the healthcheck block above. **All paths relative to the repo root** — this same file must work unchanged on WSL (Docker Desktop) and on the Pi (§2, §8).

### 4. Docs
- `README.md` stub at repo root: one paragraph on what the project is (link to `PLAN.md`), then "Local development" quickstart (create `.venv`, install requirements, run uvicorn with reload), "Run tests" (`pytest`), and "Docker" (`docker compose up --build` → `http://localhost:8090/healthz`). Note that runtime data lives in `./data` — gitignored but bind-mounted into the container (§2).
- `SESSION_LOG.md` **already exists** with a Session -1 entry and the entry format header — do not recreate it; append your own Session 0 entry per the Finish protocol below.

## Hard rules (apply to this and every session)
1. **Scope:** implement only what this prompt lists. Do not start S1+ work (no DB models, no application routes). Small incidental fixes are fine if committed separately with their own `Type:` footer.
2. **Gates before finishing:** `pytest` green; `docker build -t job-tracker .` passes **if Docker is available** in this environment (otherwise note "skipped — docker unavailable" in SESSION_LOG.md); `git status` clean.
3. **Commits:** one logical change per commit. Message = imperative summary ≤ ~70 chars, optional body, blank line, then exactly one footer: `Type:` followed by one of `feature | fix | refactor | docs | chore | test | perf`.
4. **PLAN.md is canonical.** If you find an error in it, make a minimal correction as its own commit with `Type: docs` and call it out in your report — don't silently rewrite it.
5. **Blockers:** if stuck on something outside your control, stop; record details under "Open issues" in SESSION_LOG.md (what you tried, what failed); leave the tree coherent (committed or cleanly rolled back) — never end with unexplained half-work.
6. Never commit `.venv/`, `data/`, `.env`, or any `*.db` (covered by `.gitignore`; double-check with `git status`).

## Definition of done (checklist)
- [ ] `pytest` passes, including the `/healthz` smoke test.
- [ ] `uvicorn app.main:app` serves `/healthz` locally in a venv.
- [ ] If Docker available: `docker compose up --build` starts and becomes **healthy** (compose healthcheck ok); `http://localhost:8090/healthz` returns ok; then bring it down.
- [ ] README stub, `.gitignore`, and SESSION_LOG.md present; all commits carry the `Type:` footer.

## Suggested commit order (adapt as needed)
1. "Scaffold FastAPI app with /healthz and config module" — Type: chore
2. "Pin dependencies and add health smoke test" — Type: test
3. "Add Dockerfile and compose file with healthcheck" — Type: chore
4. "Document quickstart in README" — Type: docs

## Finish protocol (mandatory)
1. Append a **Session 0** entry to `SESSION_LOG.md` using this exact shape:
   ```markdown
   ## Session 0 — <YYYY-MM-DD>
   - What was done: <bullets>
   - Commits: <hash> "message" (Type: x), ...
   - Test/build status: pytest N passed; docker build ok | skipped (reason)
   - Open issues: <none or bullets>
   - Notes for next session: <anything S1 should know, e.g. config variable names and defaults>
   ```
2. Commit the log update as its own commit — `Type: docs`.
3. Report to the user: list of commits made, test/build results, whether Docker was available, and confirmation that **Session 1** is ready (`prompts/session-1.md`).
