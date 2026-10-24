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
    """FastAPI dependency for scoped db session."""
    try:
        yield db.session
    finally:
        db.session.remove()
