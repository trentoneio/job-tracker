"""Dashboard tests (PLAN.md §6): states, filter slicing of every widget,
waiting-queue ordering and stat-card values.

Seeding goes through the repo (not the forms) and then pins every
``status_events.changed_at`` to an exact UTC instant so all day math is
deterministic no matter when the suite runs. The live DATA_DIR is never
touched (§7)."""

import re
from datetime import date, datetime, timedelta, timezone

import sqlalchemy as sa
import pytest
from fastapi.testclient import TestClient

from app import config, db, repo
from app.db import open_session
from app.main import create_app
from app.models import StatusEvent, utc_now


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """An app wired to a fresh temp DATA_DIR (same pattern as test_api.py)."""
    data_dir = tmp_path / "data"
    # config reads it at call time for uploads; db binds its own copy and the
    # lazily-created engine/session factory must be dropped so lifespan's
    # init_db() rebuilds them against this test's temp dir.
    monkeypatch.setattr(config, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(db, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(db, "_default_engine", None)
    monkeypatch.setattr(db, "_default_factory", None)

    with TestClient(create_app()) as test_client:
        yield test_client

    # Don't let later tests reuse this test's temp database.
    db._default_engine = None
    db._default_factory = None


# ---------------------------------------------------------------------------
# fixture data — the four applications used by most tests below:
#
#   A  Acme Corp / Backend Engineer, applied t-10, interviewing (first reply after 4 days)
#   B  Globex      / Data Analyst,    applied t-4,  offer       (first reply after 1 day)
#   C  Initech     / Frontend Dev,    applied t-2,  received    (no reply yet)
#   D  Acme Corp   / SRE,             applied t-30, rejected    (first reply after 5 days)
# ---------------------------------------------------------------------------

def _seed_dashboard(client):
    """Create A/B/C/D with pinned event timestamps. Returns ``(R, ids)`` where
    ``R`` is the UTC "today" used for all offsets and ``ids`` maps key → id."""
    R = utc_now().date()
    # (key, company, title, ref, applied_days_ago, status, change_days_ago|None)
    specs = [
        ("A", "Acme Corp", "Backend Engineer", "REF-A", 10, "interviewing", 6),
        ("B", "Globex", "Data Analyst", None, 4, "offer", 3),
        ("C", "Initech", "Frontend Dev", "REF-C", 2, "received", None),
        ("D", "Acme Corp", "SRE", "REF-D", 30, "rejected", 25),
    ]

    def at(days_ago: int, hour: int, minute: int) -> datetime:
        base = datetime(R.year, R.month, R.day, hour, minute, tzinfo=timezone.utc)
        return base - timedelta(days=days_ago)

    ids: dict[str, int] = {}
    event_times: dict[int, list[datetime]] = {}
    with open_session() as session:
        for key, company, title, ref, applied_days, status, change_days in specs:
            application = repo.create_application(
                session,
                company=company,
                job_title=title,
                reference_number=ref,
                applied_on=R - timedelta(days=applied_days),
            )
            if status != "received":
                repo.update_application(session, application.id, status=status)
            ids[key] = application.id
            event_times[application.id] = [at(applied_days, 9, 0)] + (
                [at(change_days, 12, 0)] if change_days else []
            )

    # Pin every event to its spec time so day math never depends on wall clock.
    with open_session() as session:
        per_app: dict[int, int] = {}
        for event in session.scalars(
            sa.select(StatusEvent).order_by(StatusEvent.application_id, StatusEvent.id)
        ):
            seq = per_app.get(event.application_id, 0)
            event.changed_at = event_times[event.application_id][seq]
            per_app[event.application_id] = seq + 1
        session.commit()

    return R, ids


# ---------------------------------------------------------------------------
# HTML helpers — the page is server-rendered; assert on visible values.
# ---------------------------------------------------------------------------

def _card(page: str, label: str) -> str | None:
    """The stat-value text of the card whose label matches exactly."""
    match = re.search(
        r'<span class="stat-value">([^<]*)</span>\s*<span class="stat-label">'
        + re.escape(label),
        page,
        flags=re.S,
    )
    return match.group(1).strip() if match else None


def _data_rows(page: str, start_marker: str, end_marker: str) -> list[list[str]]:
    """Plain-text cell lists of every data-href table row between two markers."""
    start = page.index(start_marker)
    chunk = page[start:page.index(end_marker, start)]
    rows = []
    for match in re.finditer(
        r'<tr data-href="/applications/\d+"[^>]*>(.*?)</tr>', chunk, flags=re.S
    ):
        cells = [
            re.sub(r"<[^>]+>", "", cell).strip()
            for cell in re.findall(r"<td[^>]*>(.*?)</td>", match.group(1), flags=re.S)
        ]
        rows.append(cells)
    return rows


def _queue_rows(page: str) -> list[list[str]]:
    """[company, title, status, days, links-cell] per waiting-queue row."""
    return _data_rows(page, 'id="waiting-title"', 'id="all-title"')


# ---------------------------------------------------------------------------
# empty states
# ---------------------------------------------------------------------------

def test_empty_dashboard(client):
    page = client.get("/").text
    assert _card(page, "Total applications") == "0"
    assert _card(page, "Waiting on employer") == "0"
    assert _card(page, "Closed (terminal) rate") == "—"
    assert _card(page, "Median days to first response") == "—"
    assert "No applications yet" in page
    assert "Nothing waiting right now." in page
    # HTMX is vendored locally and the filter bar re-renders through it (§3/§6).
    assert "/static/vendor/htmx.min.js" in page
    assert 'hx-get="/"' in page and 'hx-target="body"' in page


def test_no_match_filter_shows_empty_states(client):
    _seed_dashboard(client)
    page = client.get("/?company=NoSuchCorp").text
    assert _card(page, "Total applications") == "0"
    assert _card(page, "Waiting on employer") == "0"
    assert _card(page, "Closed (terminal) rate") == "—"
    assert _card(page, "Median days to first response") == "—"
    assert "Nothing matches these filters" in page
    assert "Nothing waiting right now." in page


# ---------------------------------------------------------------------------
# unfiltered dashboard: every widget over the full dataset
# ---------------------------------------------------------------------------

def test_unfiltered_widgets_cover_all_data(client):
    R, _ = _seed_dashboard(client)
    page = client.get("/").text

    # Cards: 4 total; A+B+C waiting; 1/4 closed → 25%; median of (4,1,5) days.
    assert _card(page, "Total applications") == "4"
    assert _card(page, "Waiting on employer") == "3"
    assert _card(page, "Closed (terminal) rate") == "25%"
    assert _card(page, "Median days to first response") == "4"

    # Waiting queue: most days since applied first (§6 item 4).
    queue = _queue_rows(page)
    assert [(row[0], row[2], row[3]) for row in queue] == [
        ("Acme Corp", "interviewing", "10"),
        ("Globex", "offer", "4"),
        ("Initech", "received", "2"),
    ]

    # All-applications table: newest applied first, with ref/days/links cells.
    rows = _data_rows(page, 'id="all-title"', "</section>")
    assert [(row[0], row[1], row[3], row[4], row[5]) for row in rows] == [
        ("Initech", "Frontend Dev", (R - timedelta(days=2)).isoformat(), "received", "2"),
        ("Globex", "Data Analyst", (R - timedelta(days=4)).isoformat(), "offer", "4"),
        ("Acme Corp", "Backend Engineer", (R - timedelta(days=10)).isoformat(), "interviewing", "10"),
        ("Acme Corp", "SRE", (R - timedelta(days=30)).isoformat(), "rejected", "30"),
    ]
    # Ref column shows refs where present and a dash otherwise.
    assert [row[2] for row in rows] == ["REF-C", "—", "REF-A", "REF-D"]


# ---------------------------------------------------------------------------
# filters slice every widget with the same predicate (§6 item 2)
# ---------------------------------------------------------------------------

def test_company_filter_slices_every_widget(client):
    _seed_dashboard(client)
    page = client.get("/?company=Acme%20Corp").text

    # Slice is A + D: total 2, only A waiting, 1/2 closed → 50%, median of (4,5).
    assert _card(page, "Total applications") == "2"
    assert _card(page, "Waiting on employer") == "1"
    assert _card(page, "Closed (terminal) rate") == "50%"
    assert _card(page, "Median days to first response") == "4.5"

    queue = _queue_rows(page)
    assert [(row[0], row[3]) for row in queue] == [("Acme Corp", "10")]

    rows = _data_rows(page, 'id="all-title"', "</section>")
    # Exactly A and D remain (A applied t-10 sorts before D at t-30).
    assert [(row[0], row[1]) for row in rows] == [
        ("Acme Corp", "Backend Engineer"),
        ("Acme Corp", "SRE"),
    ]

    # Unfiltered companies are absent from the whole page — including the
    # company dropdown, which only offers All companies + the filtered set.
    assert "Globex" not in page and "Initech" not in page


def test_status_filter_slices_every_widget(client):
    _seed_dashboard(client)
    page = client.get("/?status=interviewing&status=offer").text

    # Slice is A + B: both waiting, none closed, median of (4,1).
    assert _card(page, "Total applications") == "2"
    assert _card(page, "Waiting on employer") == "2"
    assert _card(page, "Closed (terminal) rate") == "0%"
    assert _card(page, "Median days to first response") == "2.5"

    queue = _queue_rows(page)
    assert [(row[0], row[3]) for row in queue] == [("Acme Corp", "10"), ("Globex", "4")]

    # The rejected app (D) and the still-received one (C) are gone.
    assert "REF-D" not in page and "REF-C" not in page

    # Chip selections survive a re-render; unchecked statuses stay unchecked.
    flat = re.sub(r"\s+", " ", page)
    assert 'value="interviewing" checked' in flat
    assert 'value="offer" checked' in flat
    assert 'value="rejected" checked' not in flat


def test_date_filter_slices_every_widget(client):
    R, _ = _seed_dashboard(client)
    date_from = (R - timedelta(days=10)).isoformat()
    date_to = (R - timedelta(days=2)).isoformat()
    page = client.get(f"/?date_from={date_from}&date_to={date_to}").text

    # Slice is A + B + C: D (applied t-30) falls outside the range.
    assert _card(page, "Total applications") == "3"
    assert _card(page, "Waiting on employer") == "3"
    assert _card(page, "Closed (terminal) rate") == "0%"
    assert _card(page, "Median days to first response") == "2.5"

    rows = _data_rows(page, 'id="all-title"', "</section>")
    assert [row[1] for row in rows] == ["Frontend Dev", "Data Analyst", "Backend Engineer"]
    assert "REF-D" not in page and "SRE" not in page

    # The date inputs echo the active range back.
    flat = re.sub(r"\s+", " ", page)
    assert f'name="date_from" value="{date_from}"' in flat
    assert f'name="date_to" value="{date_to}"' in flat


def test_invalid_dates_are_rejected(client):
    _seed_dashboard(client)
    assert client.get("/?date_from=not-a-date").status_code == 422
    assert client.get("/?date_to=bogus").status_code == 422
