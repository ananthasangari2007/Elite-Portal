"""
Elite Portal backend package.
Francis Xavier Engineering College | Elite Batch 2025-2029

The HTTP application is the FastAPI app in ``app.fastapi.app`` (ASGI entry: ``main:app``).
This module only exposes the shared database facade and the idempotent seed helpers
used by the CLI (``python -m app.cli``) and the test-suite.
"""
import os

from app.database import db  # noqa: F401  (re-exported: ``from app import db``)


def get_initial_admin_password():
    password = os.getenv("ADMIN_PASSWORD") or os.getenv("INITIAL_ADMIN_PASSWORD")
    if password:
        return password
    from config import is_production_environment

    if is_production_environment():
        raise RuntimeError("ADMIN_PASSWORD or INITIAL_ADMIN_PASSWORD must be set in production")
    return "Admin@1234"  # development-only default


class _ScriptContext:
    """Minimal stand-in for the old Flask app object used by maintenance scripts
    (``app = create_app(); with app.app_context(): ...``)."""

    def __init__(self):
        from config import Config

        self.config = {k: getattr(Config, k) for k in dir(Config) if k.isupper()}

    def app_context(self):
        from contextlib import contextmanager

        from app.database import remove_session

        @contextmanager
        def _ctx():
            try:
                yield self
            finally:
                remove_session()

        return _ctx()


def create_app(*_args, **_kwargs):
    """Compatibility shim for scripts; the web app is ``app.fastapi.app.create_app``."""
    return _ScriptContext()


def seed_domains():
    """Seed the four default domains (idempotent)."""
    from app.models import Domain

    defaults = [
        {
            "code": "DSA",
            "name": "Data Structures & Algorithms",
            "description": "Master core DSA concepts essential for all engineering disciplines.",
            "icon": "cpu",
            "color": "#4f46e5",
            "is_compulsory": True,
        },
        {
            "code": "FULLSTACK",
            "name": "Full Stack Development",
            "description": "Build end-to-end web applications with modern frameworks.",
            "icon": "layers",
            "color": "#0891b2",
            "is_compulsory": False,
        },
        {
            "code": "AIML",
            "name": "Artificial Intelligence & Machine Learning",
            "description": "Explore AI models, ML pipelines, and intelligent systems.",
            "icon": "brain",
            "color": "#7c3aed",
            "is_compulsory": False,
        },
        {
            "code": "EMBEDDED",
            "name": "Embedded Systems & IoT",
            "description": "Program microcontrollers and build connected IoT solutions.",
            "icon": "zap",
            "color": "#059669",
            "is_compulsory": False,
        },
    ]

    for d in defaults:
        if Domain.query.filter_by(code=d["code"]).first() is None:
            db.session.add(Domain(**d, is_active=True))
    db.session.commit()


def seed_admin_user():
    from app.models import User

    email = "admin@elite.edu"
    if User.query.filter_by(email=email).first() is None:
        user = User(name="System Administrator", email=email, role="admin", profile_completed=True)
        user.set_password(get_initial_admin_password())
        db.session.add(user)
    db.session.commit()
