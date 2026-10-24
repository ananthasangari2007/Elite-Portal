"""
Elite Portal — shared business services.

Centralises point-ledger rules, betting scoring, business-day handling,
domain access control and dashboard aggregation used by the /api/v1 layer.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import current_app
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import (
    Announcement,
    Appeal,
    Assessment,
    AssessmentAttempt,
    ContentCompletion,
    Domain,
    DomainAssignment,
    EliteTask,
    LearningDay,
    PointAdjustmentRequest,
    PointLedger,
    StudentDomainEnrollment,
    StudentRequest,
    TaskEvidence,
    User,
)

UTC = ZoneInfo("UTC")


# ── Time helpers ──────────────────────────────────────────────────────────
def institution_tz() -> ZoneInfo:
    try:
        return ZoneInfo(current_app.config.get("INSTITUTION_TIMEZONE", "Asia/Kolkata"))
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def to_local(dt: datetime | None):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(institution_tz())


def iso(dt: datetime | None):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def business_date(dt: datetime | None = None) -> date:
    """Return the Asia/Kolkata business date for a UTC timestamp."""
    if dt is None:
        dt = datetime.now(UTC)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(institution_tz()).date()


# ── Point ledger ──────────────────────────────────────────────────────────
def points_total(student_id: int) -> int:
    total = (
        db.session.query(func.coalesce(func.sum(PointLedger.points), 0))
        .filter(PointLedger.student_id == student_id, PointLedger.is_reversed.is_(False))
        .scalar()
    )
    return int(total or 0)


def points_breakdown(student_id: int) -> dict:
    rows = (
        db.session.query(
            PointLedger.transaction_type,
            func.coalesce(func.sum(PointLedger.points), 0),
        )
        .filter(PointLedger.student_id == student_id, PointLedger.is_reversed.is_(False))
        .group_by(PointLedger.transaction_type)
        .all()
    )
    breakdown = {t: int(v or 0) for t, v in rows}
    return {
        "total": sum(breakdown.values()),
        "tasks": breakdown.get("task_approval", 0),
        "assessments": breakdown.get("assessment", 0),
        "betting": breakdown.get("betting_assessment", 0),
        "adjustments": breakdown.get("adjustment", 0),
        "bonus": breakdown.get("bonus", 0),
        "penalty": breakdown.get("penalty", 0),
        "penalties": breakdown.get("penalty", 0),
    }


def find_ledger_entry(
    student_id: int, transaction_type: str, reference_type: str | None, reference_id: int | None
):
    if not reference_type or reference_id is None:
        return None
    return PointLedger.query.filter_by(
        student_id=student_id,
        transaction_type=transaction_type,
        reference_type=reference_type,
        reference_id=reference_id,
    ).first()


def award_points(
    *,
    student_id: int,
    points: int,
    transaction_type: str,
    created_by: int,
    reference_type: str | None = None,
    reference_id: int | None = None,
    domain_id: int | None = None,
    description: str | None = None,
    is_override: bool = False,
    override_reason: str | None = None,
) -> PointLedger:
    """Award points exactly once for a given (type, reference) tuple."""
    existing = find_ledger_entry(student_id, transaction_type, reference_type, reference_id)
    if existing is not None:
        return existing

    entry = PointLedger(
        student_id=student_id,
        points=int(points),
        transaction_type=transaction_type,
        reference_type=reference_type,
        reference_id=reference_id,
        domain_id=domain_id,
        description=description,
        created_by=created_by,
        is_override=is_override,
        override_reason=override_reason,
    )
    db.session.add(entry)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        existing = find_ledger_entry(student_id, transaction_type, reference_type, reference_id)
        if existing is not None:
            return existing
        raise
    return entry


def reverse_points(entry: PointLedger, reversed_by: int):
    if entry.is_reversed:
        return entry
    entry.is_reversed = True
    entry.reversed_by = reversed_by
    entry.reversed_at = now_utc()
    return entry


# ── Betting assessment rules (institution-defined, exact) ─────────────────
BETTING_RULES = {
    "above_80": {"locked": 700, "attendance": 100, "label": "Score greater than 80"},
    "40_to_80": {"locked": 350, "attendance": 100, "label": "Score 40 to 80 inclusive"},
    "1_to_39": {"locked": 0, "attendance": 100, "label": "Score 1 to 39"},
    "attended_zero": {"locked": 0, "attendance": 50, "label": "Score 0 after attending"},
    "absent": {"locked": 0, "attendance": 0, "label": "Absent / never attended"},
}


def betting_rule(score: int, total_marks: int, attended: bool) -> dict:
    """Compute the institution's exact betting assessment point rule."""
    score = int(score or 0)
    total_marks = int(total_marks or 0)

    if not attended:
        rule = "absent"
    elif score <= 0:
        rule = "attended_zero"
    else:
        pct = (score / total_marks * 100) if total_marks > 0 else 0
        if pct > 80:
            rule = "above_80"
        elif pct >= 40:
            rule = "40_to_80"
        else:
            rule = "1_to_39"

    info = BETTING_RULES[rule]
    return {
        "rule": rule,
        "label": info["label"],
        "locked_points": info["locked"],
        "attendance_points": info["attendance"],
        "total_points": info["locked"] + info["attendance"],
    }


