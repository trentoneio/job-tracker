# Session 5 Prompt — CSV Exports & File Polish

**Project:** Job Application Tracker — single-user, LAN-hosted job application tracker.
**Repo root:** `C:\Users\Trenton\coding-projects\job-tracker`
**Shell paths:** may be Git Bash/MSYS2 (`/c/Users/Trenton/coding-projects/job-tracker`) or WSL (`/mnt/c/Users/Trenton/coding-projects/job-tracker`) — detect with `ls /c` vs `ls /mnt/c`.

You are starting fresh with **no memory of previous sessions**. The only prior state is this repository and this `prompts/` directory.

## Start here (do these first, in order)
1. `cd` into the repo root. Run:
   - `git log --oneline -70` — expected to end with Sessions 0–4 commits (scaffold, data layer, application API + uploads, dashboard UI core, charts). If not, **stop and report**.
   - `git status` — must be clean.
   - Read `PLAN.md` in full (canonical requirements), then the tail of `SESSION_LOG.md`, then this file.
2. Baseline: venv (`python -m venv .venv && source .venv/bin/activate`), install deps, run `pytest` — must be green **before** you change anything.

## Where we are
Sessions 0–4 are done: the full dashboard works — HTMX filter bar reshapes every widget server-side (stat cards, waiting queue, table), Sankey + pie charts re-init on swap; application lifecycle with validated PDF upload/download and original-filename downloads. The export links in the header are still the placeholder left by S3, and no CSV endpoints exist yet. Your job: data-out per **PLAN.md §5** plus final polish per §11 Session 5 scope.

## Your job this session (deliverables)

### 1. `GET /api/export.csv` — applications export
- Respects the active filter query string when present; with no filters, exports the full dataset (§5 "export what you're looking at"). Reuse S1's shared filter predicate — **no separate filtering logic**.
- Columns exactly: `id`, `company`, `job_title`, `reference_number`, `applied_on`, `status`, `job_posting_url`, `notes`, resume filename, application filename, `created_at`, `updated_at` (use the original filenames stored in S2 for the two PDF columns).
- Response is a CSV file download with `Content-Disposition: attachment; filename="applications_YYYYMMDD_HHMM.csv"` (UTC timestamp).

### 2. `GET /api/events.csv` — status-history export
- Rows per status event, same filter semantics as the applications export (§5): columns include application id, company, from_status, to_status, changed_at.
- Same dated download-name pattern, e.g. `status_events_YYYYMMDD_HHMM.csv`.

### 3. Header buttons (§6 item 1)
Replace S3's placeholder with "Export CSV" and "Export history" links that **carry the current filter query string**, so whatever is on screen is what gets exported. Links (plain GETs) are fine — no HTMX needed here.

### 4. File polish
- Verify end-to-end that every PDF download link in the UI (waiting queue, table, detail page) streams with the **original filename** via `/files/...`; fix any gaps.
- Error/empty-state polish: friendly 404 page for unknown application/file ids; clear upload-error messages where validation fails (§7); consistent empty states everywhere (§6). Keep visual changes minimal and in keeping with the existing layout — this is a pass, not a redesign.

### 5. README usage docs
Add a user-facing "Using the app" section: adding an application (fields + PDFs), tracking status over time (events/timeline view), filters that reshape the dashboard, exporting CSVs (full vs filtered), downloading stored PDFs; where data lives (`./data` = `app.db` + `uploads/`) and the backup recipe per §7 (copy `app.db` + `uploads/`, container stopped is safest); note the 15 MB upload cap. The Pi deployment section arrives in S6 — leave a one-line pointer ("see Deploy on Raspberry Pi, added in Session 6").

### 6. Tests (`tests/test_export.py`)
- Full export: columns and rows exactly match DB contents (seeded fixture set).
- Each filter combination (single company; status subset; date range): exported rows equal the filtered dashboard view — assert against the same predicate, not a reimplementation.
- Download filename format correct for both endpoints; `events.csv` rows match the application's `status_events` history exactly (order included) and join in the company name.

## Hard rules (apply to this and every session)
1. **Scope:** exports + polish only — no new dashboard widgets, no deployment changes (S6). Don't break chart re-init or filter behavior; incidental fixes go in separate commits with their own `Type:` footer.
2. **Gates before finishing:** `pytest` green (old + new); tests fully offline (fixtures, temp DBs — §9); `docker build -t job-tracker .` passes **if Docker is available** (else note it in SESSION_LOG.md); `git status` clean.
3. **Commits:** one logical change per commit; imperative summary ≤ ~70 chars, optional body, blank line, then exactly one footer: `Type:` = one of `feature | fix | refactor | docs | chore | test | perf`.
4. **PLAN.md is canonical.** Fix errors via a separate minimal `Type: docs` commit and call them out in your report.
5. **Blockers:** stop if stuck; record under "Open issues" in SESSION_LOG.md with what you tried; leave the tree coherent — never end with unexplained half-work.
6. Never commit `.venv/`, `data/`, `.env`, or any `*.db` (covered by `.gitignore`).

## Definition of done (checklist)
- [ ] CSV contents match DB exactly for full export and every filter combination; both endpoints produce correctly named file downloads.
- [ ] Manual checklist passes in a real browser (run uvicorn locally): add an application with both PDFs → change its status once → apply a single-company filter → Export CSV and Export history under that filter → open both files and confirm rows/columns match the on-screen slice; download the resume/application PDFs and confirm original filenames; clear filters and re-export the full dataset. If no interactive browser is available, document exactly what you verified server-side (TestClient responses) under Open issues.
- [ ] 404/upload-error pages render cleanly; empty states consistent.
- [ ] README "Using the app" section written with backup recipe.
- [ ] `pytest` green (old + new); Docker build passes if available; all commits carry `Type:` footers; SESSION_LOG updated.

## Suggested commit order (adapt as needed)
1. "Add /api/export.csv applications endpoint" — Type: feature
2. "Add /api/events.csv status-history endpoint" — Type: feature
3. "Wire export buttons into dashboard header with active filters" — Type: feature
4. "Polish 404s, upload errors, and empty states" — Type: fix
5. "Document app usage in README" — Type: docs
6. "Cover CSV exports with fixture tests" — Type: test

## Finish protocol (mandatory)
1. Append a **Session 5** entry to `SESSION_LOG.md`:
   ```markdown
   ## Session 5 — <YYYY-MM-DD>
   - What was done: <bullets>
   - Commits: <hash> "message" (Type: x), ...
   - Test/build status: pytest N passed; docker build ok | skipped (reason)
   - Open issues: <none or bullets>
   - Notes for next session: <anything S6 should know — e.g. README structure so the deploy section slots in cleanly, current Dockerfile/compose state>
   ```
2. Commit the log update separately — `Type: docs`.
3. Report to the user: commits made, test/build results, manual checklist outcome (or what was verified server-side instead), and confirmation that **Session 6** is ready (`prompts/session-6.md`).
