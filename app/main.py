"""FastAPI application factory for the job tracker."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db


def create_app() -> FastAPI:
    """Build and return the configured app.

    Startup work runs in the lifespan below; static-file mounting (dashboard
    assets, S3) goes at the bottom of this function.
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

    # S3: app.mount("/static", StaticFiles(directory=...), name="static").

    return app


# Module-level instance so `uvicorn app.main:app` works out of the box.
app = create_app()