def apply_betting_points(attempt: AssessmentAttempt, created_by: int | None = None) -> dict:
    """Persist betting fields and award the ledger entry idempotently."""
    if attempt.assessment.assessment_type != "betting":
        return {}

    rule = betting_rule(attempt.score or 0, attempt.total_marks or 0, bool(attempt.attended))
    attempt.locked_points = rule["locked_points"]
    attempt.attendance_points = rule["attendance_points"]
    attempt.total_points_awarded = rule["total_points"]
    attempt.points_rule_applied = rule["rule"]

    if rule["total_points"] > 0:
        award_points(
            student_id=attempt.student_id,
            points=rule["total_points"],
            transaction_type="betting_assessment",
            reference_type="AssessmentAttempt",
            reference_id=attempt.id,
            domain_id=attempt.assessment.domain_id,
            description=(
                f"Betting assessment: {attempt.assessment.title} "
                f"({rule['locked_points']} locked + {rule['attendance_points']} attendance)"
            ),
            created_by=created_by or attempt.student_id,
        )
    db.session.flush()
    return rule


# ── Domain access ─────────────────────────────────────────────────────────
def assigned_domains(user: User, assignment_type: str | None = None):
    query = Domain.query.join(DomainAssignment, DomainAssignment.domain_id == Domain.id).filter(
        DomainAssignment.user_id == user.id
    )
    if assignment_type:
        query = query.filter(DomainAssignment.assignment_type == assignment_type)
    return query


def domain_ids_for(user: User, assignment_type: str | None = None) -> list[int]:
    return [d.id for d in assigned_domains(user, assignment_type).all()]


def enrolled_domains(student_id: int):
    return (
        Domain.query.join(
            StudentDomainEnrollment, StudentDomainEnrollment.domain_id == Domain.id
        )
        .filter(
            StudentDomainEnrollment.student_id == student_id,
            StudentDomainEnrollment.is_active.is_(True),
        )
        .order_by(Domain.is_compulsory.desc(), Domain.name.asc())
        .all()
    )


def enrolled_domain_ids(student_id: int) -> list[int]:
    return [d.id for d in enrolled_domains(student_id)]


def can_access_domain(user: User, domain_id: int) -> bool:
    if user.role == "admin":
        return True
    if user.role == "student":
        return StudentDomainEnrollment.query.filter_by(
            student_id=user.id, domain_id=domain_id, is_active=True
        ).first() is not None
    if user.role in ("coordinator", "faculty"):
        return DomainAssignment.query.filter_by(user_id=user.id, domain_id=domain_id).first() is not None
    return False


