"""Authentication API — role-verified login, sessions, password reset."""
from datetime import datetime

from flask import Blueprint, current_app, request, session, url_for
from flask_login import current_user, login_user, logout_user

from app import db, limiter
from app.api.utils import (
    ApiError,
    csrf_token,
    fail,
    json_body,
    ok,
    user_public,
)
from app.models import DomainAssignment, PasswordResetToken, User
from app.services.portal import audit, enrolled_domains, iso, now_utc

auth_api = Blueprint("api_auth", __name__, url_prefix="/api/v1/auth")

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


@auth_api.get("/csrf")
def get_csrf():
    return ok({"csrf_token": csrf_token()})


@auth_api.get("/me")
def me():
    if not current_user.is_authenticated:
        raise ApiError("Authentication required.", 401, "unauthenticated")
    return ok(
        {
            "user": user_public(current_user),
            "domains": [
                {"id": d.id, "code": d.code, "name": d.name, "is_compulsory": d.is_compulsory, "color": d.color}
                for d in enrolled_domains(current_user.id)
            ]
            if current_user.role == "student"
            else [],
        }
    )


@auth_api.post("/login")
@limiter.limit("10 per minute")
def login():
    data = json_body()
    portal = (data.get("portal") or "").strip().lower()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    remember = bool(data.get("remember"))

    if portal not in PORTAL_ROLES:
        raise ApiError("Select a valid login option.", 400, "invalid_portal")
    if not email or not password:
        raise ApiError("Email and password are required.", 400, "missing_credentials")

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

    # Coordinators and faculty can only sign in once an administrator has
    # assigned them at least one domain.
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

    login_user(user, remember=remember)
    session.permanent = True
    user.last_login = now_utc()
    db.session.commit()

    return ok(
        {
            "user": user_public(user),
            "redirect": {
                "student": "/student",
                "coordinator": "/coordinator",
                "faculty": "/faculty",
                "admin": "/admin",
            }[user.role],
            "profile_required": user.role == "student" and not user.profile_completed,
        }
    )


@auth_api.post("/logout")
def logout():
    if current_user.is_authenticated:
        audit(current_user.id, "auth.logout", target_type="User", target_id=current_user.id)
        db.session.commit()
    logout_user()
    session.clear()
    return ok({"message": "Signed out."})


@auth_api.post("/register")
@limiter.limit("5 per hour")
def register():
    data = json_body()
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    register_number = (data.get("register_number") or "").strip()

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
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return ok({"message": "Account created. An administrator must approve it before you can sign in."}, 201)


@auth_api.post("/forgot-password")
@limiter.limit("5 per hour")
def forgot_password():
    data = json_body()
    email = (data.get("email") or "").strip().lower()
    if not email:
        raise ApiError("Email address is required.", 400, "missing_email")

    user = User.query.filter_by(email=email).first()
    response = {
        "message": "If an account exists for that email, a reset link has been generated.",
        "delivery": "email" if current_app.config.get("MAIL_SERVER") else "console",
    }

    if user is None:
        return ok(response)

    PasswordResetToken.query.filter_by(user_id=user.id, used=False).update({"used": True})
    token = PasswordResetToken.generate(user.id)
    db.session.add(token)
    db.session.commit()

    reset_path = f"/reset-password?token={token.token}"
    if current_app.config.get("MAIL_SERVER"):
        try:
            from app.routes.auth import _send_reset_email

            reset_url = request.host_url.rstrip("/") + reset_path
            _send_reset_email(user, reset_url)
        except Exception:
            current_app.logger.exception("Password reset email failed")
            response["message"] = (
                "A reset token was created but the email could not be sent. "
                "Please contact the administrator."
            )
            response["delivery"] = "failed"
    else:
        current_app.logger.warning("[DEV] Password reset link for %s: %s", email, reset_path)
        response["message"] = (
            "Email delivery is not configured on this server. "
            "The reset link has been written to the server log."
        )
        if not current_app.config.get("is_production"):
            response["dev_reset_token"] = token.token
            response["dev_reset_path"] = reset_path
    return ok(response)


@auth_api.post("/reset-password")
@limiter.limit("10 per hour")
def reset_password():
    data = json_body()
    token_value = (data.get("token") or "").strip()
    password = data.get("password") or ""

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


@auth_api.post("/change-password")
def change_password():
    if not current_user.is_authenticated:
        raise ApiError("Authentication required.", 401, "unauthenticated")
    data = json_body()
    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""

    if not current_user.check_password(current_password):
        raise ApiError("Your current password is incorrect.", 400, "invalid_password")
    if len(new_password) < 8:
        raise ApiError("New password must be at least 8 characters.", 400, "weak_password")

    current_user.set_password(new_password)
    audit(current_user.id, "auth.password_change", target_type="User", target_id=current_user.id)
    db.session.commit()
    return ok({"message": "Password updated."})


@auth_api.patch("/profile")
def update_profile():
    if not current_user.is_authenticated:
        raise ApiError("Authentication required.", 401, "unauthenticated")
    data = json_body()

    editable = [
        "name",
        "register_number",
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
            setattr(current_user, field, value.strip() if isinstance(value, str) and value.strip() else None)

    if "year" in data and data["year"] not in (None, ""):
        try:
            current_user.year = int(data["year"])
        except (TypeError, ValueError):
            raise ApiError("Year must be a number.", 400, "invalid_year")

    if not current_user.name:
        raise ApiError("Name cannot be empty.", 400, "invalid_name")

    current_user.profile_completed = True
    db.session.commit()
    return ok({"user": user_public(current_user), "message": "Profile updated."})
