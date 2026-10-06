"""Database engine, session factory and initialization.

All runtime state lives in a single SQLite file under DATA_DIR — ``data/app.db``
for local dev runs, ``/app/data/app.db`` inside the container. Every new
connection gets:

* ``journal_mode=WAL`` — writes survive crashes and readers don't block writers;
* ``busy_timeout=5000`` — short-lived reader/writer overlap waits instead of erroring;
* ``foreign_keys=ON`` — SQLite ignores FK constraints by default, so this is what
  actually makes the ``ON DELETE CASCADE`` on ``status_events.application_id`` fire.

The engine for the app's own DATA_DIR is created lazily: merely importing this
module has no disk side effects. Tests instead call :func:`create_db_engine`
with a temp directory, so pytest never touches the live database.
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import DATA_DIR

_DB_FILENAME = "app.db"
_BUSY_TIMEOUT_MS = 5000


def db_file(data_dir: str | Path | None = None) -> Path:
    """Path of the SQLite file for *data_dir* (defaults to config.DATA_DIR)."""
    directory = Path(data_dir) if data_dir is not None else Path(DATA_DIR)
    return directory / _DB_FILENAME


def create_db_engine(data_dir: str | Path | None = None) -> Engine:
    """Create an engine for the SQLite file in *data_dir* and configure pragmas.

    Defaults to ``config.DATA_DIR``; creates the directory if it is missing.
    The app uses this once at startup (via :func:`get_db_engine`), tests use it
    per-test with a temp directory.
    """
    directory = db_file(data_dir).parent
    directory.mkdir(parents=True, exist_ok=True)
    # Forward-slash paths keep the SQLAlchemy URL unambiguous on Windows too.
    engine = create_engine(f"sqlite:///{db_file(data_dir).as_posix()}")

    @event.listens_for(engine, "connect")
    def _configure_sqlite_connection(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS};")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Session factory bound to *engine*.

    ``expire_on_commit=False`` means objects returned by repository functions
    stay fully readable after the transaction commits (and even after the
    session closes), which keeps the calling layers simple.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)


_default_engine: Optional[Engine] = None
_default_factory: Optional[sessionmaker[Session]] = None


def get_db_engine() -> Engine:
    """The single app-wide engine for the configured DATA_DIR (created lazily)."""
    global _default_engine, _default_factory
    if _default_engine is None:
        _default_engine = create_db_engine()
        _default_factory = make_session_factory(_default_engine)
    return _default_engine


def get_session_factory() -> sessionmaker[Session]:
    """The single app-wide session factory (created together with the engine)."""
    get_db_engine()  # ensures both globals are initialized
    assert _default_factory is not None
    return _default_factory


@contextmanager
def open_session() -> Iterator[Session]:
    """Open a session on the default engine.

    Repository functions commit their own work; this only owns connection
    lifetime for the request-handling and rendering layers.
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def init_db(engine: Engine | None = None) -> None:
    """Create all tables if they do not exist yet (idempotent).

    Called from the FastAPI lifespan at startup so the first request never has
    to race table creation. Pass a test engine to initialize an isolated DB.
    """
    from app import models  # noqa: F401 — registers mappers on Base.metadata

    target = engine if engine is not None else get_db_engine()
    models.Base.metadata.create_all(target)
