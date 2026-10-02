"""Runtime configuration for the job tracker.

Plain module reading environment variables with defaults, so the same code
runs in Docker (DATA_DIR=/app/data) and locally (e.g. DATA_DIR=./data).
"""

import os

# Directory holding all runtime state (SQLite DB, uploaded PDFs). Defaults to
# the container path; override via env for local dev, e.g. DATA_DIR=./data.
DATA_DIR = os.getenv("DATA_DIR", "/app/data")

# Per-file upload size cap in MB (§7).
MAX_UPLOAD_MB = 15

# Status vocabulary (§4.1). Adding a status later is one line here plus one
# STATUS_COLORS entry below (S3 renders the badge colors).
STATUSES = ("received", "interviewing", "offer", "accepted", "rejected", "ghosted")

# Subset of STATUSES still "waiting on a reply" (§4.1) — drives the waiting
# queue and stat cards in S3.
WAITING_STATUSES = ("received", "interviewing", "offer")

# Badge color per status for the dashboard (S3 consumes this).
STATUS_COLORS = {
    "received": "#2563eb",     # blue — submitted, no reply yet
    "interviewing": "#f59e0b",  # amber — interview(s) in progress
    "offer": "#8b5cf6",         # purple — offer extended, decision pending
    "accepted": "#16a34a",      # green — job secured
    "rejected": "#dc2626",      # red — declined / not selected
    "ghosted": "#6b7280",       # gray — process ended without response
}
