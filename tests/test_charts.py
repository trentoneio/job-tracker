"""Chart payload tests: the server-computed Sankey and pie data behind each
dashboard render, not the rendered pixels.

The fixture builds known transition histories across several companies,
statuses and applied dates through repo + pinned event timestamps (same
pattern as ``tests/test_dashboard.py::_seed_dashboard``); then we assert both
the JSON embedded in ``GET /`` responses and the pure analytics functions
across a matrix of filter combinations — the same slice predicate that drives
every other widget."""

import json
import re
from datetime import date, datetime, timedelta, timezone

import sqlalchemy as sa
import pytest
from fastapi.testclient import TestClient

from app import analytics, config, db, repo
from app.db import open_session
from app.main import create_app
from app.models import Application, StatusEvent, utc_now


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """An app wired to a fresh temp DATA_DIR (same pattern as test_dashboard.py)."""
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
# fixture data — five applications spanning the status vocabulary:
#
#   A  Acme Corp / Backend Engineer, applied t-40: received → interviewing → offer → accepted
#   B  Acme Corp / SRE,              applied t-35: received → rejected
#   C  Globex      / Data Analyst,   applied t-20: received (no reply yet)
#   D  Initech     / Frontend Dev,   applied t-15: received → interviewing
#   E  Hooli       / ML Engineer,    applied t-5:  received → offer → accepted
# ---------------------------------------------------------------------------

def _seed_charts(client):
    """Create A/B/C/D/E with pinned event timestamps. Returns UTC "today" R."""
    R = utc_now().date()
    # (key, company, title, ref, applied_days_ago, [(change_days_ago, status)])
    specs = [
        ("A", "Acme Corp", "Backend Engineer", "REF-A", 40, [(36, "interviewing"), (28, "offer"), (12, "accepted")]),
        ("B", "Acme Corp", "SRE", "REF-B", 35, [(20, "rejected")]),
        ("C", "Globex", "Data Analyst", None, 20, []),
        ("D", "Initech", "Frontend Dev", "REF-D", 15, [(7, "interviewing")]),
        ("E", "Hooli", "ML Engineer", "REF-E", 5, [(3, "offer"), (1, "accepted")]),
    ]

    def at(days_ago: int) -> datetime:
        return datetime(R.year, R.month, R.day, tzinfo=timezone.utc).replace(
            hour=9, minute=0
        ) - timedelta(days=days_ago)

    event_times: dict[int, list[datetime]] = {}
    with open_session() as session:
        for key, company, title, ref, applied_days, changes in specs:
            application = repo.create_application(
                session,
                company=company,
                job_title=title,
                reference_number=ref,
                applied_on=R - timedelta(days=applied_days),
            )
            for _, status in changes:  # one change per step, in the spec's order
                repo.update_application(session, application.id, status=status)
            event_times[application.id] = [at(applied_days)] + [at(d) for d, _ in changes]

    # Pin every event to its spec time so payloads never depend on wall clock.
    with open_session() as session:
        per_app: dict[int, int] = {}
        for event in session.scalars(
            sa.select(StatusEvent).order_by(StatusEvent.application_id, StatusEvent.id)
        ):
            seq = per_app.get(event.application_id, 0)
            event.changed_at = event_times[event.application_id][seq]
            per_app[event.application_id] = seq + 1
        session.commit()

    return R


# ---------------------------------------------------------------------------
# HTML helpers — the payloads are embedded as JSON script tags per render.
# ---------------------------------------------------------------------------

def _payload(page: str, tag_id: str) -> dict:
    """Parse the chart payload embedded under ``<script id=tag_id>``."""
    match = re.search(
        r'<script type="application/json" id="%s">(.*?)</script>' % re.escape(tag_id),
        page,
        flags=re.S,
    )
    assert match is not None, f"{tag_id} payload missing from rendered dashboard"
    return json.loads(match.group(1))


def _check_sankey(payload: dict) -> None:
    """Structural invariants every Sankey payload must satisfy."""
    names = [node["name"] for node in payload["nodes"]]
    assert len(names) == len(set(names)), "duplicate nodes"
    # The synthetic waiting sink, when present, is the last node and never a
    # source: applications flow into it while they are still open.
    if "waiting" in names:
        assert names[-1] == "waiting"
    for link in payload["links"]:
        assert set(link) == {"source", "target", "value"}
        assert link["source"] in names and link["target"] in names
        assert link["source"] != link["target"], "no self-transitions are possible"
        assert isinstance(link["value"], int) and link["value"] >= 1
        # Terminal statuses have no outflow by construction.
        assert link["source"] not in ("accepted", "rejected", "ghosted")
        # The waiting sink has no outflow of its own either.
        assert link["source"] != "waiting"


