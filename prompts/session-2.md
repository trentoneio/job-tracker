# Session 2 Prompt — Application API & PDF Uploads

**Project:** Job Application Tracker — single-user, LAN-hosted job application tracker.
**Repo root:** `C:\Users\Trenton\coding-projects\job-tracker`
**Shell paths:** may be Git Bash/MSYS2 (`/c/Users/Trenton/coding-projects/job-tracker`) or WSL (`/mnt/c/Users/Trenton/coding-projects/job-tracker`) — detect with `ls /c` vs `ls /mnt/c`.

You are starting fresh with **no memory of previous sessions**. The only prior state is this repository and this `prompts/` directory.

## Start here (do these first, in order)
1. `cd` into the repo root. Run:
   - `git log --oneline -35` — expected to end with Sessions 0–1 commits (scaffold + health test, Dockerfile/compose, README; then DB layer: models, WAL init, repository functions). If not, **stop and report**.
   - `git status` — must be clean.
   - Read `PLAN.md` in full (canonical requirements), then the tail of `SESSION_LOG.md` (Session 1's "Notes for next session" lists the repo function signatures to use), then this file.
2. Baseline: venv (`python -m venv .venv && source .venv/bin/activate`), install deps, run `pytest` — must be green **before** you change anything.

## Where we are
Sessions 0–1 are done: FastAPI skeleton with `/healthz`, config constants (status vocabulary, upload cap), working Dockerfile/compose on WSL, and a tested data layer in `app/db.py` / `app/models.py` / `app/repo.py` — applications + append-only status_events, event-append rules enforced at the repo level. There is still **no HTTP surface for applications** and no real UI (S2 = your job: API + uploads; S3 builds the dashboard on top of these routes).

## Your job this session (deliverables)

### 1. Application routes (e.g. `app/routes/applications.py`, registered in the app factory)
Per **PLAN.md §5** — server-rendered forms, redirects after POST. Minimal working templates are acceptable for now; S3 replaces them with the real dashboard layout (§6). Keep behavior exactly as specified:

- `GET /applications/new` + `POST /applications/new` — form fields per model: company (required), job_title (required), reference_number, applied_on (DATE, required), job_posting_url, notes, plus optional multipart file parts for resume and application PDF. **No status field on create** — creating always starts at `received` (§4 rule). On success: 303 redirect to the detail page. Validation errors re-render the form with inline messages (server-side; no JSON API).
- `GET /applications/{id}` — detail page: all fields, current status badge, an **inline edit form** (all fields editable in one form), the **status timeline** built from `status_events` (from → to, dated, in order), and links to the stored PDFs via `/files/...` when present. Unknown id → 404.
- `POST /applications/{id}/update` — field edits including status change and/or new/replacement PDF uploads; repo appends a status event **only** if the status actually changed (§4 rule); 303 back to detail after save.
- `POST /applications/{id}/delete` — with confirmation (a simple inline confirm form is fine in this session), deletes row + events via the repo **and removes the stored files on disk** (§7); redirect to `/`.

### 2. Upload handling & validation (`app/uploads.py` or similar)
Per **PLAN.md §7**:
- Validate by extension (`.pdf`) **and** magic bytes (`%PDF` prefix). Reject anything else with a clear error message shown in the form.
- Enforce the size cap from config `MAX_UPLOAD_MB` = 15 MB — reject oversized files before writing to disk.
- Store at `data/uploads/<application_id>/{resume,application}.pdf`. Re-uploading **replaces** the old file on disk (delete/overwrite) and updates the stored original filename; storage paths stay stable.
- On delete: remove both files and their directory.

### 3. File download endpoint
Per §5 — `GET /files/{application_id}/{kind}` where kind is `resume` or `application`: stream the stored PDF with `Content-Disposition: attachment` using the **original filename** from the DB (storage names stay stable, originals are for display/download naming). 404 if the application or file doesn't exist. No auth beyond LAN (§12).

### 4. Minimal templates
`app/templates/` — a small `base.html` plus create/detail pages just functional enough to exercise the whole flow. Keep them deliberately plain; S3 rebuilds this as the real dashboard layout per §6. Do not build stat cards, waiting queue, filters, or charts here.

### 5. Tests (`tests/test_api.py`, and upload tests alongside)
Use `TestClient` with a temp `DATA_DIR` fixture and **generated valid PDF bytes** (a minimal byte string starting with `%PDF`) — no network, no real files from the filesystem:
- Full lifecycle: create → appears on detail page → update non-status fields (no new event) → status change (exactly one new event with correct from/to) → delete (row + events gone, **files removed from disk**).
- Upload validation: a `.pdf`-named file whose contents aren't `%PDF...` is rejected; an oversized (>15 MB) file is rejected before hitting disk; valid PDFs accepted.
- Replacement semantics: uploading a second resume replaces the first on disk and updates the original-filename metadata.
- 303 redirect after create/update; 404 for unknown application or `/files/...` path.

## Hard rules (apply to this and every session)
1. **Scope:** application API + uploads only. No dashboard widgets, no filter bar, no charts, no CSV export — those are S3/S4/S5. Small incidental fixes fine if committed separately with their own `Type:` footer.
2. **Gates before finishing:** `pytest` green (old + new); tests must run fully offline (fixtures, temp DBs, generated PDF bytes — §9); `docker build -t job-tracker .` passes **if Docker is available** (else note it in SESSION_LOG.md); `git status` clean.
3. **Commits:** one logical change per commit; imperative summary ≤ ~70 chars, optional body, blank line, then exactly one footer: `Type:` = one of `feature | fix | refactor | docs | chore | test | perf`.
4. **PLAN.md is canonical.** Fix errors via a separate minimal `Type: docs` commit and call them out in your report.
5. **Blockers:** stop if stuck; record under "Open issues" in SESSION_LOG.md with what you tried; leave the tree coherent — never end with unexplained half-work.
6. Never commit `.venv/`, `data/`, `.env`, or any `*.db` (covered by `.gitignore`).

## Definition of done (checklist)
- [ ] Full create → view → edit → status-change → delete lifecycle works end-to-end in tests, including file cleanup on delete.
- [ ] Non-PDF content and oversized files rejected with clear messages; replacement semantics verified.
- [ ] Status-change event rule holds through the API path (one event per change, none for field-only edits).
- [ ] `pytest` green (old + new); Docker build passes if available; all commits carry `Type:` footers; SESSION_LOG updated.

## Suggested commit order (adapt as needed)
1. "Add upload validation and storage helpers" — Type: feature
2. "Add application create/detail/update/delete routes" — Type: feature
3. "Add PDF download endpoint with original filenames" — Type: feature
4. "Cover API lifecycle and upload rules with tests" — Type: test

## Finish protocol (mandatory)
1. Append a **Session 2** entry to `SESSION_LOG.md`:
   ```markdown
   ## Session 2 — <YYYY-MM-DD>
   - What was done: <bullets>
   - Commits: <hash> "message" (Type: x), ...
   - Test/build status: pytest N passed; docker build ok | skipped (reason)
   - Open issues: <none or bullets>
   - Notes for next session: <anything S3 should know — template locations, route shapes, where the export-link placeholder will go in the header>
   ```
2. Commit the log update separately — `Type: docs`.
3. Report to the user: commits made, test/build results, and confirmation that **Session 3** is ready (`prompts/session-3.md`).