def can_manage_domain(user: User, domain_id: int) -> bool:
    if user.role == "admin":
        return True
    if user.role == "coordinator":
        return DomainAssignment.query.filter_by(
            user_id=user.id, domain_id=domain_id, assignment_type="coordinator"
        ).first() is not None
    return False


def student_ids_in_domains(domain_ids: list[int]) -> list[int]:
    if not domain_ids:
        return []
    rows = (
        db.session.query(StudentDomainEnrollment.student_id)
        .filter(StudentDomainEnrollment.domain_id.in_(domain_ids), StudentDomainEnrollment.is_active.is_(True))
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def scope_domain_ids(user: User) -> list[int] | None:
    """Domain scope for staff. Admins get None (= all domains)."""
    if user.role == "admin":
        return None
    return domain_ids_for(user)


def scoped_student_ids(user: User) -> list[int] | None:
    domain_ids = scope_domain_ids(user)
    if domain_ids is None:
        return None
    return student_ids_in_domains(domain_ids)


# ── Learning progress ─────────────────────────────────────────────────────
def domain_progress(student_id: int, domain_id: int) -> dict:
    published = LearningDay.query.filter_by(domain_id=domain_id, status="published").count()
    completed = (
        db.session.query(func.count(func.distinct(LearningDay.id)))
        .join(ContentCompletion, ContentCompletion.learning_day_id == LearningDay.id)
        .filter(
            LearningDay.domain_id == domain_id,
            ContentCompletion.student_id == student_id,
            ContentCompletion.is_day_complete.is_(True),
        )
        .scalar()
        or 0
    )
    return {
        "published_days": int(published),
        "completed_days": int(completed),
        "percent": round((completed / published) * 100) if published else 0,
    }


def current_streak(student_id: int) -> int:
    rows = (
        db.session.query(TaskEvidence.submission_date)
        .filter(TaskEvidence.student_id == student_id, TaskEvidence.status == "approved")
        .group_by(TaskEvidence.submission_date)
        .order_by(TaskEvidence.submission_date.desc())
        .all()
    )
    approved = {r[0] for r in rows}
    if not approved:
        return 0
    cursor = business_date()
    if cursor not in approved:
        cursor = cursor - timedelta(days=1)
        if cursor not in approved:
            return 0
    streak = 0
    while cursor in approved:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak


# ── Daily task submission (one per student per task per business day) ──────────────
def today_submission(student_id: int, task_id: int | None = None) -> TaskEvidence | None:
    q = TaskEvidence.query.filter_by(
        student_id=student_id, submission_date=business_date()
    )
    if task_id is not None:
        q = q.filter_by(task_id=task_id)
    return q.first()


def can_submit_daily_task(student_id: int, task_id: int | None = None) -> tuple[bool, str | None]:
    existing = today_submission(student_id, task_id=task_id)
    if existing is None:
        return True, None
    if existing.status == "rejected":
        return False, "Your submission for this task today was rejected. One submission is allowed per day for each assigned task."
    return False, "You have already submitted this Elite Task today. One submission per assigned task is allowed each day."


def submit_daily_task(*, task: EliteTask, student_id: int, evidence: dict) -> TaskEvidence:
    """Create today's evidence row inside a transaction; unique constraint guards races."""
    allowed, message = can_submit_daily_task(student_id, task_id=task.id)
    if not allowed:
        raise ValueError(message)

    row = TaskEvidence(
        task_id=task.id,
        student_id=student_id,
        evidence_type=evidence.get("evidence_type", "link"),
        file_key=evidence.get("file_key"),
        file_name=evidence.get("file_name"),
        file_size=evidence.get("file_size"),
        file_type=evidence.get("file_type"),
        link_url=evidence.get("link_url"),
        notes=evidence.get("notes"),
        submission_date=business_date(),
        status="pending",
        submitted_at=now_utc(),
    )
    db.session.add(row)
    try:
        db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError(
            "You have already submitted this Elite Task today. One submission per assigned task is allowed each day."
        ) from exc
    return row


# ── Notifications & audit ─────────────────────────────────────────────────
def notify(user_id: int, title: str, message: str, notification_type: str = "info", link_url: str | None = None):
    from app.models import Notification

    row = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        link_url=link_url,
    )
    db.session.add(row)
    return row


