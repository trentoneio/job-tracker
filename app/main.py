"""FastAPI application factory for the job tracker."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Build and return the configured app.

    Single place to hook in startup work: a lifespan context manager (DB init,
    S1) goes on the ``FastAPI(...)`` call below, and static-file mounting
    (dashboard assets, S3) goes at the bottom of this function.
    """
    # S1: app = FastAPI(title=..., lifespan=lifespan) once DB init exists.
    app = FastAPI(title="Job Application Tracker")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "job-tracker"}

    # S3: app.mount("/static", StaticFiles(directory=...), name="static").

    return app


# Module-level instance so `uvicorn app.main:app` works out of the box.
app = create_app()
