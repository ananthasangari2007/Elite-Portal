"""Seed local development login accounts for the Elite Portal.

Usage:
    python scripts/seed_dev_accounts.py [--reset-passwords]

Creates one account for each portal role (student, domain coordinator,
faculty coordinator, admin) using reserved example.com addresses, assigns the
correct role and domain assignment, and prints the credentials.

Safety:
    * Refuses to run when FLASK_ENV/APP_ENV is production/staging.
    * Idempotent — running it repeatedly does not create duplicate accounts.
    * Existing accounts keep their password unless ``--reset-passwords`` is passed,
      so seeding never silently overwrites a developer's password.

Passwords can be supplied via environment variables (see ``env_var`` below).
When unset, the documented development defaults are used. Never use these
values for a production deployment.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import is_production_environment  # noqa: E402


DEV_ACCOUNTS = [
    {
        "email": "student@example.com",
        "name": "Dev Student",
        "role": "student",
        "env_var": "DEV_STUDENT_PASSWORD",
        "default_password": "DevStudent@1234",
        "department": "CSE",
        "register_number": "DEV2025CS001",
        "enroll_domains": ["DSA", "FULLSTACK"],
    },
    {
        "email": "domain.coordinator@example.com",
        "name": "Dev Domain Coordinator",
        "role": "coordinator",
        "env_var": "DEV_DOMAIN_COORDINATOR_PASSWORD",
        "default_password": "DevCoordinator@1234",
        "department": "CSE",
        "assign_domains": ["DSA", "FULLSTACK"],
    },
    {
        "email": "faculty.coordinator@example.com",
        "name": "Dev Faculty Coordinator",
        "role": "faculty",
        "env_var": "DEV_FACULTY_COORDINATOR_PASSWORD",
        "default_password": "DevFaculty@1234",
        "department": "CSE",
        "assign_domains": ["DSA", "FULLSTACK", "AIML", "EMBEDDED"],
    },
    {
        "email": "admin@example.com",
        "name": "Dev Administrator",
        "role": "admin",
        "env_var": "DEV_ADMIN_PASSWORD",
        "default_password": "DevAdmin@1234",
    },
]


def _get_domain(code):
    from app.models import Domain

    return Domain.query.filter_by(code=code.upper()).first()


def _apply_assignments(user, spec):
    from app import db
    from app.models import DomainAssignment, StudentDomainEnrollment

    missing = []
    for code in spec.get("enroll_domains", []):
        domain = _get_domain(code)
        if domain is None:
            missing.append(code)
            continue
        row = StudentDomainEnrollment.query.filter_by(
            student_id=user.id, domain_id=domain.id
        ).first()
        if row is None:
            row = StudentDomainEnrollment(
                student_id=user.id, domain_id=domain.id, is_active=True
            )
            db.session.add(row)
        else:
            row.is_active = True

    for index, code in enumerate(spec.get("assign_domains", [])):
        domain = _get_domain(code)
        if domain is None:
            missing.append(code)
            continue
        existing = DomainAssignment.query.filter_by(
            user_id=user.id, domain_id=domain.id, assignment_type=user.role
        ).first()
        if existing is None:
            db.session.add(
                DomainAssignment(
                    user_id=user.id,
                    domain_id=domain.id,
                    assignment_type=user.role,
                    is_primary=(index == 0),
                )
            )
    return missing


def seed(reset_passwords=False):
    from app import create_app, db, seed_domains
    from app.models import User

    app = create_app()
    with app.app_context():
        seed_domains()
        db.session.commit()

        results = []
        for spec in DEV_ACCOUNTS:
            configured_password = os.getenv(spec["env_var"]) or spec["default_password"]
            user = User.query.filter_by(email=spec["email"]).first()
            created = False
            if user is None:
                user = User(
                    name=spec["name"],
                    email=spec["email"],
                    role=spec["role"],
                    approval_status="approved",
                    profile_completed=True,
                    is_active_account=True,
                    department=spec.get("department"),
                    register_number=spec.get("register_number"),
                )
                user.set_password(configured_password)
                db.session.add(user)
                db.session.flush()
                created = True
            else:
                user.role = spec["role"]
                user.is_active_account = True
                user.approval_status = "approved"
                user.profile_completed = True
                if reset_passwords:
                    user.set_password(configured_password)

            missing = _apply_assignments(user, spec)
            results.append(
                {
                    "email": spec["email"],
                    "role": spec["role"],
                    "created": created,
                    "password": configured_password if (created or reset_passwords) else None,
                    "missing_domains": missing,
                }
            )

        db.session.commit()

        print("Development accounts ready (development environment only):")
        for r in results:
            status = "created" if r["created"] else "exists (password unchanged)"
            line = f"  {r['role']:<11} {r['email']:<34} [{status}]"
            if r["password"]:
                line += f"  password: {r['password']}"
            print(line)
            if r["missing_domains"]:
                print(f"      warning: domains not found: {', '.join(r['missing_domains'])}")
        print(
            "\nPasswords can be overridden with DEV_STUDENT_PASSWORD, "
            "DEV_DOMAIN_COORDINATOR_PASSWORD, DEV_FACULTY_COORDINATOR_PASSWORD, "
            "DEV_ADMIN_PASSWORD."
        )
        return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset-passwords",
        action="store_true",
        help="Reset the password of accounts that already exist.",
    )
    args = parser.parse_args()

    if is_production_environment():
        print("Refusing to seed development accounts in a production environment.")
        sys.exit(1)

    seed(reset_passwords=args.reset_passwords)


if __name__ == "__main__":
    main()
