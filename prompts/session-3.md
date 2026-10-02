# Session 3 Prompt — Dashboard UI Core

**Project:** Job Application Tracker — single-user, LAN-hosted job application tracker.
**Repo root:** `C:\Users\Trenton\coding-projects\job-tracker`
**Shell paths:** may be Git Bash/MSYS2 (`/c/Users/Trenton/coding-projects/job-tracker`) or WSL (`/mnt/c/Users/Trenton/coding-projects/job-tracker`) — detect with `ls /c` vs `ls /mnt/c`.

You are starting fresh with **no memory of previous sessions**. The only prior state is this repository and this `prompts/` directory.

## Start here (do these first, in order)
1. `cd` into the repo root. Run:
   - `git log --oneline -45` — expected to end with Sessions 0–2 commits (scaffold, data layer, application API + uploads). If not, **stop and report**.
   - `git status` — must be clean.
   - Read `PLAN.md` in full (canonical requirements), then the tail of `SESSION_LOG.md`, then this file.
2. Baseline: venv (`python -m venv .venv && source .venv/bin/activate`), install deps, run `pytest` — must be green **before** you change anything.

## Where we are
Sessions 0–2 are done: the app serves `/healthz`; a tested data layer (applications + append-only status_events with event rules) in `app/db.py` / `models.py` / `repo.py`; and the full application lifecycle over HTTP — create/detail/update/delete routes, validated multipart PDF uploads, file downloads with original filenames. Minimal working templates exist from S2, but there is **no real UI yet**. Your job: build the single-page dashboard per **PLAN.md §6 items 1–4 and 7** plus polished new/edit pages. No charts yet (S4), no CSV export wiring (S5).

## Your job this session (deliverables)

### 1. Static assets & base layout
- Mount `app/static` at `/static` in the app factory.
- **Vendor HTMX locally** — commit `app/static/vendor/htmx.min.js`. No CDN or runtime internet dependency (§3: LAN-only).
- Jinja base template `app/templates/base.html` implementing §6 item 1 header: app name · "New application" button · a clearly marked placeholder spot for the export links (S5 wires them): e.g. `{# TODO(S5): Export CSV / Export history links #}`.

### 2. Filter bar (§6 item 2)
- Company dropdown populated from distinct companies in the data; status checkboxes/chips covering every status in `app/config.py`'s `STATUSES`; applied-date range (from/to); "Clear filters".
- Submitting re-renders **the entire page** via HTMX with identical markup, so every widget below reflects the same slice. The query-string semantics must be exactly: `company`, `status` (repeatable), `date_from`, `date_to`; all params optional; empty = everything (§5 — this same string later drives both CSV endpoints). Reuse S1's shared filter predicate — no second, parallel filtering logic.

### 3. Stat cards (§6 item 3)
Computed server-side for the filtered set:
- total applications · waiting count (status in `WAITING_STATUSES`) · closed rate (% of filtered apps at a terminal status: accepted/rejected/ghosted; "—" if none) · median days to first response — for each application that has at least one non-initial event, take days between `applied_on` and the first such event's `changed_at`, then the median over the filtered set ("—" if no data).

### 4. Waiting queue (§6 item 4)
The headline widget: one row per waiting-status application — company, title, reference #, applied date, **days elapsed**, posting link, resume/application PDF links (when present). Sorted by days elapsed descending. Empty state: "Nothing waiting right now".

### 5. All-applications table (§6 item 7)
Compact rows: company, title, ref #, applied date, status badge (color from `STATUS_COLORS` in config), days since applied, links to detail/resume PDF/application PDF/posting; clicking a row opens the detail page. Empty state: "No applications yet — add your first".

### 6. New/edit pages (§6 last paragraph)
Rebuild S2's minimal templates on top of this base layout: create form at `/applications/new`; edit form inline on the detail page with **all fields editable in one form**; status timeline below the form (from → to, dated). Keep S2 behavior exactly as-is — including that a save only appends an event when the status actually changed.

### 7. Tests (`tests/test_dashboard.py`)
`TestClient` + fixture data seeded via the repo:
- Empty DB renders with empty states present; no crashes.
- With fixtures: stat card values correct (total, waiting count, closed rate, median days); waiting queue rows = expected set sorted by days elapsed descending.
- Filters reshape **every widget**: assert that under a company filter only that company's applications appear in the table and queue, and that unfiltered companies are absent from the page; same for a status set and a date range.
- The HTMX re-render (simulated via a plain GET with query string) returns the same sliced view.

## Hard rules (apply to this and every session)
1. **Scope:** dashboard UI core only — no ECharts/Sankey/pie (S4), no CSV endpoints or working export buttons (S5). Don't change S2 route behavior; incidental fixes go in separate commits with their own `Type:` footer.
2. **Gates before finishing:** `pytest` green (old + new); tests fully offline (fixtures, temp DBs — §9); `docker build -t job-tracker .` passes **if Docker is available** (else note it in SESSION_LOG.md); `git status` clean.
3. **Commits:** one logical change per commit; imperative summary ≤ ~70 chars, optional body, blank line, then exactly one footer: `Type:` = one of `feature | fix | refactor | docs | chore | test | perf`.
4. **PLAN.md is canonical.** Fix errors via a separate minimal `Type: docs` commit and call them out in your report.
5. **Blockers:** stop if stuck; record under "Open issues" in SESSION_LOG.md with what you tried; leave the tree coherent — never end with unexplained half-work.
6. Never commit `.venv/`, `data/`, `.env`, or any `*.db` (covered by `.gitignore`). Note: vendored JS files are source and **are** committed.

## Definition of done (checklist)
- [ ] Add an application from the browser and see it appear in the waiting queue and the table (manual check — run uvicorn locally with a temp `DATA_DIR`; if no interactive browser is available, document exactly what you verified server-side under Open issues).
- [ ] Filters reshape every widget (stat cards, waiting queue, table) on submit; Clear filters restores everything.
- [ ] New/edit pages work end-to-end including status timeline and empty states.
- [ ] `pytest` green (old + new); Docker build passes if available; all commits carry `Type:` footers; SESSION_LOG updated.

## Suggested commit order (adapt as needed)
1. "Vendor HTMX locally and add base layout with header" — Type: chore
2. "Add filter bar re-rendering whole dashboard via HTMX" — Type: feature
3. "Add stat cards, waiting queue, and applications table" — Type: feature
4. "Rebuild create/edit pages on base layout with status timeline" — Type: feature
5. "Cover dashboard rendering and filters with tests" — Type: test

## Finish protocol (mandatory)
1. Append a **Session 3** entry to `SESSION_LOG.md`:
   ```markdown
   ## Session 3 — <YYYY-MM-DD>
   - What was done: <bullets>
   - Commits: <hash> "message" (Type: x), ...
   - Test/build status: pytest N passed; docker build ok | skipped (reason)
   - Open issues: <none or bullets>
   - Notes for next session: <anything S4 should know — where chart JSON will embed, the HTMX swap event/handler names to hook into>
   ```
2. Commit the log update separately — `Type: docs`.
3. Report to the user: commits made, test/build results, manual verification outcome (or what was verified server-side instead), and confirmation that **Session 4** is ready (`prompts/session-4.md`).
