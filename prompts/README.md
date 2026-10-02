# Session Prompts — Job Application Tracker

One prompt file per build session (`session-0.md`, `session-1.md`, …). Each one is **fully self-contained**: it assumes zero memory of any previous session, relying only on the state of this repository (code, git history, `SESSION_LOG.md`) and this directory. `session--1.md` is the special case: it is the original architecture brief that started this project (no code was produced by it).

## How to run a session
1. Start with the next unstarted build session: read that file in full from the top (`prompts/session-N.md`).
2. The prompt's "Start here" checklist tells you exactly what prior state to verify before writing anything — if it doesn't match, stop and report instead of guessing.
3. Follow the prompt's deliverables, hard rules, definition-of-done checklist, and finish protocol (which includes updating `SESSION_LOG.md` and reporting commits).

## Session index
| File | Scope |
|---|---|
| `session--1.md` | Initial architecture brief — verbatim original request, top of file (architecture-only session, no code; see `PLAN.md` for the resulting design). Appended below it: the Session -0.5 prompt (prompt-creation session; also no code) |
| `session-0.md` | Repo scaffolding: app/ layout, pinned deps, /healthz, Dockerfile/compose skeleton, README stub |
| `session-1.md` | Data layer: SQLAlchemy models, DB init (WAL), repository functions with event-append rules |
| `session-2.md` | Application API + uploads: CRUD routes, multipart PDF validation, file download endpoint |
| `session-3.md` | Dashboard UI core: base layout, HTMX filter bar, stat cards, waiting queue, table, forms, empty states |
| `session-4.md` | Analytics charts: vendored ECharts, Sankey from status_events, pie of current statuses |
| `session-5.md` | Exports & file polish: CSV endpoints wired to header buttons, original-filename downloads, README usage docs |
| `session-6.md` | Pi deployment & hardening: final Dockerfile (non-root + healthcheck), compose, Pi guide in README, clean-room verification

All build sessions 0–6 are now prompted; each file is fully self-contained — a fresh session starts by reading its own prompt only.

## Ground rules baked into every prompt
- Do only that session's scope; never start later sessions' work.
- End with: tests green, docker build passing (from S0 onward), a coherent tree, and a `SESSION_LOG.md` entry — all committed with the repo's commit convention (imperative summary + body + single trailing `Type:` footer).
