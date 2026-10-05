"""Server-side payload builders for the dashboard charts (PLAN.md §6 items 5–6).

Pure functions over repository results — no database access in this module, so
the same code renders the live dashboard and can be tested against fixture
data. Inputs are exactly what ``repo.get_status_events_for_filter`` /
``repo.list_applications`` return for the active filter slice (events ordered
per application by ``(changed_at, id)``, which is all these functions rely on).

Each payload is ready to feed ECharts client-side: the Sankey builder returns
``{"nodes": [{"name"}...], "links": [{"source", "target", "value"}...]}`` and
the pie builder returns ``{"total": N, "slices": [{"status", "count",
"percent"}...]}``.
"""

from typing import Iterable

from app.config import STATUSES
from app.models import StatusEvent, Application


def _ordered_statuses(statuses: set[str]) -> list[str]:
    """Status names in the canonical §4.1 vocabulary order.

    The database CHECK constraint means every row already uses a known status;
    unknown names (should this ever change) sort alphabetically after them so
    output stays deterministic either way.
    """
    return [s for s in STATUSES if s in statuses] + sorted(statuses - set(STATUSES))


def sankey_payload(events: Iterable[StatusEvent]) -> dict[str, list]:
    """ECharts-ready Sankey payload of status flow within a filtered slice (§6 item 5).

    Nodes are every status appearing in any event (``from_status`` or
    ``to_status``) of the slice's applications. Links are the consecutive
    transitions each application took — its ordered events, read as
    ``from_status → to_status`` pairs; an application counts once per distinct
    transition even if a later edit repeats it, so a link value is always
    "how many applications went that way", never a raw event count. The first
    event of each application has ``from_status = None`` (§4) and contributes
    a node but no edge. Terminal statuses have no outflow by construction
    (§4.1), so the diagram shows where each cohort ended up.

    Node order follows the §4.1 vocabulary; links are sorted by their source
    then target node position, keeping renders deterministic.
    """
    transitions: dict[int, set[tuple[str | None, str]]] = {}
    statuses: set[str] = set()
    for event in events:  # input is ordered within each application
        pair = (event.from_status, event.to_status)
        transitions.setdefault(event.application_id, set()).add(pair)
        if event.from_status is not None:
            statuses.add(event.from_status)
        statuses.add(event.to_status)

    edge_counts: dict[tuple[str, str], int] = {}
    for pairs in transitions.values():  # one count per application per pair
        for source, target in pairs:
            if source is not None:
                edge_counts[(source, target)] = edge_counts.get((source, target), 0) + 1

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
    """ECharts-ready pie payload of the current-status distribution (§6 item 6).

    Each application counts once at its *current* status — the mirrored column
    that always equals the latest event per §4. Slices are ordered by the §4.1
    vocabulary and carry a whole-slice percentage rounded to one decimal;
    ``total`` is zero (and ``slices`` empty) when the filter matches nothing.
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
