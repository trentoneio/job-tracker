"""Theme system tests: structural checks on the rendered HTML, not pixels.

The theme is applied via a ``data-theme`` attribute on ``<html>`` that an inline
bootstrap script in the head sets from localStorage before first paint; every
color rule references CSS custom properties defined per theme. The picker is a
plain <select> re-wired by document-level listeners after each HTMX body swap,
so these tests assert the server-rendered scaffolding those scripts rely on:
the bootstrap script, all five palette definitions, and the picker with its
five options present on every page (dashboard, new application, detail)."""

import re
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, db, repo
from app.db import open_session
from app.main import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """An app wired to a fresh temp DATA_DIR (same pattern as test_charts.py)."""
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


def _application_id(client) -> int:
    """Create one application through the repo layer and return its id."""
    with open_session() as session:
        application = repo.create_application(
            session, company="Acme", job_title="Engineer", applied_on=date(2026, 1, 5)
        )
        return application.id


def _assert_theme_scaffolding(page: str) -> None:
    """Every page must ship the full theme scaffolding."""
    # <html> starts as light; the head bootstrap script may upgrade it from
    # localStorage before first paint.
    assert '<html lang="en" data-theme="light">' in page
    # Pre-paint bootstrap reading localStorage (no flash of unthemed CSS).
    assert 'localStorage.getItem("jt-theme")' in page
    # The picker, with the five themes in stable order and human labels.
    start = page.index('id="theme-select"')
    select = page[start : page.index("</select>", start)]
    pairs = re.findall(r'<option value="([a-z]+)">([^<]+)</option>', select)
    assert [value for value, _ in pairs] == ["light", "dark", "dracula", "nord", "gruvbox"]
    assert [label for _, label in pairs] == ["Light", "Dark", "Dracula", "Nord", "Gruvbox"]


def _assert_palettes(page: str) -> None:
    """All five palettes must be defined and each must define the core vars."""
    for theme in ("light", "dark", "dracula", "nord", "gruvbox"):
        block = page.split(f'[data-theme="{theme}"]')[1].split("}")[0]
        assert "--bg" in block, f"{theme} palette missing --bg"


def test_dashboard_page_has_theme_scaffolding(client):
    _assert_theme_scaffolding(client.get("/").text)


def test_new_application_page_has_theme_scaffolding(client):
    _assert_theme_scaffolding(client.get("/applications/new").text)


def test_detail_page_has_theme_scaffolding(client):
    application_id = _application_id(client)
    page = client.get(f"/applications/{application_id}").text
    _assert_theme_scaffolding(page)


def test_all_five_palettes_are_defined(client):
    _assert_palettes(client.get("/").text)


def _base_html_source() -> str:
    """The raw template behind every page - the chart controller lives here."""
    root = Path(__file__).resolve().parent.parent
    return (root / "app" / "templates" / "base.html").read_text(encoding="utf-8")


def test_sankey_series_sets_explicit_theme_label_color():
    """ECharts 6 paints labels left at their default color with a baked-in white
    halo (stroke + paint order). That wrecks readability on the dark themes, so
    the Sankey series must carry an explicit label color fed by the active
    theme's --chart-text variable."""
    source = _base_html_source()
    sankey_body = source[source.index("function renderSankey") : source.index("function renderPie")]
    assert 'label: { color: cssVar("--chart-text")' in sankey_body, (
        "sankey series has no explicit label color - ECharts 6 will paint its "
        "default white text halo on dark themes"
    )


def test_pie_series_sets_explicit_theme_label_color():
    """Same guard for the current-status pie: an explicit --chart-text-driven
    label color (with its formatter intact), not ECharts' default."""
    source = _base_html_source()
    pie_body = source[source.index("function renderPie") : source.index("function renderCharts")]
    assert 'color: cssVar("--chart-text")' in pie_body and "formatter" in pie_body, (
        "pie label lost its explicit theme color or formatter"
    )
