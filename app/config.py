"""Runtime configuration for the job tracker.

Plain module reading environment variables with defaults, so the same code
runs in Docker (DATA_DIR=/app/data) and locally (e.g. DATA_DIR=./data).
"""

import os

# Directory holding all runtime state (SQLite DB, uploaded PDFs). Defaults to
# the container path; override via env for local dev, e.g. DATA_DIR=./data.
DATA_DIR = os.getenv("DATA_DIR", "/app/data")

# Per-file upload size cap in MB.
MAX_UPLOAD_MB = 15

# Automatic ghosting threshold: an application still at ``received`` with no
# update for more than this many days is moved to ``ghosted`` (see
# repo.auto_ghost_stale_received). Override via env, e.g. GHOST_AFTER_DAYS=90.
GHOST_AFTER_DAYS = int(os.getenv("GHOST_AFTER_DAYS", "180"))

# Status vocabulary. Adding a status later is one line here plus one
# STATUS_COLORS entry below (the templates render the badge colors).
STATUSES = ("received", "interviewing", "offer", "accepted", "rejected", "ghosted")

# Subset of STATUSES still "waiting on a reply" — drives the waiting
# queue and stat cards on the dashboard.
WAITING_STATUSES = ("received", "interviewing", "offer")

# Badge color per status, used by the templates.
STATUS_COLORS = {
    "received": "#2563eb",     # blue — submitted, no reply yet
    "interviewing": "#f59e0b",  # amber — interview(s) in progress
    "offer": "#8b5cf6",         # purple — offer extended, decision pending
    "accepted": "#16a34a",      # green — job secured
    "rejected": "#dc2626",      # red — declined / not selected
    "ghosted": "#6b7280",       # gray — process ended without response
}
