"""Student API — dashboard, learning, assessments, Elite Tasks, points, requests."""
from __future__ import annotations

import random
from datetime import timedelta

from flask import Blueprint, current_app, request
from flask_login import current_user
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.api.utils import (
    ApiError,
    assessment_public,
    attempt_public,
    day_public,
    domain_public,
    evidence_public,
    get_int,
    iso,
    json_body,
    material_public,
    ok,
    paginate,
    question_public,
    require_roles,
)
from app.models import (
    Announcement,
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentAuthorization,
    AssessmentOption,
    AssessmentQuestion,
    CodingSubmission,
    ContentCompletion,
    Domain,
    EliteTask,
    LearningDay,
    LearningMaterial,
    Notification,
    RequestMessage,
    StudentDomainEnrollment,
    StudentRequest,
    TaskEvidence,
)
from app.services.portal import (
    active_announcements,
    apply_betting_points,
    award_points,
    betting_rule,
    business_date,
    can_submit_daily_task,
    current_streak,
    domain_progress,
    enrolled_domains,
    enrolled_domain_ids,
    find_ledger_entry,
    iso as iso_dt,
    leaderboard,
    now_utc,
    points_breakdown,
    points_total,
    student_dashboard,
    student_leaderboard_ranks,
    submit_daily_task,
    today_submission,
)

student_api = Blueprint("api_student", __name__, url_prefix="/api/v1")


def _student():
    if current_user.role != "student":
        raise ApiError("Student access only.", 403, "forbidden")
    return current_user


def _require_domain(domain_id):
    ids = enrolled_domain_ids(current_user.id)
    if int(domain_id) not in ids:
        raise ApiError("You are not enrolled in this domain.", 403, "not_enrolled")


# ── Dashboard ─────────────────────────────────────────────────────────────
@student_api.get("/student/dashboard")
@require_roles("student")
def dashboard():
    return ok(student_dashboard(current_user.id))


@student_api.get("/student/points")
@require_roles("student")
def my_points():
    from app.models import PointLedger

    entries = (
        PointLedger.query.filter_by(student_id=current_user.id)
        .order_by(PointLedger.created_at.desc())
        .limit(200)
        .all()
    )
    return ok(
        {
            "summary": points_breakdown(current_user.id),
            "history": [
                {
                    "id": e.id,
                    "points": e.points,
                    "type": e.transaction_type,
                    "description": e.description,
                    "domain_id": e.domain_id,
                    "is_override": e.is_override,
                    "is_reversed": e.is_reversed,
                    "created_at": iso(e.created_at),
                }
                for e in entries
            ],
        }
    )


# ── Domains & enrollment ──────────────────────────────────────────────────
@student_api.get("/domains")
def list_domains():
    if not current_user.is_authenticated:
        raise ApiError("Authentication required.", 401, "unauthenticated")
    domains = Domain.query.filter_by(is_active=True).order_by(Domain.is_compulsory.desc(), Domain.name).all()
    enrolled = set(enrolled_domain_ids(current_user.id)) if current_user.role == "student" else set()
    return ok(
        [
            {**domain_public(d), "enrolled": d.id in enrolled}
            for d in domains
        ]
    )


@student_api.get("/student/domains")
@require_roles("student")
def my_domains():
    domains = enrolled_domains(current_user.id)
    all_domains = Domain.query.filter_by(is_active=True).order_by(Domain.is_compulsory.desc(), Domain.name).all()
    return ok(
        {
            "enrolled": [
                {**domain_public(d), "progress": domain_progress(current_user.id, d.id)} for d in domains
            ],
            "available": [domain_public(d) for d in all_domains if d.id not in {x.id for x in domains}],
            "max_optional": int(current_app.config.get("MAX_OPTIONAL_DOMAINS", 2)),
        }
    )


