"""Server-rendered application routes (PLAN.md §5, S2 scope).

Create / detail / inline edit+status change / delete, plus multipart PDF
uploads. Forms post to real endpoints and redirect after success (§5);
validation problems re-render the same form with inline messages — there is
no JSON API in this layer. New applications always start at ``received``;
the create form has no status field (§4).

The templates are deliberately minimal placeholders — S3 rebuilds them as
the real dashboard layout (§6), including where the CSV/JSON export links
will live in the header.

Layering follows §4: request handlers only call repo functions through
``open_session()``; PDF filesystem work goes to ``app/uploads.py``.
"""

from datetime import date
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import config, repo, uploads
from app.db import open_session

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)
router = APIRouter()


def _clean(value: str | None) -> str | None:
    """Trim whitespace; empty strings become None (optional fields)."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def _parse_applied_on(raw: str, errors: dict[str, str]) -> date | None:
    """Parse a required YYYY-MM-DD field into ``errors`` on failure."""
    text = raw.strip()
    if not text:
        errors["applied_on"] = "Applied date is required."
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        errors["applied_on"] = f"{text} is not a valid date (expected YYYY-MM-DD)."
        return None


async def _collect_file_parts(
    resume_pdf: UploadFile | None, application_pdf: UploadFile | None
) -> tuple[dict[str, tuple[str, bytes]], dict[str, str]]:
    """Read and validate the optional PDF parts before anything is written.

    Returns ``(files, errors)`` where *files* maps kind → (original name,
    bytes) for accepted parts and *errors* maps form field names to messages.
    A part that was not chosen contributes nothing.
    """
    fields = {"resume": "resume_pdf", "application": "application_pdf"}
    files: dict[str, tuple[str, bytes]] = {}
    errors: dict[str, str] = {}
    for upload, kind in ((resume_pdf, "resume"), (application_pdf, "application")):
        if upload is None or not (upload.filename or "").strip():
            continue  # no file chosen for this slot
        content = await upload.read()
        try:
            uploads.validate_pdf(upload.filename, content)
        except uploads.UploadError as exc:
            errors[fields[kind]] = str(exc)
        else:
            files[kind] = (upload.filename, content)
    return files, errors


def _new_context(values: dict[str, object], errors: dict[str, str]) -> dict[str, object]:
    return {
        "values": values,
        "errors": errors,
        "max_upload_mb": config.MAX_UPLOAD_MB,
    }


def _detail_context(
    application,
    events,
    values: dict[str, object],
    errors: dict[str, str],
) -> dict[str, object]:
    return {
        "application": application,
        "events": events,
        "values": values,
        "errors": errors,
        "status_options": list(config.STATUSES),
        "badge_color": config.STATUS_COLORS.get(application.status, "#6b7280"),
        "max_upload_mb": config.MAX_UPLOAD_MB,
    }


@router.get("/")
def index(request: Request):
    """Placeholder home page until S3 builds the dashboard (§5/§6)."""
    with open_session() as session:
        applications = repo.list_applications(session)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "applications": applications,
            "status_colors": config.STATUS_COLORS,
        },
    )


@router.get("/applications/new")
def new_application_form(request: Request):
    return templates.TemplateResponse(request, "new.html", _new_context({}, {}))


@router.post("/applications/new")
async def create_application(
    request: Request,
    company: str = Form(""),
    job_title: str = Form(""),
    reference_number: str = Form(""),
    applied_on: str = Form(""),
    job_posting_url: str = Form(""),
    notes: str = Form(""),
    resume_pdf: UploadFile | None = File(None),
    application_pdf: UploadFile | None = File(None),
):
    """Create an application (always starting at ``received``) and store any
    uploaded PDFs. Redirects to the new detail page (§5)."""
    errors: dict[str, str] = {}
    company_value = _clean(company)
    job_title_value = _clean(job_title)
    if not company_value:
        errors["company"] = "Company is required."
    if not job_title_value:
        errors["job_title"] = "Job title is required."
    applied_date = _parse_applied_on(applied_on, errors)

    values = {  # echoed back so a failed submission keeps the user's input
        "company": company_value or "",
        "job_title": job_title_value or "",
        "reference_number": _clean(reference_number) or "",
        "applied_on": applied_on.strip(),
        "job_posting_url": _clean(job_posting_url) or "",
        "notes": (notes or "").strip(),
    }

    if errors:  # don't even read the file parts when the form is invalid
        return templates.TemplateResponse(request, "new.html", _new_context(values, errors))

    files, file_errors = await _collect_file_parts(resume_pdf, application_pdf)
    if file_errors:
        errors.update(file_errors)
        return templates.TemplateResponse(request, "new.html", _new_context(values, errors))

    with open_session() as session:
        # The row goes in first so uploads have a stable <id> directory.
        application = repo.create_application(
            session,
            company=company_value,
            job_title=job_title_value,
            applied_on=applied_date,
            reference_number=_clean(reference_number),
            job_posting_url=_clean(job_posting_url),
            notes=_clean(notes),
        )
        metadata: dict[str, str] = {}
        failed_field = None
        for kind in files:  # only the kinds that were actually uploaded
            try:
                relative_path = uploads.store_upload(
                    kind=kind,
                    filename=files[kind][0],
                    content=files[kind][1],
                    application_id=application.id,
                )
            except OSError as exc:
                failed_field = "resume_pdf" if kind == "resume" else "application_pdf"
                errors[failed_field] = f"Could not save the uploaded file ({exc})."
                break
            metadata[f"{kind}_pdf"] = relative_path
            metadata[f"{kind}_file_name"] = files[kind][0]

        if failed_field is not None:
            # Don't leave a half-created application behind.
            uploads.delete_application_files(application.id)
            repo.delete_application(session, application.id)
            return templates.TemplateResponse(
                request, "new.html", _new_context(values, errors)
            )

        if metadata:
            repo.update_application(session, application.id, **metadata)

    return RedirectResponse(f"/applications/{application.id}", status_code=303)


@router.get("/applications/{application_id}")
def application_detail(request: Request, application_id: int):
    """All fields, the inline edit form, the stored-PDF links and the full
    status timeline from ``status_events`` (§5)."""
    with open_session() as session:
        application = repo.get_application(session, application_id)
        if application is None:
            raise HTTPException(status_code=404, detail="Application not found")
        events = repo.get_status_events(session, application.id)

    return templates.TemplateResponse(
        request, "detail.html", _detail_context(application, events, {}, {})
    )


@router.post("/applications/{application_id}/update")
async def update_application(
    request: Request,
    application_id: int,
    company: str = Form(""),
    job_title: str = Form(""),
    reference_number: str = Form(""),
    applied_on: str = Form(""),
    status: str = Form(""),
    job_posting_url: str = Form(""),
    notes: str = Form(""),
    resume_pdf: UploadFile | None = File(None),
    application_pdf: UploadFile | None = File(None),
):
    """Save field edits and/or new PDFs for one application. A status change
    (and only a real change) appends exactly one ``status_events`` row (§4)."""
    with open_session() as session:
        application = repo.get_application(session, application_id)
        if application is None:
            raise HTTPException(status_code=404, detail="Application not found")

        errors: dict[str, str] = {}
        company_value = _clean(company)
        job_title_value = _clean(job_title)
        if not company_value:
            errors["company"] = "Company is required."
        if not job_title_value:
            errors["job_title"] = "Job title is required."
        applied_date = _parse_applied_on(applied_on, errors)
        status_value = _clean(status) or ""
        if status_value not in config.STATUSES:
            errors["status"] = f"Status must be one of {', '.join(config.STATUSES)}."

        values = {
            "company": company_value or "",
            "job_title": job_title_value or "",
            "reference_number": _clean(reference_number) or "",
            "applied_on": applied_on.strip(),
            "status": status,
            "job_posting_url": _clean(job_posting_url) or "",
            "notes": (notes or "").strip(),
        }

        if errors:  # don't read file parts when the form is invalid
            return templates.TemplateResponse(
                request,
                "detail.html",
                _detail_context(application, repo.get_status_events(session, application.id), values, errors),
            )

        files, file_errors = await _collect_file_parts(resume_pdf, application_pdf)
        if file_errors:
            errors.update(file_errors)
            return templates.TemplateResponse(
                request,
                "detail.html",
                _detail_context(application, repo.get_status_events(session, application.id), values, errors),
            )

        # Field edits commit first; new PDFs then replace the stored files and
        # their metadata (§7). If a disk write fails, the previous file is
        # still intact on disk with its old metadata — no inconsistency.
        repo.update_application(
            session,
            application_id,
            company=company_value,
            job_title=job_title_value,
            reference_number=_clean(reference_number),
            applied_on=applied_date,
            status=status_value,
            job_posting_url=_clean(job_posting_url),
            notes=_clean(notes),
        )

        for kind in files:
            try:
                relative_path = uploads.store_upload(
                    kind=kind,
                    filename=files[kind][0],
                    content=files[kind][1],
                    application_id=application.id,
                )
            except OSError as exc:
                field = "resume_pdf" if kind == "resume" else "application_pdf"
                errors[field] = f"Could not save the uploaded file ({exc})."
                break
            repo.update_application(
                session, application_id, **{f"{kind}_pdf": relative_path, f"{kind}_file_name": files[kind][0]}
            )

    if errors:
        with open_session() as session:
            application = repo.get_application(session, application_id)
            events = repo.get_status_events(session, application.id)
        return templates.TemplateResponse(
            request, "detail.html", _detail_context(application, events, values, errors)
        )

    return RedirectResponse(f"/applications/{application_id}", status_code=303)


@router.post("/applications/{application_id}/delete")
def delete_application_route(application_id: int):
    """Delete the row (and its history rows via repo) and both stored PDFs."""
    with open_session() as session:
        deleted = repo.delete_application(session, application_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Application not found")
    uploads.delete_application_files(application_id)
    return RedirectResponse("/", status_code=303)
