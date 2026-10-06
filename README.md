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

One-time per clone — enable the commit-message hook that enforces PLAN §10's
trailing `Type:` footer convention:
```
git config core.hooksPath scripts/git-hooks
```

## Using the app

The dashboard (`GET /`) shows four stat cards, a waiting queue (who has been
silent longest), status-flow and current-status charts, and an all-applications
table — every widget computed over the same filtered slice.

- **Add an application** via “+ New application” in the header: company and
  job title are required; reference number, applied date (defaults to today),
  posting URL, notes, plus optional resume and full-application PDFs. Both
  PDFs must be real `.pdf` files of at most **15 MB each** — anything else is
  rejected with an inline message before a single byte touches disk. New
  applications always start in `received`.
- **Track status over time** from the application’s detail page: pick a new
  status (and edit any other field) and save. Every change appends exactly one
  row to the append-only history, which the status timeline shows — including
  when it first became received. Deleting an application removes its history
  rows and both stored PDFs.
- **Filter** by company, current status (multi-select chips), or applied-date
  range; every widget reshapes around the same slice, with friendly empty
  states when nothing matches. “Clear filters” returns to the full dataset.
- **Export what you’re looking at**: the header’s “Export CSV” downloads the
  applications as CSV and “Export history” downloads their full status
  histories (one row per event). With no active filter both export the whole
  dataset; with a filter they download exactly the slice on screen. Filenames
  are timestamped (`applications_YYYYMMDD_HHMM.csv`, UTC).
- **Download stored PDFs** from any table’s Resume/PDF links or the detail
  page’s Documents section — served under the original filenames you uploaded
  (stored as `<DATA_DIR>/uploads/<id>/<kind>.pdf`; re-uploading replaces in
  place).

Live state lives in `./data` at the repo root: `app.db` (SQLite) plus an
`uploads/` tree of PDFs. To back up, copy that whole directory — with the
container stopped if you want a guaranteed-consistent snapshot (§2, §7 of
PLAN.md). The data directory is gitignored and bind-mounted into Docker at
`/app/data`, so it survives rebuilds.

(Deploying on a Raspberry Pi gets its own section when Session 6 ships.)

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

Session 3 builds the dashboard on top of that (PLAN.md §6): a shared base layout
with header (`app/templates/base.html`) and HTMX vendored under
`app/static/vendor/`, so no runtime internet is needed. The index page has four
stat cards computed by pure functions in `app/dashboard.py` over the filtered
slice (total, waiting count, closed rate, median days to first response), a
waiting queue sorted most-days-elapsed-first, and an all-applications table with
row-click navigation; a filter bar (company / status chips / applied-date range)
re-renders the whole page via HTMX — or as a plain GET form without JavaScript.
The new/detail pages were rebuilt on the same layout, and the detail page gains
the append-only status timeline.

Session 4 adds the two remaining dashboard widgets (PLAN.md §6 items 5–6):
**ECharts v6.1.0** vendored locally (`app/static/vendor/echarts.min.js`) and
loaded from the base layout, plus a new pure-function module `app/analytics.py`
that turns the filtered event slice into two JSON payloads — Sankey nodes in
the §4.1 vocabulary order with links whose value is how many *applications*
took each distinct transition (per-application dedupe), and pie slices of
current-status counts with one-decimal percentages — embedded per render as
`application/json` script tags inside new “Status flow” / “Current status”
sections between the waiting queue and the all-applications table. A shared
chart controller in `<head>` renders (and disposes) both charts on initial load
and after every HTMX body swap, so filter changes re-chart with no stale state
or stacked listeners, and slices without transitions/applications show friendly
empty states. This session also set a repo-wide commit standard:
`scripts/git-hooks/commit-msg` enforces the change type at the very end of
every message (`Type:` footer as last non-blank line), enabled via
`core.hooksPath` (one-time setup in the quickstart above).

Session 5 adds the data-out side (PLAN.md §5) and final polish: both CSV
export endpoints (`GET /api/export.csv` for the applications, columns exactly
per §5; `GET /api/events.csv` for one row per status event), each reusing the
dashboard’s shared filter predicate so no filters exports the full dataset —
and wired into the header as “Export CSV” / “Export history” buttons that
carry the active filter query string. The polish pass covers friendly HTML
404 pages for unknown application/file ids and routes, PDF download links in
the waiting queue (matching the table and detail page), and the user-facing
“Using the app” section above.

Everything is covered by temp-database test suites (`tests/test_data.py`,
`tests/test_api.py`, `tests/test_dashboard.py`, `tests/test_charts.py`,
`tests/test_export.py`).

Session 6 packages it all for Raspberry Pi deployment (§7, §8): a hardened
`Dockerfile` (multi-arch `python:3.12-slim`, pinned deps, a dedicated
non-root `jobtracker` user that owns `/app/data`) plus an `entrypoint.py`
that runs as root only long enough on first start to adopt the host's data
directory, then drops privileges for good and execs uvicorn — the server
process itself always shows in `ps`/`/proc` as non-root. The compose file
(verifiable against §8: relative paths, `${PORT:-8090}`, `restart:
unless-stopped`, stdlib `/healthz` probe) is unchanged from session 0, and a
`.dockerignore` keeps personal data, venvs, tests and git history out of the
build context. Verified end-to-end in a clean room: built from committed files
only, healthy within ~30 s, an application created over HTTP with its PDFs
landing in `./data`, all still present after a full stop/start.

All sessions from [PLAN.md](PLAN.md) §11 are complete. See
[SESSION_LOG.md](SESSION_LOG.md) for what each session shipped.

## Deploy on a Raspberry Pi

The whole app runs inside one Docker container (§7), and this repository is
everything you need. The `python:3.12-slim` base image is multi-arch, so there
is no cross-compilation — you build natively on the Pi (arm64):

```bash
# 1. Get the code onto the Pi (git clone, or copy the folder over SSH/USB)
cd job-tracker

# 2. Build and start — first build takes a few minutes on the Pi
docker compose up -d --build
```

3. Open `http://<pi-ip>:8090` from any device on your network — phone,
laptop, whatever. For a stable address instead of the raw IP, reserve the
Pi's address in your router's DHCP settings (or use `raspberrypi.local` if
mDNS works on your devices).

Notes:

- **Reboots:** the container comes back automatically after a Pi power cycle
  (`restart: unless-stopped`). Stop it for maintenance with
  `docker compose down`, then start it again with `docker compose up -d`.
- **Different port?** The host-side port is overridable via environment:
  `PORT=9000 docker compose up -d --build`. (The container always listens on
  8000 internally; only the published port changes.)
- **Data directory:** everything lives in `./data` at the repo root. On first
  start, if Docker created that directory as root, the entrypoint adopts its
  ownership before dropping to the non-root server user — nothing for you to
  configure manually.

### Backup and restore

Everything you've recorded — every application row plus every uploaded PDF —
is one directory: `./data` (`app.db`, its WAL sidecar files, and the
`uploads/` tree). Backing up means copying that directory somewhere durable:

```bash
docker compose stop   # safest: no writes in flight while you copy
cp -r data /path/to/somewhere-else/job-tracker-backup-$(date +%F)
```

Restoring is the reverse: put the backed-up contents back into `./data`, then
`docker compose up -d`. (Copying a live database usually works fine thanks to
SQLite's WAL mode, but stopping first guarantees a consistent snapshot.)

Disk use stays small by design (§7): each application holds at most two PDFs,
each capped at 15 MB, so even hundreds of applications occupy well under a
gigabyte — trivial for an SD card. If you file many large scans, check up with
`du -sh data/` now and then.

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
