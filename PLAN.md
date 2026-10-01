# Job Application Tracker — Project Plan

- **Repo root:** `C:\Users\Trenton\coding-projects\job-tracker` (Windows) · `/mnt/c/Users/Trenton/coding-projects/job-tracker` (WSL)
- **Status:** architecture defined in session -1 (2026-07-08). Build sessions start at 0.
- **Companions:** `prompts/` (session briefs), `SESSION_LOG.md` (per-session log), git conventions mirrored from the sibling project `pricehawk`.

## 1. Vision & goals

A single-user, local-network webapp that keeps a living record of every job application: what was applied for, when, with which documents, and how each one progressed through its status lifecycle — all viewable in one dashboard.

**Core requirements (from the session -1 brief):**
- Record per application: company, job title, reference number, date applied, full application PDF (when available), resume PDF used, link to the job posting, current status.
- Statuses change over time (received → interviewing → offer/accepted/rejected/ghosted, …) and every change is part of the record.
- Dashboard surfaces: a "waiting on reply" queue in one place; a Sankey diagram of application status flow; a pie chart of current status distribution.
- Filters (e.g., single company) that reshape **the entire dashboard**, not just one widget.
- All data exportable to a local downloadable format (CSV).
- Data persists across crashes, power loss, and restarts — no re-import needed. The project lives in one directory containing both source and running state.
- Hosted on a Raspberry Pi, developed on Windows/WSL, reachable from any device on the LAN. Docker is the hosting mechanism.

**Non-goals (for now):** multi-user accounts/auth, cloud sync or backups off-box, scraping job boards or auto-tracking postings, mobile app, reminders/notifications (possible future additions — see §13).

## 2. High-level architecture

One container, one service, no external dependencies:

```
          Any device on the LAN                Raspberry Pi (arm64)
 ┌──────────────┐   http://<pi-ip>:8090   ┌─────────────────────────────────┐
 │  Browser      │ ─────────────────────► │ docker-compose service         │
 │ (phone, PC, …)│ ◄───────────────────── │ ┌─────────────────────────────┐ │
 └──────────────┘                         │ │ FastAPI app                 │ │
                                          │ │  • server-rendered UI (Jinja)│ │
                                          │ │  • JSON/CSV endpoints        │ │
                                          │ │  • PDF upload / download     │ │
                                          │ └──────────────┬──────────────┘ │
                                          │                │ bind mount    │
                                          │              /app/data         │
                                          └────────────────┼────────────────┘
                                                           │
                              ./data   (inside the repo directory, gitignored)
                                 • app.db                  SQLite database (WAL mode)
                                 • uploads/<id>/resume.pdf        PDF documents
                                 • uploads/<id>/application.pdf
```

- **Single project directory** holds source *and* running state: `app/` is code, `data/` is the live record. `data/` is gitignored but bind-mounted into the container, so it survives container rebuilds, Pi reboots, and power loss — satisfying the "one directory" requirement without committing personal data.
- **No separate database service.** SQLite (single file) is durable with WAL mode and trivially sized for one user; a Postgres sidecar would add operational cost for no benefit at this scale.
- The same `docker-compose.yml` works unchanged on the Windows/WSL dev box (Docker Desktop) and on the Pi: all paths are relative to the repo root, so there are zero platform-specific path branches.

## 3. Tech stack & rationale

| Layer | Choice | Why |
|---|---|---|
| Backend | **FastAPI** (Python) | Lightweight, excellent multipart upload handling, auto OpenAPI docs for free, easy to test; matches the proven in-house pattern from `pricehawk`. |
| ORM / DB | **SQLAlchemy 2.x + SQLite (WAL)** | Single-file durable database, zero service ops, append-friendly history table; single-writer usage makes it a non-issue. |
| Frontend | **Jinja2 templates + HTMX** | No JS build toolchain for a single-user app: forms post to real endpoints, filters re-render server-side, charts re-init client-side on swap. Keeps the container a simple `pip install` image. |
| Charts | **ECharts, vendored locally** (`app/static/vendor/`) | Native Sankey + pie support; served from disk so the app works with no CDN/internet dependency once loaded — right for LAN-only hosting. |
| Runtime / host | **Docker Compose**, `python:3.12-slim` (multi-arch) | One container, one volume, healthcheck; base image is multi-arch so the Pi builds/runs native arm64 with no cross-compilation. |