def audit(
    actor_id: int,
    action: str,
    *,
    target_type: str | None = None,
    target_id: int | None = None,
    description: str | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    ip_address: str | None = None,
):
    from app.models import AuditLog

    row = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        description=description,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
    )
    db.session.add(row)
    return row


def active_announcements(user: User):
    now = now_utc()
    query = Announcement.query.filter(
        Announcement.status == "published",
        or_(Announcement.publish_at.is_(None), Announcement.publish_at <= now),
        or_(Announcement.expires_at.is_(None), Announcement.expires_at >= now),
    )
    if user.role == "student":
        query = query.filter(
            or_(
                Announcement.target_audience.in_(["all", "students"]),
                Announcement.target_domain_id.in_(enrolled_domain_ids(user.id) or [-1]),
            )
        )
    else:
        target = {
            "coordinator": ["all", "coordinators"],
            "faculty": ["all", "faculty"],
            "admin": ["all", "admin"],
        }.get(user.role, ["all"])
        query = query.filter(
            or_(Announcement.target_audience.in_(target), Announcement.target_domain_id.isnot(None))
        )
    return query.order_by(Announcement.publish_at.desc().nulls_last(), Announcement.created_at.desc())


# ── Leaderboards ──────────────────────────────────────────────────────────
def leaderboard(
    scope: str = "overall",
    domain_id: int | None = None,
    month: str | None = None,
    department: str | None = None,
    limit: int = 20,
):
    """Eligible points only: ledger rows that are not reversed."""
    query = (
        db.session.query(
            User.id,
            User.name,
            User.register_number,
            User.department,
            User.avatar_url,
            func.coalesce(func.sum(PointLedger.points), 0).label("points"),
        )
        .join(PointLedger, PointLedger.student_id == User.id)
        .filter(User.role == "student", PointLedger.is_reversed.is_(False))
    )
    if department:
        query = query.filter(func.lower(User.department) == department.strip().lower())

    if scope != "overall" and scope != "monthly":
        if domain_id:
            query = query.filter(PointLedger.domain_id == domain_id)
        else:
            query = query.join(Domain, Domain.id == PointLedger.domain_id).filter(func.lower(Domain.code) == scope.lower())

    if scope == "monthly" and month:
        try:
            year, mon = [int(x) for x in month.split("-")]
            start = datetime(year, mon, 1)
            end = datetime(year + 1, 1, 1) if mon == 12 else datetime(year, mon + 1, 1)
            query = query.filter(PointLedger.created_at >= start, PointLedger.created_at < end)
        except (ValueError, TypeError):
            pass

    rows = (
        query.group_by(User.id, User.name, User.register_number, User.department, User.avatar_url)
        .order_by(func.coalesce(func.sum(PointLedger.points), 0).desc(), User.name.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "rank": i,
            "student_id": r[0],
            "name": r[1],
            "register_number": r[2],
            "department": r[3],
            "avatar_url": r[4],
            "points": int(r[5] or 0),
        }
        for i, r in enumerate(rows, start=1)
    ]


