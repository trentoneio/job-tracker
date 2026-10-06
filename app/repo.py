"""Repository functions for the data layer.

Higher layers (the HTTP routes, the dashboard render, the CSV exports) call
these instead of managing sessions themselves. Each function runs its
work inside a single transaction and commits before returning.

Conventions:

* ``session`` is the first argument so tests can point at their own database;
  app-layer call sites get one from ``app.db.open_session()``.
* Returned models are fully loaded (the session factory uses
  ``expire_on_commit=False``), safe to read after the session closes.
"""

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import GHOST_AFTER_DAYS, STATUSES
from app.models import Application, StatusEvent, utc_now

_MISSING = object()


def create_application(
    session: Session,
    *,
    company: str,
    job_title: str,
    applied_on: date,
    reference_number: Optional[str] = None,
    status: Any = _MISSING,  # accepted but ignored — see docstring
    job_posting_url: Optional[str] = None,
    notes: Optional[str] = None,
    resume_pdf: Optional[str] = None,
    application_pdf: Optional[str] = None,
    resume_file_name: Optional[str] = None,
    application_file_name: Optional[str] = None,
) -> Application:
    """Insert a new application and its single initial status event.

    Every application starts at ``received`` no matter what is passed in:
    the row and the ``NULL → received`` event are written in one transaction.
    The ``status`` parameter exists so the create form can pass its input
    through unchanged; it is deliberately ignored here rather than asserted on,
    keeping this layer tolerant of later UI evolution.
    """
    if status is not _MISSING and status != "received":
        # Documented as accepted-but-ignored: silently starting a fresh
        # application somewhere other than "received" would corrupt the event
        # log, so fail loudly during development instead.
        raise ValueError(
            f"new applications always start at 'received', got {status!r}"
        )

    application = Application(
        company=company,
        job_title=job_title,
        applied_on=applied_on,
        reference_number=reference_number,
        status="received",
        job_posting_url=job_posting_url,
        notes=notes,
        resume_pdf=resume_pdf,
        application_pdf=application_pdf,
        resume_file_name=resume_file_name,
        application_file_name=application_file_name,
    )
    session.add(application)
    session.flush()  # obtain the id for the FK below; same transaction

    session.add(
        StatusEvent(application_id=application.id, from_status=None, to_status="received")
    )
    session.commit()
    return application


def get_application(session: Session, application_id: int) -> Optional[Application]:
    """Return the application with this id, or ``None`` if it does not exist."""
    return session.get(Application, application_id)


