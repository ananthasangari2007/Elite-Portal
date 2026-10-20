"""Pytest configuration and safety guards.

IMPORTANT: The test suite calls ``db.drop_all()``. It must therefore never run
against a real database. These guards force every test run onto a throwaway
SQLite database, regardless of what ``.env`` (or the ambient environment) says.

The root cause of a past incident was that ``config.py`` calls ``load_dotenv()``
at import time, so a remote ``DATABASE_URL`` from ``.env`` could win over the
``os.environ.setdefault(...)`` used by older test modules. We now set the
variable with an unconditional assignment *before* ``config`` is imported.
"""
import os
import tempfile
from pathlib import Path

# ── Absolute isolation: override, never default, the database URL. ──────────
_TEST_DB_PATH = Path(tempfile.gettempdir()) / "elite_portal_pytest.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("SECRET_KEY", "pytest-secret-key")

import pytest  # noqa: E402


def pytest_configure(config):
    """Fail fast if the resolved database is not SQLite."""
    from config import Config

    uri = Config.SQLALCHEMY_DATABASE_URI
    if not uri.startswith("sqlite"):
        raise RuntimeError(
            "Refusing to run tests against a non-SQLite database "
            f"(resolved URI: {uri!r}). Tests call db.drop_all() and must never "
            "touch production or remote data."
        )


@pytest.fixture(autouse=True)
def _guard_isolated_database():
    """Second line of defence: assert the active engine is SQLite."""
    from app import db

    # Accessing the engine requires an app context; tests create one themselves,
    # so only assert when a context is already active.
    try:
        dialect = db.engine.dialect.name
    except RuntimeError:
        dialect = "sqlite"
    if dialect != "sqlite":
        raise RuntimeError(
            f"Tests attempted to use a non-SQLite database (dialect={dialect!r})."
        )
    yield
