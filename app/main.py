"""FastAPI application factory for the job tracker."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import init_db
from app.routes.applications import router as applications_router
from app.routes.exports import router as exports_router


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
    app.include_router(exports_router)

    # Friendly HTML 404 page for unknown application/file ids and routes
    # (S5 polish); any other status code keeps the default JSON shape.
    templates = Jinja2Templates(
        directory=str(Path(__file__).resolve().parent / "templates")
    )

    @app.exception_handler(HTTPException)
    def http_exception(request: Request, exc: HTTPException):
        if exc.status_code != 404:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return templates.TemplateResponse(
            request,
            "error.html",
            {"status_code": exc.status_code, "detail": exc.detail or "The page you requested does not exist."},
            status_code=404,
        )

    # Unknown GET routes (typed URLs) also get the friendly HTML 404; this
    # catch-all is registered last so every real route and mount wins first.
    @app.get("/{path:path}")
    def unknown_route() -> None:
        raise HTTPException(status_code=404, detail="The page you requested does not exist.")

    return app


# Module-level instance so `uvicorn app.main:app` works out of the box.
app = create_app()