def _check_pie(payload: dict) -> None:
    """Structural invariants every pie payload must satisfy."""
    assert set(payload) == {"total", "slices"}
    assert payload["total"] == sum(s["count"] for s in payload["slices"])
    assert len({s["status"] for s in payload["slices"]}) == len(payload["slices"])


# ---------------------------------------------------------------------------
# embedding + wiring (the server side of the dashboard charts)
# ---------------------------------------------------------------------------

def test_dashboard_embeds_chart_payloads_and_vendors_echarts(client):
    _seed_charts(client)
    page = client.get("/").text

    # Both payloads are embedded per render, one JSON script tag each (and
    # parse cleanly as JSON — _payload raises if they don't).
    assert 'id="sankey-data"' in page and 'id="pie-data"' in page
    _payload(page, "sankey-data")
    _payload(page, "pie-data")

    # The chart sections exist for the client controller to render into.
    assert 'id="sankey-chart" class="chart"' in page
    assert 'id="pie-chart" class="chart"' in page

    # ECharts is vendored locally and the head registers one shared swap
    # listener (it lives in <head>, so body swaps never re-run or stack it).
    assert "/static/vendor/echarts.min.js" in page
    assert "htmx:afterSwap" in page


# ---------------------------------------------------------------------------
# unfiltered dashboard: both charts over the full dataset
# ---------------------------------------------------------------------------

def test_unfiltered_sankey_and_pie(client):
    _seed_charts(client)
    page = client.get("/").text

    sankey = _payload(page, "sankey-data")
    _check_sankey(sankey)
    # Nodes follow the status vocabulary order, with the synthetic waiting
    # node last; ghosted never occurred here.
    assert [n["name"] for n in sankey["nodes"]] == [
        "received", "interviewing", "offer", "accepted", "rejected", "waiting",
    ]
    # One count per application per distinct transition:
    # received→interviewing was taken by A and D; offer→accepted by A and E.
    # C (still received) and D (still interviewing) flow into waiting instead
    # of vanishing off the right edge.
    assert sankey["links"] == [
        {"source": "received", "target": "interviewing", "value": 2},
        {"source": "received", "target": "offer", "value": 1},
        {"source": "received", "target": "rejected", "value": 1},
        {"source": "received", "target": "waiting", "value": 1},
        {"source": "interviewing", "target": "offer", "value": 1},
        {"source": "interviewing", "target": "waiting", "value": 1},
        {"source": "offer", "target": "accepted", "value": 2},
    ]

    pie = _payload(page, "pie-data")
    _check_pie(pie)
    # Current statuses: C received, D interviewing, A+E accepted, B rejected.
    # No one is currently at `offer`, so that slice is absent entirely.
    assert pie == {
        "total": 5,
        "slices": [
            {"status": "received", "count": 1, "percent": 20.0},
            {"status": "interviewing", "count": 1, "percent": 20.0},
            {"status": "accepted", "count": 2, "percent": 40.0},
            {"status": "rejected", "count": 1, "percent": 20.0},
        ],
    }


# ---------------------------------------------------------------------------
# filters slice both charts with the same predicate
# ---------------------------------------------------------------------------

def test_company_filter_slices_charts(client):
    _seed_charts(client)
    page = client.get("/?company=Acme%20Corp").text  # A + B only

    sankey = _payload(page, "sankey-data")
    _check_sankey(sankey)
    assert [n["name"] for n in sankey["nodes"]] == [
        "received", "interviewing", "offer", "accepted", "rejected",
    ]
    # A's full history stays (its later statuses count); B adds received→rejected.
    assert sankey["links"] == [
        {"source": "received", "target": "interviewing", "value": 1},
        {"source": "received", "target": "rejected", "value": 1},
        {"source": "interviewing", "target": "offer", "value": 1},
        {"source": "offer", "target": "accepted", "value": 1},
    ]

    pie = _payload(page, "pie-data")
    assert pie == {
        "total": 2,
        "slices": [
            {"status": "accepted", "count": 1, "percent": 50.0},
            {"status": "rejected", "count": 1, "percent": 50.0},
        ],
    }