def _apply_filters(
    query,
    *,
    company: Optional[str] = None,
    statuses: Iterable[str] | None = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    """Shared filter predicate (every parameter optional; empty means all).

    * ``company`` — exact match.
    * ``statuses`` — current status in the given set; an empty/None iterable
      means no restriction ("all applications").
    * ``date_from``/``date_to`` — inclusive range on ``applied_on``.

    The same predicate powers both CSV endpoints and the dashboard render, so
    "export what you are looking at" holds by construction.
    """
    if company is not None:
        query = query.where(Application.company == company)
    status_list = list(statuses or ())
    if status_list:
        query = query.where(Application.status.in_(status_list))
    if date_from is not None:
        query = query.where(Application.applied_on >= date_from)
    if date_to is not None:
        query = query.where(Application.applied_on <= date_to)
    return query


def list_applications(
    session: Session,
    *,
    company: Optional[str] = None,
    statuses: Iterable[str] | None = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[Application]:
    """Return applications matching the (all-optional) filters.

    Ordered newest first by ``applied_on`` (id as tiebreaker), which is also the
    dashboard's default sort. No parameters / empty values return all
    applications, ordered identically.
    """
    query = select(Application)
    query = _apply_filters(
        query, company=company, statuses=statuses, date_from=date_from, date_to=date_to
    )
    query = query.order_by(Application.applied_on.desc(), Application.id.desc())
    return list(session.scalars(query))


def get_status_events(session: Session, application_id: int) -> list[StatusEvent]:
    """All status events for one application, oldest first (the timeline)."""
    query = select(StatusEvent).where(StatusEvent.application_id == application_id)
    query = query.order_by(StatusEvent.changed_at.asc(), StatusEvent.id.asc())
    return list(session.scalars(query))


def get_status_events_for_filter(
    session: Session,
    *,
    company: Optional[str] = None,
    statuses: Iterable[str] | None = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[StatusEvent]:
    """Every status event belonging to the currently filtered application set.

    Filter semantics are identical to :func:`list_applications` (predicate on
    current ``applications.status``); for every matching application its full
    event history is returned. Ordered deterministically by application id,
    then timestamp — the exact input shape the Sankey payload builder and the
    ``/api/events.csv`` export consume.
    """
    query = select(StatusEvent).join(
        Application, StatusEvent.application_id == Application.id
    )
    # _apply_filters binds its clauses against the joined Application entity.
    query = _apply_filters(
        query,
        company=company,
        statuses=statuses,
        date_from=date_from,
        date_to=date_to,
    )
    return list(session.scalars(query.order_by(
        Application.id.asc(), StatusEvent.changed_at.asc(), StatusEvent.id.asc()
    )))


# Columns without a default that may never be NULL.
_NON_NULLABLE_FIELDS = frozenset({"company", "job_title", "applied_on"})

_UPDATABLE_FIELDS = frozenset({
    "company",
    "job_title",
    "reference_number",
    "applied_on",
    "status",
    "job_posting_url",
    "notes",
    "resume_pdf",
    "application_pdf",
    "resume_file_name",
    "application_file_name",
})


def update_application(
    session: Session,
    application_id: int,
    *,
    status_changed_on: date | None = None,
    **fields: Any,
) -> Optional[Application]:
    """Apply field edits to an existing application.

    * Omit a keyword argument to leave that column unchanged; passing ``None``
      clears the column (so form edits can empty optional fields).
    * If ``status`` is provided and differs from the current value, exactly one
      event (old → new) is appended and ``applications.status`` mirrors it.
      Setting the same status appends nothing.
    * ``status_changed_on`` optionally backdates that event's timestamp: a
      calendar day becomes midnight UTC on that date. It only applies when a
      real status change happens; otherwise (and with no value) events are
      stamped with the current time.
    * ``updated_at`` is always bumped, even for non-status edits or no-ops.

    Returns the updated application, or ``None`` if the id does not exist.
    Unknown field names raise ``TypeError``; invalid statuses and attempts to
    clear a required column (company/job_title/applied_on) raise
    ``ValueError`` — all before any database change.
    """
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise TypeError(f"cannot update field(s): {', '.join(sorted(unknown))}")

    new_status = fields.pop("status", _MISSING)
    if new_status is not _MISSING and new_status not in STATUSES:
        raise ValueError(
            f"unknown status {new_status!r}; expected one of {', '.join(STATUSES)}"
        )

    # Explicit event timestamp: a day becomes midnight UTC; a full datetime is
    # used as given. Anything else is a caller bug, not user input.
    if type(status_changed_on) is date:
        status_time = datetime.combine(
            status_changed_on, time.min, tzinfo=timezone.utc
        )
    elif isinstance(status_changed_on, datetime):
        status_time = status_changed_on
    elif status_changed_on is None:
        status_time = None
    else:
        raise TypeError("status_changed_on must be a date, a datetime or None")

    application = session.get(Application, application_id)
    if application is None:
        return None

    # Validate everything before mutating anything: a failed update must not
    # leave partially-changed objects behind regardless of key order.
    for name, value in fields.items():
        if value is None and name in _NON_NULLABLE_FIELDS:
            raise ValueError(f"field {name!r} cannot be cleared")

    previous_status = application.status
    for name, value in fields.items():
        setattr(application, name, value)

    status_changed = False
    if new_status is not _MISSING and new_status != previous_status:
        status_changed = True
        application.status = new_status

    if status_changed:
        event = StatusEvent(
            application_id=application.id,
            from_status=previous_status,
            to_status=new_status,
        )
        # Only set changed_at when an explicit timestamp was given: passing
        # None explicitly would bind NULL and bypass the column default.
        if status_time is not None:
            event.changed_at = status_time
        session.add(event)

    application.updated_at = utc_now()
    session.commit()
    return application


def auto_ghost_stale_received(
    session: Session, *, today: date | None = None
) -> list[int]:
    """Ghost applications stuck at ``received`` past the inactivity window.

    An application is stale when its current status is ``received`` and it has
    had no update for more than ``config.GHOST_AFTER_DAYS`` days (default 180):
    ``updated_at`` strictly before midnight UTC on (today − GHOST_AFTER_DAYS).
    Exactly the boundary day does not trigger; one day past it does. Any edit
    — status or otherwise — resets ``updated_at``, so a touched application is
    never ghosted.

    Each stale application gets its status flipped to ``ghosted`` with exactly
    one new event (received → ghosted) stamped at the current time, and its
    ``updated_at`` bumped. Everything runs in a single transaction: all-or-
    nothing on failure. Returns the affected application ids.
    """
    today = today or utc_now().date()
    cutoff = datetime.combine(
        today - timedelta(days=GHOST_AFTER_DAYS), time.min
    )
    query = select(Application).where(
        Application.status == "received",
        Application.updated_at < cutoff,
    )
    stale = list(session.scalars(query))
    for application in stale:
        session.add(
            StatusEvent(
                application_id=application.id,
                from_status="received",
                to_status="ghosted",
            )
        )
        application.status = "ghosted"
        application.updated_at = utc_now()
    session.commit()
    return [app.id for app in stale]


def delete_application(session: Session, application_id: int) -> bool:
    """Delete the application; its status events cascade away with it.

    Returns ``True`` if a row was deleted. Removing the PDFs from
    ``<DATA_DIR>/uploads/<id>/`` belongs to the route handlers — this layer
    only owns rows.
    """
    application = session.get(Application, application_id)
    if application is None:
        return False
    # ORM cascade ("all, delete-orphan") removes the events; the DB-level FK
    # CASCADE (with foreign_keys=ON in app.db) is a backstop for any path that
    # deletes rows outside the ORM.
    session.delete(application)
    session.commit()
    return True