def student_leaderboard_ranks(student_id: int) -> dict:
    """Computes exact current rank for a student in Overall and each enrolled domain."""
    # 1. Overall rank
    overall_all = (
        db.session.query(
            User.id,
            func.coalesce(func.sum(PointLedger.points), 0).label("pts"),
        )
        .join(PointLedger, PointLedger.student_id == User.id)
        .filter(User.role == "student", PointLedger.is_reversed.is_(False))
        .group_by(User.id)
        .order_by(func.coalesce(func.sum(PointLedger.points), 0).desc())
        .all()
    )
    overall_rank = next((idx for idx, (uid, _) in enumerate(overall_all, start=1) if uid == student_id), None)
    overall_pts = next((int(pts or 0) for uid, pts in overall_all if uid == student_id), 0)

    # 2. Registered domains ranks
    enrolled = enrolled_domains(student_id)
    domain_ranks = {}
    for d in enrolled:
        d_all = (
            db.session.query(
                User.id,
                func.coalesce(func.sum(PointLedger.points), 0).label("pts"),
            )
            .join(PointLedger, PointLedger.student_id == User.id)
            .filter(User.role == "student", PointLedger.is_reversed.is_(False), PointLedger.domain_id == d.id)
            .group_by(User.id)
            .order_by(func.coalesce(func.sum(PointLedger.points), 0).desc())
            .all()
        )
        d_rank = next((idx for idx, (uid, _) in enumerate(d_all, start=1) if uid == student_id), None)
        d_pts = next((int(pts or 0) for uid, pts in d_all if uid == student_id), 0)
        domain_ranks[d.code] = {
            "domain_id": d.id,
            "domain_name": d.name,
            "domain_code": d.code,
            "rank": d_rank,
            "points": d_pts,
        }

    return {
        "overall": {"rank": overall_rank, "points": overall_pts},
        "domains": domain_ranks,
    }


# ── Dashboard aggregations ────────────────────────────────────────────────
def student_dashboard(student_id: int) -> dict:
    domains = enrolled_domains(student_id)
    domain_ids = [d.id for d in domains]

    pub_counts = {}
    comp_counts = {}
    if domain_ids:
        for dom_id, cnt in (
            db.session.query(LearningDay.domain_id, func.count(LearningDay.id))
            .filter(LearningDay.domain_id.in_(domain_ids), LearningDay.status == "published")
            .group_by(LearningDay.domain_id)
            .all()
        ):
            pub_counts[dom_id] = int(cnt)

        for dom_id, cnt in (
            db.session.query(LearningDay.domain_id, func.count(func.distinct(LearningDay.id)))
            .join(ContentCompletion, ContentCompletion.learning_day_id == LearningDay.id)
            .filter(
                LearningDay.domain_id.in_(domain_ids),
                ContentCompletion.student_id == student_id,
                ContentCompletion.is_day_complete.is_(True),
            )
            .group_by(LearningDay.domain_id)
            .all()
        ):
            comp_counts[dom_id] = int(cnt)

    progress = [
        {
            "domain_id": d.id,
            "code": d.code,
            "name": d.name,
            "color": d.color,
            "icon": d.icon,
            "published_days": pub_counts.get(d.id, 0),
            "completed_days": comp_counts.get(d.id, 0),
            "percent": round((comp_counts.get(d.id, 0) / pub_counts[d.id]) * 100)
            if pub_counts.get(d.id, 0)
            else 0,
        }
        for d in domains
    ]

    videos_completed = 0
    for (watched,) in (
        db.session.query(ContentCompletion.videos_watched)
        .filter(ContentCompletion.student_id == student_id)
        .all()
    ):
        if isinstance(watched, list):
            videos_completed += len(watched)

    assessments_completed = AssessmentAttempt.query.filter(
        AssessmentAttempt.student_id == student_id,
        AssessmentAttempt.status.in_(["submitted", "graded"]),
    ).count()

    now = now_utc()
    today_tasks = (
        EliteTask.query.filter(
            EliteTask.status == "active",
            or_(EliteTask.publish_at.is_(None), EliteTask.publish_at <= now),
            or_(EliteTask.due_date.is_(None), EliteTask.due_date >= now),
            or_(EliteTask.domain_id.is_(None), EliteTask.domain_id.in_(domain_ids or [-1])),
        )
        .order_by(EliteTask.due_date.asc().nulls_last())
        .limit(5)
        .all()
    )
    submitted_today = today_submission(student_id)

    upcoming = (
        Assessment.query.filter(
            Assessment.status.in_(["published", "scheduled"]),
            Assessment.domain_id.in_(domain_ids or [-1]),
            or_(Assessment.scheduled_end.is_(None), Assessment.scheduled_end >= now),
        )
        .order_by(Assessment.scheduled_start.asc().nulls_last())
        .limit(5)
        .all()
    )

    recent = (
        PointLedger.query.filter_by(student_id=student_id)
        .order_by(PointLedger.created_at.desc())
        .limit(6)
        .all()
    )

    recent_completions = (
        ContentCompletion.query.filter_by(student_id=student_id, is_day_complete=True)
        .order_by(ContentCompletion.completed_at.desc())
        .limit(4)
        .all()
    )

    appeals_assigned = (
        Appeal.query.filter(
            Appeal.student_id == student_id,
            Appeal.status == "in_review",
            Appeal.assigned_to.isnot(None),
        )
        .all()
    )
    faculty_instructions = [
        {
            "id": a.id,
            "faculty_name": a.assigned_reviewer.name if a.assigned_reviewer else "Faculty Coordinator",
            "faculty_email": a.assigned_reviewer.email if a.assigned_reviewer else None,
            "assessment": a.attempt.assessment.title if a.attempt else "Assessment",
            "message": f"You are instructed to meet the faculty {a.assigned_reviewer.name if a.assigned_reviewer else ''}.",
        }
        for a in appeals_assigned
    ]

    return {
        "total_points": points_total(student_id),
        "videos_completed": videos_completed,
        "assessments_completed": assessments_completed,
        "current_streak": current_streak(student_id),
        "progress": progress,
        "faculty_instructions": faculty_instructions,
        "today_tasks": [
            {
                "id": t.id,
                "title": t.title,
                "potential_points": t.potential_points,
                "due_date": iso(t.due_date),
                "domain_id": t.domain_id,
                "submitted": submitted_today is not None and submitted_today.task_id == t.id,
            }
            for t in today_tasks
        ],
        "daily_task_submitted": submitted_today is not None,
        "upcoming_assessments": [
            {
                "id": a.id,
                "title": a.title,
                "type": a.assessment_type,
                "domain_id": a.domain_id,
                "scheduled_start": iso(a.scheduled_start),
                "scheduled_end": iso(a.scheduled_end),
                "time_limit_minutes": a.time_limit_minutes,
            }
            for a in upcoming
        ],
        "recent_activity": [
            {
                "id": e.id,
                "points": e.points,
                "type": e.transaction_type,
                "description": e.description,
                "created_at": iso(e.created_at),
            }
            for e in recent
        ]
        + [
            {
                "id": f"c{cc.id}",
                "points": 0,
                "type": "content_completion",
                "description": f"Completed learning day: {cc.learning_day.title}",
                "created_at": iso(cc.completed_at),
            }
            for cc in recent_completions
        ],
    }


