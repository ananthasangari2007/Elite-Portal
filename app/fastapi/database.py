"""SQLAlchemy database session binding for FastAPI."""
from __future__ import annotations

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool

from config import Config
from app import db
import app.models as models

logger = logging.getLogger("elite_portal.db")

db_url = Config.SQLALCHEMY_DATABASE_URI
engine_options = dict(getattr(Config, "SQLALCHEMY_ENGINE_OPTIONS", {}))

if "sqlite" in db_url:
    if ":memory:" in db_url:
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
        )
else:
    # Optimized for Neon serverless PostgreSQL
    engine_options.setdefault("pool_pre_ping", True)
    engine_options["pool_recycle"] = 45  # Recycle connections after 45s of idle
    engine_options["pool_timeout"] = 20
    engine_options.setdefault("pool_size", 10)
    engine_options.setdefault("max_overflow", 20)

    connect_args = dict(engine_options.get("connect_args", {}))
    connect_args.setdefault("keepalives", 1)
    connect_args.setdefault("keepalives_idle", 30)
    connect_args.setdefault("keepalives_interval", 10)
    connect_args.setdefault("keepalives_count", 5)
    engine_options["connect_args"] = connect_args

    engine = create_engine(db_url, **engine_options)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionLocal)

# Bind db.session so existing services in app.services.* continue to work
db.session = db_session

# Bind query_property for all SQLAlchemy models
for attr in dir(models):
    obj = getattr(models, attr)
    if isinstance(obj, type) and hasattr(obj, "__table__"):
        try:
            obj.query = db_session.query_property()
        except Exception:
            pass


def get_db():
    """FastAPI dependency for scoped db session with rollback and removal."""
    try:
        if db.session.is_active:
            db.session.rollback()
    except Exception:
        db.session.remove()

    try:
        yield db.session
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            db.session.remove()
        except Exception:
            pass
