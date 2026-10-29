"""Authentication, session signing, CSRF and role-based dependencies for FastAPI.

Session model (unchanged contract): login issues a signed, timestamped token that is
set as the HttpOnly ``session`` cookie and also returned as ``data.token`` so the SPA
can send ``Authorization: Bearer <token>`` when cookies are unavailable. Both carry
the same payload: ``{"_user_id", "api_csrf", "rem"}``.
"""
from __future__ import annotations

import logging
import secrets
from typing import Callable, Optional

from fastapi import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.database import db
from app.models.user import User
from config import Config

logger = logging.getLogger("elite_portal.auth")

SERIALIZER_SALT = "cookie-session"
SESSION_COOKIE = "session"
ANON_CSRF_COOKIE = "elite_csrf"
SESSION_HINT_COOKIE = "elite_session"
SESSION_LIFETIME = int(getattr(Config, "SESSION_LIFETIME_SECONDS", 8 * 3600))
REMEMBER_LIFETIME = 30 * 24 * 3600
COOKIE_SAMESITE = (getattr(Config, "SESSION_COOKIE_SAMESITE", "Lax") or "Lax").lower()

# Same exemptions the original Flask API used (pre-session endpoints).
CSRF_EXEMPT_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/register",
    "/api/v1/auth/roster-lookup",
}

serializer = URLSafeTimedSerializer(Config.SECRET_KEY, salt=SERIALIZER_SALT)
csrf_serializer = URLSafeTimedSerializer(Config.SECRET_KEY, salt="anon-csrf")


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "bad_request", details=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.details = details

    @property
    def status_code(self) -> int:
        return self.status

    def to_dict(self) -> dict:
        err = {"code": self.code, "message": self.message}
        if self.details is not None:
            err["details"] = self.details
        return {"error": err}


# ── Token helpers ─────────────────────────────────────────────────────────
def create_session_token(user_id: int, csrf_token: str, remember: bool = False) -> str:
    return serializer.dumps({"_user_id": str(user_id), "api_csrf": csrf_token, "rem": bool(remember)})


def decode_session_token(token: str, max_age: Optional[int] = None) -> Optional[dict]:
    """Decode a signed session token; None if invalid or expired.

    "Remember me" tokens are valid for REMEMBER_LIFETIME (previously they were
    rejected after 8h even though the cookie lived 30 days, which produced
    unexpected 401s from /auth/me for remembered sessions).
    """
    if not token:
        return None
    try:
        data, issued_at = serializer.loads(token, max_age=REMEMBER_LIFETIME, return_timestamp=True)
    except (SignatureExpired, BadSignature):
        return None
    except Exception:
        logger.debug("Malformed session token", exc_info=True)
        return None
    if not isinstance(data, dict):
        return None
    limit = max_age or (REMEMBER_LIFETIME if data.get("rem") else SESSION_LIFETIME)
    from datetime import datetime, timezone

    age = (datetime.now(timezone.utc) - issued_at).total_seconds()
    if age > limit:
        return None
    return data


def _cookie_kwargs() -> dict:  # noqa: D401 - shared cookie attributes
    samesite = COOKIE_SAMESITE if COOKIE_SAMESITE in {"lax", "strict", "none"} else "lax"
    return {
        "httponly": True,
        "samesite": samesite,
        "path": "/",
        "secure": bool(Config.is_production or samesite == "none"),
    }


def set_session_cookie(
    response: Response, user_id: int, csrf_val: str, remember: bool = False, token: Optional[str] = None
) -> str:
    token = token or create_session_token(user_id, csrf_val, remember)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=REMEMBER_LIFETIME if remember else SESSION_LIFETIME,
        **_cookie_kwargs(),
    )
    # Non-sensitive, script-readable marker ("a session may exist"). The SPA uses it to
    # skip the /auth/me probe for signed-out visitors instead of always getting a 401.
    hint_kwargs = {k: v for k, v in _cookie_kwargs().items() if k != "httponly"}
    response.set_cookie(
        key=SESSION_HINT_COOKIE,
        value="1",
        max_age=REMEMBER_LIFETIME if remember else SESSION_LIFETIME,
        httponly=False,
        **hint_kwargs,
    )
    response.delete_cookie(ANON_CSRF_COOKIE, path="/")
    return token


