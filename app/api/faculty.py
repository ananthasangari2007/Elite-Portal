"""Faculty Coordinator API — grading queue, appeals, point adjustments, requests."""
from __future__ import annotations

from datetime import timedelta
from flask import Blueprint, request
from flask_login import current_user

from app import db
from app.api.utils import (
    ApiError,
    assessment_public,
    attempt_public,
    authorization_public,
    domain_public,
    evidence_public,
    get_int,
    iso,
    json_body,
    ok,
    paginate,
    require_roles,
)
from app.models import (
    Appeal,
    Assessment,
    AssessmentAttempt,
    AssessmentAuthorization,
    Domain,
    GradingHistory,
    PointAdjustmentRequest,
    StudentRequest,
    TaskEvidence,
    User,
)
from app.services.portal import (
    audit,
    award_points,
    faculty_dashboard,
    find_ledger_entry,
    notify,
    now_utc,
    points_breakdown,
    reverse_points,
    scoped_student_ids,
)

faculty_api = Blueprint("api_faculty", __name__, url_prefix="/api/v1")


def _scope_ids():
    scoped = scoped_student_ids(current_user)
    if scoped is None:
        return None
    return scoped


def _assert_in_scope(student_id):
    scoped = _scope_ids()
    if scoped is not None and student_id not in scoped:
        raise ApiError("You do not have access to this student.", 403, "forbidden")


@faculty_api.get("/faculty/dashboard")
@require_roles("faculty", "admin")
def dashboard():
    return ok(faculty_dashboard(current_user))


@faculty_api.get("/faculty/domains")
@require_roles("faculty", "admin")
def my_domains():
    from app.services.portal import domain_ids_for

    if current_user.role == "admin":
        rows = Domain.query.order_by(Domain.name).all()
    else:
        ids = domain_ids_for(current_user)
        rows = Domain.query.filter(Domain.id.in_(ids or [-1])).order_by(Domain.name).all()
    return ok([domain_public(d) for d in rows])


# ── Task evidence approvals ───────────────────────────────────────────────
@faculty_api.get("/faculty/task-evidence")
@require_roles("faculty", "coordinator", "admin")
def task_evidence():
    scoped = _scope_ids()
    query = TaskEvidence.query
    if scoped is not None:
        query = query.filter(TaskEvidence.student_id.in_(scoped or [-1]))
    if request.args.get("status"):
        query = query.filter(TaskEvidence.status == request.args["status"])
    query = query.order_by(TaskEvidence.submitted_at.desc())
    paged = paginate(query)
    return ok([evidence_public(e) for e in paged["items"]], meta=paged["meta"])


@faculty_api.post("/faculty/task-evidence/<int:evidence_id>/review")
@require_roles("faculty", "coordinator", "admin")
def review_evidence(evidence_id):
    evidence = db.session.get(TaskEvidence, evidence_id)
    if evidence is None:
        raise ApiError("Evidence not found.", 404, "not_found")
    _assert_in_scope(evidence.student_id)
    if evidence.status != "pending":
        raise ApiError("This evidence has already been reviewed.", 409, "already_reviewed")

    data = json_body()
    decision = (data.get("decision") or "").strip().lower()
    if decision not in {"approved", "rejected"}:
        raise ApiError("Decision must be approved or rejected.", 400, "invalid_decision")
    feedback = (data.get("feedback") or "").strip()

    if decision == "approved":
        points = get_int(data.get("points"), evidence.task.potential_points, 0, name="points")
        max_points = evidence.task.potential_points or 0
        if points > max_points:
            raise ApiError("Awarded points cannot exceed the task points.", 400, "invalid_points")
        evidence.status = "approved"
        evidence.points_awarded = points
        evidence.reviewed_by = current_user.id
        evidence.reviewed_at = now_utc()
        evidence.reviewer_feedback = feedback or "Approved."
        ledger = award_points(
            student_id=evidence.student_id,
            points=points,
            transaction_type="task_approval",
            reference_type="TaskEvidence",
            reference_id=evidence.id,
            domain_id=evidence.task.domain_id,
            description=f"Elite Task approved: {evidence.task.title}",
            created_by=current_user.id,
        )
        evidence.point_ledger_id = ledger.id
        notify(
            evidence.student_id,
            "Elite Task approved",
            f"“{evidence.task.title}” was approved. +{points} points.",
            "success",
            link_url="/student/tasks",
        )
        action = "task.approve"
    else:
        evidence.status = "rejected"
        evidence.points_awarded = 0
        evidence.reviewed_by = current_user.id
        evidence.reviewed_at = now_utc()
        evidence.reviewer_feedback = feedback or "Rejected."
        notify(
            evidence.student_id,
            "Elite Task rejected",
            f"“{evidence.task.title}” was not approved. {feedback}",
            "warning",
            link_url="/student/tasks",
        )
        action = "task.reject"

    db.session.add(
        GradingHistory(evidence_id=evidence.id, graded_by=current_user.id, action=action, score=evidence.points_awarded, feedback=feedback)
    )
    audit(current_user.id, action, target_type="TaskEvidence", target_id=evidence.id)
    db.session.commit()
    return ok(evidence_public(evidence))


