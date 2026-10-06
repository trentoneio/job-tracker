"""Server-side payload builders for the dashboard charts.

Pure functions over repository results — no database access in this module, so
the same code renders the live dashboard and can be tested against fixture
data. The Sankey builder takes one filter slice's applications (their current
statuses) plus their full event histories; the pie builder takes just the
applications. Inputs are exactly what ``repo.list_applications`` /
``repo.get_status_events_for_filter`` return for the active slice (events
ordered per application by ``(changed_at, id)``, which is all these functions
rely on).

Each payload is ready to feed ECharts client-side: the Sankey builder returns
``{"nodes": [{"name"}...], "links": [{"source", "target", "value"}...]}`` and
the pie builder returns ``{"total": N, "slices": [{"status", "count",
"percent"}...]}``.
"""

from typing import Iterable

from app.config import STATUSES, WAITING_STATUSES
from app.models import Application, StatusEvent


def _ordered_statuses(statuses: set[str]) -> list[str]:
    """Status names in the canonical vocabulary order.

    The database CHECK constraint means every row already uses a known status;
    unknown names (should this ever change) sort alphabetically after them so
    output stays deterministic either way.
    """
    return [s for s in STATUSES if s in statuses] + sorted(statuses - set(STATUSES))


#: The synthetic output-side node that still-open applications flow into. It is
#: not a real status — only ``config.WAITING_STATUSES`` feed it, and it never
#: has outflow of its own.
WAITING_NODE = "waiting"


def sankey_payload(
    applications: Iterable[Application], events: Iterable[StatusEvent]
) -> dict[str, list]:
    """ECharts-ready Sankey payload of status flow within a filtered slice.

    ``applications`` and ``events`` are one filter slice's rows — the current
    statuses plus their full event histories. Nodes are every status appearing
    in the slice, plus a synthetic ``waiting`` node whenever some applications
    have not reached a terminal status yet: each application still sitting at
    an open status (``received`` / ``interviewing`` / ``offer``) contributes
    one link from that status into ``waiting``, so every application shows up
    on the diagram's output side — either in its final state or waiting.

    Links are the consecutive transitions each application took — its ordered
    events, read as ``from_status → to_status`` pairs; an application counts
    once per distinct transition even if a later edit repeats it, so a link
    value is always "how many applications went that way", never a raw event
    count. The first event of each application has ``from_status = None`` and
    contributes a node but no edge. Terminal statuses have no outflow by
    construction, which keeps the right edge readable: where each cohort ended
    up, or is still waiting.

    Node order follows the status vocabulary with ``waiting`` last; links are
    sorted by their source then target node position, keeping renders deterministic.
    """
    transitions: dict[int, set[tuple[str | None, str]]] = {}
    statuses: set[str] = set()
    for event in events:  # input is ordered within each application
        pair = (event.from_status, event.to_status)
        transitions.setdefault(event.application_id, set()).add(pair)
        if event.from_status is not None:
            statuses.add(event.from_status)
        statuses.add(event.to_status)

    waiting_by_source: dict[str, int] = {}
    for application in applications:
        if application.status in WAITING_STATUSES:
            waiting_by_source[application.status] = (
                waiting_by_source.get(application.status, 0) + 1
            )
    statuses.update(waiting_by_source)
    if waiting_by_source:
        statuses.add(WAITING_NODE)

    edge_counts: dict[tuple[str, str], int] = {}
    for pairs in transitions.values():  # one count per application per pair
        for source, target in pairs:
            if source is not None:
                edge_counts[(source, target)] = edge_counts.get((source, target), 0) + 1

    for source, count in waiting_by_source.items():
        key = (source, WAITING_NODE)
        edge_counts[key] = edge_counts.get(key, 0) + count

    order = _ordered_statuses(statuses)
    position = {name: i for i, name in enumerate(order)}
    links = [
        {"source": source, "target": target, "value": value}
        for (source, target), value in sorted(
            edge_counts.items(), key=lambda item: (position[item[0][0]], position[item[0][1]])
        )
    ]
    return {
        "nodes": [{"name": name} for name in order],
        "links": links,
    }


def pie_payload(applications: Iterable[Application]) -> dict[str, object]:
    """ECharts-ready pie payload of the current-status distribution.

    Each application counts once at its *current* status — the mirrored column
    that always equals the latest event per the repo layer's rules. Slices are
    ordered by the status vocabulary and carry a whole-slice percentage rounded
    to one decimal; ``total`` is zero (and ``slices`` empty) when the filter
    matches nothing.
    """
    counts: dict[str, int] = {}
    for application in applications:
        counts[application.status] = counts.get(application.status, 0) + 1

    total = len(applications)
    slices: list[dict[str, object]] = []
    if total:
        for status in _ordered_statuses(set(counts)):
            count = counts[status]
            slices.append(
                {"status": status, "count": count, "percent": round(100.0 * count / total, 1)}
            )
    return {"total": total, "slices": slices}
