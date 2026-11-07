"""Authentication lifecycle, CSRF and RBAC tests against the FastAPI app."""
from fastapi.testclient import TestClient

from app.database import db
from app.fastapi.auth import create_session_token
from tests.helpers import PASSWORD, assign, domain, login, make_user, seed_domains


def test_health_and_ready(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok" and body["database"] == "ok" and body["framework"] == "FastAPI"
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/ready").json() == {"status": "ready"}
    assert client.get("/api/v1/ready").status_code == 200


def test_security_headers_present(client):
    res = client.get("/api/v1/auth/csrf")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Cache-Control"] == "no-store"


def test_me_unauthenticated_returns_401_json(client):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthenticated"


def test_login_cookie_and_bearer_session(app, client):
    make_user("s@test.com", "student")
    res = login(client, "s@test.com", "student")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["user"]["email"] == "s@test.com"
    assert data["token"] and data["csrf_token"] and data["redirect"] == "/student"
    assert "password_hash" not in data["user"]

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["csrf_token"] == data["csrf_token"]

    with TestClient(app) as bearer_client:
        me_bearer = bearer_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {data['token']}"})
        assert me_bearer.status_code == 200


def test_stale_bearer_token_does_not_mask_valid_cookie(client):
    """Root cause of repeated /auth/me 401s: an old localStorage token overrode a valid cookie."""
    make_user("s@test.com", "student")
    login(client, "s@test.com", "student")
    res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer stale.invalid.token"})
    assert res.status_code == 200
    res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer null"})
    assert res.status_code == 200


def test_remember_me_token_outlives_default_session(client, monkeypatch):
    import app.fastapi.auth as auth_mod

    user = make_user("s@test.com", "student")
    remembered = create_session_token(user.id, "csrf", remember=True)
    normal = create_session_token(user.id, "csrf", remember=False)
    monkeypatch.setattr(auth_mod, "SESSION_LIFETIME", -1)  # simulate 8h having elapsed
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {normal}"}).status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {remembered}"}).status_code == 200


def test_tampered_token_rejected(client):
    user = make_user("s@test.com", "student")
    token = create_session_token(user.id, "csrf")
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token[:-2]}xx"})
    assert res.status_code == 401


