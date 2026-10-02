"""Data layer tests: models, repository rules (§4) and the shared filter predicate.

Every fixture builds a throwaway SQLite database under pytest's ``tmp_path`` —
the real DATA_DIR (and thus any user data) is never touched, per PLAN.md §7.
"""

import time
from datetime import date

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app import repo
from app.db import create_db_engine, init_db, make_session_factory
from app.models import Application, StatusEvent


@pytest.fixture()
def engine(tmp_path):
    """A fresh database in a temp dir; double-init proves idempotency."""
    eng = create_db_engine(tmp_path / "data")
    init_db(eng)
    init_db(eng)  # must be safe to run twice (restarts, re-runs)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    """A bound ORM session; closed afterwards even on test failure."""
    db = make_session_factory(engine)()
    try:
        yield db
    finally:
        db.close()


def _make(session, **overrides):
    kwargs = dict(company="Acme Corp", job_title="Backend Engineer", applied_on=date(2026, 9, 1))
    kwargs.update(overrides)
    return repo.create_application(session, **kwargs)


def _events(db, application_id):
    """Fresh read of one application's events straight from the table."""
    stmt = select(StatusEvent).where(StatusEvent.application_id == application_id)
    return list(db.scalars(stmt.order_by(StatusEvent.changed_at.asc(), StatusEvent.id.asc())))


# ---------------------------------------------------------------------------
# creation
# ---------------------------------------------------------------------------

def test_create_persists_fields_and_defaults(session):
    app = _make(
        session,
        reference_number="REF-42",
        job_posting_url="https://example.com/jobs/1",
        notes="first contact via LinkedIn",
        resume_pdf="resume.pdf",
        application_pdf="application.pdf",
        resume_file_name="my-cv.pdf",
        application_file_name="cover-letter.pdf",
    )
    assert app.id is not None
    fresh = repo.get_application(session, app.id)

    assert fresh.company == "Acme Corp"
    assert fresh.job_title == "Backend Engineer"
    assert fresh.applied_on == date(2026, 9, 1)
    assert fresh.reference_number == "REF-42"
    assert fresh.job_posting_url == "https://example.com/jobs/1"
    assert fresh.notes == "first contact via LinkedIn"
    assert fresh.resume_pdf == "resume.pdf"
    assert fresh.application_pdf == "application.pdf"
    assert fresh.resume_file_name == "my-cv.pdf"
    assert fresh.application_file_name == "cover-letter.pdf"
    assert fresh.status == "received"
    assert fresh.created_at is not None and fresh.updated_at is not None


def test_create_writes_exactly_one_initial_event(session):
    app = _make(session)
    events = _events(session, app.id)

    assert len(events) == 1
    event = events[0]
    assert event.application_id == app.id
    assert event.from_status is None  # no previous status at creation time
    assert event.to_status == "received"
    assert event.changed_at is not None


def test_create_rejects_non_received_initial_status(session):
    with pytest.raises(ValueError, match="always start at 'received'"):
        _make(session, status="offer")
    # nothing was committed by the failed call
    assert repo.list_applications(session) == []


# ---------------------------------------------------------------------------
# lookups and deletes
# ---------------------------------------------------------------------------

def test_get_application_returns_none_for_missing_id(session):
    assert repo.get_application(session, 999) is None


def test_delete_cascades_events_and_is_idempotent(session):
    app = _make(session)
    repo.update_application(session, app.id, status="interviewing")
    assert len(_events(session, app.id)) == 2

    assert repo.delete_application(session, app.id) is True
    assert repo.get_application(session, app.id) is None
    assert _events(session, app.id) == []

    # DB-level check: no orphaned rows anywhere in status_events
    orphans = session.execute(
        select(func.count()).select_from(StatusEvent).where(StatusEvent.application_id == app.id)
    ).scalar()
    assert orphans == 0
    assert repo.delete_application(session, app.id) is False


def test_check_constraint_rejects_unknown_status_at_database_level(session):
    """Even code that bypasses the repository cannot store a bad status."""
    bad = Application(company="X", job_title="Y", applied_on=date(2026, 9, 1), status="bogus")
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# ---------------------------------------------------------------------------
# status event rules (§4)
# ---------------------------------------------------------------------------

def test_status_change_appends_exactly_one_event_with_from_and_to(session):
    app = _make(session)
    first_changed_at = _events(session, app.id)[0].changed_at

    time.sleep(0.01)
    repo.update_application(session, app.id, status="interviewing")
    events = _events(session, app.id)
    assert len(events) == 2
    assert (events[1].from_status, events[1].to_status) == ("received", "interviewing")
    assert events[1].changed_at >= first_changed_at

    # full lifecycle chain stays consistent end to end
    time.sleep(0.01)
    repo.update_application(session, app.id, status="offer")
    time.sleep(0.01)
    updated = repo.update_application(session, app.id, status="accepted", notes="signed")

    assert [(e.from_status, e.to_status) for e in _events(session, app.id)] == [
        (None, "received"),
        ("received", "interviewing"),
        ("interviewing", "offer"),
        ("offer", "accepted"),
    ]
    # applications.status mirrors the latest event (§4 rule)
    assert updated.status == "accepted" == _events(session, app.id)[-1].to_status


def test_same_status_appends_no_event_but_bumps_updated_at(session):
    app = _make(session)
    time.sleep(0.01)
    old_updated_at = repo.get_application(session, app.id).updated_at

    updated = repo.update_application(session, app.id, status="received")

    assert len(_events(session, app.id)) == 1
    assert updated.updated_at > old_updated_at


