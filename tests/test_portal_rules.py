"""Betting scoring boundaries, point integrity and daily-task limits."""
from datetime import datetime, timedelta

import pytest

from app.database import db
from app.models import Domain, EliteTask, StudentDomainEnrollment, User
from app.services.portal import (
    award_points,
    betting_rule,
    business_date,
    can_submit_daily_task,
    points_total,
    submit_daily_task,
)


@pytest.fixture(autouse=True)
def _db(fresh_db):
    yield


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
        (41, True, 350, 100, 450),
        (79, True, 350, 100, 450),
        (80, True, 350, 100, 450),
        (81, True, 700, 100, 800),
        (100, True, 700, 100, 800),
        (50, False, 0, 0, 0),
        (0, False, 0, 0, 0),
    ],
)
def test_betting_boundary_scores(score, attended, expected_locked, expected_attendance, expected_total):
    result = betting_rule(score, 100, attended)
    assert result["locked_points"] == expected_locked
    assert result["attendance_points"] == expected_attendance
    assert result["total_points"] == expected_total


def test_absent_zero_is_not_attended_zero():
    assert betting_rule(0, 100, attended=False)["total_points"] == 0
    assert betting_rule(0, 100, attended=True)["total_points"] == 50


def test_point_award_is_idempotent():
    student = _make_student()
    kwargs = dict(student_id=student.id, points=100, transaction_type="task_approval",
                  reference_type="TaskEvidence", reference_id=1, created_by=student.id)
    first = award_points(**kwargs)
    second = award_points(**kwargs)
    db.session.commit()
    assert first.id == second.id
    assert points_total(student.id) == 100


def test_daily_task_limit_and_unique_constraint():
    admin = User(name="Admin", email="a@test.com", role="admin", approval_status="approved")
    admin.set_password("secret123")
    student = _make_student("t@test.com")
    db.session.add(admin)
    db.session.commit()
    task = EliteTask(title="Task", description="Do it", potential_points=50, status="active",
                     created_by=admin.id, due_date=datetime.utcnow() + timedelta(days=1))
    db.session.add(task)
    db.session.commit()

    submit_daily_task(task=task, student_id=student.id, evidence={"evidence_type": "link", "link_url": "https://x.com"})
    db.session.commit()
    allowed, message = can_submit_daily_task(student.id)
    assert allowed is False and "already submitted" in message.lower()
    with pytest.raises(ValueError):
        submit_daily_task(task=task, student_id=student.id, evidence={"evidence_type": "link", "link_url": "https://y.com"})


def test_business_date_uses_institution_timezone():
    # 18:30 UTC is already the next day in Asia/Kolkata (UTC+5:30).
    assert business_date(datetime(2026, 1, 1, 18, 30)).isoformat() == "2026-01-02"
    assert business_date(datetime(2026, 1, 1, 18, 29)).isoformat() == "2026-01-01"


def test_compulsory_dsa_enrollment_rule():
    from app import seed_domains

    seed_domains()
    seed_domains()  # idempotent
    assert Domain.query.count() == 4
    dsa = Domain.query.filter_by(code="DSA").first()
    assert dsa.is_compulsory is True
    student = _make_student("c@test.com")
    db.session.add(StudentDomainEnrollment(student_id=student.id, domain_id=dsa.id, is_active=True))
    db.session.commit()
    assert StudentDomainEnrollment.query.filter_by(student_id=student.id, is_active=True).count() == 1
