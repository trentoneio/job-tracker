"""FastAPI application factory for the job tracker."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routes.applications import router as applications_router


def create_app() -> FastAPI:
    """Build and return the configured app.

    Startup work runs in the lifespan below; static assets (vendored HTMX,
    S3) are mounted at /static at the bottom of this function.
    """

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Ensure the SQLite database (and its data directory) exists before
        # serving any request (§7); idempotent across restarts.
        init_db()
        yield

    app = FastAPI(title="Job Application Tracker", lifespan=lifespan)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "job-tracker"}

    # Dashboard assets, served from disk — no CDN or runtime internet
    # dependency (§3 LAN-only hosting).
    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.include_router(applications_router)

    return app


# Module-level instance so `uvicorn app.main:app` works out of the box.
app = create_app()
