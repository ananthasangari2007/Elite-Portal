"""Student domain selection and role-verified login (ported from the Flask test-suite)."""
from app.models import StudentDomainEnrollment
from tests.helpers import assign, domain, login, make_user, seed_domains


def _active_ids(student_id):
    return {e.domain_id for e in StudentDomainEnrollment.query.filter_by(student_id=student_id, is_active=True).all()}


def _setup(client, email="s@test.com"):
    seed_domains()
    student = make_user(email, "student")
    assert login(client, email, "student").status_code == 200
    return student


def test_empty_selection_still_enrolls_compulsory_dsa(client):
    student = _setup(client)
    assert client.post("/api/v1/student/domains", json={"domain_ids": []}).status_code == 200
    assert domain("DSA").id in _active_ids(student.id)


def test_optional_only_payload_auto_includes_dsa(client):
    student = _setup(client)
    res = client.post("/api/v1/student/domains", json={"domain_ids": [domain("FULLSTACK").id]})
    assert res.status_code == 200
    assert _active_ids(student.id) == {domain("DSA").id, domain("FULLSTACK").id}


def test_two_optional_domains_allowed(client):
    student = _setup(client)
    ids = [domain("DSA").id, domain("FULLSTACK").id, domain("AIML").id]
    assert client.post("/api/v1/student/domains", json={"domain_ids": ids}).status_code == 200
    assert _active_ids(student.id) == set(ids)


def test_too_many_optional_domains_rejected(client):
    student = _setup(client)
    ids = [domain(c).id for c in ("DSA", "FULLSTACK", "AIML", "EMBEDDED")]
    res = client.post("/api/v1/student/domains", json={"domain_ids": ids})
    assert res.status_code == 400 and res.json()["error"]["code"] == "too_many_optional"
    assert _active_ids(student.id) == set()


def test_unknown_domain_rejected(client):
    _setup(client)
    res = client.post("/api/v1/student/domains", json={"domain_ids": [domain("DSA").id, 99999]})
    assert res.status_code == 400 and res.json()["error"]["code"] == "invalid_domains"


def test_reselection_is_idempotent(client):
    student = _setup(client)
    payload = {"domain_ids": [domain("DSA").id, domain("AIML").id]}
    for _ in range(2):
        assert client.post("/api/v1/student/domains", json=payload).status_code == 200
    assert StudentDomainEnrollment.query.filter_by(student_id=student.id).count() == 2


def test_optional_change_after_lock_is_blocked(client):
    _setup(client)
    client.post("/api/v1/student/domains", json={"domain_ids": [domain("DSA").id, domain("FULLSTACK").id]})
    res = client.post("/api/v1/student/domains", json={"domain_ids": [domain("DSA").id, domain("AIML").id]})
    assert res.status_code == 403 and res.json()["error"]["code"] == "domain_change_locked"


def test_selected_domains_persist_across_sessions(app, client):
    from fastapi.testclient import TestClient

    _setup(client)
    client.post("/api/v1/student/domains", json={"domain_ids": [domain("FULLSTACK").id]})
    with TestClient(app) as again:
        login(again, "s@test.com", "student")
        codes = {d["code"] for d in again.get("/api/v1/auth/me").json()["data"]["domains"]}
        assert codes == {"DSA", "FULLSTACK"}


def test_faculty_login_requires_faculty_assignment(client):
    seed_domains()
    fac = make_user("f@test.com", "faculty")
    assign(fac, domain("FULLSTACK"), "faculty")
    res = login(client, "f@test.com", "faculty")
    assert res.status_code == 200 and res.json()["data"]["user"]["role"] == "faculty"


def test_student_domains_requires_authentication(client):
    assert client.get("/api/v1/student/domains").status_code == 401
