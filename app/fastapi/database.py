"""FastAPI database bindings (re-exports the framework-independent layer)."""
from __future__ import annotations

from app.database import db, engine, remove_session, request_scope, session as db_session  # noqa: F401
import app.models  # noqa: F401  (register every mapped class)


def get_db():
    """FastAPI dependency yielding the request-scoped session.

    The request middleware owns the session lifecycle (rollback + remove at the end
    of every request), so this only hands out the session.
    """
    yield db.session
