# Job Application Tracker

A single-user, LAN-hosted web app that keeps a living record of every job
application: what was applied for, when, with which documents (resume + full
application PDF), and how it progressed through the status lifecycle — all
viewable in one dashboard with a waiting queue, Sankey funnel, status pie
chart, filters, and CSV export. Your data never leaves your network: one
SQLite database plus an upload folder is the entire state of the app.

## Features

- **Applications** with company, job title, reference number, applied date,
  posting URL, notes, and up to two PDFs (resume + full application), each
  validated as a real `.pdf` file of at most 15 MB before it touches disk.
- **Editable status history.** Every change appends one dated event to the
  timeline on the detail page, and every existing step can be corrected in
  place — a mis-keyed date or an intermediate status — without deleting and
  recreating the application. You can also enter the date a change actually
  happened (backdating is allowed; future dates are rejected), so a remembered
  update lands where it belongs. When creating an application you can record
  the whole journey at once — applied, interviewed, accepted, whatever already
  happened — and each step becomes its own dated event.
- **Automatic ghosting.** Applications that sit at `received` for more than
  180 days without any update are moved to `ghosted` automatically, with an
  event recording when the sweep ran. The threshold is configurable via the
  `GHOST_AFTER_DAYS` environment variable. Any edit resets the clock — a
  touched application is never ghosted.
- **Dashboard.** Four stat cards (total, waiting, closed rate, median days to
  first response), a waiting queue sorted by who has been silent longest, an
  ECharts Sankey of status flow, and a current-status pie chart. Applications
  that haven't reached a final status yet flow into a `waiting` node on the
  Sankey, so open applications are visible instead of vanishing. The All
  Applications table also shows how many days each row has sat untouched —
  any edit resets that counter.
- **Filters.** By company, current status (multi-select chips), or applied-date
  range — every widget, queue, and table reshapes around the same slice.
- **Export what you're looking at.** "Export CSV" downloads the applications on
  screen; "Export history" downloads their full event histories (one row per
  status change). No filters active means the whole dataset.
- **Themes.** Five switchable themes — Light, Dark, Dracula, Nord, and
  Gruvbox — with your choice remembered in the browser between visits.
- **Self-contained.** HTMX and ECharts are vendored locally; there is no CDN or
  runtime internet dependency. Runs in a single Docker container on any
  architecture, including Raspberry Pi (arm64).

## Quick start (Docker)

The whole app runs inside one container, and this repository is everything you
need. The `python:3.12-slim` base image is multi-arch, so it builds natively —
on a Raspberry Pi or any other machine:

```bash
# 1. Get the code (git clone, or copy the folder over SSH/USB)
cd job-tracker

# 2. Build and start — first build takes a few minutes on a Pi
docker compose up -d --build
```

3. Open `http://<host-ip>:8090` from any device on your network — phone,
   laptop, whatever. For a stable address instead of the raw IP, reserve the
   host's address in your router's DHCP settings (or use `<name>.local` if mDNS
   works on your devices).

Notes:

- **Reboots:** the container comes back automatically after a power cycle
  (`restart: unless-stopped`). Stop it for maintenance with
  `docker compose down`, then start it again with `docker compose up -d`.
- **Different port?** The host-side port is overridable via environment:
  `PORT=9000 docker compose up -d --build`. (The container always listens on
  8000 internally; only the published port changes.)
- **First start:** if Docker created your data directory as root, the
  entrypoint adopts its ownership and then drops privileges to a dedicated
  non-root user for good — nothing to configure manually.

## Using the app

The dashboard (`/`) shows four stat cards, a waiting queue (who has been
silent longest), status-flow and current-status charts, and an all-applications
table — every widget computed over the same filtered slice.

- **Add an application** via "+ New application" in the header: company and job
  title are required; reference number, applied date, posting URL, notes, plus
  optional resume and full-application PDFs. New applications always start at
  `received`.
