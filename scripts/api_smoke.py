"""End-to-end API smoke test for the Elite Portal.

Runs against the configured database using the Flask test client.
Usage: python scripts/api_smoke.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402

PASSED = []
FAILED = []


def check(label, condition, extra=""):
    if condition:
        PASSED.append(label)
        print(f"  PASS  {label}")
    else:
        FAILED.append(f"{label} {extra}")
        print(f"  FAIL  {label} {extra}")


class Client:
    def __init__(self, app):
        self.client = app.test_client()
        token = self.client.get("/api/v1/auth/csrf").get_json()["data"]["csrf_token"]
        self.headers = {"X-CSRF-Token": token}

    def req(self, method, path, **kwargs):
        kwargs.setdefault("headers", {}).update(self.headers)
        return getattr(self.client, method)(path, **kwargs)

    def login(self, email, password, portal):
        return self.req("post", "/api/v1/auth/login", json={"email": email, "password": password, "portal": portal})

    def logout(self):
        return self.req("post", "/api/v1/auth/logout")


def main():
    app = create_app()
    app.config["WTF_CSRF_ENABLED"] = False

    print("\n== Public config ==")
    public = app.test_client()
    cfg = public.get("/api/v1/public/config").get_json()["data"]
    order = [o["key"] for o in cfg["login_options"]]
    check("login order is student, coordinator, faculty, admin", order == ["student", "coordinator", "faculty", "admin"], order)

    print("\n== Auth & role checks ==")
    anon = Client(app)
    r = anon.req("get", "/api/v1/student/dashboard")
    check("anonymous cannot access student dashboard", r.status_code == 401, r.status_code)

    mismatch = Client(app)
    r = mismatch.login("admin@elite.edu", "Admin@1234", "student")
    check("role mismatch is rejected", r.status_code == 403 and r.get_json()["error"]["code"] == "role_mismatch", r.status_code)

    bad = Client(app)
    r = bad.login("admin@elite.edu", "wrongpass", "admin")
    check("wrong password rejected", r.status_code == 401, r.status_code)

    print("\n== Student flow ==")
    student = Client(app)
    r = student.login("aarthi@elite.edu", "Elite@1234", "student")
    check("student login succeeds", r.status_code == 200, r.get_json())
    r = student.req("get", "/api/v1/student/dashboard")
    dash = r.get_json()["data"]
    check("student dashboard returns metrics", "total_points" in dash and "progress" in dash)
    check("student dashboard has progress for DSA", any(p["code"] == "DSA" for p in dash["progress"]))

    r = student.req("get", "/api/v1/student/domains")
    domains = r.get_json()["data"]
    check("student domain list loads", r.status_code == 200)
    dsa_id = next(d["id"] for d in domains["enrolled"] + domains["available"] if d["code"] == "DSA")

    # Optional domain limit enforcement
    r = student.req("post", "/api/v1/student/domains", json={"domain_ids": [d["id"] for d in domains["enrolled"] + domains["available"]]})
    check("exceeding optional domain limit is rejected", r.status_code == 400 and r.get_json()["error"]["code"] == "too_many_optional", r.status_code)

    r = student.req("get", f"/api/v1/student/domains/{dsa_id}/learning-path")
    path = r.get_json()["data"]
    check("learning path loads with days", r.status_code == 200 and len(path["days"]) >= 1, r.status_code)
    day_id = path["days"][0]["id"]

    r = student.req("get", f"/api/v1/learning-days/{day_id}")
    check("learning day detail loads with materials", r.status_code == 200 and len(r.get_json()["data"]["materials"]) >= 1)
    r = student.req("post", f"/api/v1/learning-days/{day_id}/complete")
    check("learning day completion works", r.status_code == 200, r.get_json())
    r2 = student.req("post", f"/api/v1/learning-days/{day_id}/complete")
    check("duplicate completion is idempotent", r2.status_code == 200 and r2.get_json()["data"]["already_completed"] is True)

    r = student.req("get", "/api/v1/student/materials?type=video")
    check("materials filter by type works", r.status_code == 200)

    r = student.req("get", "/api/v1/student/assessments")
    assessments = r.get_json()["data"]
    mcq = next(a for a in assessments if a["assessment_type"] == "mcq")
    check("assessments list includes MCQ", r.status_code == 200 and mcq is not None)

    r = student.req("get", f"/api/v1/assessments/{mcq['id']}/instructions")
    check("assessment instructions load", r.status_code == 200)

    r = student.req("post", f"/api/v1/assessments/{mcq['id']}/start")
    if r.status_code in (200, 201):
        attempt = r.get_json()["data"]
        check("assessment attempt starts", attempt["questions"], r.get_json())
        attempt_id = attempt["attempt"]["id"]
        q = attempt["questions"][0]
        correct_option = q["options"][0]["id"]
        r = student.req("patch", f"/api/v1/attempts/{attempt_id}/answers", json={"question_id": q["id"], "selected_option_id": correct_option})
        check("answer autosave works", r.status_code == 200, r.get_json())
        r = student.req("post", f"/api/v1/attempts/{attempt_id}/submit")
        check("assessment submits and grades", r.status_code == 200 and r.get_json()["data"]["attempt"]["status"] in ("graded", "submitted"), r.get_json())
        r = student.req("get", f"/api/v1/attempts/{attempt_id}/result")
        check("assessment result is readable", r.status_code == 200, r.get_json())
        check("attempt payload does not leak is_correct", all("is_correct" not in o for o in q["options"]))
    else:
        check("max attempts correctly enforced", r.status_code == 403 and r.get_json()["error"]["code"] == "no_attempts_left", r.get_json())
        r_inst = student.req("get", f"/api/v1/assessments/{mcq['id']}/instructions")
        completed_result = r_inst.get_json()["data"].get("latest_result")
        if completed_result:
            r = student.req("get", f"/api/v1/attempts/{completed_result['id']}/result")
            check("assessment result is readable", r.status_code == 200, r.get_json())

    r = student.req("get", "/api/v1/student/tasks")
    tasks = r.get_json()["data"]["tasks"]
    check("elite tasks list loads", r.status_code == 200 and len(tasks) >= 1)
    available = next((t for t in tasks if t["state"] == "available"), None)
    if available is not None:
        r = student.req("post", f"/api/v1/student/tasks/{available['id']}/submit", json={"evidence_type": "link", "link_url": "https://github.com/example/solution", "notes": "Done"})
        check("first daily task submission succeeds", r.status_code == 201, r.get_json())
        r = student.req("post", f"/api/v1/student/tasks/{available['id']}/submit", json={"evidence_type": "link", "link_url": "https://github.com/example/again"})
        check("second daily task submission is blocked", r.status_code == 409 and r.get_json()["error"]["code"] == "daily_limit", r.status_code)
    else:
        any_task = tasks[0]
        r = student.req("post", f"/api/v1/student/tasks/{any_task['id']}/submit", json={"evidence_type": "link", "link_url": "https://github.com/example/again"})
        check("daily task submission honors daily limit or state", r.status_code in (400, 409), r.status_code)

    r = student.req("get", "/api/v1/student/points")
    check("point history loads", r.status_code == 200 and "summary" in r.get_json()["data"])
    r = student.req("get", "/api/v1/leaderboards?scope=overall")
    check("overall leaderboard loads", r.status_code == 200 and len(r.get_json()["data"]["entries"]) >= 1)

    r = student.req("post", "/api/v1/student/requests", json={"category": "general", "subject": "Test request", "message": "Hello faculty, this is a test."})
    check("student can create a request", r.status_code == 201, r.get_json())
    request_id = r.get_json()["data"]["id"]

    print("\n== Coordinator flow ==")
    coord = Client(app)
    r = coord.login("coordinator@elite.edu", "Elite@1234", "coordinator")
    check("coordinator login succeeds", r.status_code == 200, r.get_json())
    r = coord.req("get", "/api/v1/coordinator/dashboard")
    check("coordinator dashboard loads", r.status_code == 200 and "enrolled_students" in r.get_json()["data"])

    r = coord.req("get", "/api/v1/coordinator/domains")
    cdomains = r.get_json()["data"]
    check("coordinator sees assigned domains only", all(d["code"] in ("DSA",) or d["code"] == "DSA" for d in cdomains), cdomains)
    cdsa = next(d for d in cdomains if d["code"] == "DSA")

    r = coord.req("post", f"/api/v1/coordinator/domains/{cdsa['id']}/days", json={"title": "Sliding Window Deep Dive", "description": "Advanced window problems"})
    check("coordinator creates a learning day", r.status_code == 201, r.get_json())
    new_day = r.get_json()["data"]["id"]
    r = coord.req("post", f"/api/v1/coordinator/days/{new_day}/materials", json={"title": "Window Notes", "material_type": "link", "url": "https://example.com/notes"})
    check("coordinator adds a material", r.status_code == 201, r.get_json())
    r = coord.req("post", f"/api/v1/coordinator/days/{new_day}/publish")
    check("coordinator publishes the day", r.status_code == 200, r.get_json())

    r = coord.req("get", "/api/v1/coordinator/submissions?status=submitted")
    check("coordinator submissions list loads", r.status_code == 200)

    print("\n== Faculty flow ==")
    fac = Client(app)
    r = fac.login("faculty@elite.edu", "Elite@1234", "faculty")
    check("faculty login succeeds", r.status_code == 200, r.get_json())
    r = fac.req("get", "/api/v1/faculty/dashboard")
    check("faculty dashboard loads", r.status_code == 200 and "total_students" in r.get_json()["data"])

    r = fac.req("get", "/api/v1/faculty/task-evidence?status=pending")
    evidence = r.get_json()["data"]
    check("faculty sees pending task evidence endpoint", r.status_code == 200)
    if evidence:
        ev_id = evidence[0]["id"]
        r = fac.req("post", f"/api/v1/faculty/task-evidence/{ev_id}/review", json={"decision": "approved", "points": 50, "feedback": "Great work"})
        check("task evidence approval awards points", r.status_code == 200 and r.get_json()["data"]["status"] == "approved", r.get_json())
        r = fac.req("post", f"/api/v1/faculty/task-evidence/{ev_id}/review", json={"decision": "approved"})
        check("duplicate evidence review is blocked", r.status_code == 409, r.status_code)

    r = fac.req("get", "/api/v1/faculty/requests")
    check("faculty request inbox loads", r.status_code == 200)
    r = fac.req("get", f"/api/v1/requests/{request_id}")
    check("faculty can open a student request", r.status_code == 200, r.get_json())
    r = fac.req("post", f"/api/v1/requests/{request_id}/messages", json={"message": "We are looking into it."})
    check("faculty can reply to a request", r.status_code == 201, r.get_json())

    # Point adjustment
    r = fac.req("get", "/api/v1/faculty/appeals")
    check("appeals list loads", r.status_code == 200)

    print("\n== Admin flow ==")
    admin = Client(app)
    r = admin.login("admin@elite.edu", "Admin@1234", "admin")
    check("admin login succeeds", r.status_code == 200, r.get_json())
    r = admin.req("get", "/api/v1/admin/dashboard")
    check("admin dashboard loads", r.status_code == 200 and "total_students" in r.get_json()["data"])

    r = admin.req("get", "/api/v1/admin/users?role=student")
    check("admin user list loads", r.status_code == 200 and len(r.get_json()["data"]) >= 5)

    r = admin.req("post", "/api/v1/admin/announcements", json={"title": "Smoke Test Notice", "content": "Automated smoke test announcement.", "target_audience": "students", "status": "published"})
    check("admin publishes an announcement", r.status_code == 201, r.get_json())

    r = admin.req("get", "/api/v1/admin/settings")
    check("admin settings load", r.status_code == 200 and len(r.get_json()["data"]) >= 5)
    r = admin.req("put", "/api/v1/admin/settings", json={"settings": {"upload_max_mb": 30}})
    check("admin settings save", r.status_code == 200, r.get_json())

    r = admin.req("get", "/api/v1/admin/audit-logs")
    logs = r.get_json()["data"]
    check("audit logs recorded", r.status_code == 200 and len(logs) >= 1, logs)

    # Access control: admin endpoints blocked for students
    r = student.req("get", "/api/v1/admin/users")
    check("student cannot access admin endpoints", r.status_code == 403, r.status_code)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("Failures:")
        for f in FAILED:
            print("  -", f)
        sys.exit(1)
    print("All smoke checks passed.")


if __name__ == "__main__":
    main()
