"""Authentication endpoints for FastAPI."""
from __future__ import annotations

import logging
import os
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from pydantic import BaseModel

from app import db
from app.fastapi.auth import (
    ApiError,
    clear_session_cookie,
    create_session_token,
    current_session,
    get_csrf_token,
    get_current_user,
    get_current_user_optional,
    issue_anon_csrf,
    set_session_cookie,
)
from app.fastapi.utils import json_body, ok, user_public
from app.models.domain import DomainAssignment
from app.models.user import PasswordResetToken, User
from app.services.portal import audit, enrolled_domains, now_utc
from app.services.roster import (
    RosterUnavailable,
    lookup_student,
    mask_email,
    normalize_register_number,
    roster_enabled,
)
from app.services.storage import StorageError, save_file, validate_upload
from app.fastapi.ratelimit import rate_limit
from config import Config
from sqlalchemy import func

AVATAR_MAX_BYTES = 5 * 1024 * 1024

logger = logging.getLogger("elite_portal.auth_router")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

PORTAL_ROLES = {
    "student": "student",
    "coordinator": "coordinator",
    "faculty": "faculty",
    "admin": "admin",
}

PORTAL_LABELS = {
    "student": "Student Login",
    "coordinator": "Domain Coordinator Login",
    "faculty": "Faculty Coordinator Login",
    "admin": "Admin Login",
}


class LoginPayload(BaseModel):
    portal: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    remember: Optional[bool] = False


