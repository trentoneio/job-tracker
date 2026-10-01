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