def clear_session_cookie(response: Response):
    response.delete_cookie(key=SESSION_COOKIE, **_cookie_kwargs())
    response.delete_cookie(key=SESSION_HINT_COOKIE, path="/")


def _candidate_tokens(request: Request) -> list[str]:
    """Bearer header first, then cookie. Both are tried, so a stale token left in
    localStorage no longer masks a valid cookie session (a source of spurious 401s)."""
    tokens = []
    auth_header = request.headers.get("Authorization", "")
    if auth_header[:7].lower() == "bearer ":
        bearer = auth_header[7:].strip()
        if bearer and bearer not in {"null", "undefined"}:
            tokens.append(bearer)
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie and cookie not in tokens:
        tokens.append(cookie)
    return tokens


def current_session(request: Request) -> Optional[dict]:
    """Return the first valid session payload for this request (cached per request)."""
    if hasattr(request.state, "session_payload"):
        return request.state.session_payload
    payload = None
    for token in _candidate_tokens(request):
        payload = decode_session_token(token)
        if payload:
            break
    request.state.session_payload = payload
    return payload


# ── User dependencies ─────────────────────────────────────────────────────
def get_current_user_optional(request: Request) -> Optional[User]:
    data = current_session(request)
    if not data:
        return None
    try:
        user_id = int(data.get("_user_id") or data.get("user_id"))
    except (TypeError, ValueError):
        return None
    try:
        user = db.session.get(User, user_id)
    except Exception:
        # Stale pooled connection: roll back once and retry (pool_pre_ping covers most cases).
        db.session.rollback()
        user = db.session.get(User, user_id)
    if not user or not user.is_active_account:
        return None
    return user


def get_current_user(request: Request) -> User:
    user = get_current_user_optional(request)
    if not user:
        raise ApiError("Authentication required.", 401, "unauthenticated")
    return user


def require_roles(*roles: str) -> Callable:
    """Dependency factory: 401 when signed out, 403 when the role is not allowed."""

    def role_checker(request: Request) -> User:
        user = get_current_user(request)
        if roles and user.role not in roles:
            raise ApiError("You do not have permission to perform this action.", 403, "forbidden")
        return user

    return role_checker


# ── CSRF ──────────────────────────────────────────────────────────────────
def get_csrf_token(request: Request) -> str:
    """CSRF token bound to the current session, or None-equivalent fresh value."""
    data = current_session(request)
    if data and data.get("api_csrf"):
        return data["api_csrf"]
    anon = _anon_csrf(request)
    return anon or secrets.token_urlsafe(32)


def _anon_csrf(request: Request) -> Optional[str]:
    raw = request.cookies.get(ANON_CSRF_COOKIE)
    if not raw:
        return None
    try:
        return csrf_serializer.loads(raw, max_age=SESSION_LIFETIME)
    except (BadSignature, SignatureExpired):
        return None


def issue_anon_csrf(response: Response, token: str):
    """Pre-login CSRF token (e.g. avatar upload on the registration page)."""
    response.set_cookie(ANON_CSRF_COOKIE, csrf_serializer.dumps(token), max_age=SESSION_LIFETIME, **_cookie_kwargs())


def check_csrf(request: Request) -> Optional[dict]:
    """Return an error body when CSRF validation fails, else None.

    Enforced for every mutating /api/ request except the pre-session endpoints,
    matching the original Flask API behaviour.
    """
    if request.url.path.rstrip("/") in CSRF_EXEMPT_PATHS:
        return None
    supplied = request.headers.get("X-CSRF-Token", "")
    error = {"error": {"code": "csrf_failed", "message": "Invalid or missing CSRF token."}}
    if not supplied:
        return error
    data = current_session(request)
    expected = (data or {}).get("api_csrf") or _anon_csrf(request)
    if expected and secrets.compare_digest(expected, supplied):
        return None
    return error


def verify_csrf(request: Request):
    """Dependency form of :func:`check_csrf` (kept for compatibility)."""
    error = check_csrf(request)
    if error:
        raise ApiError(error["error"]["message"], 403, "csrf_failed")