# ── Appeals ───────────────────────────────────────────────────────────────
def _appeal_payload(appeal):
    assigned_name = appeal.assigned_reviewer.name if appeal.assigned_reviewer else None
    assigned_email = appeal.assigned_reviewer.email if appeal.assigned_reviewer else None
    return {
        "id": appeal.id,
        "student_id": appeal.student_id,
        "student": appeal.student.name,
        "register_number": appeal.student.register_number,
        "attempt_id": appeal.attempt_id,
        "evidence_id": appeal.evidence_id,
        "reference": (
            appeal.attempt.assessment.title
            if appeal.attempt
            else (appeal.evidence.task.title if appeal.evidence else None)
        ),
        "reference_type": "assessment" if appeal.attempt_id else "task",
        "original_score": appeal.original_score,
        "reason": appeal.reason,
        "supporting_info": appeal.supporting_info,
        "status": appeal.status,
        "assigned_to": appeal.assigned_to,
        "assigned_reviewer": assigned_name,
        "assigned_reviewer_email": assigned_email,
        "instruction_message": (
            f"You are instructed to meet the faculty {assigned_name} ({assigned_email})"
            if appeal.assigned_to and assigned_name
            else None
        ),
        "review_comments": appeal.review_comments,
        "decision": appeal.decision,
        "new_score": appeal.new_score,
        "created_at": iso(appeal.created_at),
        "updated_at": iso(appeal.updated_at),
        "resolved_at": iso(appeal.resolved_at),
    }


@faculty_api.get("/faculty/appeals")
@require_roles("faculty", "coordinator", "admin")
def appeals():
    scoped = _scope_ids()
    query = Appeal.query
    if scoped is not None:
        query = query.filter(Appeal.student_id.in_(scoped or [-1]))
    if request.args.get("status"):
        query = query.filter(Appeal.status == request.args["status"])
    query = query.order_by(Appeal.created_at.desc())
    paged = paginate(query)
    return ok([_appeal_payload(a) for a in paged["items"]], meta=paged["meta"])


@faculty_api.post("/faculty/appeals/<int:appeal_id>/assign")
@require_roles("faculty", "admin")
def assign_appeal(appeal_id):
    appeal = db.session.get(Appeal, appeal_id)
    if appeal is None:
        raise ApiError("Appeal not found.", 404, "not_found")
    _assert_in_scope(appeal.student_id)
    appeal.assigned_to = current_user.id
    if appeal.status == "open":
        appeal.status = "in_review"

    # Immediately notify the student that they are instructed to meet the faculty
    notify(
        appeal.student_id,
        "Appeal Under Review — Action Required",
        f"You are instructed to meet the faculty {current_user.name} ({current_user.email}) regarding your appeal.",
        link_url="/student/appeals",
    )
    db.session.commit()
    return ok(_appeal_payload(appeal))


