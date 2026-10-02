"""Smoke test for the /healthz probe (target of the compose healthcheck)."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_returns_ok():
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "job-tracker"