- **Track status over time** from the application's detail page: pick a new
  status (and edit any other field), optionally enter the date the change
  actually happened, and save. Every real change appends exactly one dated row
  to the event history that the timeline below shows — including when it first
  became `received` — and every existing step can be corrected in place from
  the same page. Deleting an application removes its history rows and both
  stored PDFs.
- **Filter** by company, current status (multi-select chips), or applied-date
  range; "Clear filters" returns to the full dataset.
- **Export** from the header as described in Features. Filenames are
  timestamped (`applications_YYYYMMDD_HHMM.csv`, UTC).
- **Download stored PDFs** from any table's Resume/PDF links or the detail
  page's Documents section — served under the original filenames you uploaded.

## Configuration (environment variables)

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATA_DIR` | `/app/data` | Where the SQLite database and uploaded PDFs live. Set to a path inside your project for local development outside Docker. |
| `PORT` | `8090` | Host-side port published by Docker Compose (container always listens on 8000). |
| `GHOST_AFTER_DAYS` | `180` | Days without any update at `received` before an application is automatically moved to `ghosted`. |

## Local development

```bash
python -m venv .venv
# Windows (PowerShell):    .venv\Scripts\Activate.ps1
# Windows (Git Bash):      source .venv/Scripts/activate
# WSL / Linux / macOS:     source .venv/bin/activate
pip install -r requirements.txt

set DATA_DIR=./data              # Git Bash / WSL / macOS
$env:DATA_DIR = "./data"         # PowerShell
uvicorn app.main:app --reload
```

Then open http://localhost:8000/healthz — it should return
`{"status": "ok", "service": "job-tracker"}`. (Local dev serves on port 8000;
the Docker setup publishes 8090 by default.)

One-time per clone — enable the commit-message hook that enforces this
repository's trailing `Type:` footer convention:

```bash
git config core.hooksPath scripts/git-hooks
```

Every commit message must end with exactly one of, as its last non-blank line:
`Type: feature`, `Type: fix`, `Type: refactor`, `Type: docs`, `Type: chore`,
`Type: test`, or `Type: perf`.

## Run the tests

The suite is fully offline — each test builds a throwaway database under
pytest's temp directory, so your live data (if any) is never touched.

```bash
pytest
```

## Runtime data and backups

Live state lives in `./data` at the repo root: `app.db` (SQLite) plus an
`uploads/` tree of PDFs. The directory is gitignored but bind-mounted into the
container at `/app/data`, so it survives rebuilds and restarts.

Backing up means copying that whole directory somewhere durable:

```bash
docker compose stop   # safest: no writes in flight while you copy
cp -r data /path/to/somewhere-else/job-tracker-backup-$(date +%F)
```

Restoring is the reverse: put the backed-up contents back into `./data`, then
`docker compose up -d`. (Copying a live database usually works fine thanks to
SQLite's WAL mode, but stopping first guarantees a consistent snapshot.)

Disk use stays small by design: each application holds at most two PDFs, each
capped at 15 MB, so even hundreds of applications occupy well under a gigabyte.

## Architecture notes

- **Layers:** `app/repo.py` owns every database rule (status vocabulary,
  status-event chain consistency, including in-place step corrections,
  auto-ghosting); request handlers in `app/routes/`
  only call repo functions through short-lived sessions; pure display math
  lives in `app/dashboard.py` and `app/analytics.py`, which makes the charts'
  payloads unit-testable without HTTP.
- **Charts:** ECharts v6 is vendored under `app/static/vendor/`; a shared
  controller renders (and disposes) both charts on load, after every HTMX body
  swap, and on theme change — no stale state or stacked listeners.
- **Frontend:** server-rendered Jinja templates with HTMX for filter re-renders;
  the page works as plain GET/POST forms without JavaScript. Themes are CSS
  custom properties switched by a `data-theme` attribute, persisted in
  `localStorage`.
- **Deployment:** hardened `python:3.12-slim` image with pinned dependencies,
  a dedicated non-root server user, a stdlib `/healthz` probe, and relative
  paths throughout — the same compose file runs on a Raspberry Pi or any
  Docker host.