def _completion_by_day(domain_ids: list[int]) -> list[dict]:
    rows = (
        db.session.query(
            LearningDay.id,
            LearningDay.day_number,
            LearningDay.title,
            func.count(func.distinct(ContentCompletion.student_id)),
        )
        .outerjoin(ContentCompletion, ContentCompletion.learning_day_id == LearningDay.id)
        .filter(LearningDay.domain_id.in_(domain_ids or [-1]), LearningDay.status == "published")
        .group_by(LearningDay.id, LearningDay.day_number, LearningDay.title)
        .order_by(LearningDay.day_number.asc())
        .limit(12)
        .all()
    )
    return [
        {"day_id": r[0], "day_number": r[1], "title": r[2], "completed": int(r[3] or 0)}
        for r in rows
    ]


def coordinator_dashboard(user: User) -> dict:
    domain_ids = domain_ids_for(user, "coordinator")
    domains = Domain.query.filter(Domain.id.in_(domain_ids or [-1])).all()

    student_ids = student_ids_in_domains(domain_ids)
    published_days = LearningDay.query.filter(
        LearningDay.domain_id.in_(domain_ids or [-1]), LearningDay.status == "published"
    ).count()

    attempts = (
        AssessmentAttempt.query.join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
        .filter(Assessment.domain_id.in_(domain_ids or [-1]))
    )
    submitted = attempts.filter(
        AssessmentAttempt.status.in_(["submitted", "graded"])
    ).count()
    pending = attempts.filter(AssessmentAttempt.status == "submitted").count()

    pending_rows = (
        attempts.filter(AssessmentAttempt.status == "submitted")
        .order_by(AssessmentAttempt.submitted_at.asc())
        .limit(6)
        .all()
    )

    recent = (
        AssessmentAttempt.query.join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
        .filter(
            Assessment.domain_id.in_(domain_ids or [-1]),
            AssessmentAttempt.status.in_(["submitted", "graded"]),
        )
        .order_by(AssessmentAttempt.submitted_at.desc())
        .limit(6)
        .all()
    )

    pub_activity = (
        db.session.query(LearningDay.day_number, LearningDay.title, LearningDay.published_at)
        .filter(LearningDay.domain_id.in_(domain_ids or [-1]), LearningDay.published_at.isnot(None))
        .order_by(LearningDay.published_at.desc())
        .limit(6)
        .all()
    )

    return {
        "enrolled_students": len(student_ids),
        "published_days": published_days,
        "assessments_submitted": submitted,
        "pending_grading": pending,
        "domains": [
            {
                "id": d.id,
                "code": d.code,
                "name": d.name,
                "color": d.color,
                "students": d.student_count,
                "published_days": d.published_days_count,
            }
            for d in domains
        ],
        "progress_by_day": _completion_by_day(domain_ids),
        "pending_grading_list": [
            {
                "id": a.id,
                "student": a.student.name,
                "assessment": a.assessment.title,
                "submitted_at": iso(a.submitted_at),
            }
            for a in pending_rows
        ],
        "recent_activity": [
            {
                "id": a.id,
                "student": a.student.name,
                "assessment": a.assessment.title,
                "status": a.status,
                "score": a.score,
                "at": iso(a.graded_at or a.submitted_at),
            }
            for a in recent
        ],
        "publication_activity": [
            {"day_number": r[0], "title": r[1], "published_at": iso(r[2])} for r in pub_activity
        ],
    }


