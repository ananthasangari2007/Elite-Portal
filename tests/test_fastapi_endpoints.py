"""
FastAPI Endpoints Test Suite
Validates health, authentication, role enforcement, and session/Bearer token flows.
"""
import pytest
from fastapi.testclient import TestClient

from app.fastapi.app import create_app
from app.fastapi.database import db, engine
import app.models as models
from app.models import Domain, User


@pytest.fixture(scope="module")
def app():
    # Create all tables on the SQLite test engine
    db.Model.metadata.create_all(bind=engine)
    return create_app()


@pytest.fixture(scope="module")
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def setup_test_users():
    """Ensure test users and default domain exist in test SQLite database."""
    db.Model.metadata.create_all(bind=engine)
    db.session.rollback()

    admin = User.query.filter_by(email="admin@fxec.ac.in").first()
    if not admin:
        admin = User(
            name="System Admin",
            email="admin@fxec.ac.in",
            role="admin",
            approval_status="approved",
            is_active_account=True,
            profile_completed=True,
        )
        admin.set_password("Admin@1234")
        db.session.add(admin)

    student = User.query.filter_by(email="student@fxec.ac.in").first()
    if not student:
        student = User(
            name="Test Student",
            email="student@fxec.ac.in",
            role="student",
            register_number="952021104001",
            approval_status="approved",
            is_active_account=True,
            profile_completed=True,
        )
        student.set_password("Student@1234")
        db.session.add(student)

    dsa_domain = Domain.query.filter_by(code="DSA").first()
    if not dsa_domain:
        dsa_domain = Domain(
            code="DSA",
            name="Data Structures & Algorithms",
            description="Compulsory DSA domain",
            is_compulsory=True,
            is_active=True,
        )
        db.session.add(dsa_domain)

    db.session.commit()
    yield
    db.session.rollback()


def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["framework"] == "FastAPI"

    res_v1 = client.get("/api/v1/health")
    assert res_v1.status_code == 200
    assert res_v1.json()["status"] == "ok"


def test_csrf_token_endpoint(client):
    res = client.get("/api/v1/auth/csrf")
    assert res.status_code == 200
    body = res.json()
    assert "data" in body
    assert "csrf_token" in body["data"]
    assert len(body["data"]["csrf_token"]) > 10


def test_unauthenticated_auth_me(client):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    body = res.json()
    assert "error" in body
    assert body["error"]["code"] in ("unauthenticated", "unauthorized")


def test_login_invalid_credentials(client):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "student@fxec.ac.in", "password": "WrongPassword123", "portal": "student"},
    )
    assert res.status_code == 401
    body = res.json()
    assert body["error"]["code"] == "invalid_credentials"


def test_login_and_auth_me_cookie_and_bearer(app, client):
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "student@fxec.ac.in", "password": "Student@1234", "portal": "student"},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()["data"]
    assert login_data["user"]["email"] == "student@fxec.ac.in"
    assert "token" in login_data
    token = login_data["token"]

    # Test /auth/me with Cookie session
    me_cookie = client.get("/api/v1/auth/me")
    assert me_cookie.status_code == 200
    assert me_cookie.json()["data"]["user"]["email"] == "student@fxec.ac.in"

    # Test /auth/me with Bearer token using a fresh client without cookies
    with TestClient(app) as alt_client:
        me_bearer = alt_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_bearer.status_code == 200
        assert me_bearer.json()["data"]["user"]["email"] == "student@fxec.ac.in"


def test_role_enforcement(client):
    # Student login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "student@fxec.ac.in", "password": "Student@1234", "portal": "student"},
    )
    assert login_res.status_code == 200

    # Student cannot access admin dashboard -> 403 Forbidden
    admin_dash = client.get("/api/v1/admin/dashboard")
    assert admin_dash.status_code == 403
    assert admin_dash.json()["error"]["code"] == "forbidden"

    # Now login as Admin
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@fxec.ac.in", "password": "Admin@1234", "portal": "admin"},
    )
    assert admin_login.status_code == 200

    # Admin CAN access admin dashboard -> 200 OK
    admin_dash_ok = client.get("/api/v1/admin/dashboard")
    assert admin_dash_ok.status_code == 200
    assert "data" in admin_dash_ok.json()


def test_student_domains_list(client):
    client.post(
        "/api/v1/auth/login",
        json={"email": "student@fxec.ac.in", "password": "Student@1234", "portal": "student"},
    )
    res = client.get("/api/v1/student/domains")
    assert res.status_code == 200
    domains = res.json()["data"]
    assert isinstance(domains, dict)
    assert any(d["code"] == "DSA" for d in domains["available"])


def test_logout_clears_session(client):
    client.post(
        "/api/v1/auth/login",
        json={"email": "student@fxec.ac.in", "password": "Student@1234", "portal": "student"},
    )
    logout_res = client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200

    # After logout, /auth/me returns 401
    me_after = client.get("/api/v1/auth/me")
    assert me_after.status_code == 401


def test_resilient_login_after_stale_session(client):
    # Perform login
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "student@fxec.ac.in", "password": "Student@1234", "portal": "student"},
    )
    assert res.status_code == 200

    # Subsequent login with wrong password returns 401 (never 500)
    res_bad = client.post(
        "/api/v1/auth/login",
        json={"email": "student@fxec.ac.in", "password": "WrongPassword", "portal": "student"},
    )
    assert res_bad.status_code == 401
    assert res_bad.json()["error"]["code"] == "invalid_credentials"

    # Another login with correct credentials still succeeds (clean session)
    res_retry = client.post(
        "/api/v1/auth/login",
        json={"email": "student@fxec.ac.in", "password": "Student@1234", "portal": "student"},
    )
    assert res_retry.status_code == 200