@student_api.post("/student/domains")
@require_roles("student")
def select_domains():
    data = json_body()
    requested = data.get("domain_ids")
    if requested is None:
        requested = []
    if not isinstance(requested, list):
        raise ApiError("domain_ids must be a list of domain IDs.", 400, "invalid_domains")

    try:
        requested_ids = {int(x) for x in requested}
    except (TypeError, ValueError):
        raise ApiError("Domain selections must be numeric IDs.", 400, "invalid_domains")

    if requested_ids:
        selected = Domain.query.filter(
            Domain.id.in_(requested_ids), Domain.is_active.is_(True)
        ).all()
        if len(selected) != len(requested_ids):
            raise ApiError("One or more selected domains are unavailable.", 400, "invalid_domains")

    # Compulsory domains (DSA) apply to every student, so they are always
    # included server-side even when the client omits them. This keeps the
    # contract simple and prevents an empty selection from failing the save.
    compulsory = {
        d.id for d in Domain.query.filter_by(is_compulsory=True, is_active=True).all()
    }
    desired_ids = requested_ids | compulsory
    if not desired_ids:
        raise ApiError("Select at least one domain.", 400, "invalid_domains")

    max_optional = int(current_app.config.get("MAX_OPTIONAL_DOMAINS", 2))
    optional_ids = desired_ids - compulsory
    if len(optional_ids) > max_optional:
        raise ApiError(
            f"You may select at most {max_optional} optional primary domains.",
            400,
            "too_many_optional",
        )

    now = now_utc()
    existing = StudentDomainEnrollment.query.filter_by(student_id=current_user.id).all()
    existing_active = {e.domain_id for e in existing if e.is_active}
    existing_optional = existing_active - compulsory

    # The change lock only applies to swapping optional domains. Adding (or
    # back-filling) a compulsory domain never counts as a change.
    if existing_active and existing_optional != optional_ids:
        domains = Domain.query.filter(Domain.id.in_(desired_ids)).all()
        allows_change = any(
            d.domain_change_allowed_until and d.domain_change_allowed_until >= now for d in domains
        )
        if not allows_change:
            raise ApiError(
                "Domain changes are closed for this batch. Contact an administrator to authorize a change.",
                403,
                "domain_change_locked",
            )

    try:
        for domain_id in desired_ids:
            row = StudentDomainEnrollment.query.filter_by(
                student_id=current_user.id, domain_id=domain_id
            ).first()
            if row is None:
                row = StudentDomainEnrollment(
                    student_id=current_user.id, domain_id=domain_id, is_active=True, enrolled_at=now
                )
                db.session.add(row)
            elif not row.is_active:
                row.is_active = True

        # Deactivate enrollments that were removed while preserving history.
        for row in existing:
            if row.domain_id not in desired_ids:
                row.is_active = False

        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ApiError(
            "Unable to save your domain selection. Please try again.",
            503,
            "save_failed",
        ) from exc

    return ok(
        {
            "message": "Domain selection saved.",
            "enrolled": [
                {**domain_public(d), "progress": domain_progress(current_user.id, d.id)}
                for d in enrolled_domains(current_user.id)
            ],
        }
    )


# ── Learning path ─────────────────────────────────────────────────────────
@student_api.get("/student/domains/<int:domain_id>/learning-path")
@require_roles("student")
def learning_path(domain_id):
    _require_domain(domain_id)
    domain = db.session.get(Domain, domain_id)
    if domain is None:
        raise ApiError("Domain not found.", 404, "not_found")

    days = (
        LearningDay.query.filter(
            LearningDay.domain_id == domain_id,
            LearningDay.status.in_(["published", "locked"]),
        )
        .order_by(LearningDay.day_number.asc())
        .all()
    )
    completions = {
        c.learning_day_id: c
        for c in ContentCompletion.query.filter_by(student_id=current_user.id).all()
    }

    result = []
    first_incomplete = None
    for day in days:
        completion = completions.get(day.id)
        completed = bool(completion and completion.is_day_complete)
        if not completed and first_incomplete is None:
            first_incomplete = day.id
        result.append(
            {
                **day_public(day),
                "completed": completed,
                "completed_at": iso(completion.completed_at) if completion else None,
                "locked": day.is_locked or (day.prerequisite_day_id is not None and not completed),
                "current": False,
            }
        )
    for item in result:
        item["current"] = item["id"] == first_incomplete

    return ok(
        {
            "domain": domain_public(domain),
            "progress": domain_progress(current_user.id, domain_id),
            "days": result,
            "current_day_id": first_incomplete,
        }
    )


@student_api.get("/learning-days/<int:day_id>")
@require_roles("student")
def learning_day_detail(day_id):
    day = db.session.get(LearningDay, day_id)
    if day is None:
        raise ApiError("Learning day not found.", 404, "not_found")
    _require_domain(day.domain_id)
    if day.status not in ("published", "locked"):
        raise ApiError("This learning day is not published yet.", 403, "not_published")

    completion = ContentCompletion.query.filter_by(
        student_id=current_user.id, learning_day_id=day.id
    ).first()
    return ok(
        {
            **day_public(day, include_materials=True),
            "domain": domain_public(day.domain, include_counts=False),
            "completed": bool(completion and completion.is_day_complete),
            "completed_at": iso(completion.completed_at) if completion else None,
            "assessments": [assessment_public(a) for a in day.assessments.all() if a.status == "published"],
        }
    )


@student_api.post("/learning-days/<int:day_id>/complete")
@require_roles("student")
def complete_day(day_id):
    day = db.session.get(LearningDay, day_id)
    if day is None:
        raise ApiError("Learning day not found.", 404, "not_found")
    _require_domain(day.domain_id)
    if day.status != "published" or day.is_locked:
        raise ApiError("This learning day is locked.", 403, "day_locked")

    completion = ContentCompletion.query.filter_by(
        student_id=current_user.id, learning_day_id=day.id
    ).first()
    already = bool(completion and completion.is_day_complete)
    if completion is None:
        completion = ContentCompletion(student_id=current_user.id, learning_day_id=day.id)
        db.session.add(completion)
    if not completion.is_day_complete:
        completion.is_day_complete = True
        completion.completed_at = now_utc()
    db.session.commit()

    return ok(
        {
            "message": "Learning day already completed." if already else "Learning day completed.",
            "already_completed": already,
            "progress": domain_progress(current_user.id, day.domain_id),
        }
    )


