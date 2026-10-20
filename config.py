import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv()


def normalize_database_url(url):
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def is_production_environment():
    env = (os.getenv("FLASK_ENV") or os.getenv("APP_ENV") or "development").lower()
    return env in {"production", "prod", "staging"}


class Config:
    is_production = is_production_environment()

    if os.getenv("SECRET_KEY"):
        SECRET_KEY = os.getenv("SECRET_KEY")
    elif is_production:
        raise RuntimeError("SECRET_KEY must be set in production")
    else:
        SECRET_KEY = "dev-secret-change-me"

    _db_url = normalize_database_url(os.getenv("DATABASE_URL"))
    if _db_url:
        SQLALCHEMY_DATABASE_URI = _db_url
    elif is_production:
        raise RuntimeError("DATABASE_URL must be set to a PostgreSQL URL in production")
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'instance' / 'elite_portal.sqlite3'}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = is_production
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = is_production
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.getenv("SESSION_LIFETIME_SECONDS", str(60 * 60 * 8)))
    )

    # REST API / SPA
    API_PREFIX = "/api/v1"
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
        ).split(",")
        if origin.strip()
    ]
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "instance" / "uploads"))
    MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))

    # Institutional settings
    INSTITUTION_NAME = os.getenv("INSTITUTION_NAME", "Francis Xavier Engineering College")
    INSTITUTION_TIMEZONE = os.getenv("INSTITUTION_TIMEZONE", "Asia/Kolkata")
    BATCH_NAME = os.getenv("BATCH_NAME", "Elite Batch 2025-2029")

    # Cloudflare R2 / S3-compatible storage
    R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL", "")
    R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "elite-portal-files")
    R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "")

    # Email (for password reset)
    MAIL_SERVER = os.getenv("MAIL_SERVER", "")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "")

    # Rate limiting
    RATELIMIT_DEFAULT = "200 per day;50 per hour"
    RATELIMIT_STORAGE_URL = os.getenv("RATELIMIT_STORAGE_URL", "memory://")

    # Domain enrollment rules
    MAX_OPTIONAL_DOMAINS = int(os.getenv("MAX_OPTIONAL_DOMAINS", "2"))
