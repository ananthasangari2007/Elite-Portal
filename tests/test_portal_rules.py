"""Tests for betting scoring boundaries, point integrity and daily-task limits."""
import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app import create_app, db  # noqa: E402
from app.models import (  # noqa: E402
    Assessment,
    AssessmentAttempt,
    Domain,
    EliteTask,
    PointLedger,
    StudentDomainEnrollment,
    TaskEvidence,
    User,
)
from app.services.portal import (  # noqa: E402
    award_points,
    betting_rule,
    business_date,
    can_submit_daily_task,
    points_total,
    submit_daily_task,
)


@pytest.fixture()
def app():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()


def _make_student(email="s@test.com"):
    student = User(name="Student", email=email, role="student", approval_status="approved")
    student.set_password("secret123")
    db.session.add(student)
    db.session.commit()
    return student


@pytest.mark.parametrize(
    "score,attended,expected_locked,expected_attendance,expected_total",
    [
        (0, True, 0, 50, 50),
        (1, True, 0, 100, 100),
        (39, True, 0, 100, 100),
        (40, True, 350, 100, 450),
        (80, True, 350, 100, 450),
        (81, True, 700, 100, 800),
        (50, False, 0, 0, 0),
    ],
)
def test_betting_boundary_scores(app, score, attended, expected_locked, expected_attendance, expected_total):
    result = betting_rule(score, 100, attended)
    assert result["locked_points"] == expected_locked
    assert result["attendance_points"] == expected_attendance
    assert result["total_points"] == expected_total


def test_absent_zero_is_not_attended_zero(app):
    absent = betting_rule(0, 100, attended=False)
    attended = betting_rule(0, 100, attended=True)
    assert absent["total_points"] == 0
    assert attended["total_points"] == 50


def test_point_award_is_idempotent(app):
    student = _make_student()
    first = award_points(
        student_id=student.id,
        points=100,
        transaction_type="task_approval",
        reference_type="TaskEvidence",
        reference_id=1,
        created_by=student.id,
    )
    second = award_points(
        student_id=student.id,
        points=100,
        transaction_type="task_approval",
        reference_type="TaskEvidence",
        reference_id=1,
        created_by=student.id,
    )
    db.session.commit()
    assert first.id == second.id
    assert points_total(student.id) == 100


def test_daily_task_limit_and_unique_constraint(app):
    admin = User(name="Admin", email="a@test.com", role="admin", approval_status="approved")
    admin.set_password("secret123")
    student = _make_student("t@test.com")
    db.session.add(admin)
    db.session.commit()

    task = EliteTask(
        title="Task",
        description="Do it",
        potential_points=50,
        status="active",
        created_by=admin.id,
        due_date=datetime.utcnow() + timedelta(days=1),
    )
    db.session.add(task)
    db.session.commit()

    submit_daily_task(task=task, student_id=student.id, evidence={"evidence_type": "link", "link_url": "https://x.com"})
    db.session.commit()

    allowed, message = can_submit_daily_task(student.id)
    assert allowed is False
    assert "already submitted" in message.lower()

    # The unique constraint also guards the same business day.
    with pytest.raises(ValueError):
        submit_daily_task(task=task, student_id=student.id, evidence={"evidence_type": "link", "link_url": "https://y.com"})


def test_business_date_uses_institution_timezone(app):
    # 18:30 UTC is already the next day in Asia/Kolkata (UTC+5:30).
    value = business_date(datetime(2026, 1, 1, 18, 30))
    assert value.isoformat() == "2026-01-02"


def test_compulsory_dsa_enrollment_rule(app):
    from app import seed_domains

    seed_domains()
    dsa = Domain.query.filter_by(code="DSA").first()
    assert dsa.is_compulsory is True
    student = _make_student("c@test.com")
    db.session.add(StudentDomainEnrollment(student_id=student.id, domain_id=dsa.id, is_active=True))
    db.session.commit()
    assert StudentDomainEnrollment.query.filter_by(student_id=student.id, is_active=True).count() == 1