@student_api.get("/student/materials")
@require_roles("student")
def materials():
    material_type = request.args.get("type")
    domain_id = get_int(request.args.get("domain_id"), None, name="domain_id")
    domain_ids = enrolled_domain_ids(current_user.id)
    if domain_id:
        _require_domain(domain_id)
        domain_ids = [domain_id]

    query = (
        LearningMaterial.query.join(LearningDay, LearningDay.id == LearningMaterial.learning_day_id)
        .filter(
            LearningDay.domain_id.in_(domain_ids or [-1]),
            LearningDay.status == "published",
            LearningMaterial.status == "published",
        )
    )
    if material_type and material_type != "all":
        query = query.filter(LearningMaterial.material_type == material_type)

    query = query.order_by(LearningDay.day_number.asc(), LearningMaterial.display_order.asc())
    paged = paginate(query, default_per_page=50, max_per_page=200)
    paged["items"] = [
        {
            **material_public(m),
            "domain_id": m.learning_day.domain_id,
            "domain": m.learning_day.domain.name,
            "day_number": m.learning_day.day_number,
            "day_title": m.learning_day.title,
        }
        for m in paged["items"]
    ]
    return ok(paged["items"], meta=paged["meta"])


# ── Assessments ───────────────────────────────────────────────────────────
def _student_assessment_access(assessment, student_id):
    now = now_utc()
    completed_count = AssessmentAttempt.query.filter(
        AssessmentAttempt.student_id == student_id,
        AssessmentAttempt.assessment_id == assessment.id,
        AssessmentAttempt.status != "in_progress",
    ).count()

    auths = AssessmentAuthorization.query.filter(
        AssessmentAuthorization.assessment_id == assessment.id,
        AssessmentAuthorization.is_active == True,
        (AssessmentAuthorization.student_id == student_id) | (AssessmentAuthorization.student_id.is_(None)),
    ).all()
    active_auths = [a for a in auths if not a.valid_until or a.valid_until >= now]

    has_student_unlock = any(a.authorization_type == "student_unlock" and a.student_id == student_id for a in active_auths)
    has_proctor_open = any(a.authorization_type in ("proctor_open", "admin_release") for a in active_auths)

    extra_attempts = sum(a.extra_attempts for a in active_auths if a.authorization_type == "student_unlock")
    total_allowed_attempts = assessment.max_attempts + extra_attempts
    attempts_remaining = max(total_allowed_attempts - completed_count, 0)

    lock_reason = None
    if assessment.status != "published" and not has_proctor_open:
        lock_reason = "not_published"
    elif assessment.scheduled_start and now < assessment.scheduled_start and not has_student_unlock and not has_proctor_open:
        lock_reason = "scheduled_countdown"
    elif assessment.scheduled_end and now > assessment.scheduled_end and not has_student_unlock and not has_proctor_open:
        lock_reason = "window_expired"
    elif attempts_remaining <= 0:
        lock_reason = "no_attempts_left"

    is_accessible = (lock_reason is None)
    return is_accessible, lock_reason, attempts_remaining, completed_count, active_auths


@student_api.get("/student/assessments")
@require_roles("student")
def assessments():
    domain_ids = enrolled_domain_ids(current_user.id)
    now = now_utc()
    query = Assessment.query.filter(
        Assessment.domain_id.in_(domain_ids or [-1]),
        Assessment.status.in_(["published", "scheduled", "closed"]),
    )
    if request.args.get("domain_id"):
        domain_id = get_int(request.args["domain_id"])
        _require_domain(domain_id)
        query = query.filter(Assessment.domain_id == domain_id)

    rows = query.order_by(Assessment.scheduled_start.asc().nulls_last(), Assessment.created_at.desc()).all()
    attempts = (
        AssessmentAttempt.query.filter_by(student_id=current_user.id)
        .order_by(AssessmentAttempt.started_at.desc())
        .all()
    )
    by_assessment: dict[int, list] = {}
    for a in attempts:
        by_assessment.setdefault(a.assessment_id, []).append(a)

    result = []
    for a in rows:
        mine = by_assessment.get(a.id, [])
        active = next((x for x in mine if x.status == "in_progress"), None)
        latest = mine[0] if mine else None
        accessible, lock_reason, remaining, used_count, _ = _student_assessment_access(a, current_user.id)
        result.append(
            {
                **assessment_public(a),
                "available": accessible,
                "lock_reason": lock_reason,
                "attempts_used": used_count,
                "attempts_remaining": remaining,
                "active_attempt_id": active.id if active else None,
                "latest_attempt": attempt_public(latest) if latest else None,
                "is_past": bool(a.scheduled_end and a.scheduled_end < now),
            }
        )
    return ok(result)


