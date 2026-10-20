"""
Elite Portal — Application Factory
Francis Xavier Engineering College | Elite Batch 2025-2029
"""
import os
from pathlib import Path

import click
from flask import Flask, jsonify, redirect, request, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.choose_portal"
    csrf.init_app(app)
    limiter.init_app(app)

    # ── Legacy blueprints (kept for backwards compat) ──────────────────────
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.exports import exports_bp
    from app.routes.penalties import penalties_bp
    from app.routes.profile import profile_bp
    from app.routes.students import students_bp
    from app.routes.submissions import submissions_bp
    from app.routes.support import support_bp
    from app.routes.tasks import tasks_bp
    from app.routes.elite_sprint import elite_sprint_bp

    # ── New Elite Portal blueprints ────────────────────────────────────────
    from app.routes.student import student_bp
    from app.routes.coordinator import coordinator_bp
    from app.routes.faculty import faculty_bp
    from app.routes.admin_portal import admin_portal_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(submissions_bp)
    app.register_blueprint(penalties_bp)
    app.register_blueprint(exports_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(elite_sprint_bp)

    # New role blueprints
    app.register_blueprint(student_bp)
    app.register_blueprint(coordinator_bp)
    app.register_blueprint(faculty_bp)
    app.register_blueprint(admin_portal_bp)

    # Versioned JSON API for the React SPA
    from app.api import register_api

    register_api(app)

    register_cli(app)
    register_sprint_status_guard(app)
    register_profile_guard(app)
    register_api_security(app)

    return app


def register_api_security(app):
    """CORS, CSRF and JSON error handling for the versioned API."""
    from app.api.utils import ApiError, fail, require_csrf

    csrf_exempt_paths = {
        "/api/v1/auth/login",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/register",
    }

    @app.before_request
    def api_preflight_and_csrf():
        if not request.path.startswith("/api/"):
            return None
        if request.method == "OPTIONS":
            return ("", 204)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.path not in csrf_exempt_paths:
                require_csrf()
        return None

    @app.after_request
    def api_cors(response):
        origin = request.headers.get("Origin")
        allowed = app.config.get("CORS_ORIGINS", [])
        if origin and origin in allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, X-CSRF-Token, X-Requested-With, Authorization"
            )
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
        return response

    @app.errorhandler(ApiError)
    def handle_api_error(exc):
        return fail(exc.message, exc.status, exc.code, exc.details)

    @app.errorhandler(404)
    def handle_404(exc):
        if request.path.startswith("/api/"):
            return fail("Resource not found.", 404, "not_found")
        return exc

    @app.errorhandler(405)
    def handle_405(exc):
        if request.path.startswith("/api/"):
            return fail("Method not allowed.", 405, "method_not_allowed")
        return exc

    @app.errorhandler(500)
    def handle_500(exc):
        if request.path.startswith("/api/"):
            app.logger.exception("Unhandled API error")
            return fail("An internal server error occurred.", 500, "server_error")
        return exc


def register_profile_guard(app):
    @app.before_request
    def require_student_profile():
        if request.path.startswith("/api/"):
            return None
        if not current_user.is_authenticated:
            return None
        if current_user.role != "student" or current_user.profile_completed:
            return None
        allowed_endpoints = {
            "profile.edit", "auth.logout", "static",
            "student.profile", "student.profile_save",
        }
        if request.endpoint in allowed_endpoints:
            return None
        return redirect(url_for("profile.edit"))


def register_sprint_status_guard(app):
    @app.before_request
    def close_elapsed_sprint_sessions():
        try:
            from app.services.elite_sprint import close_expired_sprints
            close_expired_sprints()
        except Exception:
            pass


def get_initial_admin_password():
    password = os.getenv("ADMIN_PASSWORD") or os.getenv("INITIAL_ADMIN_PASSWORD")
    if password:
        return password
    env = (os.getenv("FLASK_ENV") or "development").lower()
    if env in {"production", "prod", "staging"}:
        raise RuntimeError("ADMIN_PASSWORD or INITIAL_ADMIN_PASSWORD must be set in production")
    return "Admin@1234"


def seed_domains():
    """Seed the four default domains."""
    from app.models import Domain

    defaults = [
        {
            "code": "DSA",
            "name": "Data Structures & Algorithms",
            "description": "Master core DSA concepts essential for all engineering disciplines.",
            "icon": "cpu",
            "color": "#4f46e5",
            "is_compulsory": True,
        },
        {
            "code": "FULLSTACK",
            "name": "Full Stack Development",
            "description": "Build end-to-end web applications with modern frameworks.",
            "icon": "layers",
            "color": "#0891b2",
            "is_compulsory": False,
        },
        {
            "code": "AIML",
            "name": "Artificial Intelligence & Machine Learning",
            "description": "Explore AI models, ML pipelines, and intelligent systems.",
            "icon": "brain",
            "color": "#7c3aed",
            "is_compulsory": False,
        },
        {
            "code": "EMBEDDED",
            "name": "Embedded Systems & IoT",
            "description": "Program microcontrollers and build connected IoT solutions.",
            "icon": "zap",
            "color": "#059669",
            "is_compulsory": False,
        },
    ]

    for d in defaults:
        existing = Domain.query.filter_by(code=d["code"]).first()
        if existing is None:
            domain = Domain(**d, is_active=True)
            db.session.add(domain)

    db.session.commit()