@faculty_api.post("/faculty/appeals/<int:appeal_id>/decision")
@require_roles("faculty", "admin")
def decide_appeal(appeal_id):
    appeal = db.session.get(Appeal, appeal_id)
    if appeal is None:
        raise ApiError("Appeal not found.", 404, "not_found")
    _assert_in_scope(appeal.student_id)
    if appeal.status in {"resolved", "rejected"}:
        raise ApiError("This appeal is already closed.", 409, "already_closed")

    data = json_body()
    action = (data.get("action") or "").strip().lower()
    if action not in {"uphold", "reject", "overturn", "partial"}:
        raise ApiError("Choose a valid decision.", 400, "invalid_decision")
    comments = (data.get("review_comments") or "").strip()

    if action == "reject":
        appeal.status = "rejected"
        appeal.decision = "upheld"
        appeal.review_comments = comments
        appeal.resolved_by = current_user.id
        appeal.resolved_at = now_utc()
    else:
        new_score = get_int(data.get("new_score"), appeal.original_score, 0, name="new_score")
        appeal.decision = "overturned" if action in {"overturn", "uphold"} else "partial"
        appeal.new_score = new_score
        appeal.review_comments = comments
        appeal.status = "resolved"
        appeal.resolved_by = current_user.id
        appeal.resolved_at = now_utc()

        if appeal.attempt_id:
            attempt = db.session.get(AssessmentAttempt, appeal.attempt_id)
            if attempt and new_score is not None:
                max_marks = attempt.total_marks or attempt.assessment.total_marks or 0
                if new_score > max_marks:
                    raise ApiError("New score cannot exceed total marks.", 400, "invalid_score")
                old = attempt.score
                attempt.score = new_score
                attempt.graded_at = now_utc()
                attempt.graded_by = current_user.id
                db.session.add(
                    GradingHistory(
                        attempt_id=attempt.id,
                        graded_by=current_user.id,
                        action="appeal_adjust",
                        score=new_score,
                        previous_score=old,
                        feedback=comments,
                    )
                )
                if attempt.assessment.assessment_type == "betting":
                    existing = find_ledger_entry(attempt.student_id, "betting_assessment", "AssessmentAttempt", attempt.id)
                    if existing:
                        reverse_points(existing, current_user.id)
                    from app.services.portal import apply_betting_points

                    apply_betting_points(attempt, created_by=current_user.id)
                else:
                    existing = find_ledger_entry(attempt.student_id, "assessment", "AssessmentAttempt", attempt.id)
                    if existing:
                        reverse_points(existing, current_user.id)
                    if new_score > 0:
                        award_points(
                            student_id=attempt.student_id,
                            points=new_score,
                            transaction_type="assessment",
                            reference_type="AssessmentAttempt",
                            reference_id=attempt.id,
                            domain_id=attempt.assessment.domain_id,
                            description=f"Appeal adjustment: {attempt.assessment.title}",
                            created_by=current_user.id,
                        )
        elif appeal.evidence_id:
            evidence = db.session.get(TaskEvidence, appeal.evidence_id)
            if evidence:
                old = evidence.points_awarded or 0
                evidence.points_awarded = new_score
                evidence.status = "approved"
                evidence.reviewed_by = current_user.id
                evidence.reviewed_at = now_utc()
                existing = find_ledger_entry(evidence.student_id, "task_approval", "TaskEvidence", evidence.id)
                if existing:
                    reverse_points(existing, current_user.id)
                if new_score > 0:
                    ledger = award_points(
                        student_id=evidence.student_id,
                        points=new_score,
                        transaction_type="task_approval",
                        reference_type="TaskEvidence",
                        reference_id=evidence.id,
                        domain_id=evidence.task.domain_id,
                        description=f"Appeal adjustment: {evidence.task.title}",
                        created_by=current_user.id,
                    )
                    evidence.point_ledger_id = ledger.id

    notify(
        appeal.student_id,
        "Appeal decision",
        f"Your appeal was {appeal.status}. {comments}",
        "info",
        link_url="/student/appeals",
    )
    audit(current_user.id, f"appeal.{action}", target_type="Appeal", target_id=appeal.id)
    db.session.commit()
    return ok(_appeal_payload(appeal))


# ── Point adjustments ─────────────────────────────────────────────────────
def _adjustment_payload(row):
    return {
        "id": row.id,
        "student_id": row.student_id,
        "student": row.student.name,
        "register_number": row.student.register_number,
        "request_type": row.request_type,
        "current_points": row.current_points,
        "requested_points": row.requested_points,
        "delta": row.requested_points - row.current_points,
        "reason": row.reason,
        "requested_by": row.requester.name if row.requester else None,
        "status": row.status,
        "reviewed_by": row.reviewer.name if row.reviewer else None,
        "review_notes": row.review_notes,
        "created_at": iso(row.created_at),
        "reviewed_at": iso(row.reviewed_at),
    }


@faculty_api.get("/faculty/point-adjustments")
@require_roles("faculty", "coordinator", "admin")
def point_adjustments():
    scoped = _scope_ids()
    query = PointAdjustmentRequest.query
    if scoped is not None:
        query = query.filter(PointAdjustmentRequest.student_id.in_(scoped or [-1]))
    if request.args.get("status"):
        query = query.filter(PointAdjustmentRequest.status == request.args["status"])
    query = query.order_by(PointAdjustmentRequest.created_at.desc())
    paged = paginate(query)
    return ok([_adjustment_payload(r) for r in paged["items"]], meta=paged["meta"])