@student_api.get("/assessments/<int:assessment_id>/instructions")
@require_roles("student")
def assessment_instructions(assessment_id):
    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None:
        raise ApiError("Assessment not found.", 404, "not_found")
    _require_domain(assessment.domain_id)

    attempts = AssessmentAttempt.query.filter_by(
        student_id=current_user.id, assessment_id=assessment.id
    ).all()
    completed = [a for a in attempts if a.status != "in_progress"]
    active = next((a for a in attempts if a.status == "in_progress"), None)

    accessible, lock_reason, remaining, used_count, auths = _student_assessment_access(assessment, current_user.id)

    return ok(
        {
            **assessment_public(assessment),
            "available": accessible,
            "lock_reason": lock_reason,
            "attempts_used": used_count,
            "attempts_remaining": remaining,
            "active_attempt_id": active.id if active else None,
            "latest_result": attempt_public(completed[0]) if completed else None,
            "is_authorized": len(auths) > 0,
        }
    )


def _attempt_deadline(attempt: AssessmentAttempt):
    candidates = []
    if attempt.assessment.time_limit_minutes:
        candidates.append(attempt.started_at + timedelta(minutes=attempt.assessment.time_limit_minutes))
    if attempt.assessment.scheduled_end:
        candidates.append(attempt.assessment.scheduled_end)
    return min(candidates) if candidates else None


@student_api.post("/assessments/<int:assessment_id>/start")
@require_roles("student")
def start_attempt(assessment_id):
    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None:
        raise ApiError("Assessment not found.", 404, "not_found")
    _require_domain(assessment.domain_id)

    existing = AssessmentAttempt.query.filter_by(
        student_id=current_user.id, assessment_id=assessment.id, status="in_progress"
    ).first()
    if existing:
        return ok(_attempt_payload(existing, resumed=True))

    accessible, lock_reason, remaining, used_count, auths = _student_assessment_access(assessment, current_user.id)
    if not accessible:
        if lock_reason == "no_attempts_left":
            raise ApiError("You have used all allowed attempts for this assessment.", 403, "no_attempts_left")
        elif lock_reason == "scheduled_countdown":
            raise ApiError("This assessment has not opened yet.", 403, "scheduled_countdown")
        elif lock_reason == "window_expired":
            raise ApiError("The window for this assessment has closed.", 403, "window_expired")
        else:
            raise ApiError("This assessment is not currently available.", 403, "not_available")

    attempt = AssessmentAttempt(
        assessment_id=assessment.id,
        student_id=current_user.id,
        status="in_progress",
        started_at=now_utc(),
        total_marks=assessment.total_marks,
        attended=True,
        ip_address=request.remote_addr,
        integrity_flags=[],
    )
    db.session.add(attempt)
    db.session.commit()
    return ok(_attempt_payload(attempt, resumed=False), 201)


def _attempt_payload(attempt, resumed=False):
    import hashlib

    questions = list(attempt.assessment.questions)
    if attempt.assessment.shuffle_questions:
        seed = int(hashlib.sha256(f"q{attempt.id}".encode()).hexdigest(), 16) % (2**31)
        random.Random(seed).shuffle(questions)

    payload_questions = []
    for q in questions:
        data = question_public(q)
        if attempt.assessment.shuffle_options and data.get("options"):
            seed = int(hashlib.sha256(f"o{attempt.id}-{q.id}".encode()).hexdigest(), 16) % (2**31)
            random.Random(seed).shuffle(data["options"])
        payload_questions.append(data)

    saved = {a.question_id: a for a in attempt.answers}
    deadline = _attempt_deadline(attempt)
    return {
        "attempt": attempt_public(attempt),
        "assessment": assessment_public(attempt.assessment),
        "questions": payload_questions,
        "answers": [
            {
                "question_id": a.question_id,
                "selected_option_id": a.selected_option_id,
                "marked_for_review": a.marked_for_review,
            }
            for a in saved.values()
        ],
        "deadline": iso(deadline),
        "server_time": iso(now_utc()),
        "resumed": resumed,
    }


@student_api.get("/attempts/<int:attempt_id>")
@require_roles("student")
def get_attempt(attempt_id):
    attempt = db.session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.student_id != current_user.id:
        raise ApiError("Attempt not found.", 404, "not_found")
    if attempt.status != "in_progress":
        return ok({"attempt": attempt_public(attempt, include_detail=True), "finished": True})
    return ok({**_attempt_payload(attempt, resumed=True), "finished": False})


@student_api.patch("/attempts/<int:attempt_id>/answers")
@require_roles("student")
def save_answer(attempt_id):
    attempt = db.session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.student_id != current_user.id:
        raise ApiError("Attempt not found.", 404, "not_found")
    if attempt.status != "in_progress":
        raise ApiError("This attempt is already submitted.", 409, "attempt_closed")

    deadline = _attempt_deadline(attempt)
    if deadline and now_utc() > deadline:
        raise ApiError("Time is up for this assessment. Submit to finish.", 409, "time_expired")

    data = json_body()
    question_id = get_int(data.get("question_id"), name="question_id")
    question = db.session.get(AssessmentQuestion, question_id)
    if question is None or question.assessment_id != attempt.assessment_id:
        raise ApiError("Question does not belong to this assessment.", 400, "invalid_question")

    option_id = data.get("selected_option_id")
    if option_id is not None:
        option_id = get_int(option_id, name="selected_option_id")
        option = db.session.get(AssessmentOption, option_id)
        if option is None or option.question_id != question.id:
            raise ApiError("Invalid answer option.", 400, "invalid_option")

    answer = AssessmentAnswer.query.filter_by(attempt_id=attempt.id, question_id=question.id).first()
    if answer is None:
        answer = AssessmentAnswer(attempt_id=attempt.id, question_id=question.id)
        db.session.add(answer)
    answer.selected_option_id = option_id
    answer.marked_for_review = bool(data.get("marked_for_review", answer.marked_for_review))
    db.session.commit()
    return ok({"saved": True, "saved_at": iso(now_utc())})