def test_non_status_edits_change_no_events_but_bump_updated_at(session):
    app = _make(session)
    time.sleep(0.01)
    old_updated_at = repo.get_application(session, app.id).updated_at

    # None clears a nullable column; omitted keys stay untouched (§4 rule 3)
    updated = repo.update_application(
        session, app.id, company="Beta LLC", notes=None
    )

    assert len(_events(session, app.id)) == 1
    assert updated.company == "Beta LLC"
    assert updated.notes is None
    assert updated.job_title == "Backend Engineer"  # omitted key untouched
    assert updated.status == "received"
    assert updated.updated_at > old_updated_at


def test_update_returns_none_for_missing_id(session):
    assert repo.update_application(session, 999, notes="x") is None


def test_update_validates_before_writing(session):
    app = _make(session)

    with pytest.raises(ValueError, match="unknown status"):
        repo.update_application(session, app.id, status="bogus", notes="will not stick")
    with pytest.raises(TypeError, match="cannot update field"):
        repo.update_application(session, app.id, hacker=True)
    # required columns cannot be cleared to None
    for required in ("company", "job_title", "applied_on"):
        with pytest.raises(ValueError, match="cannot be cleared"):
            repo.update_application(session, app.id, **{required: None})

    fresh = repo.get_application(session, app.id)
    assert fresh.status == "received" and fresh.notes is None


def test_relationship_exposes_events_in_order(session):
    app = _make(session)
    time.sleep(0.01)
    repo.update_application(session, app.id, status="interviewing")

    # Expire everything so .events triggers a fresh DB load through the
    # relationship (exercising its order_by: changed_at then id).
    session.expire_all()
    loaded = session.get(Application, app.id)
    assert [(e.from_status, e.to_status) for e in loaded.events] == [
        (None, "received"),
        ("received", "interviewing"),
    ]


# ---------------------------------------------------------------------------
# shared filter predicate (§5: every parameter optional; empty = all)
# ---------------------------------------------------------------------------

def _seed(session):
    """Two applications with distinct dates/statuses for the filter tests."""
    acme = repo.create_application(
        session, company="Acme Corp", job_title="Backend Engineer",
        applied_on=date(2026, 9, 1),
    )
    globex = repo.create_application(
        session, company="Globex", job_title="Frontend Developer",
        applied_on=date(2026, 9, 5), notes="referral",
    )
    return acme, globex


def test_list_without_filters_returns_all_newest_first(session):
    acme, globex = _seed(session)
    listed = repo.list_applications(session)
    assert [a.id for a in listed] == [globex.id, acme.id]


def test_filter_by_company_is_exact_match(session):
    acme, globex = _seed(session)
    assert [a.company for a in repo.list_applications(session, company="Acme Corp")] == ["Acme Corp"]
    # partial matches must not leak through
    assert repo.list_applications(session, company="Acme") == []


def test_filter_by_status_set_uses_current_status(session):
    acme, globex = _seed(session)
    repo.update_application(session, acme.id, status="interviewing")

    assert [a.company for a in repo.list_applications(session, statuses={"interviewing"})] == ["Acme Corp"]
    # multi-status set is a union
    listed = repo.list_applications(session, statuses={"offer", "accepted", "received"})
    assert sorted(a.company for a in listed) == ["Globex"]


def test_empty_statuses_means_no_restriction(session):
    acme, globex = _seed(session)
    assert len(repo.list_applications(session, statuses=None)) == 2
    assert len(repo.list_applications(session, statuses=[])) == 2


def test_date_range_is_inclusive_on_both_ends(session):
    acme, globex = _seed(session)
    # both boundaries land exactly on the seeded dates
    listed = repo.list_applications(
        session, date_from=date(2026, 9, 1), date_to=date(2026, 9, 5)
    )
    assert sorted(a.company for a in listed) == ["Acme Corp", "Globex"]
    # one day tighter on each side excludes both
    assert repo.list_applications(
        session, date_from=date(2026, 9, 2), date_to=date(2026, 9, 4)
    ) == []
    # only lower bound set keeps everything from that day on
    assert [
        a.company for a in repo.list_applications(session, date_from=date(2026, 9, 5))
    ] == ["Globex"]


def test_combined_filters_intersect(session):
    acme, globex = _seed(session)
    repo.update_application(session, acme.id, status="interviewing")

    listed = repo.list_applications(
        session,
        company="Acme Corp",
        statuses={"interviewing", "offer"},
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 30),
    )
    assert [a.id for a in listed] == [acme.id]


def test_events_for_filter_covers_matching_applications_only(session):
    acme, globex = _seed(session)
    time.sleep(0.01)
    repo.update_application(session, acme.id, status="interviewing")  # 2 events now

    # filter on current status -> only Acme's full history comes back
    filtered = repo.get_status_events_for_filter(session, statuses={"interviewing"})
    assert [(e.application_id, e.to_status) for e in filtered] == [
        (acme.id, "received"),
        (acme.id, "interviewing"),
    ]

    # company filter selects the other application's history
    by_company = repo.get_status_events_for_filter(session, company="Globex")
    assert [(e.application_id, e.to_status) for e in by_company] == [
        (globex.id, "received"),
    ]

    # no filter -> everything, ordered by application id then timestamp
    all_events = repo.get_status_events_for_filter(session)
    assert [(e.application_id, e.to_status) for e in all_events] == [
        (acme.id, "received"),
        (acme.id, "interviewing"),
        (globex.id, "received"),
    ]


# ---------------------------------------------------------------------------
# engine configuration (§7)
# ---------------------------------------------------------------------------

def test_wal_journal_mode_is_active(engine):
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar().lower() == "wal"


def test_foreign_keys_pragma_is_enforced(engine):
    # foreign_keys must be ON per connection for the FK CASCADE to work
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
