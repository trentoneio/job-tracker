"""CSV export endpoints (PLAN.md §5).

Both endpoints reuse the exact same shared filter predicate as the dashboard
render — no separate filtering logic. No filters = full dataset ("export what
you're looking at"). Rows are built purely from repository results; nothing
here touches SQL directly.
"""

import csv
import io
from datetime import date, datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Query, Response

from app.db import open_session
from app.repo import get_status_events_for_filter, list_applications

router = APIRouter()


def _clean(value: str | None) -> str | None:
    """Trim a free-text filter value; empty/whitespace-only means no filter."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _download_name(prefix: str) -> str:
    """UTC timestamped download name, e.g. ``applications_20261005_1830.csv``."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    return f"{prefix}_{stamp}.csv"


def _csv_response(rows: list[list], header: list[str], filename: str) -> Response:
    """Serialize rows to CSV and serve it as an attachment download."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)  # None cells serialize as empty strings.
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/export.csv")
def export_applications_csv(
    company: Annotated[Optional[str], Query()] = None,
    status: Annotated[list[str], Query()] = [],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> Response:
    """Download the (filtered) applications as CSV.

    Same filter params and semantics as ``GET /`` (§6 item 2), same shared
    predicate as every dashboard widget (§5). Columns exactly per §5:
    id, company, job_title, reference_number, applied_on, status,
    job_posting_url, notes, resume filename, application filename,
    created_at, updated_at. The two PDF columns carry the original filenames
    stored in S2 (empty when nothing was uploaded).
    """
    with open_session() as session:
        apps = list_applications(
            session,
            company=_clean(company),
            statuses=[value for value in status if value],
            date_from=date_from,
            date_to=date_to,
        )

    rows = [
        [
            app.id,
            app.company,
            app.job_title,
            app.reference_number,
            app.applied_on.isoformat(),
            app.status,
            app.job_posting_url,
            app.notes,
            app.resume_file_name,
            app.application_file_name,
            app.created_at.isoformat(),
            app.updated_at.isoformat(),
        ]
        for app in apps
    ]
    return _csv_response(
        rows,
        [
            "id",
            "company",
            "job_title",
            "reference_number",
            "applied_on",
            "status",
            "job_posting_url",
            "notes",
            "resume_filename",
            "application_filename",
            "created_at",
            "updated_at",
        ],
        _download_name("applications"),
    )


@router.get("/api/events.csv")
def export_status_events_csv(
    company: Annotated[Optional[str], Query()] = None,
    status: Annotated[list[str], Query()] = [],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> Response:
    """Download the (filtered) applications' full status histories as CSV.

    One row per status event — initial creation included (`from_status` empty)
    — in the same deterministic order as ``repo.get_status_events_for_filter``
    (application id, then timeline order), so rows exactly match each
    application's ``status_events`` history. Same filter params and semantics
    as ``GET /``; company is joined from the applications under the same
    predicate.
    """
    with open_session() as session:
        events = get_status_events_for_filter(
            session,
            company=_clean(company),
            statuses=[value for value in status if value],
            date_from=date_from,
            date_to=date_to,
        )
        companies = {
            app.id: app.company
            for app in list_applications(
                session,
                company=_clean(company),
                statuses=[value for value in status if value],
                date_from=date_from,
                date_to=date_to,
            )
        }

    rows = [
        [
            event.application_id,
            companies[event.application_id],
            event.from_status or "",  # initial creation has no previous status
            event.to_status,
            event.changed_at.isoformat(),
        ]
        for event in events
    ]
    return _csv_response(
        rows,
        ["application_id", "company", "from_status", "to_status", "changed_at"],
        _download_name("status_events"),
    )