@student_api.post("/attempts/<int:attempt_id>/submit")
@require_roles("student")
def submit_attempt(attempt_id):
    attempt = db.session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.student_id != current_user.id:
        raise ApiError("Attempt not found.", 404, "not_found")
    if attempt.status != "in_progress":
        return ok({"attempt": attempt_public(attempt), "already_submitted": True})

    score = 0
    for answer in attempt.answers:
        if answer.selected_option_id:
            option = db.session.get(AssessmentOption, answer.selected_option_id)
            if option and option.is_correct:
                answer.is_correct = True
                answer.marks_awarded = answer.question.marks
                score += answer.question.marks or 0
            else:
                answer.is_correct = False
                answer.marks_awarded = 0

    for cs in attempt.coding_submissions:
        score += cs.marks_awarded or 0

    attempt.score = score
    attempt.submitted_at = now_utc()
    attempt.time_taken_seconds = int((attempt.submitted_at - attempt.started_at).total_seconds())

    grading_mode = getattr(attempt.assessment, "grading_mode", "automatic") or "automatic"
    if grading_mode == "automatic" or attempt.assessment.assessment_type in ("mcq", "betting"):
        attempt.status = "graded"
        if attempt.assessment.assessment_type == "betting":
            try:
                apply_betting_points(attempt, created_by=current_user.id)
            except Exception:
                current_app.logger.exception("Failed to apply betting points")
        else:
            attendance_pts = getattr(attempt.assessment, "attendance_points", 0) or 0
            total_pts = score + attendance_pts
            if total_pts > 0:
                try:
                    existing_entry = find_ledger_entry(
                        student_id=current_user.id,
                        transaction_type="assessment",
                        reference_type="AssessmentAttempt",
                        reference_id=attempt.id,
                    )
                    if not existing_entry:
                        award_points(
                            student_id=current_user.id,
                            points=total_pts,
                            transaction_type="assessment",
                            domain_id=attempt.assessment.domain_id,
                            reference_type="AssessmentAttempt",
                            reference_id=attempt.id,
                            description=f"Assessment '{attempt.assessment.title}' (Score: {score} pts, Attendance: {attendance_pts} pts)",
                            created_by=attempt.assessment.created_by or current_user.id,
                        )
                except Exception:
                    current_app.logger.exception("Failed to award assessment points")
    else:
        attempt.status = "submitted"

    db.session.commit()
    return ok({"attempt": attempt_public(attempt, include_detail=True)})


@student_api.post("/attempts/<int:attempt_id>/run-code")
@require_roles("student")
def run_code_test(attempt_id):
    attempt = db.session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.student_id != current_user.id:
        raise ApiError("Attempt not found.", 404, "not_found")
    if attempt.status != "in_progress":
        raise ApiError("This attempt is already submitted.", 409, "attempt_closed")

    data = json_body()
    language = (data.get("language") or "python").strip()
    code = data.get("code") or ""
    stdin = data.get("stdin") or data.get("custom_input") or ""
    if not code.strip():
        raise ApiError("Code cannot be empty.", 400, "empty_code")

    from app.services.code_runner import run_code
    result = run_code(language, code, stdin=stdin, timeout_seconds=5.0)
    return ok(result)


@student_api.post("/attempts/<int:attempt_id>/code")
@require_roles("student")
def submit_code(attempt_id):
    attempt = db.session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.student_id != current_user.id:
        raise ApiError("Attempt not found.", 404, "not_found")
    if attempt.status != "in_progress":
        raise ApiError("This attempt is already submitted.", 409, "attempt_closed")

    data = json_body()
    question_id = get_int(data.get("question_id"), name="question_id")
    question = db.session.get(AssessmentQuestion, question_id)
    if question is None or question.assessment_id != attempt.assessment_id:
        raise ApiError("Question does not belong to this assessment.", 400, "invalid_question")
    if question.question_type != "coding":
        raise ApiError("This question does not accept code.", 400, "not_coding")

    language = (data.get("language") or "python").strip().lower()
    code = data.get("code") or ""
    if not code.strip():
        raise ApiError("Code cannot be empty.", 400, "invalid_code")
    if len(code) > 100_000:
        raise ApiError("Code is too large.", 400, "code_too_large")

    from app.services.code_runner import evaluate_test_cases
    test_cases = question.test_cases.all()
    eval_result = evaluate_test_cases(language, code, test_cases)

    submission = CodingSubmission.query.filter_by(attempt_id=attempt.id, question_id=question.id).first()
    if submission is None:
        submission = CodingSubmission(attempt_id=attempt.id, question_id=question.id)
        db.session.add(submission)
    submission.language = language
    submission.code = code
    submission.status = "passed" if eval_result["all_passed"] else "failed"
    submission.test_results = eval_result["results"]
    max_marks = question.marks or 10
    submission.marks_awarded = int((eval_result["score_percent"] / 100) * max_marks)
    submission.submitted_at = now_utc()
    db.session.commit()

    return ok(
        {
            "message": f"Code evaluated: {eval_result['passed']}/{eval_result['total']} test cases passed.",
            "execution": "evaluated",
            "submission_id": submission.id,
            "status": submission.status,
            "marks_awarded": submission.marks_awarded,
            "results": eval_result["results"],
            "passed": eval_result["passed"],
            "total": eval_result["total"],
        }
    )


