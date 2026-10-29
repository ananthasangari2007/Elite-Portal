"""Pytest configuration and safety guards.

The suite creates and drops tables, so it must never touch a real database. The
database URL is forced to a throwaway SQLite file *before* ``config`` is imported
(``config.py`` calls ``load_dotenv()``, which must not win over this value).
"""
import os
import tempfile
from pathlib import Path

_TEST_DB_PATH = Path(tempfile.gettempdir()) / "elite_portal_pytest.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"
os.environ["APP_ENV"] = "development"
os.environ.pop("FLASK_ENV", None)
os.environ["SECRET_KEY"] = "pytest-secret-key"
os.environ["RATELIMIT_ENABLED"] = "false"
os.environ.pop("ROSTER_APPS_SCRIPT_URL", None)
os.environ["UPLOAD_FOLDER"] = str(Path(tempfile.gettempdir()) / "elite_portal_pytest_uploads")
for _key in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "MAIL_SERVER"):
    os.environ[_key] = ""

import pytest  # noqa: E402


def pytest_configure(config):
    from config import Config

    if not Config.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        raise RuntimeError("Refusing to run tests against a non-SQLite database.")


@pytest.fixture()
def fresh_db():
    """Empty schema for each test."""
    from app.database import db, remove_session

    assert db.engine.dialect.name == "sqlite"
    remove_session()
    db.drop_all()
    db.create_all()
    yield db
    remove_session()


@pytest.fixture()
def app(fresh_db):
    from app.fastapi.app import create_app

    return create_app()


@pytest.fixture()
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
