"""Elite Portal management commands (replaces the Flask CLI).

Usage:
    python -m app.cli db-upgrade [revision]      # apply migrations (default: head)
    python -m app.cli db-downgrade <revision>
    python -m app.cli db-current
    python -m app.cli seed-all                   # default admin + 4 domains (idempotent)
    python -m app.cli seed-domains
    python -m app.cli create-admin EMAIL [--password P] [--name N]
    python -m app.cli create-coordinator EMAIL DOMAIN_CODE [--password P] [--name N]
    python -m app.cli create-faculty EMAIL DOMAIN_CODE [--password P] [--name N]
    python -m app.cli reset-admin-password EMAIL [--password P]

Passwords: when --password is omitted you are prompted (never a hardcoded default).
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from app import db, get_initial_admin_password, seed_admin_user, seed_domains

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _alembic_config():
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig(str(MIGRATIONS_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    return cfg


def _password(value: str | None) -> str:
    if value:
        return value
    first = getpass.getpass("Password: ")
    if len(first) < 8 or first != getpass.getpass("Repeat password: "):
        sys.exit("Passwords must match and be at least 8 characters.")
    return first


def _staff(email, role, name, password, domain_code=None):
    from app.models import Domain, DomainAssignment, User

    user = User.query.filter_by(email=email.lower()).first()
    if user is None:
        user = User(name=name, email=email.lower(), role=role, profile_completed=True, approval_status="approved")
        user.set_password(_password(password))
        db.session.add(user)
        db.session.flush()
        print(f"Created {role} {email}.")
    elif user.role != role:
        sys.exit(f"{email} already exists with role {user.role}.")
    if domain_code:
        domain = Domain.query.filter_by(code=domain_code.upper()).first()
        if domain is None:
            sys.exit(f"Domain {domain_code} not found. Run seed-domains first.")
        exists = DomainAssignment.query.filter_by(user_id=user.id, domain_id=domain.id, assignment_type=role).first()
        if not exists:
            db.session.add(DomainAssignment(user_id=user.id, domain_id=domain.id, assignment_type=role, is_primary=True))
            print(f"Assigned {email} to {domain.name} as {role}.")
    db.session.commit()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    up = sub.add_parser("db-upgrade")
    up.add_argument("revision", nargs="?", default="head")
    down = sub.add_parser("db-downgrade")
    down.add_argument("revision")
    sub.add_parser("db-current")
    sub.add_parser("seed-all")
    sub.add_parser("seed-domains")
    for name, needs_domain in (("create-admin", False), ("create-coordinator", True), ("create-faculty", True)):
        p = sub.add_parser(name)
        p.add_argument("email")
        if needs_domain:
            p.add_argument("domain_code")
        p.add_argument("--password")
        p.add_argument("--name")
    reset = sub.add_parser("reset-admin-password")
    reset.add_argument("email")
    reset.add_argument("--password")
    args = parser.parse_args(argv)

    if args.cmd in {"db-upgrade", "db-downgrade", "db-current"}:
        from alembic import command

        cfg = _alembic_config()
        if args.cmd == "db-upgrade":
            command.upgrade(cfg, args.revision)
        elif args.cmd == "db-downgrade":
            command.downgrade(cfg, args.revision)
        else:
            command.current(cfg, verbose=True)
    elif args.cmd == "seed-all":
        seed_admin_user()
        seed_domains()
        print("Admin and domains ready.")
    elif args.cmd == "seed-domains":
        seed_domains()
        print("Domains ready: DSA (compulsory), Full Stack, AI/ML, Embedded Systems.")
    elif args.cmd == "create-admin":
        _staff(args.email, "admin", args.name or "Administrator", args.password)
    elif args.cmd == "create-coordinator":
        _staff(args.email, "coordinator", args.name or "Domain Coordinator", args.password, args.domain_code)
    elif args.cmd == "create-faculty":
        _staff(args.email, "faculty", args.name or "Faculty Coordinator", args.password, args.domain_code)
    elif args.cmd == "reset-admin-password":
        from app.models import User

        user = User.query.filter_by(email=args.email.lower(), role="admin").first()
        if not user:
            sys.exit(f"Admin {args.email} was not found.")
        user.set_password(_password(args.password))
        db.session.commit()
        print(f"Password reset for admin {args.email}.")
    db.session.remove()


if __name__ == "__main__":
    main()