def faculty_dashboard(user: User) -> dict:
    domain_ids = domain_ids_for(user)
    scoped = student_ids_in_domains(domain_ids)
    if not domain_ids:
        # Faculty without assignments see institution-wide read scope.
        scoped = [r[0] for r in db.session.query(User.id).filter(User.role == "student").all()]
        domain_ids = [d.id for d in Domain.query.all()]

    pending_grading = (
        AssessmentAttempt.query.join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
        .filter(Assessment.domain_id.in_(domain_ids or [-1]), AssessmentAttempt.status == "submitted")
        .count()
    )
    open_appeals = Appeal.query.filter(
        Appeal.student_id.in_(scoped or [-1]), Appeal.status.in_(["open", "in_review"])
    ).count()
    pending_adjustments = PointAdjustmentRequest.query.filter(
        PointAdjustmentRequest.student_id.in_(scoped or [-1]),
        PointAdjustmentRequest.status == "pending",
    ).count()

    domains = Domain.query.filter(Domain.id.in_(domain_ids or [-1])).all()

    pending_rows = (
        AssessmentAttempt.query.join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
        .filter(Assessment.domain_id.in_(domain_ids or [-1]), AssessmentAttempt.status == "submitted")
        .order_by(AssessmentAttempt.submitted_at.asc())
        .limit(6)
        .all()
    )

    requests = (
        StudentRequest.query.filter(
            StudentRequest.student_id.in_(scoped or [-1]),
            StudentRequest.status.in_(["open", "in_progress"]),
        )
        .order_by(StudentRequest.created_at.desc())
        .limit(6)
        .all()
    )

    recent = (
        PointLedger.query.filter(PointLedger.student_id.in_(scoped or [-1]))
        .order_by(PointLedger.created_at.desc())
        .limit(6)
        .all()
    )

    evidence_pending = TaskEvidence.query.filter(
        TaskEvidence.student_id.in_(scoped or [-1]), TaskEvidence.status == "pending"
    ).count()

    return {
        "total_students": len(scoped),
        "pending_grading": pending_grading,
        "open_appeals": open_appeals,
        "pending_point_adjustments": pending_adjustments,
        "pending_task_approvals": evidence_pending,
        "domains": [
            {
                "id": d.id,
                "code": d.code,
                "name": d.name,
                "color": d.color,
                "students": sum(1 for s in scoped if StudentDomainEnrollment.query.filter_by(
                    student_id=s, domain_id=d.id, is_active=True
                ).first()),
                "published_days": d.published_days_count,
                "assessments": d.assessments.count(),
            }
            for d in domains
        ],
        "pending_grading_list": [
            {
                "id": a.id,
                "student": a.student.name,
                "assessment": a.assessment.title,
                "domain": a.assessment.domain.name,
                "submitted_at": iso(a.submitted_at),
            }
            for a in pending_rows
        ],
        "student_requests": [
            {
                "id": r.id,
                "student": r.student.name,
                "subject": r.subject,
                "category": r.category,
                "status": r.status,
                "created_at": iso(r.created_at),
            }
            for r in requests
        ],
        "recent_activity": [
            {
                "id": e.id,
                "student": e.student.name,
                "points": e.points,
                "type": e.transaction_type,
                "description": e.description,
                "created_at": iso(e.created_at),
            }
            for e in recent
        ],
    }


