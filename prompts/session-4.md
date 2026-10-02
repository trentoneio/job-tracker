# Session 4 Prompt — Analytics Charts (Sankey + Pie)

**Project:** Job Application Tracker — single-user, LAN-hosted job application tracker.
**Repo root:** `C:\Users\Trenton\coding-projects\job-tracker`
**Shell paths:** may be Git Bash/MSYS2 (`/c/Users/Trenton/coding-projects/job-tracker`) or WSL (`/mnt/c/Users/Trenton/coding-projects/job-tracker`) — detect with `ls /c` vs `ls /mnt/c`.

You are starting fresh with **no memory of previous sessions**. The only prior state is this repository and this `prompts/` directory.

## Start here (do these first, in order)
1. `cd` into the repo root. Run:
   - `git log --oneline -60` — expected to end with Sessions 0–3 commits (scaffold, data layer, application API + uploads, dashboard UI core). If not, **stop and report**.
   - `git status` — must be clean.
   - Read `PLAN.md` in full (canonical requirements), then the tail of `SESSION_LOG.md` (Session 3's notes say where chart JSON will embed and which HTMX swap hook to use), then this file.
2. Baseline: venv (`python -m venv .venv && source .venv/bin/activate`), install deps, run `pytest` — must be green **before** you change anything.

## Where we are
Sessions 0–3 are done: the dashboard renders server-side — header, HTMX filter bar that re-renders the whole page, stat cards, waiting queue, all-applications table, polished new/edit pages with status timeline and empty states; validated PDF upload/download behind it. The data layer exposes the full append-only `status_events` history for every application. **No charts exist yet.** Your job: add the two ECharts per **PLAN.md §6 items 5–6**, both respecting the same filter slice as everything else on the page.

## Your job this session (deliverables)

### 1. Vendor ECharts locally
- Commit `app/static/vendor/echarts.min.js` (~1 MB). No CDN or runtime internet dependency (§3: LAN-only, §12). Include it in the base layout alongside HTMX.

### 2. Server-side chart data (`app/analytics.py`)
Pure functions over filtered applications + their status events — no framework coupling, fully unit-testable:
- **Sankey payload** (§6 item 5): nodes = statuses; edges = consecutive transitions observed within the filtered set. For each application, take its ordered event list and count every consecutive pair (`from_status → to_status`); edge value = number of applications that took that transition. Terminal statuses (accepted/rejected/ghosted) have no outflow by construction. Return ECharts-ready JSON: node names + links with `source`, `target`, `value`.
- **Pie payload** (§6 item 6): current-status distribution for the filtered set — counts and percentages per status present, using each application's current `status` (the latest event / mirrored column).

### 3. Embedding & rendering
- Embed both payloads as JSON in script tags on dashboard render, e.g. `window.__SANKEY__` / `window.__PIE__`.
- Client-side init + **re-init on every HTMX swap** (`htmx:afterSwap` listener): destroy any existing chart instances before re-initializing so repeated filter submits never stack duplicates or go stale.
- Empty-data handling: if the filtered set has no events (Sankey) or no applications (pie), show a friendly empty state instead of an erroring blank canvas ("No status changes yet" / "No data").

### 4. Tests (`tests/test_charts.py`)
Fixture DB with known transition histories across several companies/statuses/dates, built via the repo:
- Sankey payload matches expected nodes/edges/values for the full unfiltered set **and** each filter combination (single company; status subset; date range) — including that terminal statuses never appear as a source.
- Pie counts and percentages correct under the same filter combinations.
- (Charts render client-side, so tests cover the server-computed payloads — not pixels.)

## Hard rules (apply to this and every session)
1. **Scope:** charts only — no CSV export or working export buttons (S5), no deployment changes (S6). Don't alter S3 widget behavior beyond adding the two chart sections; incidental fixes go in separate commits with their own `Type:` footer.
2. **Gates before finishing:** `pytest` green (old + new); tests fully offline (fixtures, temp DBs — §9); `docker build -t job-tracker .` passes **if Docker is available** (else note it in SESSION_LOG.md); `git status` clean.
3. **Commits:** one logical change per commit; imperative summary ≤ ~70 chars, optional body, blank line, then exactly one footer: `Type:` = one of `feature | fix | refactor | docs | chore | test | perf`.
4. **PLAN.md is canonical.** Fix errors via a separate minimal `Type: docs` commit and call them out in your report.
5. **Blockers:** stop if stuck; record under "Open issues" in SESSION_LOG.md with what you tried; leave the tree coherent — never end with unexplained half-work.
6. Never commit `.venv/`, `data/`, `.env`, or any `*.db` (covered by `.gitignore`). The vendored ECharts file **is** committed — it's source.

## Definition of done (checklist)
- [ ] Both charts render and update correctly on filter changes against fixture data (manual check — run uvicorn locally with a few real/seeded applications that have status history, toggle filters via the HTMX form, confirm both charts re-render to the correct slice; if no interactive browser is available, document exactly what you verified server-side under Open issues).
- [ ] No duplicate/stale chart instances after repeated filter submits.
- [ ] Empty-data states render instead of errors.
- [ ] `pytest` green (old + new); Docker build passes if available; all commits carry `Type:` footers; SESSION_LOG updated.

## Suggested commit order (adapt as needed)
1. "Vendor ECharts locally and wire into base layout" — Type: chore
2. "Add analytics module computing Sankey/pie payloads from events" — Type: feature
3. "Embed chart JSON and re-init charts on HTMX swap" — Type: feature
4. "Cover chart payload computation with fixture tests" — Type: test

## Finish protocol (mandatory)
1. Append a **Session 4** entry to `SESSION_LOG.md`:
   ```markdown
   ## Session 4 — <YYYY-MM-DD>
   - What was done: <bullets>
   - Commits: <hash> "message" (Type: x), ...
   - Test/build status: pytest N passed; docker build ok | skipped (reason)
   - Open issues: <none or bullets>
   - Notes for next session: <anything S5 should know — e.g. exact location of the header export-link placeholder and how the active filter query string is assembled>
   ```
2. Commit the log update separately — `Type: docs`.
3. Report to the user: commits made, test/build results, manual verification outcome (or what was verified server-side instead), and confirmation that **Session 5** is ready (`prompts/session-5.md`).
