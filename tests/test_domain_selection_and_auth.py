"""Tests for student domain selection and role-verified login / RBAC."""
import pytest

from app import create_app, db
from app.models import Domain, DomainAssignment, StudentDomainEnrollment, User

CSRF_TOKEN = "test-csrf-token"
PASSWORD = "secret123"

DOMAIN_DEFAULTS = [
    ("DSA", "Data Structures & Algorithms", True),
    ("FULLSTACK", "Full Stack Development", False),
    ("AIML", "AI & Machine Learning", False),
    ("EMBEDDED", "Embedded Systems & IoT", False),
]


@pytest.fixture()
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False,
        MAX_OPTIONAL_DOMAINS=2,
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
        for code, name, compulsory in DOMAIN_DEFAULTS:
            db.session.add(
                Domain(code=code, name=name, is_compulsory=compulsory, is_active=True)
            )
        db.session.commit()
        yield app
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


def _domain(code):
    return Domain.query.filter_by(code=code).first()


def _make_user(email, role, **fields):
    user = User(
        name=email,
        email=email,
        role=role,
        approval_status="approved",
        profile_completed=True,
        **fields,
    )
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


def _assign(user, domain, assignment_type):
    db.session.add(
        DomainAssignment(
            user_id=user.id, domain_id=domain.id, assignment_type=assignment_type
        )
    )
    db.session.commit()


def _login(client, email, portal):
    return client.post(
        "/api/v1/auth/login",
        json={"portal": portal, "email": email, "password": PASSWORD},
    )


def _csrf_headers(client):
    with client.session_transaction() as sess:
        sess["api_csrf"] = CSRF_TOKEN
    return {"X-CSRF-Token": CSRF_TOKEN}


def _active_enrollment_ids(student_id):
    return {
        e.domain_id
        for e in StudentDomainEnrollment.query.filter_by(
            student_id=student_id, is_active=True
        ).all()
    }


# ── Issue 1: student domain selection ─────────────────────────────────────
def test_empty_selection_still_enrolls_compulsory_dsa(app, client):
    student = _make_user("s1@test.com", "student")
    assert _login(client, "s1@test.com", "student").status_code == 200

    resp = client.post(
        "/api/v1/student/domains", json={"domain_ids": []}, headers=_csrf_headers(client)
    )
    assert resp.status_code == 200

    enrolled = _active_enrollment_ids(student.id)
    assert _domain("DSA").id in enrolled


def test_optional_only_payload_auto_includes_dsa(app, client):
    student = _make_user("s2@test.com", "student")
    assert _login(client, "s2@test.com", "student").status_code == 200

    resp = client.post(
        "/api/v1/student/domains",
        json={"domain_ids": [_domain("FULLSTACK").id]},
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 200

    enrolled = _active_enrollment_ids(student.id)
    assert enrolled == {_domain("DSA").id, _domain("FULLSTACK").id}


def test_too_many_optional_domains_rejected(app, client):
    student = _make_user("s3@test.com", "student")
    assert _login(client, "s3@test.com", "student").status_code == 200

    resp = client.post(
        "/api/v1/student/domains",
        json={
            "domain_ids": [
                _domain("DSA").id,
                _domain("FULLSTACK").id,
                _domain("AIML").id,
                _domain("EMBEDDED").id,
            ]
        },
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "too_many_optional"
    # No partial enrollment should have been written.
    assert _active_enrollment_ids(student.id) == set()


def test_unknown_domain_rejected(app, client):
    student = _make_user("s4@test.com", "student")
    assert _login(client, "s4@test.com", "student").status_code == 200

    resp = client.post(
        "/api/v1/student/domains",
        json={"domain_ids": [_domain("DSA").id, 99999]},
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "invalid_domains"


def test_reselection_is_idempotent(app, client):
    student = _make_user("s5@test.com", "student")
    assert _login(client, "s5@test.com", "student").status_code == 200
    payload = {"domain_ids": [_domain("DSA").id, _domain("AIML").id]}

    for _ in range(2):
        resp = client.post(
            "/api/v1/student/domains", json=payload, headers=_csrf_headers(client)
        )
        assert resp.status_code == 200

    rows = StudentDomainEnrollment.query.filter_by(student_id=student.id).all()
    assert len(rows) == 2
    assert _active_enrollment_ids(student.id) == {
        _domain("DSA").id,
        _domain("AIML").id,
    }


def test_optional_change_after_lock_is_blocked(app, client):
    student = _make_user("s6@test.com", "student")
    assert _login(client, "s6@test.com", "student").status_code == 200
    client.post(
        "/api/v1/student/domains",
        json={"domain_ids": [_domain("DSA").id, _domain("FULLSTACK").id]},
        headers=_csrf_headers(client),
    )

    resp = client.post(
        "/api/v1/student/domains",
        json={"domain_ids": [_domain("DSA").id, _domain("AIML").id]},
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "domain_change_locked"


# ── Issues 2/3/5: login verification and RBAC ─────────────────────────────
def test_login_rejects_wrong_portal(app, client):
    _make_user("student2@test.com", "student")
    resp = _login(client, "student2@test.com", "coordinator")
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "role_mismatch"


def test_login_rejects_bad_password(app, client):
    _make_user("student3@test.com", "student")
    resp = client.post(
        "/api/v1/auth/login",
        json={"portal": "student", "email": "student3@test.com", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "invalid_credentials"


def test_login_rejects_inactive_account(app, client):
    user = _make_user("student4@test.com", "student")
    user.is_active_account = False
    db.session.commit()

    resp = _login(client, "student4@test.com", "student")
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "account_inactive"


def test_coordinator_without_assignment_is_blocked(app, client):
    _make_user("coord1@test.com", "coordinator")
    resp = _login(client, "coord1@test.com", "coordinator")
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "no_domain_assignment"


def test_coordinator_with_assignment_logs_in(app, client):
    coordinator = _make_user("coord2@test.com", "coordinator")
    _assign(coordinator, _domain("DSA"), "coordinator")

    resp = _login(client, "coord2@test.com", "coordinator")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["user"]["role"] == "coordinator"

    # Session persists across requests.
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.get_json()["data"]["user"]["email"] == "coord2@test.com"


def test_faculty_login_requires_faculty_assignment(app, client):
    faculty = _make_user("fac1@test.com", "faculty")
    _assign(faculty, _domain("FULLSTACK"), "faculty")
    resp = _login(client, "fac1@test.com", "faculty")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["user"]["role"] == "faculty"


def test_rbac_blocks_cross_role_access(app, client):
    student = _make_user("rbac-student@test.com", "student")
    _login(client, "rbac-student@test.com", "student")
    assert client.get("/api/v1/student/domains").status_code == 200

    coordinator = _make_user("rbac-coord@test.com", "coordinator")
    _assign(coordinator, _domain("DSA"), "coordinator")
    _login(client, "rbac-coord@test.com", "coordinator")
    assert client.get("/api/v1/student/domains").status_code == 403


def test_student_domains_requires_authentication(client):
    assert client.get("/api/v1/student/domains").status_code == 401
