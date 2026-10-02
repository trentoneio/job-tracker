"""SQLAlchemy 2.0 ORM models for the job tracker (PLAN.md §4).

Two tables:

* ``applications`` — one row per application; its ``status`` column always
  mirrors the latest event in ``status_events`` (the repo layer keeps that
  invariant, §4 rules).
* ``status_events`` — append-only history of status changes. This is the
  source of truth for lifecycle reconstruction and the Sankey diagram (§6).

All timestamps are naive UTC datetimes; the SQLite dialect stores them as
ISO-8601 strings, per §7 (stored UTC, displayed locally as plain dates).

Note on definition order: ``StatusEvent`` is defined before ``Application``
purely so that ``Application.events`` can reference real column objects for
its ``order_by`` (SQLAlchemy 2.x does not accept string expressions there);
the reverse FK/relationship uses a forward-referenced table name, which the
ORM resolves at mapper-configuration time.
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import STATUSES


class Base(DeclarativeBase):
    """Declarative base for all job-tracker tables."""


def utc_now() -> datetime:
    """Naive UTC timestamp for storage (§7)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# The status vocabulary has a single source of truth (app.config.STATUSES);
# mirror it into a DB-level CHECK so bad data cannot be written even if some
# code path bypasses the repository layer.
_STATUS_VALUES = ", ".join(f"'{status}'" for status in STATUSES)


class StatusEvent(Base):
    """Append-only record of one status change (§4).

    Events are never edited or deleted: the full lifecycle of an application is
    reconstructable at any time, and this table feeds both the detail-page
    timeline (S2/S3) and the Sankey diagram (S4).
    """

    __tablename__ = "status_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # NULL on the initial event written when the application is created.
    from_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)

    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    application: Mapped["Application"] = relationship(back_populates="events")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return (
            f"<StatusEvent id={self.id} app={self.application_id} "
            f"{self.from_status!r} -> {self.to_status!r} at {self.changed_at!r}>"
        )


class Application(Base):
    """One job application (§4)."""

    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="ck_applications_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    job_title: Mapped[str] = mapped_column(Text, nullable=False)
    reference_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applied_on: Mapped[date] = mapped_column(Date, nullable=False)

    # Always mirrors the latest status_events row (§4 rules). Creating an
    # application always starts at "received", regardless of inputs.
    status: Mapped[str] = mapped_column(Text, nullable=False, default="received")

    job_posting_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # PDF storage paths are relative to data/uploads/<id>/ (§7). The original
    # uploaded file names are stored separately so downloads can use friendly
    # names while the on-disk storage names stay stable.
    resume_pdf: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    application_pdf: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resume_file_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    application_file_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    events: Mapped[list["StatusEvent"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by=[StatusEvent.changed_at.asc(), StatusEvent.id.asc()],
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Application id={self.id} company={self.company!r} status={self.status!r}>"
