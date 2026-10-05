"""PDF upload validation and on-disk storage (PLAN.md §7).

An application can carry two PDFs — ``resume`` and ``application``. Both are:

* validated by extension (``.pdf``) **and** magic bytes (``%PDF`` prefix),
* capped at ``config.MAX_UPLOAD_MB`` megabytes, checked before anything is
  written to disk (§7),
* stored under ``<DATA_DIR>/uploads/<application_id>/<kind>.pdf`` — stable
  paths so re-uploads can simply replace the file in place.

Original file names never touch this module: the repository layer keeps them
in ``applications.resume_file_name`` / ``applications.application_file_name``
so downloads can use friendly names while storage stays predictable (§7).
This module owns every filesystem write for PDFs; ``app/repo.py`` deliberately
does not touch disk (§4/§7 split).

The data directory is read from ``config.DATA_DIR`` at call time (not import
time) so tests can point the whole app at a temp dir.
"""

import shutil
from pathlib import Path

from app import config


class UploadError(ValueError):
    """A rejected upload; its message is safe to show in the form."""


#: The two PDF slots an application can carry, and their DB column prefixes.
KINDS = ("resume", "application")

PDF_MAGIC_BYTES = b"%PDF"


def max_upload_bytes() -> int:
    """The current per-file size cap from config, in bytes (§7)."""
    return config.MAX_UPLOAD_MB * 1024 * 1024


def validate_pdf(filename: str, content: bytes) -> None:
    """Raise :class:`UploadError` unless *content* is an acceptable PDF.

    Checks, in order: ``.pdf`` extension, size cap (before any disk write),
    and the ``%PDF`` magic-byte prefix (§7).
    """
    if not filename.lower().endswith(".pdf"):
        raise UploadError(f"{filename} must be a PDF file (.pdf extension).")
    if len(content) > max_upload_bytes():
        limit_mb = config.MAX_UPLOAD_MB
        raise UploadError(
            f"{filename} is larger than the {limit_mb} MB upload limit."
        )
    if not content.startswith(PDF_MAGIC_BYTES):
        raise UploadError(f"{filename} does not look like a valid PDF file.")


def upload_directory(application_id: int, data_dir: str | Path | None = None) -> Path:
    """The per-application directory holding its stored PDFs."""
    base = Path(data_dir) if data_dir is not None else Path(config.DATA_DIR)
    return base / "uploads" / str(application_id)


def stored_path(
    kind: str, application_id: int, data_dir: str | Path | None = None
) -> Path:
    """The stable on-disk path for one (application, kind) PDF."""
    if kind not in KINDS:
        raise ValueError(f"unknown upload kind {kind!r}; expected one of {KINDS}")
    return upload_directory(application_id, data_dir) / f"{kind}.pdf"


def store_upload(
    *,
    kind: str,
    filename: str,
    content: bytes,
    application_id: int,
    data_dir: str | Path | None = None,
) -> str:
    """Validate *content* and write it to the stable storage path.

    Re-uploading for the same (application, kind) **replaces** the previous
    file on disk (§7). Returns the DATA_DIR-relative path that gets stored in
    the database (``uploads/<id>/<kind>.pdf``).
    """
    # Extension + magic bytes + size cap — always before any disk write.
    validate_pdf(filename, content)
    path = stored_path(kind, application_id, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)  # replacement semantics: old file goes first
    path.write_bytes(content)
    return f"uploads/{application_id}/{kind}.pdf"


def delete_application_files(application_id: int, data_dir: str | Path | None = None) -> None:
    """Remove both stored PDFs and their directory (no-op if already gone)."""
    shutil.rmtree(upload_directory(application_id, data_dir), ignore_errors=True)