@student_api.post("/attempts/<int:attempt_id>/integrity")
@require_roles("student")
def integrity_event(attempt_id):
    attempt = db.session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.student_id != current_user.id:
        raise ApiError("Attempt not found.", 404, "not_found")
    data = json_body(required=False)
    event = (data.get("event") or "unknown")[:80]
    flags = list(attempt.integrity_flags or [])
    flags.append({"event": event, "at": iso(now_utc())})
    attempt.integrity_flags = flags
    db.session.commit()
    return ok({"recorded": True, "note": "Integrity signals require human review and never change scores automatically."})


@student_api.get("/attempts/<int:attempt_id>/result")
@require_roles("student")
def attempt_result(attempt_id):
    attempt = db.session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.student_id != current_user.id:
        raise ApiError("Attempt not found.", 404, "not_found")
    if attempt.status == "in_progress":
        raise ApiError("This attempt is not submitted yet.", 409, "in_progress")

    policy = attempt.assessment.show_results_after
    if policy == "never":
        raise ApiError("Results for this assessment are not released.", 403, "results_hidden")
    if policy == "grading" and attempt.status != "graded":
        raise ApiError("Results will be available after grading.", 403, "results_pending")

    detail = attempt_public(attempt, include_detail=True)
    detail["show_correct_answers"] = bool(attempt.assessment.show_correct_answers)
    detail["review"] = []
    if attempt.assessment.show_correct_answers:
        for answer in attempt.answers:
            detail["review"].append(
                {
                    "question_id": answer.question_id,
                    "question": answer.question.question_text,
                    "selected_option_id": answer.selected_option_id,
                    "correct_option_ids": [o.id for o in answer.question.options if o.is_correct],
                    "is_correct": answer.is_correct,
                    "marks_awarded": answer.marks_awarded,
                    "marks": answer.question.marks,
                }
            )
    return ok(detail)


# ── Elite Tasks ───────────────────────────────────────────────────────────
def _task_available(task: EliteTask, domain_ids: list[int]) -> bool:
    if task.status != "active":
        return False
    now = now_utc()
    if task.publish_at and task.publish_at > now:
        return False
    if task.due_date and task.due_date < now:
        return False
    if task.domain_id is not None and task.domain_id not in domain_ids:
        return False
    return True


@student_api.get("/student/tasks")
@require_roles("student")
def elite_tasks():
    domain_ids = enrolled_domain_ids(current_user.id)
    tasks = (
        EliteTask.query.filter(
            or_(EliteTask.domain_id.is_(None), EliteTask.domain_id.in_(domain_ids or [-1])),
            EliteTask.status.in_(["active", "upcoming", "completed"]),
        )
        .order_by(EliteTask.due_date.asc().nulls_last())
        .all()
    )
    b_date = business_date()
    today_evidences = {
        e.task_id: e
        for e in TaskEvidence.query.filter_by(
            student_id=current_user.id, submission_date=b_date
        ).all()
    }
    all_evidences = {
        e.task_id: e
        for e in TaskEvidence.query.filter_by(student_id=current_user.id)
        .order_by(TaskEvidence.submitted_at.desc())
        .all()
    }

    rows = []
    for t in tasks:
        today_ev = today_evidences.get(t.id)
        latest_ev = all_evidences.get(t.id)
        is_available = _task_available(t, domain_ids)

        if today_ev:
            state = "completed"
        elif is_available:
            state = "available"
        else:
            state = "upcoming" if t.status != "completed" else "completed"

        rows.append(
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "instructions": t.instructions,
                "domain_id": t.domain_id,
                "domain": t.domain.name if t.domain else None,
                "category": t.category,
                "potential_points": t.potential_points,
                "allowed_evidence_formats": t.allowed_evidence_formats or ["pdf", "image", "zip", "link"],
                "status": t.status,
                "due_date": iso(t.due_date),
                "publish_at": iso(t.publish_at),
                "state": state,
                "submitted_today": today_ev is not None,
                "can_submit": today_ev is None and is_available,
                "submission": evidence_public(today_ev or latest_ev) if (today_ev or latest_ev) else None,
            }
        )
    return ok({"tasks": rows, "business_date": b_date.isoformat()})


