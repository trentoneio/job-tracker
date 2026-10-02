"""Repository functions for the data layer (PLAN.md §4 rules).

Higher layers (API routes in S2, dashboard rendering in S3, CSV export in S5)
call these instead of managing sessions themselves. Each function runs its
work inside a single transaction and commits before returning.

Conventions:

* ``session`` is the first argument so tests can point at their own database;
  app-layer call sites get one from ``app.db.open_session()``.
* Returned models are fully loaded (the session factory uses
  ``expire_on_commit=False``), safe to read after the session closes.
"""

from collections.abc import Iterable
from datetime import date
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import STATUSES
from app.models import Application, StatusEvent, utc_now

_MISSING = object()


def create_application(
    session: Session,
    *,
    company: str,
    job_title: str,
    applied_on: date,
    reference_number: Optional[str] = None,
    status: Any = _MISSING,  # accepted-but-ignored per §4 (see docstring)
    job_posting_url: Optional[str] = None,
    notes: Optional[str] = None,
    resume_pdf: Optional[str] = None,
    application_pdf: Optional[str] = None,
    resume_file_name: Optional[str] = None,
    application_file_name: Optional[str] = None,
) -> Application:
    """Insert a new application and its single initial status event.

    Every application starts at ``received`` no matter what is passed in (§4):
    the row and the ``NULL → received`` event are written in one transaction.
    The ``status`` parameter exists so S2's create form can pass its input
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
    """Shared filter predicate (§5: every parameter optional; empty = all).

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
    dashboard's default sort (§5). No parameters / empty values return all
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
    then timestamp — the exact input shape S4's Sankey builder and S5's
    ``/api/events.csv`` consume.
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
    session: Session, application_id: int, **fields: Any
) -> Optional[Application]:
    """Apply field edits to an existing application.

    * Omit a keyword argument to leave that column unchanged; passing ``None``
      clears the column (so S2's forms can empty optional fields).
    * If ``status`` is provided and differs from the current value, exactly one
      event (old → new) is appended and ``applications.status`` mirrors it.
      Setting the same status appends nothing (§4).
    * ``updated_at`` is always bumped, even for non-status edits or no-ops.

    Returns the updated application, or ``None`` if the id does not exist.
    Unknown field names raise ``TypeError``; invalid statuses raise
    ``ValueError`` (both before any database change).
    """
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise TypeError(f"cannot update field(s): {', '.join(sorted(unknown))}")

    new_status = fields.pop("status", _MISSING)
    if new_status is not _MISSING and new_status not in STATUSES:
        raise ValueError(
            f"unknown status {new_status!r}; expected one of {', '.join(STATUSES)}"
        )

    application = session.get(Application, application_id)
    if application is None:
        return None

    previous_status = application.status
    for name, value in fields.items():
        setattr(application, name, value)

    status_changed = False
    if new_status is not _MISSING and new_status != previous_status:
        status_changed = True
        application.status = new_status

    if status_changed:
        session.add(
            StatusEvent(
                application_id=application.id,
                from_status=previous_status,
                to_status=new_status,
            )
        )

    application.updated_at = utc_now()
    session.commit()
    return application


def delete_application(session: Session, application_id: int) -> bool:
    """Delete the application; its status events cascade away (§4).

    Returns ``True`` if a row was deleted. Removing the PDFs from
    ``data/uploads/<id>/`` is S2's concern — this layer only owns rows.
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
