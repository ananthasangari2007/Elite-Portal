"""Shared helpers for API tests."""
from app.database import db
from app.models import Domain, DomainAssignment, User

PASSWORD = "Secret@1234"

DOMAIN_DEFAULTS = [
    ("DSA", "Data Structures & Algorithms", True),
    ("FULLSTACK", "Full Stack Development", False),
    ("AIML", "AI & Machine Learning", False),
    ("EMBEDDED", "Embedded Systems & IoT", False),
]


def seed_domains():
    for code, name, compulsory in DOMAIN_DEFAULTS:
        db.session.add(Domain(code=code, name=name, is_compulsory=compulsory, is_active=True))
    db.session.commit()


def domain(code):
    return Domain.query.filter_by(code=code).first()


def make_user(email, role, **fields):
    fields.setdefault("approval_status", "approved")
    fields.setdefault("profile_completed", True)
    user = User(name=fields.pop("name", email.split("@")[0]), email=email, role=role, **fields)
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    user_id = user.id
    db.session.remove()
    return db.session.get(User, user_id)


def assign(user, domain_obj, assignment_type):
    db.session.add(DomainAssignment(user_id=user.id, domain_id=domain_obj.id, assignment_type=assignment_type))
    db.session.commit()


def login(client, email, portal, remember=False):
    """Sign in and attach the CSRF header for subsequent mutating requests."""
    res = client.post(
        "/api/v1/auth/login", json={"portal": portal, "email": email, "password": PASSWORD, "remember": remember}
    )
    if res.status_code == 200:
        client.headers["X-CSRF-Token"] = res.json()["data"]["csrf_token"]
    return res