@faculty_api.post("/faculty/point-adjustments")
@require_roles("faculty", "coordinator", "admin")
def create_adjustment():
    data = json_body()
    student_id = get_int(data.get("student_id"), name="student_id")
    student = db.session.get(User, student_id)
    if student is None or student.role != "student":
        raise ApiError("Student not found.", 404, "not_found")
    _assert_in_scope(student_id)

    request_type = (data.get("request_type") or "other").strip()
    if request_type not in {"assessment_correction", "task_recount", "bonus", "penalty_reversal", "other"}:
        raise ApiError("Choose a valid request type.", 400, "invalid_type")
    reason = (data.get("reason") or "").strip()
    if len(reason) < 5:
        raise ApiError("Provide a reason.", 400, "invalid_reason")
    current = points_breakdown(student_id)["total"]
    requested = get_int(data.get("requested_points"), current, 0, name="requested_points")

    row = PointAdjustmentRequest(
        student_id=student_id,
        request_type=request_type,
        current_points=current,
        requested_points=requested,
        reason=reason,
        requested_by=current_user.id,
        status="pending",
    )
    db.session.add(row)
    db.session.commit()
    return ok(_adjustment_payload(row), 201)


@faculty_api.post("/faculty/point-adjustments/<int:adjustment_id>/review")
@require_roles("faculty", "admin")
def review_adjustment(adjustment_id):
    row = db.session.get(PointAdjustmentRequest, adjustment_id)
    if row is None:
        raise ApiError("Adjustment request not found.", 404, "not_found")
    _assert_in_scope(row.student_id)
    if row.status != "pending":
        raise ApiError("This request has already been reviewed.", 409, "already_reviewed")

    data = json_body()
    decision = (data.get("decision") or "").strip().lower()
    if decision not in {"approved", "rejected"}:
        raise ApiError("Decision must be approved or rejected.", 400, "invalid_decision")
    notes = (data.get("review_notes") or "").strip()

    row.status = decision
    row.reviewed_by = current_user.id
    row.review_notes = notes
    row.reviewed_at = now_utc()

    if decision == "approved":
        delta = row.requested_points - row.current_points
        entry = award_points(
            student_id=row.student_id,
            points=delta,
            transaction_type="adjustment",
            reference_type="PointAdjustmentRequest",
            reference_id=row.id,
            description=f"Point adjustment ({row.request_type})",
            created_by=current_user.id,
            is_override=True,
            override_reason=row.reason,
        )
        row.point_ledger_id = entry.id
        notify(
            row.student_id,
            "Points adjusted",
            f"Your points were adjusted by {delta:+d}. {notes}",
            "info",
            link_url="/student/points",
        )

    audit(current_user.id, f"point_adjustment.{decision}", target_type="PointAdjustmentRequest", target_id=row.id)
    db.session.commit()
    return ok(_adjustment_payload(row))


# ── Student request inbox ─────────────────────────────────────────────────
@faculty_api.get("/faculty/requests")
@require_roles("faculty", "coordinator", "admin")
def request_inbox():
    scoped = _scope_ids()
    query = StudentRequest.query
    if scoped is not None:
        query = query.filter(StudentRequest.student_id.in_(scoped or [-1]))
    if request.args.get("status"):
        query = query.filter(StudentRequest.status == request.args["status"])
    if request.args.get("category"):
        query = query.filter(StudentRequest.category == request.args["category"])
    query = query.order_by(StudentRequest.updated_at.desc())
    paged = paginate(query)
    return ok(
        [
            {
                "id": r.id,
                "student": r.student.name,
                "register_number": r.student.register_number,
                "category": r.category,
                "subject": r.subject,
                "status": r.status,
                "handler": r.handler.name if r.handler else None,
                "message_count": len(r.messages),
                "updated_at": iso(r.updated_at),
                "created_at": iso(r.created_at),
            }
            for r in paged["items"]
        ],
        meta=paged["meta"],
    )


@faculty_api.get("/faculty/analytics")
@require_roles("faculty", "coordinator", "admin")
def analytics():
    from app.api.coordinator import analytics as coordinator_analytics

    return coordinator_analytics()