def seed_admin_user():
    from app.models import User

    email = "admin@elite.edu"
    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User(
            name="System Administrator",
            email=email,
            role="admin",
            profile_completed=True,
        )
        user.set_password(get_initial_admin_password())
        db.session.add(user)

    db.session.commit()


def register_cli(app):
    @app.cli.command("seed-admin")
    def seed_admin():
        """Seed the default admin user."""
        seed_admin_user()
        click.echo("Admin user is ready.")

    @app.cli.command("seed-domains")
    def seed_domains_cmd():
        """Seed the four default learning domains."""
        seed_domains()
        click.echo("Domains seeded: DSA (compulsory), Full Stack, AI/ML, Embedded Systems.")

    @app.cli.command("seed-all")
    def seed_all():
        """Seed admin + domains."""
        seed_admin_user()
        seed_domains()
        click.echo("Admin and domains ready.")

    @app.cli.command("create-admin")
    @click.argument("email")
    @click.option("--password", default=None)
    @click.option("--name", default="Administrator")
    def create_admin(email, password, name):
        """Create an admin account: flask create-admin admin@example.com --password Secret"""
        from app.models import User

        if password is None:
            password = get_initial_admin_password()

        user = User.query.filter_by(email=email).first()
        if user:
            click.echo(f"User with email {email} already exists.")
            return
        user = User(name=name, email=email, role="admin", profile_completed=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin {email} created.")

    @app.cli.command("create-coordinator")
    @click.argument("email")
    @click.argument("domain_code")
    @click.option("--password", default=None)
    @click.option("--name", default="Domain Coordinator")
    def create_coordinator(email, domain_code, password, name):
        """Create a domain coordinator: flask create-coordinator email@x.com DSA"""
        from app.models import User, Domain, DomainAssignment

        if password is None:
            password = "Coord@1234"

        domain = Domain.query.filter_by(code=domain_code.upper()).first()
        if not domain:
            click.echo(f"Domain {domain_code} not found. Run flask seed-domains first.")
            return

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(name=name, email=email, role="coordinator", profile_completed=True)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

        assignment = DomainAssignment.query.filter_by(
            user_id=user.id, domain_id=domain.id, assignment_type="coordinator"
        ).first()
        if not assignment:
            assignment = DomainAssignment(
                domain_id=domain.id,
                user_id=user.id,
                assignment_type="coordinator",
                is_primary=True,
            )
            db.session.add(assignment)

        db.session.commit()
        click.echo(f"Coordinator {email} assigned to {domain.name}.")

    @app.cli.command("create-faculty")
    @click.argument("email")
    @click.option("--password", default=None)
    @click.option("--name", default="Faculty Coordinator")
    def create_faculty(email, password, name):
        """Create a faculty coordinator account."""
        from app.models import User

        if password is None:
            password = "Faculty@1234"

        user = User.query.filter_by(email=email).first()
        if user:
            click.echo(f"User {email} already exists.")
            return
        user = User(name=name, email=email, role="faculty", profile_completed=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Faculty {email} created.")

    @app.cli.command("reset-admin-password")
    @click.argument("email")
    @click.option("--password", default=None)
    def reset_admin_password(email, password):
        """Reset an admin password."""
        from app.models import User

        password = password or get_initial_admin_password()
        user = User.query.filter_by(email=email, role="admin").first()
        if not user:
            click.echo(f"Admin {email} was not found.")
            return
        user.set_password(password)
        db.session.commit()
        click.echo(f"Password reset for admin {email}.")

    @app.cli.command("seed-task-catalog")
    def seed_task_catalog_command():
        """Seed sample task catalog."""
        try:
            from app.models import User
            from app.services.catalog import seed_task_catalog
            admin = User.query.filter_by(role="admin").first()
            seed_task_catalog(created_by=admin.id if admin else None)
            click.echo("Task catalog is ready.")
        except Exception as e:
            click.echo(f"Catalog seed skipped: {e}")

    @app.cli.command("seed-tasks")
    def seed_tasks_command():
        """Alias for seeding the task catalog."""
        try:
            from app.services.catalog import seed_task_catalog
            from app.models import User
            admin = User.query.filter_by(role="admin").first()
            seed_task_catalog(created_by=admin.id if admin else None)
            click.echo("Task catalog is ready.")
        except Exception as e:
            click.echo(f"Catalog seed skipped: {e}")
