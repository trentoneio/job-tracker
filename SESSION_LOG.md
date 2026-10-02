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