class RegisterPayload(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    register_number: Optional[str] = None
    phone_number: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    leetcode_url: Optional[str] = None
    avatar_url: Optional[str] = None


class RosterLookupPayload(BaseModel):
    register_number: Optional[str] = None


class ForgotPasswordPayload(BaseModel):
    email: Optional[str] = None


class ResetPasswordPayload(BaseModel):
    token: Optional[str] = None
    password: Optional[str] = None


class ChangePasswordPayload(BaseModel):
    current_password: Optional[str] = None
    new_password: Optional[str] = None


@router.get("/csrf")
def get_csrf(request: Request):
    token = get_csrf_token(request)
    res = ok({"csrf_token": token})
    if not current_session(request):
        # Signed-out callers (e.g. registration avatar upload) get a cookie-bound token.
        issue_anon_csrf(res, token)
    return res


@router.get("/me")
def me(request: Request):
    user = get_current_user_optional(request)
    if not user:
        raise ApiError("Authentication required.", 401, "unauthenticated")

    csrf_val = get_csrf_token(request)
    domains_data = []
    if user.role == "student":
        domains_data = [
            {
                "id": d.id,
                "code": d.code,
                "name": d.name,
                "is_compulsory": d.is_compulsory,
                "color": d.color,
            }
            for d in enrolled_domains(user.id)
        ]

    return ok(
        {
            "user": user_public(user),
            "csrf_token": csrf_val,
            "domains": domains_data,
        }
    )


@router.post("/login", dependencies=[Depends(rate_limit("login", 10, 60))])
def login(payload: LoginPayload, request: Request, response: Response):
    portal = (payload.portal or "").strip().lower()
    email = (payload.email or "").strip().lower()
    password = payload.password or ""
    remember = bool(payload.remember)

    if portal not in PORTAL_ROLES:
        raise ApiError("Select a valid login option.", 400, "invalid_portal")
    if not email or not password:
        raise ApiError("Email and password are required.", 400, "missing_credentials")

    try:
        user = User.query.filter_by(email=email).first()
    except Exception:
        db.session.rollback()
        user = User.query.filter_by(email=email).first()

    if user is None or not user.check_password(password):
        raise ApiError("Incorrect email or password. Please try again.", 401, "invalid_credentials")

    expected_role = PORTAL_ROLES[portal]
    if user.role != expected_role:
        correct = next((k for k, v in PORTAL_ROLES.items() if v == user.role), None)
        raise ApiError(
            f"This account is not a {PORTAL_LABELS[portal].replace(' Login', '')} account. "
            f"Please use the {PORTAL_LABELS.get(correct, 'correct')} option.",
            403,
            "role_mismatch",
        )
    if not user.is_active_account:
        raise ApiError("Your account has been deactivated. Contact the administrator.", 403, "account_inactive")
    if user.role == "student" and user.approval_status == "pending":
        raise ApiError("Your student account is pending admin approval.", 403, "pending_approval")

    if user.role in {"coordinator", "faculty"}:
        assigned = DomainAssignment.query.filter_by(
            user_id=user.id, assignment_type=user.role
        ).first()
        if assigned is None:
            label = "Domain Coordinator" if user.role == "coordinator" else "Faculty Coordinator"
            raise ApiError(
                f"This {label} account has no domain assignment yet. "
                "Please contact an administrator.",
                403,
                "no_domain_assignment",
            )

    csrf_val = secrets.token_urlsafe(32)

    user.last_login = now_utc()
    db.session.commit()

    redirect_path = {
        "student": "/student",
        "coordinator": "/coordinator",
        "faculty": "/faculty",
        "admin": "/admin",
    }[user.role]

    # Cookie and Bearer token are the same signed value, so both paths agree on expiry
    # (previously the Bearer token ignored "remember" and expired after 8h).
    session_token = create_session_token(user.id, csrf_val, remember=remember)
    res = ok(
        {
            "user": user_public(user),
            "token": session_token,
            "csrf_token": csrf_val,
            "redirect": redirect_path,
            "profile_required": user.role == "student" and not user.profile_completed,
        }
    )
    set_session_cookie(res, user.id, csrf_val, remember=remember, token=session_token)
    return res


@router.post("/logout")
def logout(request: Request):
    user = get_current_user_optional(request)
    if user:
        audit(user.id, "auth.logout", target_type="User", target_id=user.id)
        db.session.commit()

    new_csrf = secrets.token_urlsafe(32)
    res = ok({"message": "Signed out.", "csrf_token": new_csrf})
    clear_session_cookie(res)
    return res


@router.post("/upload-avatar", dependencies=[Depends(rate_limit("avatar", 20, 3600))])
def upload_avatar(request: Request, file: UploadFile = File(...)):
    # Optional auth: the registration screen uploads an avatar before an account exists
    # (same behaviour as the original endpoint, which did not require a session).
    filename = file.filename or "avatar.png"

    # Validate extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in {"png", "jpg", "jpeg", "webp", "gif"}:
        raise ApiError("Profile picture must be an image (PNG, JPG, WEBP).", 400, "invalid_image_type")

    try:
        validate_upload(file, max_bytes=AVATAR_MAX_BYTES, allowed={"png", "jpg", "jpeg", "webp", "gif"})
        meta = save_file(file, folder="avatars")
    except ValueError as exc:
        raise ApiError(str(exc), 400, "invalid_file") from exc
    except StorageError as exc:
        raise ApiError(str(exc), 503, "storage_unavailable") from exc
    return ok(meta, 201)


@router.post("/roster-lookup", dependencies=[Depends(rate_limit("roster", 20, 3600))])
def roster_lookup(payload: RosterLookupPayload):
    """Confirm a register number against the approved roster (masked details only)."""
    if not roster_enabled():
        raise ApiError("Roster verification is not enabled.", 404, "roster_disabled")
    register_number = normalize_register_number(payload.register_number)
    if not register_number:
        raise ApiError("Please enter your register number.", 400, "missing_register_number")
    record = _roster_record_or_error(register_number)
    return ok(
        {
            "register_number": record["register_number"],
            "name": record["name"],
            "department": record["department"],
            "email_hint": mask_email(record["email"]),
        }
    )


def _roster_record_or_error(register_number: str) -> dict:
    try:
        record = lookup_student(register_number)
    except RosterUnavailable:
        raise ApiError(
            "Student verification is temporarily unavailable. Please try again in a few minutes.",
            503,
            "roster_unavailable",
        )
    if record is None:
        raise ApiError(
            "This register number is not on the approved Elite roster. Contact your coordinator.",
            403,
            "not_eligible",
        )
    return record


def _register_number_taken(register_number: str, exclude_user_id: Optional[int] = None) -> bool:
    query = User.query.filter(func.upper(func.replace(User.register_number, " ", "")) == register_number)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return db.session.query(query.exists()).scalar()


@router.post("/register", dependencies=[Depends(rate_limit("register", 5, 3600))])
def register(payload: RegisterPayload):
    name = (payload.name or "").strip()
    email = (payload.email or "").strip().lower()
    password = payload.password or ""
    register_number = normalize_register_number(payload.register_number)
    phone_number = (payload.phone_number or "").strip()
    linkedin_url = (payload.linkedin_url or "").strip()
    github_url = (payload.github_url or "").strip()
    leetcode_url = (payload.leetcode_url or "").strip()
    avatar_url = (payload.avatar_url or "").strip()

    if len(name) < 2:
        raise ApiError("Please enter your full name.", 400, "invalid_name")
    if "@" not in email or len(email) < 5:
        raise ApiError("Please enter a valid email address.", 400, "invalid_email")
    if len(password) < 8:
        raise ApiError("Password must be at least 8 characters.", 400, "weak_password")
    if User.query.filter_by(email=email).first():
        raise ApiError("This email is already registered.", 409, "email_exists")
    if register_number and _register_number_taken(register_number):
        raise ApiError("This register number is already registered.", 409, "register_number_exists")

    department = None
    if roster_enabled():
        if not register_number:
            raise ApiError("Please enter your register number.", 400, "missing_register_number")
        record = _roster_record_or_error(register_number)
        if record["email"] and record["email"] != email:
            raise ApiError(
                "Use the college email address registered for this register number.", 400, "email_mismatch"
            )
        name = record["name"] or name
        department = record["department"]

    user = User(
        name=name,
        email=email,
        role="student",
        approval_status="pending",
        register_number=register_number or None,
        department=department,
        phone_number=phone_number or None,
        linkedin_url=linkedin_url or None,
        github_url=github_url or None,
        leetcode_url=leetcode_url or None,
        avatar_url=avatar_url or None,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return ok({"message": "Account created. An administrator must approve it before you can sign in."}, 201)


@router.post("/forgot-password", dependencies=[Depends(rate_limit("forgot", 5, 3600))])
def forgot_password(payload: ForgotPasswordPayload, request: Request):
    email = (payload.email or "").strip().lower()
    if not email:
        raise ApiError("Email address is required.", 400, "missing_email")

    user = User.query.filter_by(email=email).first()
    has_mail = bool(getattr(Config, "MAIL_SERVER", None))
    response = {
        "message": "If an account exists for that email, a reset link has been generated.",
        "delivery": "email" if has_mail else "console",
    }

    if user is None:
        return ok(response)

    PasswordResetToken.query.filter_by(user_id=user.id, used=False).update({"used": True})
    token = PasswordResetToken.generate(user.id)
    db.session.add(token)
    db.session.commit()

    reset_path = f"/reset-password?token={token.token}"
    if has_mail:
        try:
            from app.services.mailer import send_reset_email
            base_url = (os.getenv("FRONTEND_URL") or str(request.base_url)).rstrip("/")
            send_reset_email(user, base_url + reset_path)
        except Exception:
            logger.exception("Password reset email failed")
            response["message"] = (
                "A reset token was created but the email could not be sent. "
                "Please contact the administrator."
            )
            response["delivery"] = "failed"
    else:
        logger.warning("[DEV] Password reset link for %s: %s", email, reset_path)
        response["message"] = (
            "Email delivery is not configured on this server. "
            "The reset link has been written to the server log."
        )
        if not getattr(Config, "is_production", False):
            response["dev_reset_token"] = token.token
            response["dev_reset_path"] = reset_path

    return ok(response)


@router.post("/reset-password", dependencies=[Depends(rate_limit("reset", 10, 3600))])
def reset_password(payload: ResetPasswordPayload):
    token_value = (payload.token or "").strip()
    password = payload.password or ""

    if len(password) < 8:
        raise ApiError("Password must be at least 8 characters.", 400, "weak_password")

    record = PasswordResetToken.query.filter_by(token=token_value, used=False).first()
    if record is None or not record.is_valid:
        raise ApiError("This password reset link is invalid or has expired.", 400, "invalid_token")

    record.user.set_password(password)
    record.user.clear_reset_token()
    record.used = True
    db.session.commit()
    return ok({"message": "Password reset successfully. You can now sign in."})


@router.post("/change-password")
def change_password(payload: ChangePasswordPayload, user: User = Depends(get_current_user)):
    current_password = payload.current_password or ""
    new_password = payload.new_password or ""

    if not user.check_password(current_password):
        raise ApiError("Your current password is incorrect.", 400, "invalid_password")
    if len(new_password) < 8:
        raise ApiError("New password must be at least 8 characters.", 400, "weak_password")

    user.set_password(new_password)
    audit(user.id, "auth.password_change", target_type="User", target_id=user.id)
    db.session.commit()
    return ok({"message": "Password updated."})


@router.patch("/profile")
def update_profile(data: dict = Depends(json_body), user: User = Depends(get_current_user)):
    original_register_number = normalize_register_number(user.register_number)
    editable = [
        "name",
        "register_number",
        "phone_number",
        "department",
        "section",
        "linkedin_url",
        "github_url",
        "leetcode_url",
        "preferred_domain",
        "avatar_url",
        "bio",
    ]
    for field in editable:
        if field in data:
            value = data[field]
            setattr(user, field, value.strip() if isinstance(value, str) and value.strip() else None)

    if "register_number" in data and user.register_number:
        user.register_number = normalize_register_number(user.register_number)
        if _register_number_taken(user.register_number, exclude_user_id=user.id):
            raise ApiError("This register number is already registered.", 409, "register_number_exists")
        if user.role == "student" and roster_enabled() and user.register_number != original_register_number:
            _roster_record_or_error(user.register_number)

    if "year" in data and data["year"] not in (None, ""):
        try:
            user.year = int(data["year"])
        except (TypeError, ValueError):
            raise ApiError("Year must be a number.", 400, "invalid_year")

    if not user.name:
        raise ApiError("Name cannot be empty.", 400, "invalid_name")

    user.profile_completed = True
    db.session.commit()
    return ok({"user": user_public(user), "message": "Profile updated."})