def test_deactivated_user_session_is_rejected(client):
    user = make_user("s@test.com", "student")
    login(client, "s@test.com", "student")
    user.is_active_account = False
    db.session.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_clears_session(client):
    make_user("s@test.com", "student")
    login(client, "s@test.com", "student")
    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 200 and res.json()["data"]["csrf_token"]
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_failures(client):
    make_user("s@test.com", "student")
    bad = client.post("/api/v1/auth/login", json={"portal": "student", "email": "s@test.com", "password": "nope"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "invalid_credentials"
    unknown = client.post("/api/v1/auth/login", json={"portal": "student", "email": "x@test.com", "password": PASSWORD})
    assert unknown.status_code == 401 and unknown.json()["error"]["code"] == "invalid_credentials"
    wrong_portal = login(client, "s@test.com", "coordinator")
    assert wrong_portal.status_code == 403 and wrong_portal.json()["error"]["code"] == "role_mismatch"
    missing = client.post("/api/v1/auth/login", json={"portal": "student"})
    assert missing.status_code == 400


def test_login_rejects_inactive_and_pending(client):
    make_user("inactive@test.com", "student", is_active_account=False)
    make_user("pending@test.com", "student", approval_status="pending")
    assert login(client, "inactive@test.com", "student").json()["error"]["code"] == "account_inactive"
    assert login(client, "pending@test.com", "student").json()["error"]["code"] == "pending_approval"


def test_coordinator_requires_domain_assignment(client):
    seed_domains()
    make_user("c1@test.com", "coordinator")
    res = login(client, "c1@test.com", "coordinator")
    assert res.status_code == 403 and res.json()["error"]["code"] == "no_domain_assignment"
    c2 = make_user("c2@test.com", "coordinator")
    assign(c2, domain("DSA"), "coordinator")
    assert login(client, "c2@test.com", "coordinator").status_code == 200


# ── CSRF ──────────────────────────────────────────────────────────────────
def test_mutation_without_csrf_rejected(client):
    seed_domains()
    make_user("s@test.com", "student")
    login(client, "s@test.com", "student")
    del client.headers["X-CSRF-Token"]
    res = client.post("/api/v1/student/domains", json={"domain_ids": []})
    assert res.status_code == 403 and res.json()["error"]["code"] == "csrf_failed"
    res = client.post("/api/v1/student/domains", json={"domain_ids": []}, headers={"X-CSRF-Token": "forged"})
    assert res.status_code == 403


def test_mutation_with_login_csrf_accepted(client):
    seed_domains()
    make_user("s@test.com", "student")
    login(client, "s@test.com", "student")
    assert client.post("/api/v1/student/domains", json={"domain_ids": []}).status_code == 200


def test_bearer_client_csrf_works(app):
    seed_domains()
    make_user("s@test.com", "student")
    with TestClient(app) as c:
        data = c.post("/api/v1/auth/login", json={"portal": "student", "email": "s@test.com", "password": PASSWORD}).json()["data"]
    with TestClient(app) as bearer:
        headers = {"Authorization": f"Bearer {data['token']}", "X-CSRF-Token": data["csrf_token"]}
        assert bearer.post("/api/v1/student/domains", json={"domain_ids": []}, headers=headers).status_code == 200


def test_anonymous_csrf_for_registration_avatar(client):
    token = client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]
    files = {"file": ("a.png", b"\x89PNG\r\n\x1a\nfake", "image/png")}
    assert client.post("/api/v1/auth/upload-avatar", files=files).status_code == 403
    res = client.post("/api/v1/auth/upload-avatar", files=files, headers={"X-CSRF-Token": token})
    assert res.status_code == 201, res.text


# ── RBAC ──────────────────────────────────────────────────────────────────
def test_role_matrix(app):
    seed_domains()
    make_user("s@test.com", "student")
    make_user("a@test.com", "admin")
    coord = make_user("c@test.com", "coordinator")
    assign(coord, domain("DSA"), "coordinator")
    fac = make_user("f@test.com", "faculty")
    assign(fac, domain("DSA"), "faculty")

    matrix = {
        ("s@test.com", "student"): {"/api/v1/student/dashboard": 200, "/api/v1/admin/dashboard": 403,
                                    "/api/v1/coordinator/dashboard": 403, "/api/v1/faculty/dashboard": 403},
        ("c@test.com", "coordinator"): {"/api/v1/coordinator/dashboard": 200, "/api/v1/admin/users": 403,
                                        "/api/v1/student/dashboard": 403},
        ("f@test.com", "faculty"): {"/api/v1/faculty/dashboard": 200, "/api/v1/admin/dashboard": 403,
                                    "/api/v1/coordinator/domains": 403},
        ("a@test.com", "admin"): {"/api/v1/admin/dashboard": 200, "/api/v1/admin/users": 200,
                                  "/api/v1/admin/audit-logs": 200, "/api/v1/student/dashboard": 403},
    }
    for (email, portal), expectations in matrix.items():
        with TestClient(app) as c:
            assert login(c, email, portal).status_code == 200
            for path, status in expectations.items():
                res = c.get(path)
                assert res.status_code == status, f"{email} {path} -> {res.status_code}: {res.text[:200]}"


def test_protected_routes_require_auth(client):
    for path in ("/api/v1/student/dashboard", "/api/v1/admin/users", "/api/v1/coordinator/students",
                 "/api/v1/faculty/dashboard", "/api/v1/notifications"):
        assert client.get(path).status_code == 401, path


def test_coordinator_cannot_manage_other_domain(app):
    seed_domains()
    coord = make_user("c@test.com", "coordinator")
    assign(coord, domain("DSA"), "coordinator")
    other = domain("AIML").id
    with TestClient(app) as c:
        login(c, "c@test.com", "coordinator")
        assert c.get(f"/api/v1/coordinator/domains/{other}/days").status_code == 403
        assert c.post(f"/api/v1/coordinator/domains/{other}/days", json={"title": "Intro day"}).status_code == 403
        assert c.get(f"/api/v1/coordinator/domains/{domain('DSA').id}/days").status_code == 200
