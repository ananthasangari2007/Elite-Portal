"""Repeatable smoke test for the Elite Portal JSON API (``/api/v1``).

Exercises the real application factory, blueprints, authentication, role-based
access control and student domain selection end to end.

Runs entirely against a throwaway SQLite database and never touches the
database configured in ``.env`` (which may be a production Postgres instance).

Usage:
    python scripts/smoke_test.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config  # noqa: E402

DB_PATH = Path(tempfile.gettempdir()) / "elite_portal_smoke.sqlite3"

PASSWORD = "Smoke@1234"


class SmokeConfig(Config):
    SECRET_KEY = "smoke-test-secret"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH.as_posix()}"
    RATELIMIT_ENABLED = False
    WTF_CSRF_ENABLED = False


def _bootstrap(app):
    from app import db, seed_domains
    from app.models import Domain, DomainAssignment, User

    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_domains()
        db.session.commit()

        dsa = Domain.query.filter_by(code="DSA").first()
        fullstack = Domain.query.filter_by(code="FULLSTACK").first()

        def make_user(email, role, **fields):
            user = User(
                name=email,
                email=email,
                role=role,
                approval_status="approved",
                profile_completed=True,
                is_active_account=True,
                **fields,
            )
            user.set_password(PASSWORD)
            db.session.add(user)
            db.session.flush()
            return user

        make_user("admin@smoke.test", "admin")
        make_user("student1@smoke.test", "student")
        make_user("student2@smoke.test", "student")
        coordinator = make_user("coordinator@smoke.test", "coordinator")
        faculty = make_user("faculty@smoke.test", "faculty")

        db.session.add_all(
            [
                DomainAssignment(
                    user_id=coordinator.id,
                    domain_id=dsa.id,
                    assignment_type="coordinator",
                    is_primary=True,
                ),
                DomainAssignment(
                    user_id=coordinator.id,
                    domain_id=fullstack.id,
                    assignment_type="coordinator",
                ),
                DomainAssignment(
                    user_id=faculty.id, domain_id=dsa.id, assignment_type="faculty"
                ),
            ]
        )
        db.session.commit()


def main():
    from app import create_app

    if DB_PATH.exists():
        DB_PATH.unlink()

    app = create_app(SmokeConfig)
    _bootstrap(app)

    client = app.test_client()
    failures = []

    def check(label, condition):
        print(("ok   - " if condition else "FAIL - ") + label)
        if not condition:
            failures.append(label)

    def login(portal, email):
        client.post("/api/v1/auth/logout")
        return client.post(
            "/api/v1/auth/login",
            json={"portal": portal, "email": email, "password": PASSWORD},
        )

    def csrf_headers():
        with client.session_transaction() as session:
            session["api_csrf"] = "smoke-csrf"
        return {"X-CSRF-Token": "smoke-csrf"}

    # ── Role logins reach their dashboards ────────────────────────────────
    for portal, email, dashboard in [
        ("student", "student1@smoke.test", "/api/v1/student/dashboard"),
        ("coordinator", "coordinator@smoke.test", "/api/v1/coordinator/dashboard"),
        ("faculty", "faculty@smoke.test", "/api/v1/faculty/dashboard"),
        ("admin", "admin@smoke.test", "/api/v1/admin/dashboard"),
    ]:
        resp = login(portal, email)
        check(f"{portal} login", resp.status_code == 200)
        check(f"{portal} dashboard", client.get(dashboard).status_code == 200)

    # ── Role-based access control ─────────────────────────────────────────
    login("student", "student1@smoke.test")
    check(
        "student blocked from admin dashboard",
        client.get("/api/v1/admin/dashboard").status_code == 403,
    )

    # ── Student domain selection (compulsory DSA is always included) ──────
    login("student", "student1@smoke.test")
    resp = client.post(
        "/api/v1/student/domains", json={"domain_ids": []}, headers=csrf_headers()
    )
    check("empty domain selection saves", resp.status_code == 200)

    with app.app_context():
        from app.models import Domain, StudentDomainEnrollment, User

        student = User.query.filter_by(email="student1@smoke.test").first()
        dsa_id = Domain.query.filter_by(code="DSA").first().id
        enrolled = {
            e.domain_id
            for e in StudentDomainEnrollment.query.filter_by(
                student_id=student.id, is_active=True
            ).all()
        }
        check("compulsory DSA auto-enrolled", enrolled == {dsa_id})

    # A fresh student selecting only an optional domain still gets DSA.
    login("student", "student2@smoke.test")
    with app.app_context():
        from app.models import Domain

        fullstack_id = Domain.query.filter_by(code="FULLSTACK").first().id
    resp = client.post(
        "/api/v1/student/domains",
        json={"domain_ids": [fullstack_id]},
        headers=csrf_headers(),
    )
    check("optional-only selection saves", resp.status_code == 200)

    with app.app_context():
        from app.models import Domain, StudentDomainEnrollment, User

        student = User.query.filter_by(email="student2@smoke.test").first()
        dsa_id = Domain.query.filter_by(code="DSA").first().id
        enrolled = {
            e.domain_id
            for e in StudentDomainEnrollment.query.filter_by(
                student_id=student.id, is_active=True
            ).all()
        }
        check("DSA included with optional choice", enrolled == {dsa_id, fullstack_id})

    print()
    if failures:
        print(f"SMOKE TEST FAILED ({len(failures)} check(s)): {', '.join(failures)}")
        sys.exit(1)
    print("api-smoke-ok")


if __name__ == "__main__":
    main()