# ── Assessment Authorization Desk ─────────────────────────────────────────
@faculty_api.get("/faculty/assessments")
@require_roles("faculty", "coordinator", "admin")
def list_faculty_assessments():
    from app.services.portal import domain_ids_for
    ids = domain_ids_for(current_user) if current_user.role != "admin" else None
    query = Assessment.query
    if ids is not None:
        query = query.filter(Assessment.domain_id.in_(ids or [-1]))
    rows = query.order_by(Assessment.created_at.desc()).all()
    return ok([assessment_public(a) for a in rows])


@faculty_api.get("/faculty/authorizations")
@require_roles("faculty", "coordinator", "admin")
def list_authorizations():
    auths = AssessmentAuthorization.query.order_by(AssessmentAuthorization.created_at.desc()).all()
    return ok([authorization_public(a) for a in auths])


@faculty_api.post("/faculty/assessments/<int:assessment_id>/authorize-student")
@require_roles("faculty", "coordinator", "admin")
def authorize_student(assessment_id):
    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None:
        raise ApiError("Assessment not found.", 404, "not_found")
    data = json_body()
    student_id = get_int(data.get("student_id"), name="student_id")
    student = db.session.get(User, student_id)
    if student is None or student.role != "student":
        raise ApiError("Student not found.", 404, "student_not_found")
    _assert_in_scope(student.id)

    reason = (data.get("reason") or "Faculty override authorization").strip()
    extra_attempts = get_int(data.get("extra_attempts"), 1, minimum=1, name="extra_attempts")
    valid_minutes = get_int(data.get("valid_minutes"), None, minimum=1, name="valid_minutes")
    valid_until = (now_utc() + timedelta(minutes=valid_minutes)) if valid_minutes else None

    auth = AssessmentAuthorization(
        assessment_id=assessment.id,
        student_id=student.id,
        authorized_by=current_user.id,
        authorization_type="student_unlock",
        extra_attempts=extra_attempts,
        valid_until=valid_until,
        reason=reason,
        is_active=True,
    )
    db.session.add(auth)
    audit(
        current_user.id,
        "assessment.student_unlock",
        target_type="Assessment",
        target_id=assessment.id,
        description=f"Unlocked for {student.name}: {reason}",
    )
    notify(
        student.id,
        "Assessment Unlocked",
        f"You have been granted access to attempt '{assessment.title}'. Reason: {reason}",
        "info",
        link_url=f"/student/assessments",
    )
    db.session.commit()
    return ok(authorization_public(auth), 201)


@faculty_api.post("/faculty/assessments/<int:assessment_id>/open-proctor")
@require_roles("faculty", "coordinator", "admin")
def open_proctor(assessment_id):
    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None:
        raise ApiError("Assessment not found.", 404, "not_found")
    data = json_body(required=False) or {}
    reason = (data.get("reason") or "Proctored in-person session opened").strip()
    valid_minutes = get_int(data.get("valid_minutes"), None, minimum=1, name="valid_minutes")
    valid_until = (now_utc() + timedelta(minutes=valid_minutes)) if valid_minutes else None

    if assessment.status != "published":
        assessment.status = "published"
        if not assessment.published_at:
            assessment.published_at = now_utc()

    auth = AssessmentAuthorization(
        assessment_id=assessment.id,
        student_id=None,
        authorized_by=current_user.id,
        authorization_type="proctor_open",
        extra_attempts=0,
        valid_until=valid_until,
        reason=reason,
        is_active=True,
    )
    db.session.add(auth)
    audit(
        current_user.id,
        "assessment.proctor_open",
        target_type="Assessment",
        target_id=assessment.id,
        description=f"Proctor opened assessment '{assessment.title}': {reason}",
    )
    db.session.commit()
    return ok(authorization_public(auth), 201)


@faculty_api.delete("/faculty/authorizations/<int:auth_id>")
@require_roles("faculty", "coordinator", "admin")
def revoke_authorization(auth_id):
    auth = db.session.get(AssessmentAuthorization, auth_id)
    if auth is None:
        raise ApiError("Authorization record not found.", 404, "not_found")
    auth.is_active = False
    audit(
        current_user.id,
        "assessment.auth_revoked",
        target_type="AssessmentAuthorization",
        target_id=auth.id,
        description=f"Revoked authorization for assessment {auth.assessment_id}",
    )
    db.session.commit()
    return ok({"message": "Authorization revoked."})