**Alternatives considered:** React/Vite SPA (build toolchain + dev proxy complexity for a single user), Django (more machinery than needed — FastAPI + Jinja covers it), Node/Express (fine, but the Python stack matches this machine's established project pattern), Postgres (ops overhead with no scale benefit).

## 4. Data model

Two tables; the second is what makes the Sankey possible.

**`applications`**
| column | type | notes |
|---|---|---|
| `id` | INTEGER PK | |
| `company` | TEXT NOT NULL | filter key #1 |
| `job_title` | TEXT NOT NULL | |
| `reference_number` | TEXT, nullable | employer's ref number |
| `applied_on` | DATE NOT NULL | date the application was submitted |
| `status` | TEXT NOT NULL, default `received` | CHECK against the status set (§4.1) — always mirrors the latest event |
| `job_posting_url` | TEXT, nullable | link to the posting |
| `notes` | TEXT, nullable | free-form (interview notes, contacts, etc.) |
| `resume_pdf` / `application_pdf` | TEXT, nullable | relative paths under `data/uploads/<id>/`; original file names kept in DB for display/download naming |
| `created_at`, `updated_at` | TIMESTAMP UTC ISO-8601 | |

**`status_events`** (append-only history — the Sankey source of truth)
| column | type | notes |
|---|---|---|
| `id` | INTEGER PK | |
| `application_id` | FK → applications.id, CASCADE | |
| `from_status` | TEXT, nullable | NULL on the initial event |
| `to_status` | TEXT NOT NULL | |
| `changed_at` | TIMESTAMP UTC, default now | |

**Rules:** creating an application writes one event (`NULL → received`). A status change via edit/PATCH appends exactly one more event and updates `applications.status`. Events are never edited or deleted — the full lifecycle is reconstructable at any time.

### 4.1 Status vocabulary
| status | waiting? | meaning |
|---|---|---|
| `received` | yes | submitted, no reply yet (default) |
| `interviewing` | yes | interview(s) scheduled/done, outcome pending |
| `offer` | yes | offer extended, decision pending |
| `accepted` | no — closed | job accepted |
| `rejected` | no — closed | declined/not selected |
| `ghosted` | no — closed | process ended without response after engagement |

- The set lives in **one constant** (`app/config.py`); adding a status later is a one-line change plus a badge color.
- "Waiting on a reply" = status ∈ {received, interviewing, offer}. This drives the waiting queue and the stat cards.

## 5. API & page design

UI-first (server-rendered) with machine-readable endpoints for data out:

| Route | Method(s) | Purpose |
|---|---|---|
| `/healthz` | GET | JSON health probe; target of the compose healthcheck |
| `/` | GET | **Dashboard** — accepts filter query params (`company`, `status` (repeatable), `date_from`, `date_to`) and renders all widgets for that slice (§6) |
| `/applications/new` | GET, POST | Create form; multipart with optional `resume_pdf` / `application_pdf` parts → 303 to detail page |
| `/applications/{id}` | GET | Detail + edit form (inline), status timeline from events, PDF links |
| `/applications/{id}/update` | POST | Field edits incl. status change and/or new/replace PDFs; appends the status event if changed |
| `/applications/{id}/delete` | POST | Deletes row + its events + files on disk (with confirm) |
| `/files/{application_id}/{kind}` | GET | Streams stored PDF (`kind` = `resume` \| `application`) with `Content-Disposition` using the original file name |
| `/api/export.csv` | GET | Full applications export; respects active filters when present, **no filters = full dataset** (columns: id, company, job_title, reference_number, applied_on, status, job_posting_url, notes, resume filename, application filename, created_at, updated_at). Download name `applications_YYYYMMDD_HHMM.csv` |
| `/api/events.csv` | GET | Status-history export (application_id, company, from_status, to_status, changed_at) — same filter semantics |

Filter semantics: every param optional; empty set = all applications. The same query string is used by the dashboard render **and** both CSV endpoints, so "export what you're looking at" works naturally.

## 6. Dashboard & UI spec

Layout top-to-bottom (single page, `GET /`):
1. **Header:** app name · "New application" button · "Export CSV" + "Export history" links.
2. **Filter bar:** company dropdown (distinct companies from data), status chips/checkboxes, applied-date range, "Clear filters". Submitting re-renders the whole page via HTMX with identical markup — every widget below reflects the same slice.
3. **Stat cards** (computed server-side for the filtered set): total applications · waiting count · closed rate (% that reached a terminal status) · median days to first response (from `status_events`; "—" when no data).
4. **Waiting queue** — the headline widget: one row per application whose status is in the waiting set, showing company, title, ref #, applied date, **days elapsed**, posting link, resume/application PDF links; sorted by days-elapsed descending. "Everything still on the table" at a glance.
5. **Sankey chart (ECharts):** nodes = statuses; edges = consecutive transitions observed in `status_events` within the filtered set; edge value = number of applications taking that transition. Terminal statuses have no outflow, so the diagram literally shows where each cohort went. Data embedded as JSON (`window.__SANKEY__`) and rendered client-side; re-initialized on every HTMX swap.
6. **Pie/donut chart (ECharts):** current-status distribution for the filtered set with counts + percentages, same embedding pattern.
7. **All applications table:** compact rows — company, title, ref #, applied date, status badge (color per status), days since applied, links to detail / resume PDF / application PDF / posting; row click opens detail.

Detail/edit page: all fields editable in one form; on save, a new event is appended if status changed; below the form, that application's full **status timeline** (from → to, dated). Empty states everywhere ("No applications yet — add your first", "Nothing waiting right now").

## 7. File handling & persistence

- **Uploads:** validated by extension *and* magic bytes (`%PDF`); size cap **15 MB per file** (config constant). Stored at `data/uploads/<application_id>/{resume,application}.pdf`; re-upload replaces the old file on disk. Original filenames are stored in the DB and used for download naming — storage names stay stable.
- **Database:** SQLite with `PRAGMA journal_mode=WAL` set at init → clean recovery after crashes/power loss; single writer (one user) makes contention a non-issue.
- **Persistence guarantee:** all state = one directory (`data/`). Container restart, rebuild, Pi reboot, or power outage never touches it. Deleting `data/` is the only way to lose records — documented in the README alongside the backup recipe: copy `app.db` + `uploads/`.
- All timestamps stored UTC ISO-8601; displayed as plain dates locally.

## 8. Deployment & networking (Raspberry Pi)

**Dockerfile:** `python:3.12-slim`, pinned requirements, non-root user, copies `app/`, `EXPOSE 8000`, healthcheck hitting `/healthz` (Python one-liner — no curl needed in the slim image).

**docker-compose.yml (same file for dev and prod):**
```yaml
services:
  job-tracker:
    build: .
    ports: ["${PORT:-8090}:8000"]
    volumes: [ "./data:/app/data" ]
    restart: unless-stopped
    healthcheck: { test: [...], interval: 30s, timeout: 5s, retries: 3 }
```

**Pi setup (documented in README during session 6):** clone repo → `cd job-tracker` → `docker compose up -d --build` → open `http://<pi-ip>:8090` from any LAN device. Recommend a DHCP reservation for the Pi or use `raspberrypi.local` (mDNS) so the URL is stable. First build on the Pi compiles native arm64 — no cross-build step.

**Dev workflow:** WSL + Docker Desktop, identical compose invocation; the bind-mounted Windows path works fine at this data scale. Local dev and Pi prod therefore differ only by which machine runs `compose up`.

## 9. Testing & quality gates

`pytest`, fully offline (fixtures, temp SQLite DBs, generated test PDF bytes):
- CRUD lifecycle: create → read → update → delete, incl. file cleanup on delete.
- Status events: exactly one event on create; exactly one appended per status change; no event when only non-status fields change.
- Upload validation: rejects non-PDF content and oversize files; accepts valid PDFs; replace semantics work.
- CSV export: columns/rows match DB contents for full export and each filter combination (company, status set, date range).
- Filter logic unit tests against the same predicate used by dashboard + exports.

**Per-session gate protocol (mirrors pricehawk):** `pytest` green → `docker build` passes (from S0 onward) → `git status` clean → append `SESSION_LOG.md` entry (what changed, open issues, notes for next session) → commit(s) with the §10 convention.

## 10. Git & commit conventions

- One logical change per commit; small increments within each session.
- Commit message format:
```
<imperative summary, ≤ ~70 chars>

[optional body]

Type: feature | fix | refactor | docs | chore | test | perf
```
The trailing `Type:` footer is **mandatory** on every commit (documents documentation vs new feature vs bug fix, etc.).
- Work directly on `main` (solo project); short-lived branches only if a change gets risky.
- `.gitignore` already established: live data (`data/`, `*.db`), env overrides, Python/Docker build artifacts never enter the repo.

## 11. Session plan (vibecoding handoff)

**Protocol for every new session:**
1. `cd` into the repo root (`C:\Users\Trenton\coding-projects\job-tracker`; shell paths per header above), run `git log --oneline -5`.
2. Read this PLAN section (§11) and the end of `SESSION_LOG.md`; identify the next unstarted session.
3. Build only that session's scope; commit per logical change with the `Type:` footer (§10).
4. Finish only when: tests green, docker build passes, tree clean, SESSION_LOG updated.

**Suggested kickoff prompt:** "Read PLAN.md §11 and the end of SESSION_LOG.md, then execute **Session N** exactly as specified — deliverables, done criteria, and commit conventions (§10). Do not start work from Session N+1."

| # | Scope | Type(s) | Done when |
|---|---|---|---|
| 0 | Repo scaffolding & tooling: `app/` layout, pinned deps, FastAPI app serving `/healthz`, pytest smoke test, Dockerfile + compose that build & run locally on WSL, `.gitignore` (exists), README stub, `SESSION_LOG.md` | chore/docs | `docker compose up --build` shows healthcheck OK; `pytest` green; everything committed |
| 1 | Data layer: SQLAlchemy models (`applications`, `status_events`), DB init with WAL, repository functions incl. event-appending rules (§4) | feature | model CRUD + event rules covered by tests; pytest green |
| 2 | Application API + uploads: create/detail/edit/delete routes, multipart PDF upload with validation (§7), file download endpoint | feature | full lifecycle works end-to-end in tests incl. non-PDF rejection and oversize rejection; pytest green |
| 3 | Dashboard UI core: Jinja base layout, filter bar (company/status/date range) re-rendering the whole page via HTMX, stat cards, waiting queue, all-applications table, new/edit forms, empty states | feature | add an application from the browser and see it in the waiting queue; filters reshape every widget; pytest green |
| 4 | Analytics charts: vendor ECharts locally; Sankey built from `status_events` (filtered); pie of current statuses; embedded JSON + re-init on HTMX swap (§6.5–6) | feature | both charts render and update correctly under filter changes against fixture data; pytest green |
| 5 | Export & file polish: CSV endpoints wired to dashboard buttons, PDF download links with original filenames, error/empty-state polish, README usage docs | feature/chore | CSV contents match DB exactly (full + filtered); manual checklist passes in a real browser |
| 6 | Pi deployment & hardening: final Dockerfile (non-root + healthcheck), compose restart policy + env-overridable port, Raspberry Pi deploy guide in README, clean-room verification from a fresh clone on the Pi | chore/docs | fresh repo copy on the Pi → `compose up` → dashboard reachable from another LAN device; data survives `docker compose down && up` |

## 12. Risks & mitigations

| Risk | Mitigation |
|---|---|
| No auth, app exposed to LAN | Trusted home-network boundary only; no external ports. Optional future env-gated basic-auth (see §13) if the network ever gets untrusted devices. |
| SQLite corruption on power loss | WAL mode + single writer; backup recipe in README (copy `data/`). |
| Large PDFs filling Pi disk | 15 MB per-file cap; files stored outside the DB; disk usage noted in README. |
| Windows ↔ Pi path differences | Compose paths are all relative to repo root — identical behavior on both platforms; no absolute paths anywhere. |
| Status vocabulary drift / ambiguous "waiting" definition | Single constant + explicit waiting-set (§4.1); adding a status is documented as a one-line change. |
| Chart library bloat/CDN failure | ECharts vendored once (~1 MB), served locally — zero runtime internet dependency. |

## 13. Open questions & possible future work

- **Commit identity:** no global git identity existed on this machine, so the repo-local `user.name`/`user.email` were set to match the sibling repos (`trentoneio`). Update locally if a different identity is preferred.
- **Port:** 8090 chosen as default (env-overridable). Change in compose if it collides with something on the Pi.
- Future ideas, explicitly out of scope for now: per-application reminders/notifications, response-time stats by company, optional basic auth, multiple users, dark mode.
