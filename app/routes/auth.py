"""
Auth routes — Elite Portal
Handles portal selection, login, logout, and password reset for all 4 roles.
"""
from flask import (
    Blueprint, flash, redirect, render_template,
    request, url_for, current_app
)
from flask_login import current_user, login_user, logout_user
from datetime import datetime

from app import db
from app.models import User, PasswordResetToken


auth_bp = Blueprint("auth", __name__)


# ── Portal definitions (ORDER IS CRITICAL — DO NOT CHANGE) ────────────────
PORTALS = [
    {
        "key": "student",
        "label": "Student Login",
        "role": "student",
        "icon": "graduation-cap",
        "description": "Access learning, assessments, Elite Tasks, and points.",
        "color": "#4f46e5",
        "bg": "bg-indigo",
    },
    {
        "key": "coordinator",
        "label": "Domain Coordinator Login",
        "role": "coordinator",
        "icon": "book-open",
        "description": "Manage domain content, learning days, assessments, and submissions.",
        "color": "#0891b2",
        "bg": "bg-cyan",
    },
    {
        "key": "faculty",
        "label": "Faculty Coordinator Login",
        "role": "faculty",
        "icon": "users",
        "description": "Review grading, appeals, student requests, and point adjustments.",
        "color": "#7c3aed",
        "bg": "bg-violet",
    },
    {
        "key": "admin",
        "label": "Admin Login",
        "role": "admin",
        "icon": "shield",
        "description": "Manage users, domains, platform settings, and reports.",
        "color": "#dc2626",
        "bg": "bg-red",
    },
]

PORTAL_MAP = {p["key"]: p for p in PORTALS}

ROLE_DASHBOARD = {
    "student": "student.dashboard",
    "coordinator": "coordinator.dashboard",
    "faculty": "faculty.dashboard",
    "admin": "admin_portal.dashboard",
}


def redirect_authenticated():
    """Redirect a logged-in user to their role's dashboard."""
    target = ROLE_DASHBOARD.get(current_user.role, "dashboard.home")
    return redirect(url_for(target))


@auth_bp.route("/")
def choose_portal():
    if current_user.is_authenticated:
        return redirect_authenticated()
    return render_template("auth/choose_portal.html", portals=PORTALS)


@auth_bp.route("/login/<portal>", methods=["GET", "POST"])
def login(portal):
    portal_config = PORTAL_MAP.get(portal)
    if not portal_config:
        flash("Choose a valid portal to continue.", "warning")
        return redirect(url_for("auth.choose_portal"))

    if current_user.is_authenticated:
        return redirect_authenticated()

    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        if not email or not password:
            error = "Email and password are required."
        else:
            # Find user by email (role verified server-side)
            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):
                # Verify role matches selected portal
                if user.role != portal_config["role"]:
                    role_label = next(
                        (p["label"] for p in PORTALS if p["role"] == user.role),
                        "the correct portal"
                    )
                    error = f"This account uses {role_label}. Please select the correct login option."
                elif not user.is_active_account:
                    error = "Your account has been deactivated. Contact the administrator."
                elif user.role == "student" and user.approval_status != "approved":
                    error = "Your student account is pending admin approval."
                else:
                    login_user(user, remember=remember)
                    user.last_login = datetime.utcnow()
                    db.session.commit()
                    flash(f"Welcome back, {user.name.split()[0]}!", "success")

                    # Redirect students without completed profile to profile page
                    if user.role == "student" and not user.profile_completed:
                        return redirect(url_for("profile.edit"))

                    next_url = request.args.get("next")
                    if next_url and next_url.startswith("/"):
                        return redirect(next_url)
                    return redirect_authenticated()
            else:
                error = "Incorrect email or password. Please try again."

    return render_template(
        "auth/login.html",
        portal=portal,
        portal_config=portal_config,
        portals=PORTALS,
        error=error,
    )


@auth_bp.route("/register/student", methods=["GET", "POST"])
def register_student():
    if current_user.is_authenticated:
        return redirect_authenticated()

    error = None

    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")
            register_number = request.form.get("register_number", "").strip()

            if not name:
                raise ValueError("Name is required.")
            if not email:
                raise ValueError("College email is required.")
            if len(password) < 8:
                raise ValueError("Password must be at least 8 characters.")
            if password != confirm:
                raise ValueError("Passwords do not match.")
            if User.query.filter_by(email=email).first():
                raise ValueError("This email is already registered.")

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

            flash(
                "Account created! Your registration is pending admin approval. "
                "You will be notified when approved.",
                "success"
            )
            return redirect(url_for("auth.login", portal="student"))
        except ValueError as exc:
            error = str(exc)
        except Exception as exc:
            db.session.rollback()
            error = "Registration failed. Please try again."

    return render_template("auth/register_student.html", error=error)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect_authenticated()

    sent = False
    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            error = "Email address is required."
        else:
            user = User.query.filter_by(email=email).first()
            if user:
                # Invalidate old tokens
                PasswordResetToken.query.filter_by(user_id=user.id, used=False).update({"used": True})
                token_obj = PasswordResetToken.generate(user.id)
                db.session.add(token_obj)
                db.session.commit()

                reset_url = url_for(
                    "auth.reset_password",
                    token=token_obj.token,
                    _external=True
                )

                mail_configured = bool(current_app.config.get("MAIL_SERVER"))
                if mail_configured:
                    try:
                        _send_reset_email(user, reset_url)
                        sent = True
                    except Exception:
                        error = "Failed to send email. Contact support."
                else:
                    # In development: log the link
                    current_app.logger.warning(
                        f"[DEV] Password reset link for {email}: {reset_url}"
                    )
                    sent = True
                    flash(
                        f"[Development mode] Reset link logged to server console. "
                        f"Configure MAIL_SERVER to send emails.",
                        "info"
                    )
            else:
                # Don't reveal whether email exists
                sent = True

    return render_template("auth/forgot_password.html", sent=sent, error=error)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect_authenticated()

    token_obj = PasswordResetToken.query.filter_by(token=token, used=False).first()
    if not token_obj or not token_obj.is_valid:
        flash("This password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            token_obj.user.set_password(password)
            token_obj.used = True
            db.session.commit()
            flash("Password reset successfully. Please log in.", "success")
            # Redirect to the appropriate login portal
            role = token_obj.user.role
            portal_key = next(
                (p["key"] for p in PORTALS if p["role"] == role),
                "student"
            )
            return redirect(url_for("auth.login", portal=portal_key))

    return render_template("auth/reset_password.html", token=token, error=error)


@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.choose_portal"))


def _send_reset_email(user, reset_url):
    """Send password reset email. Requires MAIL_SERVER to be configured."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    cfg = current_app.config
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Elite Portal — Password Reset"
    msg["From"] = cfg.get("MAIL_DEFAULT_SENDER", cfg.get("MAIL_USERNAME", ""))
    msg["To"] = user.email

    html = f"""
    <html><body>
    <p>Hi {user.name},</p>
    <p>Click the link below to reset your Elite Portal password.
       This link expires in 1 hour and can only be used once.</p>
    <p><a href="{reset_url}">Reset Password</a></p>
    <p>If you did not request this, ignore this email.</p>
    <p>— Elite Portal Team</p>
    </body></html>
    """
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"]) as smtp:
        if cfg.get("MAIL_USE_TLS"):
            smtp.starttls()
        smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        smtp.send_message(msg)