def admin_dashboard() -> dict:
    students = User.query.filter_by(role="student").count()
    staff = User.query.filter(User.role.in_(["faculty", "coordinator"])).count()
    assessments = Assessment.query.count()
    submissions = AssessmentAttempt.query.filter(
        AssessmentAttempt.status.in_(["submitted", "graded"])
    ).count()

    pending_accounts = User.query.filter_by(role="student", approval_status="pending").count()
    pending_evidence = TaskEvidence.query.filter_by(status="pending").count()
    open_appeals = Appeal.query.filter(Appeal.status.in_(["open", "in_review"])).count()
    pending_adjustments = PointAdjustmentRequest.query.filter_by(status="pending").count()

    from app.models import AuditLog

    recent = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all()

    activity = []
    for offset in range(13, -1, -1):
        day = business_date() - timedelta(days=offset)
        start_local = datetime.combine(day, datetime.min.time()).replace(tzinfo=institution_tz())
        end_local = start_local + timedelta(days=1)
        start = start_local.astimezone(UTC).replace(tzinfo=None)
        end = end_local.astimezone(UTC).replace(tzinfo=None)
        activity.append(
            {
                "date": day.isoformat(),
                "submissions": AssessmentAttempt.query.filter(
                    AssessmentAttempt.submitted_at >= start, AssessmentAttempt.submitted_at < end
                ).count(),
                "evidence": TaskEvidence.query.filter(
                    TaskEvidence.submitted_at >= start, TaskEvidence.submitted_at < end
                ).count(),
                "completions": ContentCompletion.query.filter(
                    ContentCompletion.completed_at >= start, ContentCompletion.completed_at < end
                ).count(),
            }
        )

    return {
        "total_students": students,
        "total_staff": staff,
        "assessments_created": assessments,
        "total_submissions": submissions,
        "pending_accounts": pending_accounts,
        "pending_task_approvals": pending_evidence,
        "open_appeals": open_appeals,
        "pending_point_adjustments": pending_adjustments,
        "platform_activity": activity,
        "recent_activity": [
            {
                "id": r.id,
                "actor": r.actor.name if r.actor else "System",
                "action": r.action,
                "description": r.description,
                "created_at": iso(r.created_at),
            }
            for r in recent
        ],
        "system_status": {
            "database": "operational",
            "storage": "r2" if current_app.config.get("R2_BUCKET_NAME") and current_app.config.get("R2_ENDPOINT_URL") else "local-fallback",
            "email": "configured" if current_app.config.get("MAIL_SERVER") else "not-configured",
            "timezone": current_app.config.get("INSTITUTION_TIMEZONE", "Asia/Kolkata"),
        },
    }