def test_status_filter_slices_charts(client):
    _seed_charts(client)
    page = client.get("/?status=interviewing&status=accepted").text  # A + D + E

    sankey = _payload(page, "sankey-data")
    _check_sankey(sankey)
    # D's only transition plus A and E's full histories; no rejected branch.
    # D is still at interviewing, so it also flows into the waiting node.
    assert [n["name"] for n in sankey["nodes"]] == [
        "received", "interviewing", "offer", "accepted", "waiting",
    ]
    assert sankey["links"] == [
        {"source": "received", "target": "interviewing", "value": 2},
        {"source": "received", "target": "offer", "value": 1},
        {"source": "interviewing", "target": "offer", "value": 1},
        {"source": "interviewing", "target": "waiting", "value": 1},
        {"source": "offer", "target": "accepted", "value": 2},
    ]

    pie = _payload(page, "pie-data")
    assert pie == {
        "total": 3,
        "slices": [
            {"status": "interviewing", "count": 1, "percent": 33.3},
            {"status": "accepted", "count": 2, "percent": 66.7},
        ],
    }


def test_date_filter_slices_charts(client):
    R = _seed_charts(client)
    date_from = (R - timedelta(days=25)).isoformat()
    date_to = (R - timedelta(days=10)).isoformat()  # C + D only

    page = client.get(f"/?date_from={date_from}&date_to={date_to}").text
    sankey = _payload(page, "sankey-data")
    _check_sankey(sankey)
    # Both applications are still open, so each flows into the waiting node.
    assert [n["name"] for n in sankey["nodes"]] == [
        "received", "interviewing", "waiting",
    ]
    assert sankey["links"] == [
        {"source": "received", "target": "interviewing", "value": 1},
        {"source": "received", "target": "waiting", "value": 1},
        {"source": "interviewing", "target": "waiting", "value": 1},
    ]

    pie = _payload(page, "pie-data")
    assert pie == {
        "total": 2,
        "slices": [
            {"status": "received", "count": 1, "percent": 50.0},
            {"status": "interviewing", "count": 1, "percent": 50.0},
        ],
    }


def test_empty_slice_yields_empty_payloads(client):
    _seed_charts(client)
    page = client.get("/?company=Hooli&status=received").text  # E is accepted

    sankey = _payload(page, "sankey-data")
    pie = _payload(page, "pie-data")
    assert sankey == {"nodes": [], "links": []}
    assert pie == {"total": 0, "slices": []}


def test_single_open_application_flows_into_waiting(client):
    _seed_charts(client)
    page = client.get("/?status=received").text  # C only — never moved

    sankey = _payload(page, "sankey-data")
    _check_sankey(sankey)
    # No real transitions yet — but C is still open at received, so it shows
    # up on the output side via the waiting node instead of disappearing.
    assert [n["name"] for n in sankey["nodes"]] == ["received", "waiting"]
    assert sankey["links"] == [
        {"source": "received", "target": "waiting", "value": 1},
    ]

    pie = _payload(page, "pie-data")
    assert pie == {
        "total": 1,
        "slices": [{"status": "received", "count": 1, "percent": 100.0}],
    }


# ---------------------------------------------------------------------------
# pure-function edges: dedupe semantics and degenerate inputs (no HTTP needed)
# ---------------------------------------------------------------------------

def test_sankey_counts_each_application_once_per_transition(client):
    _seed_charts(client)
    # F flaps received ↔ interviewing twice: two events each way, but the Sankey
    # must still count F once per direction ("how many applications went that way").
    with open_session() as session:
        f = repo.create_application(
            session,
            company="Vandelay",
            job_title="QA Engineer",
            reference_number="REF-F",
            applied_on=date(2026, 1, 1),
        )
        for status in ("interviewing", "received", "interviewing"):
            repo.update_application(session, f.id, status=status)

    page = client.get("/").text
    sankey = _payload(page, "sankey-data")
    values = {(l["source"], l["target"]): l["value"] for l in sankey["links"]}
    assert values[("received", "interviewing")] == 3  # A, D and F — not 4
    assert values[("interviewing", "received")] == 1  # only F's edit back
    # Waiting sink: C is open at received; D and F are both open at interviewing.
    assert values[("received", "waiting")] == 1
    assert values[("interviewing", "waiting")] == 2