@student_api.get("/student/tasks/submissions")
@require_roles("student")
def my_task_submissions():
    query = TaskEvidence.query.filter_by(student_id=current_user.id).order_by(
        TaskEvidence.submitted_at.desc()
    )
    paged = paginate(query)
    return ok([evidence_public(e) for e in paged["items"]], meta=paged["meta"])


@student_api.post("/student/tasks/<int:task_id>/submit")
@require_roles("student")
def submit_task(task_id):
    task = db.session.get(EliteTask, task_id)
    if task is None:
        raise ApiError("Task not found.", 404, "not_found")
    domain_ids = enrolled_domain_ids(current_user.id)
    if not _task_available(task, domain_ids):
        raise ApiError("This task is not available.", 403, "task_unavailable")

    allowed, message = can_submit_daily_task(current_user.id, task_id=task.id)
    if not allowed:
        raise ApiError(message, 409, "daily_limit")

    data = json_body()
    evidence_type = (data.get("evidence_type") or "link").strip().lower()
    if evidence_type not in {"file", "link"}:
        raise ApiError("Evidence type must be file or link.", 400, "invalid_evidence")

    allowed_formats = [f.lower() for f in (task.allowed_evidence_formats or [])]
    if evidence_type == "link":
        link_url = (data.get("link_url") or "").strip()
        if not link_url.startswith(("http://", "https://")):
            raise ApiError("Provide a valid http(s) evidence link.", 400, "invalid_link")
        if allowed_formats and "link" not in allowed_formats:
            raise ApiError("Link evidence is not permitted for this task.", 400, "format_not_allowed")
        evidence = {"evidence_type": "link", "link_url": link_url, "notes": data.get("notes")}
    else:
        file_key = (data.get("file_key") or "").strip()
        if not file_key:
            raise ApiError("Upload a file before submitting.", 400, "missing_file")
        file_type = (data.get("file_type") or "").split("/")[-1].lower()
        if allowed_formats and file_type and file_type not in allowed_formats and file_type not in (
            "pdf",
            "png",
            "jpg",
            "jpeg",
            "zip",
            "doc",
            "docx",
        ):
            raise ApiError("This evidence format is not permitted for this task.", 400, "format_not_allowed")
        evidence = {
            "evidence_type": "file",
            "file_key": file_key,
            "file_name": data.get("file_name"),
            "file_size": data.get("file_size"),
            "file_type": file_type,
            "notes": data.get("notes"),
        }

    if not evidence.get("notes") and evidence_type == "link":
        evidence["notes"] = data.get("notes")

    try:
        row = submit_daily_task(task=task, student_id=current_user.id, evidence=evidence)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        raise ApiError(str(exc), 409, "daily_limit") from exc

    return ok(evidence_public(row), 201)


# ── Requests ──────────────────────────────────────────────────────────────
REQUEST_CATEGORIES = {
    "assessment_reeval",
    "content_access",
    "technical",
    "point_discrepancy",
    "general",
}


@student_api.get("/student/requests")
@require_roles("student")
def my_requests():
    query = StudentRequest.query.filter_by(student_id=current_user.id).order_by(
        StudentRequest.created_at.desc()
    )
    paged = paginate(query, default_per_page=20)
    return ok(
        [
            {
                "id": r.id,
                "category": r.category,
                "subject": r.subject,
                "status": r.status,
                "created_at": iso(r.created_at),
                "updated_at": iso(r.updated_at),
                "handler": r.handler.name if r.handler else None,
                "message_count": len(r.messages),
                "last_message": r.messages[-1].message if r.messages else None,
            }
            for r in paged["items"]
        ],
        meta=paged["meta"],
    )


@student_api.post("/student/requests")
@require_roles("student")
def create_request():
    data = json_body()
    category = (data.get("category") or "general").strip()
    subject = (data.get("subject") or "").strip()
    message = (data.get("message") or "").strip()
    if category not in REQUEST_CATEGORIES:
        raise ApiError("Choose a valid request category.", 400, "invalid_category")
    if len(subject) < 3:
        raise ApiError("Please provide a subject.", 400, "invalid_subject")
    if len(message) < 5:
        raise ApiError("Please describe your request.", 400, "invalid_message")

    row = StudentRequest(student_id=current_user.id, category=category, subject=subject, status="open")
    db.session.add(row)
    db.session.flush()
    db.session.add(RequestMessage(request_id=row.id, sender_id=current_user.id, message=message))
    db.session.commit()
    return ok({"id": row.id, "message": "Request submitted."}, 201)


