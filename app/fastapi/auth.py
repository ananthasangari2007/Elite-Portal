"""Authentication, session signing, and role-based dependencies for FastAPI."""
from __future__ import annotations

import logging
import secrets
from typing import Callable, Optional

from fastapi import Depends, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app import db
from app.models.user import User
from config import Config

logger = logging.getLogger("elite_portal.auth")

SERIALIZER_SALT = "cookie-session"
SESSION_LIFETIME = int(getattr(Config, "SESSION_LIFETIME_SECONDS", 8 * 3600))
REMEMBER_LIFETIME = 30 * 24 * 3600

serializer = URLSafeTimedSerializer(Config.SECRET_KEY, salt=SERIALIZER_SALT)


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


def create_session_token(user_id: int, csrf_token: str) -> str:
    """Encode session data into a signed timed token."""
    return serializer.dumps({"_user_id": str(user_id), "api_csrf": csrf_token})


def decode_session_token(token: str, max_age: Optional[int] = None) -> Optional[dict]:
    """Decode a signed session token. Returns payload dict or None if invalid/expired."""
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=max_age or SESSION_LIFETIME)
        if isinstance(data, dict):
            return data
    except (SignatureExpired, BadSignature, Exception):
        pass
    return None


def set_session_cookie(response: Response, user_id: int, csrf_val: str, remember: bool = False) -> str:
    """Signs and writes session cookie to response, returns the raw token."""
    token = create_session_token(user_id, csrf_val)
    max_age = REMEMBER_LIFETIME if remember else SESSION_LIFETIME
    response.set_cookie(
        key="session",
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        path="/",
        secure=Config.is_production,
    )
    return token


def clear_session_cookie(response: Response):
    """Clears the session cookie."""
    response.delete_cookie(
        key="session",
        path="/",
        httponly=True,
        samesite="lax",
    )


def get_current_user_optional(request: Request) -> Optional[User]:
    """Extract authenticated User from session cookie or Authorization header, or None."""
    # 1. Try Bearer header
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    # 2. Try session cookie
    if not token:
        token = request.cookies.get("session")

    if not token:
        return None

    data = decode_session_token(token)
    if not data:
        return None

    user_id_raw = data.get("_user_id") or data.get("user_id")
    if not user_id_raw:
        return None

    try:
        user_id = int(user_id_raw)
    except (ValueError, TypeError):
        return None

    user = db.session.get(User, user_id)
    if not user or not user.is_active_account:
        return None

    return user


def get_current_user(request: Request) -> User:
    """Dependency that requires an authenticated user."""
    user = get_current_user_optional(request)
    if not user:
        raise ApiError("Authentication required.", 401, "unauthenticated")
    if not user.is_active_account:
        raise ApiError("This account has been deactivated.", 403, "account_inactive")
    return user


def require_roles(*roles: str) -> Callable:
    """Dependency factory enforcing one of the allowed roles."""
    def role_checker(request: Request) -> User:
        user = get_current_user(request)
        if roles and user.role not in roles:
            raise ApiError("You do not have permission to perform this action.", 403, "forbidden")
        return user
    return role_checker


def get_csrf_token(request: Request) -> str:
    """Get CSRF token from current session or generate a fresh one."""
    token = request.cookies.get("session")
    if token:
        data = decode_session_token(token)
        if data and data.get("api_csrf"):
            return data["api_csrf"]
    return secrets.token_urlsafe(32)


def verify_csrf(request: Request):
    """Verify X-CSRF-Token header against session token."""
    supplied = request.headers.get("X-CSRF-Token")
    if not supplied:
        raise ApiError("Invalid or missing CSRF token.", 403, "csrf_failed")

    token = request.cookies.get("session")
    if token:
        data = decode_session_token(token)
        if data and data.get("api_csrf"):
            expected = data["api_csrf"]
            if secrets.compare_digest(expected, supplied):
                return

    # Also accept if supplied matches header-supplied session
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        data = decode_session_token(auth_header[7:].strip())
        if data and data.get("api_csrf"):
            expected = data["api_csrf"]
            if secrets.compare_digest(expected, supplied):
                return

    raise ApiError("Invalid or missing CSRF token.", 403, "csrf_failed")
