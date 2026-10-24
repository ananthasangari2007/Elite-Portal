"""Tests verifying end-to-end CSRF protection on API endpoints."""
import pytest

from app import create_app, db
from app.models import Domain, User

PASSWORD = "Password@1234"


@pytest.fixture()
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,  # Disables legacy Jinja WTF CSRF so API CSRF is tested
        RATELIMIT_ENABLED=False,
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
        # Seed test domain
        d = Domain(code="DSA", name="Data Structures", is_compulsory=True, is_active=True)
        db.session.add(d)

        # Seed test user
        student = User(
            name="CSRF Tester",
            email="csrftester@elite.edu",
            role="student",
            approval_status="approved",
            profile_completed=True,
        )
        student.set_password(PASSWORD)
        db.session.add(student)
        db.session.commit()

        yield app
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_csrf_token_endpoint(client):
    """GET /api/v1/auth/csrf returns a valid CSRF token."""
    res = client.get("/api/v1/auth/csrf")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert "csrf_token" in data
    assert len(data["csrf_token"]) > 20


def test_mutating_request_without_csrf_is_rejected(client):
    """Mutating request without X-CSRF-Token returns 403 csrf_failed."""
    # First sign in (login is exempt)
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "csrftester@elite.edu", "password": PASSWORD, "portal": "student"},
    )
    assert login_res.status_code == 200

    # Try mutating request without X-CSRF-Token
    res = client.post("/api/v1/student/domains", json={"domain_ids": []})
    assert res.status_code == 403
    payload = res.get_json()
    assert payload["error"]["code"] == "csrf_failed"
    assert "CSRF token" in payload["error"]["message"]


def test_mutating_request_with_invalid_csrf_is_rejected(client):
    """Mutating request with invalid X-CSRF-Token returns 403 csrf_failed."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "csrftester@elite.edu", "password": PASSWORD, "portal": "student"},
    )
    assert login_res.status_code == 200

    res = client.post(
        "/api/v1/student/domains",
        json={"domain_ids": []},
        headers={"X-CSRF-Token": "invalid-token-value"},
    )
    assert res.status_code == 403
    payload = res.get_json()
    assert payload["error"]["code"] == "csrf_failed"


def test_login_returns_csrf_token_and_validates_mutating_request(client):
    """Login returns a csrf_token which can be used to make mutating requests."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "csrftester@elite.edu", "password": PASSWORD, "portal": "student"},
    )
    assert login_res.status_code == 200
    token = login_res.get_json()["data"]["csrf_token"]
    assert token

    # Use the token for a mutating request
    res = client.post(
        "/api/v1/student/domains",
        json={"domain_ids": []},
        headers={"X-CSRF-Token": token},
    )
    assert res.status_code == 200


def test_logout_is_exempt_from_csrf_and_rotates_token(client):
    """Logout succeeds without CSRF header and provides a new anonymous token."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "csrftester@elite.edu", "password": PASSWORD, "portal": "student"},
    )
    assert login_res.status_code == 200

    # Logout without CSRF header succeeds
    logout_res = client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200
    logout_data = logout_res.get_json()["data"]
    assert "csrf_token" in logout_data
    assert logout_data["csrf_token"]


def test_me_returns_csrf_token(client):
    """GET /api/v1/auth/me returns the active session csrf_token."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "csrftester@elite.edu", "password": PASSWORD, "portal": "student"},
    )
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    data = me_res.get_json()["data"]
    assert "csrf_token" in data
    assert data["csrf_token"]
