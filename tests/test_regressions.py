"""Regression tests for endpoints that were broken after the FastAPI port."""
from fastapi.testclient import TestClient

from app.models import StudentDomainEnrollment, User
from app.database import db
from tests.helpers import assign, domain, login, make_user, seed_domains


def _coordinator_client(app):
    seed_domains()
    coord = make_user("c@test.com", "coordinator")
    assign(coord, domain("DSA"), "coordinator")
    c = TestClient(app)
    assert login(c, "c@test.com", "coordinator").status_code == 200
    return c


def test_profile_patch_applies_body(client):
    make_user("s@test.com", "student")
    login(client, "s@test.com", "student")
    res = client.patch("/api/v1/auth/profile", json={"name": "New Name", "department": "CSE", "year": 2})
    assert res.status_code == 200, res.text
    user = res.json()["data"]["user"]
    assert user["name"] == "New Name" and user["department"] == "CSE" and user["year"] == 2
    bad = client.patch("/api/v1/auth/profile", content=b"{not json", headers={"Content-Type": "application/json"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_body"


def test_duplicate_register_number_rejected(client):
    make_user("a@test.com", "student", register_number="952021104001")
    make_user("b@test.com", "student")
    login(client, "b@test.com", "student")
    res = client.patch("/api/v1/auth/profile", json={"register_number": " 952021104001 "})
    assert res.status_code == 409 and res.json()["error"]["code"] == "register_number_exists"


def test_coordinator_day_material_flow(app):
    c = _coordinator_client(app)
    dsa = domain("DSA").id
    day = c.post(f"/api/v1/coordinator/domains/{dsa}/days", json={"title": "Arrays basics"})
    assert day.status_code == 201, day.text
    day_id = day.json()["data"]["id"]

    patched = c.patch(f"/api/v1/coordinator/days/{day_id}", json={"title": "Arrays and strings"})
    assert patched.status_code == 200 and patched.json()["data"]["title"] == "Arrays and strings"

    mat = c.post(f"/api/v1/coordinator/days/{day_id}/materials",
                 json={"title": "Intro video", "material_type": "link", "url": "https://example.com/v"})
    assert mat.status_code == 201, mat.text
    listing = c.get(f"/api/v1/coordinator/days/{day_id}/materials")
    assert listing.status_code == 200
    assert [m["title"] for m in listing.json()["data"]["materials"]] == ["Intro video"]

    mat_id = mat.json()["data"]["id"]
    upd = c.patch(f"/api/v1/coordinator/materials/{mat_id}", json={"title": "Intro video v2"})
    assert upd.status_code == 200 and upd.json()["data"]["title"] == "Intro video v2"

    locked = c.post(f"/api/v1/coordinator/days/{day_id}/lock", json={"locked": True})
    assert locked.status_code == 200 and locked.json()["data"]["is_locked"] is True


def test_coordinator_students_and_progress(app):
    c = _coordinator_client(app)
    s = make_user("s@test.com", "student", register_number="R1")
    db.session.add(StudentDomainEnrollment(student_id=s.id, domain_id=domain("DSA").id, is_active=True))
    db.session.commit()

    students = c.get("/api/v1/coordinator/students")
    assert students.status_code == 200, students.text
    assert students.json()["meta"]["per_page"] == 25
    assert [x["email"] for x in students.json()["data"]] == ["s@test.com"]

    progress = c.get("/api/v1/coordinator/students/progress")
    assert progress.status_code == 200, progress.text
    assert progress.json()["data"][0]["register_number"] == "R1"

    detail = c.get(f"/api/v1/coordinator/students/{s.id}")
    assert detail.status_code == 200


def test_upload_saves_and_access_is_enforced(app, client):
    make_user("s@test.com", "student")
    make_user("other@test.com", "student")
    login(client, "s@test.com", "student")
    res = client.post("/api/v1/uploads", files={"file": ("proof.png", b"\x89PNG data", "image/png")})
    assert res.status_code == 201, res.text
    meta = res.json()["data"]
    assert meta["key"].startswith("evidence/") and meta["file_size"] == 9 and meta["storage"] == "local"

    rejected = client.post("/api/v1/uploads", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert rejected.status_code == 400 and rejected.json()["error"]["code"] == "invalid_file"
    empty = client.post("/api/v1/uploads", files={"file": ("e.png", b"", "image/png")})
    assert empty.status_code == 400

    with TestClient(app) as anon:
        assert anon.get(f"/api/v1/files/{meta['key']}").status_code == 401
        # The old public /uploads mount is gone: the raw file must not be served there.
        assert b"PNG data" not in anon.get(f"/uploads/{meta['key']}").content
    # Unattached evidence is readable by staff only (unchanged rule from the Flask API);
    # students can read it once it is linked to their own TaskEvidence record.
    make_user("admin@test.com", "admin")
    with TestClient(app) as admin:
        login(admin, "admin@test.com", "admin")
        res = admin.get(f"/api/v1/files/{meta['key']}")
        assert res.status_code == 200 and res.content == b"\x89PNG data"
    with TestClient(app) as other:
        login(other, "other@test.com", "student")
        assert other.get(f"/api/v1/files/{meta['key']}").status_code == 403


def test_storage_failure_is_not_reported_as_success(client, monkeypatch):
    from app.services import storage

    make_user("s@test.com", "student")
    login(client, "s@test.com", "student")

    def boom(*_a, **_k):
        raise storage.StorageError("The file could not be stored. Please try again.")

    monkeypatch.setattr("app.fastapi.routers.common.save_file", boom)
    res = client.post("/api/v1/uploads", files={"file": ("p.png", b"data", "image/png")})
    assert res.status_code == 503 and res.json()["error"]["code"] == "storage_unavailable"


def test_validation_errors_use_standard_envelope(client):
    seed_domains()
    make_user("s@test.com", "student")
    login(client, "s@test.com", "student")
    res = client.post("/api/v1/student/domains", json={"domain_ids": "not-a-list"})
    assert res.status_code in (400, 422)
    assert "error" in res.json() and "code" in res.json()["error"]


def test_unknown_api_route_returns_json_404(client):
    res = client.get("/api/v1/does-not-exist")
    assert res.status_code == 404 and res.json()["error"]["code"] == "not_found"


# ── Roster (Apps Script) eligibility ───────────────────────────────────────
def _enable_roster(monkeypatch, records=None, unavailable=False):
    from app.services import roster

    monkeypatch.setenv("ROSTER_APPS_SCRIPT_URL", "https://script.example/exec")

    def fake_lookup(rn):
        if unavailable:
            raise roster.RosterUnavailable("down")
        return (records or {}).get(roster.normalize_register_number(rn))

    monkeypatch.setattr("app.fastapi.routers.auth.lookup_student", fake_lookup)


ROSTER = {"952021104001": {"register_number": "952021104001", "name": "Asha K", "email": "asha@college.edu",
                           "department": "CSE"}}


def test_public_config_reports_roster_flag(client, monkeypatch):
    assert client.get("/api/v1/public/config").json()["data"]["roster_verification"] is False
    _enable_roster(monkeypatch, ROSTER)
    assert client.get("/api/v1/public/config").json()["data"]["roster_verification"] is True


def test_roster_lookup_masks_details(client, monkeypatch):
    _enable_roster(monkeypatch, ROSTER)
    res = client.post("/api/v1/auth/roster-lookup", json={"register_number": " 952021104001 "})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["name"] == "Asha K" and data["email_hint"] == "as**@college.edu" and "email" not in data


def test_register_requires_roster_membership(client, monkeypatch):
    _enable_roster(monkeypatch, ROSTER)
    base = {"name": "Someone", "password": "Password@1"}
    res = client.post("/api/v1/auth/register", json={**base, "email": "x@college.edu", "register_number": "999"})
    assert res.status_code == 403 and res.json()["error"]["code"] == "not_eligible"
    res = client.post("/api/v1/auth/register", json={**base, "email": "wrong@college.edu", "register_number": "952021104001"})
    assert res.status_code == 400 and res.json()["error"]["code"] == "email_mismatch"
    assert User.query.count() == 0

    ok = client.post("/api/v1/auth/register", json={**base, "email": "asha@college.edu", "register_number": "952021104001"})
    assert ok.status_code == 201, ok.text
    user = User.query.filter_by(email="asha@college.edu").first()
    assert user.name == "Asha K" and user.department == "CSE" and user.approval_status == "pending"

    dup = client.post("/api/v1/auth/register", json={**base, "email": "asha2@college.edu", "register_number": "952021104001"})
    assert dup.status_code == 409


def test_register_fails_closed_when_roster_unavailable(client, monkeypatch):
    _enable_roster(monkeypatch, unavailable=True)
    res = client.post("/api/v1/auth/register", json={"name": "A B", "email": "a@college.edu",
                                                     "password": "Password@1", "register_number": "952021104001"})
    assert res.status_code == 503 and res.json()["error"]["code"] == "roster_unavailable"
    assert User.query.count() == 0


def test_login_rate_limited(client, monkeypatch):
    monkeypatch.setenv("RATELIMIT_ENABLED", "true")
    from app.fastapi import ratelimit

    ratelimit._hits.clear()
    codes = [client.post("/api/v1/auth/login", json={"portal": "student", "email": "n@x.com", "password": "bad"}).status_code
             for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429
    ratelimit._hits.clear()


def test_password_hash_compat_with_existing_werkzeug_hashes():
    from app.security import check_password_hash, generate_password_hash

    # Werkzeug 3 format hashes (as stored in the existing database) still verify.
    scrypt = generate_password_hash("Admin@1234")
    assert scrypt.startswith("scrypt:32768:8:1$") and check_password_hash(scrypt, "Admin@1234")
    assert not check_password_hash(scrypt, "wrong")
    pbkdf2 = generate_password_hash("pw", method="pbkdf2:sha256:1000")
    assert check_password_hash(pbkdf2, "pw")
    assert check_password_hash("garbage", "pw") is False


def test_hashes_created_by_werkzeug_still_verify():
    werkzeug_security = __import__("pytest").importorskip("werkzeug.security")
    from app.security import check_password_hash

    for method in ("scrypt", "pbkdf2:sha256"):
        legacy = werkzeug_security.generate_password_hash("Student@1234", method=method)
        assert check_password_hash(legacy, "Student@1234"), method
        assert not check_password_hash(legacy, "nope"), method
