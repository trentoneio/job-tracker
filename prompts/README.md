# Session Prompts — Job Application Tracker

One prompt file per build session (`session-0.md`, `session-1.md`, …). Each one is **fully self-contained**: it assumes zero memory of any previous session, relying only on the state of this repository (code, git history, `SESSION_LOG.md`) and this directory. `session--1.md` is the special case: it is the original architecture brief that started this project (no code was produced by it).

## How to run a session
1. Start with the next unstarted build session: read that file in full from the top (`prompts/session-N.md`).
2. The prompt's "Start here" checklist tells you exactly what prior state to verify before writing anything — if it doesn't match, stop and report instead of guessing.
3. Follow the prompt's deliverables, hard rules, definition-of-done checklist, and finish protocol (which includes updating `SESSION_LOG.md` and reporting commits).

## Session index
| File | Scope |
|---|---|
| `session--1.md` | Initial architecture brief (verbatim original request; architecture-only session, no code) — see `PLAN.md` for the resulting design |

Build sessions 0–6 are specified in `PLAN.md` §11. Their self-contained prompt files will be written into this directory as they are scheduled.

## Ground rules baked into every prompt
- Do only that session's scope; never start later sessions' work.
- End with: tests green, docker build passing (from S0 onward), a coherent tree, and a `SESSION_LOG.md` entry — all committed with the repo's commit convention (imperative summary + body + single trailing `Type:` footer).
