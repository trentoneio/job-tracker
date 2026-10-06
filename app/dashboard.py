"""Server-side computations for the dashboard widgets.

Pure functions over repository results — no database access in this module, so
the same code renders the live dashboard and can be tested against fixture
data. "Today" is always passed in by the caller (as a UTC date), never read
here, which keeps these functions deterministic in tests.
"""

from statistics import median
from typing import Iterable, Optional

from app.config import STATUSES, WAITING_STATUSES
from app.models import Application, StatusEvent

# Terminal = every status in the vocabulary that is not "waiting"
# (accepted / rejected / ghosted). Derived from config so adding a status later
# only requires deciding which side of the line it falls on.
TERMINAL_STATUSES = tuple(status for status in STATUSES if status not in WAITING_STATUSES)


def days_elapsed(application: Application, today) -> int:
    """Whole days between ``application.applied_on`` and *today*."""
    return (today - application.applied_on).days


def waiting_queue(applications: Iterable[Application], today) -> list[Application]:
    """Applications in a waiting status, most-elapsed first.

    Ties break by id so the order is deterministic across renders.
    """
    rows = [app for app in applications if app.status in WAITING_STATUSES]
    return sorted(rows, key=lambda app: (-days_elapsed(app, today), app.id))


def first_response_events(events) -> dict[int, StatusEvent]:
    """First non-initial status event per application (its "first response").

    *events* must arrive ordered within each application by ``(changed_at, id)``
    — exactly what ``repo.get_status_events_for_filter`` guarantees. The initial
    creation events have ``from_status NULL``.
    """
    first: dict[int, StatusEvent] = {}
    for event in events:
        if event.from_status is None:
            continue  # initial event — not a response
        first.setdefault(event.application_id, event)
    return first


def median_days_to_first_response(
    applications: Iterable[Application], events
) -> Optional[float]:
    """Median days from ``applied_on`` to the first non-initial status event.

    Applications that have received no reply yet (still at their initial
    event) are excluded; returns None when nothing in the set has been
    responded to, which renders as "—" on the dashboard.
    """
    by_id = {app.id: app for app in applications}
    values = [
        (event.changed_at.date() - by_id[app_id].applied_on).days
        for app_id, event in first_response_events(events).items()
        if app_id in by_id
    ]
    if not values:
        return None
    return median(values)


def closed_rate(total: int, closed: int) -> Optional[float]:
    """Percent of the filtered set that reached a terminal status.

    Returns None when *total* is 0 (renders as "—").
    """
    if total == 0:
        return None
    return 100.0 * closed / total


def format_percent(value: Optional[float]) -> str:
    """Whole-percent display string, e.g. ``"40%"``; ``"—"`` when unknown."""
    if value is None:
        return "—"
    return f"{round(value)}%"


def format_days(value: Optional[float]) -> str:
    """Day count for display: integral values render without a decimal
    (``"12"``, not ``"12.0"``); halves keep one digit (``"7.5"``); None → ``"—"``."""
    if value is None:
        return "—"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"