@student_api.get("/student/appeals")
@require_roles("student")
def my_appeals():
    from app.models import Appeal

    rows = Appeal.query.filter_by(student_id=current_user.id).order_by(Appeal.created_at.desc()).all()
    result = []
    for a in rows:
        reviewer_name = a.assigned_reviewer.name if a.assigned_reviewer else None
        reviewer_email = a.assigned_reviewer.email if a.assigned_reviewer else None
        result.append(
            {
                "id": a.id,
                "attempt_id": a.attempt_id,
                "evidence_id": a.evidence_id,
                "assessment": a.attempt.assessment.title if a.attempt else None,
                "original_score": a.original_score,
                "reason": a.reason,
                "status": a.status,
                "decision": a.decision,
                "new_score": a.new_score,
                "assigned_to": a.assigned_to,
                "assigned_reviewer": reviewer_name,
                "assigned_reviewer_email": reviewer_email,
                "instruction_message": (
                    f"You are instructed to meet the faculty {reviewer_name} ({reviewer_email})."
                    if a.assigned_to and reviewer_name
                    else None
                ),
                "review_comments": a.review_comments,
                "created_at": iso(a.created_at),
                "resolved_at": iso(a.resolved_at),
            }
        )
    return ok(result)


@student_api.post("/student/appeals")
@require_roles("student")
def create_appeal():
    from app.models import Appeal

    data = json_body()
    attempt_id = data.get("attempt_id")
    evidence_id = data.get("evidence_id")
    reason = (data.get("reason") or "").strip()
    supporting = (data.get("supporting_info") or "").strip()
    if not reason or len(reason) < 10:
        raise ApiError("Please provide a detailed appeal reason.", 400, "invalid_reason")

    attempt = None
    evidence = None
    if attempt_id:
        attempt = db.session.get(AssessmentAttempt, get_int(attempt_id))
        if attempt is None or attempt.student_id != current_user.id:
            raise ApiError("Assessment attempt not found.", 404, "not_found")
        if attempt.status == "in_progress":
            raise ApiError("Submit the assessment before appealing.", 400, "invalid_appeal")
        original = attempt.score or 0
    elif evidence_id:
        evidence = db.session.get(TaskEvidence, get_int(evidence_id))
        if evidence is None or evidence.student_id != current_user.id:
            raise ApiError("Task submission not found.", 404, "not_found")
        original = evidence.points_awarded or 0
    else:
        raise ApiError("Link an assessment or task submission.", 400, "missing_reference")

    existing = Appeal.query.filter_by(student_id=current_user.id, status="open").filter(
        or_(
            Appeal.attempt_id == (attempt.id if attempt else None),
            Appeal.evidence_id == (evidence.id if evidence else None),
        )
    ).first()
    if existing and (attempt or evidence):
        raise ApiError("An open appeal already exists for this record.", 409, "duplicate_appeal")

    row = Appeal(
        student_id=current_user.id,
        attempt_id=attempt.id if attempt else None,
        evidence_id=evidence.id if evidence else None,
        original_score=original,
        reason=reason,
        supporting_info=supporting or None,
        status="open",
    )
    db.session.add(row)
    db.session.commit()
    return ok({"id": row.id, "message": "Appeal submitted."}, 201)


# ── Notifications / announcements / leaderboards ──────────────────────────
@student_api.get("/announcements")
def announcements():
    if not current_user.is_authenticated:
        raise ApiError("Authentication required.", 401, "unauthenticated")
    rows = active_announcements(current_user).limit(50).all()
    return ok(
        [
            {
                "id": a.id,
                "title": a.title,
                "content": a.content,
                "category": a.category,
                "target_audience": a.target_audience,
                "target_domain": a.target_domain.name if a.target_domain else None,
                "publish_at": iso(a.publish_at),
                "expires_at": iso(a.expires_at),
                "created_at": iso(a.created_at),
            }
            for a in rows
        ]
    )


@student_api.get("/notifications")
def notifications():
    if not current_user.is_authenticated:
        raise ApiError("Authentication required.", 401, "unauthenticated")
    rows = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return ok(
        [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "type": n.notification_type,
                "link_url": n.link_url,
                "is_read": n.is_read,
                "created_at": iso(n.created_at),
            }
            for n in rows
        ],
        unread=sum(1 for n in rows if not n.is_read),
    )


@student_api.get("/leaderboards")
def leaderboards():
    if not current_user.is_authenticated:
        raise ApiError("Authentication required.", 401, "unauthenticated")
    scope = (request.args.get("scope") or "overall").lower()
    domain_id = get_int(request.args.get("domain_id"), None, name="domain_id")
    department = (request.args.get("department") or "").strip() or None
    month = request.args.get("month")
    limit = get_int(request.args.get("limit"), 20, minimum=1, maximum=100, name="limit")

    # If student, restrict domain queries strictly to enrolled domains
    if current_user.role == "student" and domain_id:
        enrolled_ids = enrolled_domain_ids(current_user.id)
        if domain_id not in enrolled_ids:
            domain_id = enrolled_ids[0] if enrolled_ids else None

    rows = leaderboard(
        scope=scope,
        domain_id=domain_id,
        month=month,
        department=department,
        limit=limit,
    )
    my_ranks = (
        student_leaderboard_ranks(current_user.id)
        if current_user.role == "student"
        else None
    )
    return ok(
        {
            "scope": scope,
            "month": month,
            "department": department,
            "entries": rows,
            "me": next((r for r in rows if r["student_id"] == current_user.id), None),
            "my_ranks": my_ranks,
        }
    )
