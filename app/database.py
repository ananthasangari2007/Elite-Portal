"""Framework-independent SQLAlchemy setup (replaces Flask-SQLAlchemy).

Exposes a ``db`` facade with the same surface the models and services already use
(``db.Model``, ``db.Column``, ``db.relationship``, ``db.session`` ...), so the
existing models, services and business rules are reused unchanged.

Session scoping: one session per HTTP request. The request middleware sets
``request_scope`` (a ContextVar); Starlette propagates context into the worker
threads that run sync endpoints and dependencies, so every piece of code serving a
request sees the same session, and the middleware removes it when the request ends.
Outside a request (CLI, tests, startup), the session is scoped per thread.
"""
from __future__ import annotations

import contextvars
import logging
import re
import threading

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import DeclarativeBase, declared_attr, scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from config import Config

logger = logging.getLogger("elite_portal.db")

request_scope: contextvars.ContextVar[str | None] = contextvars.ContextVar("db_request_scope", default=None)


def _scopefunc():
    return request_scope.get() or f"thread-{threading.get_ident()}"


def _build_engine(url: str):
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
        return sa.create_engine(url, **kwargs)

    options = dict(getattr(Config, "SQLALCHEMY_ENGINE_OPTIONS", {}) or {})
    options.setdefault("pool_pre_ping", True)
    options.setdefault("pool_size", 10)
    options.setdefault("max_overflow", 20)
    options.setdefault("pool_timeout", 20)
    # Neon/serverless Postgres drops idle connections; recycle before that happens.
    options.setdefault("pool_recycle", 280)
    connect_args = dict(options.pop("connect_args", {}) or {})
    if url.startswith("postgresql"):
        connect_args.setdefault("connect_timeout", 10)
        connect_args.setdefault("keepalives", 1)
        connect_args.setdefault("keepalives_idle", 30)
        connect_args.setdefault("keepalives_interval", 10)
        connect_args.setdefault("keepalives_count", 5)
    return sa.create_engine(url, connect_args=connect_args, **options)


engine = _build_engine(Config.SQLALCHEMY_DATABASE_URI)
SessionLocal = sessionmaker(bind=engine, autoflush=True, expire_on_commit=True)
session = scoped_session(SessionLocal, scopefunc=_scopefunc)


def _camel_to_snake(name: str) -> str:
    # Same algorithm Flask-SQLAlchemy uses, so implicit table names stay identical
    # (Task -> task, PointTransaction -> point_transaction).
    name = re.sub(r"((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))", r"_\1", name)
    return name.lower().lstrip("_")


class Model(DeclarativeBase):
    """Declarative base. ``Model.query`` mirrors Flask-SQLAlchemy's legacy query API."""

    query = session.query_property()

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        return _camel_to_snake(cls.__name__)


class _DB:
    """Facade exposing the Flask-SQLAlchemy names used across the codebase."""

    Model = Model
    session = session
    engine = engine
    metadata = Model.metadata

    def __getattr__(self, name):
        # Column, Integer, String, ForeignKey, Index, UniqueConstraint, desc, func ...
        if hasattr(sa, name):
            return getattr(sa, name)
        if hasattr(orm, name):  # relationship, backref ...
            return getattr(orm, name)
        raise AttributeError(name)

    def create_all(self):
        Model.metadata.create_all(bind=engine)

    def drop_all(self):
        Model.metadata.drop_all(bind=engine)


db = _DB()


def remove_session():
    try:
        session.rollback()
    except Exception:  # connection already gone; nothing to roll back
        pass
    finally:
        session.remove()
