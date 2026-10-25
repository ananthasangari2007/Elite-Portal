"""Authentication endpoints for FastAPI."""
from __future__ import annotations

import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from pydantic import BaseModel

from app import db
from app.fastapi.auth import (
    ApiError,
    clear_session_cookie,
    create_session_token,
    get_csrf_token,
    get_current_user,
    get_current_user_optional,
    set_session_cookie,
)
from app.fastapi.utils import ok, user_public
from app.models.domain import DomainAssignment
from app.models.user import PasswordResetToken, User
from app.services.portal import audit, enrolled_domains, now_utc
from app.services.storage import save_file, validate_upload
from config import Config

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
    return ok({"csrf_token": token})


@router.get("/me")
def me(request: Request):
    try:
        user = get_current_user_optional(request)
    except Exception:
        db.session.rollback()
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


@router.post("/login")
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
    session_token = create_session_token(user.id, csrf_val)

    user.last_login = now_utc()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        user = User.query.filter_by(email=email).first()
        if user:
            user.last_login = now_utc()
            db.session.commit()

    redirect_path = {
        "student": "/student",
        "coordinator": "/coordinator",
        "faculty": "/faculty",
        "admin": "/admin",
    }[user.role]

    res = ok(
        {
            "user": user_public(user),
            "token": session_token,
            "csrf_token": csrf_val,
            "redirect": redirect_path,
            "profile_required": user.role == "student" and not user.profile_completed,
        }
    )
    set_session_cookie(res, user.id, csrf_val, remember=remember)
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


@router.post("/upload-avatar")
def upload_avatar(request: Request, file: UploadFile = File(...)):
    user = get_current_user(request)
    filename = file.filename or "avatar.png"

    # Validate extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in {"png", "jpg", "jpeg", "webp", "gif"}:
        raise ApiError("Profile picture must be an image (PNG, JPG, WEBP).", 400, "invalid_image_type")

    meta = save_file(file, folder="avatars")
    return ok(meta, 201)


@router.post("/register")
def register(payload: RegisterPayload):
    name = (payload.name or "").strip()
    email = (payload.email or "").strip().lower()
    password = payload.password or ""
    register_number = (payload.register_number or "").strip()
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

    user = User(
        name=name,
        email=email,
        role="student",
        approval_status="pending",
        register_number=register_number or None,
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


@router.post("/forgot-password")
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
            from app.routes.auth import _send_reset_email
            base_url = str(request.base_url).rstrip("/")
            reset_url = base_url + reset_path
            _send_reset_email(user, reset_url)
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


@router.post("/reset-password")
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
def update_profile(request: Request, user: User = Depends(get_current_user)):
    import json
    try:
        data = json.loads(request._body) if hasattr(request, "_body") and request._body else {}
    except Exception:
        data = {}

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