def test_pure_payloads_on_empty_inputs():
    assert analytics.sankey_payload([], []) == {"nodes": [], "links": []}
    assert analytics.pie_payload([]) == {"total": 0, "slices": []}


def test_pure_initial_event_contributes_node_only():
    event = StatusEvent(
        application_id=1,
        from_status=None,
        to_status="received",
        changed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    # With no applications passed there is nothing open, so the initial event
    # yields a node but no links — its waiting flow comes from the application's
    # current status when that list is provided (next test).
    assert analytics.sankey_payload([], [event]) == {
        "nodes": [{"name": "received"}],
        "links": [],
    }


def _pure_application(status: str) -> Application:
    return Application(
        company="Acme", job_title="Eng", applied_on=date(2026, 7, 1), status=status
    )


def test_pure_waiting_sink_counts_open_applications_once_each():
    """Every open application contributes exactly one link from its current
    status into the waiting node; terminal applications contribute none."""
    def event(event_id: int, app_id: int, frm: str | None, to: str) -> StatusEvent:
        return StatusEvent(
            id=event_id,
            application_id=app_id,
            from_status=frm,
            to_status=to,
            changed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    applications = [
        _pure_application("received"),     # never moved
        _pure_application("interviewing"),  # open at interviewing
        _pure_application("offer"),         # open at offer
        _pure_application("accepted"),      # terminal: no waiting link
    ]
    events = [
        event(1, 1, None, "received"),
        event(2, 2, None, "received"),
        event(3, 2, "received", "interviewing"),
        event(4, 3, None, "received"),
        event(5, 3, "received", "offer"),
        event(6, 4, None, "received"),
        event(7, 4, "received", "accepted"),
    ]

    payload = analytics.sankey_payload(applications, events)
    assert [n["name"] for n in payload["nodes"]] == [
        "received", "interviewing", "offer", "accepted", "waiting",
    ]
    values = {(l["source"], l["target"]): l["value"] for l in payload["links"]}
    assert values[("received", "interviewing")] == 1
    assert values[("received", "offer")] == 1
    assert values[("received", "accepted")] == 1
    # One waiting link per open application, none from the terminal one.
    assert values[("received", "waiting")] == 1
    assert values[("interviewing", "waiting")] == 1
    assert values[("offer", "waiting")] == 1
    assert ("accepted", "waiting") not in values


def test_pure_no_open_applications_means_no_waiting_node():
    """When every application is terminal, the waiting node never appears."""
    def event(event_id: int, app_id: int, frm: str | None, to: str) -> StatusEvent:
        return StatusEvent(
            id=event_id,
            application_id=app_id,
            from_status=frm,
            to_status=to,
            changed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    applications = [
        _pure_application("accepted"),
        Application(company="B", job_title="PM", applied_on=date(2026, 7, 1), status="rejected"),
    ]
    events = [
        event(1, 1, None, "received"),
        event(2, 1, "received", "accepted"),
        event(3, 2, None, "received"),
        event(4, 2, "received", "rejected"),
    ]

    payload = analytics.sankey_payload(applications, events)
    names = [n["name"] for n in payload["nodes"]]
    assert "waiting" not in names
    values = {(l["source"], l["target"]): l["value"] for l in payload["links"]}
    assert values == {("received", "accepted"): 1, ("received", "rejected"): 1}


def test_pure_sankey_dedupes_within_one_application():
    def event(app_id: int, frm: str | None, to: str) -> StatusEvent:
        return StatusEvent(
            application_id=app_id, from_status=frm, to_status=to,
            changed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    events = [
        event(1, None, "received"),
        event(1, "received", "interviewing"),
        event(1, "interviewing", "received"),
        event(1, "received", "interviewing"),  # repeat — still one count for app 1
        event(2, None, "received"),
        event(2, "received", "interviewing"),
    ]
    # No applications are passed, so there is no waiting node either.
    payload = analytics.sankey_payload([], events)
    names = [l["source"] for l in payload["links"]] + [l["target"] for l in payload["links"]]
    assert "waiting" not in names
    values = {(l["source"], l["target"]): l["value"] for l in payload["links"]}
    assert values == {("received", "interviewing"): 2, ("interviewing", "received"): 1}
