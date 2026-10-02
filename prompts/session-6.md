# Session 6 Prompt — Raspberry Pi Deployment & Hardening

**Project:** Job Application Tracker — single-user, LAN-hosted job application tracker.
**Repo root:** `C:\Users\Trenton\coding-projects\job-tracker`
**Shell paths:** may be Git Bash/MSYS2 (`/c/Users/Trenton/coding-projects/job-tracker`) or WSL (`/mnt/c/Users/Trenton/coding-projects/job-tracker`) — detect with `ls /c` vs `ls /mnt/c`.

You are starting fresh with **no memory of previous sessions**. The only prior state is this repository and this `prompts/` directory.

## Start here (do these first, in order)
1. `cd` into the repo root. Run:
   - `git log --oneline -80` — expected to end with Sessions 0–5 commits (scaffold, data layer, application API + uploads, dashboard UI core, charts, exports & polish). If not, **stop and report**.
   - `git status` — must be clean.
   - Read `PLAN.md` in full (canonical requirements), then the tail of `SESSION_LOG.md`, then this file.
2. Baseline: venv (`python -m venv .venv && source .venv/bin/activate`), install deps, run `pytest` — must be green **before** you change anything.

## Where we are
Sessions 0–5 are done: the complete app works locally (WSL + Docker Desktop) — dashboard with HTMX filters reshaping every widget, Sankey + pie charts, validated PDF uploads/downloads, CSV exports wired to header buttons, README usage docs. A Dockerfile and compose file have existed since Session 0 but remain scaffolds. **This session is packaging and deployment, not features.** Your job: make the repo deployable as-is on a Raspberry Pi (arm64) per **PLAN.md §2/§7/§8** — one container, LAN access at `:8090`, data survives everything.

## Your job this session (deliverables)

### 1. Final Dockerfile (§8)
- Keep base `python:3.12-slim` (multi-arch → native arm64 build on the Pi; no cross-compilation) and pinned requirements. Copy only what runtime needs — tests can stay out of the image.
- **Non-root user:** create a dedicated system user (e.g. `useradd -r -s /sbin/nologin jobtracker`), `chown` the data directory so SQLite + WAL files are writable by it, and switch to it before running uvicorn. Verify inside the built container that the process actually runs non-root — don't assume.
- **Healthcheck** hitting `/healthz` via a Python stdlib one-liner (slim image has no curl), per §8: interval 30s / timeout 5s / retries 3. Keep `EXPOSE 8000`.

### 2. Finalize `docker-compose.yml`
Same file for dev and prod (§2/§8) — no platform-specific branches, zero extra setup from a fresh clone:
- service `job-tracker`; `build: .`
- ports `"${PORT:-8090}:8000"` (env-overridable host port; default 8090 per §12)
- volume `./data:/app/data` — all paths relative to the repo root
- `restart: unless-stopped`
- healthcheck block per §8

### 3. README "Deploy on Raspberry Pi" section (§8)
Step-by-step for a non-expert, replacing S5's placeholder pointer:
1. Clone/copy the repository onto the Pi → `cd job-tracker`.
2. `docker compose up -d --build` (first build compiles native arm64 on the Pi — note it takes a few minutes).
3. Open `http://<pi-ip>:8090` from any device on the LAN; recommend a DHCP reservation or `raspberrypi.local` (mDNS) for a stable URL.
- Plus: backup/restore = copy `./data` (`app.db` + `uploads/`; container stopped is safest), and the disk-usage note tied to the 15 MB upload cap (§7).

### 4. Clean-room verification — this session's real gate
If Docker is available in this environment, simulate a fresh clone:
1. Copy **only committed files** into a temp directory (no `.venv/`, no `data/`, no `.git`).
2. `docker compose up -d --build` → container becomes healthy within ~30s; `/healthz` ok on the mapped port.
3. Create an application over HTTP with PDF uploads (curl or browser) → confirm `app.db` and `uploads/<id>/` appear under the bind-mounted `data/`.
4. `docker compose down && docker compose up` → data still there (persistence proof).
5. Confirm the process runs as the non-root user (`docker inspect` / in-container `ps`).

If Docker is **not** available: do everything statically verifiable, then record under Open issues — "skipped local clean-room verification; verify on Pi" — with the exact commands to run there. The physical Raspberry Pi step (fresh clone + reachable from a second LAN device) is performed by you only if a Pi is actually reachable in this environment; otherwise leave precise Pi-side verification steps in your report and under Open issues.

## Hard rules (apply to this session — final build session)
1. **Scope:** packaging + deployment docs only. No new features, no UI changes beyond what's needed for a correct build. The local dev workflow (venv + uvicorn + pytest) must keep working exactly as before. Incidental fixes go in separate commits with their own `Type:` footer.
2. **Gates before finishing:** `pytest` green; clean-room verification per above (or documented skip); `git status` clean.
3. **Commits:** one logical change per commit; imperative summary ≤ ~70 chars, optional body, blank line, then exactly one footer: `Type:` = one of `feature | fix | refactor | docs | chore | test | perf`.
4. **PLAN.md is canonical.** §8 conflicts are resolved in favor of what makes deployment actually work — record any such discrepancy as a minimal `Type: docs` correction and call it out in your report.
5. **Blockers:** if stuck, stop; record under "Open issues" in SESSION_LOG.md with the exact commands to run later (Pi-side steps included); leave the tree coherent — never end with unexplained half-work.
6. Never commit `.venv/`, `data/`, `.env`, or any `*.db` (covered by `.gitignore`).

## Definition of done (checklist)
- [ ] Fresh-copy build → healthy container serving on port 8090; non-root process confirmed (or documented skip with exact Pi commands).
- [ ] `app.db` + `uploads/` created under the bind volume and survive a down/up cycle (where verified locally).
- [ ] Compose file identical for dev/prod: relative paths only, env-overridable port, restart policy, §8 healthcheck.
- [ ] README deploy section accurate end-to-end; backup recipe present.
- [ ] All commits carry `Type:` footers; SESSION_LOG updated; `pytest` green.

## Suggested commit order (adapt as needed)
1. "Harden Dockerfile with non-root user and final healthcheck" — Type: chore
2. "Finalize compose file for dev-and-prod Raspberry Pi deployment" — Type: chore
3. "Document Raspberry Pi deployment in README" — Type: docs

## Finish protocol (mandatory)
1. Append a **Session 6** entry to `SESSION_LOG.md`:
   ```markdown
   ## Session 6 — <YYYY-MM-DD>
   - What was done: <bullets>
   - Commits: <hash> "message" (Type: x), ...
   - Test/build status: pytest N passed; clean-room verification ok | skipped (reason) + exact Pi commands to run
   - Open issues: <none or bullets>
   - Notes for next session: none — all planned build sessions complete. Next step is manual Raspberry Pi deployment from the README.
   ```
2. Commit the log update separately — `Type: docs`.
3. Report to the user: commits made, test/build results, clean-room evidence (or exactly what remains for the Pi), and confirmation that **all planned build sessions are complete** — remaining step is manual Raspberry Pi deployment from the README.
