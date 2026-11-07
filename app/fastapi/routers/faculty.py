"""Faculty Coordinator endpoints for FastAPI."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app import db
from app.fastapi.auth import ApiError, require_roles
from app.fastapi.utils import (
    assessment_public,
    authorization_public,
    domain_public,
    evidence_public,
    get_int,
    iso,
    ok,
    paginate,
)
from app.models.assessment import (
    Assessment,
    AssessmentAttempt,
    AssessmentAuthorization,
)
from app.models.domain import Domain
from app.models.platform import Appeal, GradingHistory, PointAdjustmentRequest, StudentRequest, TaskEvidence
from app.models.user import User
from app.services.portal import (
    audit,
    award_points,
    domain_ids_for,
    faculty_dashboard,
    find_ledger_entry,
    notify,
    now_utc,
    points_breakdown,
    reverse_points,
    scoped_student_ids,
)

logger = logging.getLogger("elite_portal.faculty_router")

router = APIRouter(prefix="/api/v1/faculty", tags=["faculty"])


class ReviewEvidencePayload(BaseModel):
    decision: str
    points: Optional[int] = None
    feedback: Optional[str] = None


class DecideAppealPayload(BaseModel):
    action: str
    new_score: Optional[int] = None
    review_comments: Optional[str] = None


class CreateAdjustmentPayload(BaseModel):
    student_id: int
    request_type: Optional[str] = "other"
    requested_points: Optional[int] = None
    reason: str


class ReviewAdjustmentPayload(BaseModel):
    decision: str
    review_notes: Optional[str] = None


class AuthorizeStudentPayload(BaseModel):
    student_id: int
    reason: Optional[str] = "Faculty override authorization"
    extra_attempts: Optional[int] = 1
    valid_minutes: Optional[int] = None


class OpenProctorPayload(BaseModel):
    reason: Optional[str] = "Proctored in-person session opened"
    valid_minutes: Optional[int] = None


def _scope_ids(user: User):
    return scoped_student_ids(user)


def _assert_in_scope(user: User, student_id: int):
    scoped = _scope_ids(user)
    if scoped is not None and student_id not in scoped:
        raise ApiError("You do not have access to this student.", 403, "forbidden")


def _appeal_payload(appeal: Appeal) -> dict:
    assigned_name = appeal.assigned_reviewer.name if appeal.assigned_reviewer else None
    assigned_email = appeal.assigned_reviewer.email if appeal.assigned_reviewer else None
    return {
        "id": appeal.id,
        "student_id": appeal.student_id,
        "student": appeal.student.name if appeal.student else None,
        "register_number": appeal.student.register_number if appeal.student else None,
        "attempt_id": appeal.attempt_id,
        "evidence_id": appeal.evidence_id,
        "reference": (
            appeal.attempt.assessment.title
            if appeal.attempt and appeal.attempt.assessment
            else (appeal.evidence.task.title if appeal.evidence and appeal.evidence.task else None)
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


def _adjustment_payload(row: PointAdjustmentRequest) -> dict:
    return {
        "id": row.id,
        "student_id": row.student_id,
        "student": row.student.name if row.student else None,
        "register_number": row.student.register_number if row.student else None,
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


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/dashboard")
def dashboard(user: User = Depends(require_roles("faculty", "admin"))):
    return ok(faculty_dashboard(user))


@router.get("/domains")
def my_domains(user: User = Depends(require_roles("faculty", "admin"))):
    if user.role == "admin":
        rows = Domain.query.order_by(Domain.name).all()
    else:
        ids = domain_ids_for(user)
        rows = Domain.query.filter(Domain.id.in_(ids or [-1])).order_by(Domain.name).all()
    return ok([domain_public(d) for d in rows])


@router.get("/task-evidence")
def task_evidence(
    status: Optional[str] = Query(None),
    page: int = Query(1),
    per_page: int = Query(20),
    user: User = Depends(require_roles("faculty", "coordinator", "admin")),
):
    scoped = _scope_ids(user)
    query = TaskEvidence.query
    if scoped is not None:
        query = query.filter(TaskEvidence.student_id.in_(scoped or [-1]))
    if status:
        query = query.filter(TaskEvidence.status == status)
    query = query.order_by(TaskEvidence.submitted_at.desc())
    paged = paginate(query, page=page, per_page=per_page)
    return ok([evidence_public(e) for e in paged["items"]], meta=paged["meta"])


@router.post("/task-evidence/{evidence_id}/review")
def review_evidence(
    evidence_id: int,
    payload: ReviewEvidencePayload,
    user: User = Depends(require_roles("faculty", "coordinator", "admin")),
):
    evidence = db.session.get(TaskEvidence, evidence_id)
    if evidence is None:
        raise ApiError("Evidence not found.", 404, "not_found")
    _assert_in_scope(user, evidence.student_id)
    if evidence.status != "pending":
        raise ApiError("This evidence has already been reviewed.", 409, "already_reviewed")

    decision = (payload.decision or "").strip().lower()
    if decision not in {"approved", "rejected"}:
        raise ApiError("Decision must be approved or rejected.", 400, "invalid_decision")
    feedback = (payload.feedback or "").strip()

    if decision == "approved":
        max_points = evidence.task.potential_points or 0
        points = payload.points if payload.points is not None else max_points
        if points > max_points:
            raise ApiError("Awarded points cannot exceed the task points.", 400, "invalid_points")
        evidence.status = "approved"
        evidence.points_awarded = points
        evidence.reviewed_by = user.id
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
            created_by=user.id,
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
        evidence.reviewed_by = user.id
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
        GradingHistory(evidence_id=evidence.id, graded_by=user.id, action=action, score=evidence.points_awarded, feedback=feedback)
    )
    audit(user.id, action, target_type="TaskEvidence", target_id=evidence.id)
    db.session.commit()
    return ok(evidence_public(evidence))


@router.get("/appeals")
def appeals(
    status: Optional[str] = Query(None),
    page: int = Query(1),
    per_page: int = Query(20),
    user: User = Depends(require_roles("faculty", "coordinator", "admin")),
):
    scoped = _scope_ids(user)
    query = Appeal.query
    if scoped is not None:
        query = query.filter(Appeal.student_id.in_(scoped or [-1]))
    if status:
        query = query.filter(Appeal.status == status)
    query = query.order_by(Appeal.created_at.desc())
    paged = paginate(query, page=page, per_page=per_page)
    return ok([_appeal_payload(a) for a in paged["items"]], meta=paged["meta"])


@router.post("/appeals/{appeal_id}/assign")
def assign_appeal(appeal_id: int, user: User = Depends(require_roles("faculty", "admin"))):
    appeal = db.session.get(Appeal, appeal_id)
    if appeal is None:
        raise ApiError("Appeal not found.", 404, "not_found")
    _assert_in_scope(user, appeal.student_id)
    appeal.assigned_to = user.id
    if appeal.status == "open":
        appeal.status = "in_review"

    notify(
        appeal.student_id,
        "Appeal Under Review — Action Required",
        f"You are instructed to meet the faculty {user.name} ({user.email}) regarding your appeal.",
        link_url="/student/appeals",
    )
    db.session.commit()
    return ok(_appeal_payload(appeal))


@router.post("/appeals/{appeal_id}/decision")
def decide_appeal(
    appeal_id: int,
    payload: DecideAppealPayload,
    user: User = Depends(require_roles("faculty", "admin")),
):
    appeal = db.session.get(Appeal, appeal_id)
    if appeal is None:
        raise ApiError("Appeal not found.", 404, "not_found")
    _assert_in_scope(user, appeal.student_id)
    if appeal.status in {"resolved", "rejected"}:
        raise ApiError("This appeal is already closed.", 409, "already_closed")

    action = (payload.action or "").strip().lower()
    if action not in {"uphold", "reject", "overturn", "partial"}:
        raise ApiError("Choose a valid decision.", 400, "invalid_decision")
    comments = (payload.review_comments or "").strip()

    if action == "reject":
        appeal.status = "rejected"
        appeal.decision = "upheld"
        appeal.review_comments = comments
        appeal.resolved_by = user.id
        appeal.resolved_at = now_utc()
    else:
        new_score = payload.new_score if payload.new_score is not None else appeal.original_score
        appeal.decision = "overturned" if action in {"overturn", "uphold"} else "partial"
        appeal.new_score = new_score
        appeal.review_comments = comments
        appeal.status = "resolved"
        appeal.resolved_by = user.id
        appeal.resolved_at = now_utc()

        if appeal.attempt_id:
            attempt = db.session.get(AssessmentAttempt, appeal.attempt_id)
            if attempt and new_score is not None:
                max_marks = attempt.total_marks or (attempt.assessment.total_marks if attempt.assessment else 0)
                if new_score > max_marks:
                    raise ApiError("New score cannot exceed total marks.", 400, "invalid_score")
                old = attempt.score
                attempt.score = new_score
                attempt.graded_at = now_utc()
                attempt.graded_by = user.id
                db.session.add(
                    GradingHistory(
                        attempt_id=attempt.id,
                        graded_by=user.id,
                        action="appeal_adjust",
                        score=new_score,
                        previous_score=old,
                        feedback=comments,
                    )
                )
                if attempt.assessment and attempt.assessment.assessment_type == "betting":
                    existing = find_ledger_entry(attempt.student_id, "betting_assessment", "AssessmentAttempt", attempt.id)
                    if existing:
                        reverse_points(existing, user.id)
                    apply_betting_points(attempt, created_by=user.id)
                else:
                    existing = find_ledger_entry(attempt.student_id, "assessment", "AssessmentAttempt", attempt.id)
                    if existing:
                        reverse_points(existing, user.id)
                    if new_score > 0 and attempt.assessment:
                        award_points(
                            student_id=attempt.student_id,
                            points=new_score,
                            transaction_type="assessment",
                            reference_type="AssessmentAttempt",
                            reference_id=attempt.id,
                            domain_id=attempt.assessment.domain_id,
                            description=f"Appeal adjustment: {attempt.assessment.title}",
                            created_by=user.id,
                        )
        elif appeal.evidence_id:
            evidence = db.session.get(TaskEvidence, appeal.evidence_id)
            if evidence:
                evidence.points_awarded = new_score
                evidence.status = "approved"
                evidence.reviewed_by = user.id
                evidence.reviewed_at = now_utc()
                existing = find_ledger_entry(evidence.student_id, "task_approval", "TaskEvidence", evidence.id)
                if existing:
                    reverse_points(existing, user.id)
                if new_score > 0 and evidence.task:
                    ledger = award_points(
                        student_id=evidence.student_id,
                        points=new_score,
                        transaction_type="task_approval",
                        reference_type="TaskEvidence",
                        reference_id=evidence.id,
                        domain_id=evidence.task.domain_id,
                        description=f"Appeal adjustment: {evidence.task.title}",
                        created_by=user.id,
                    )
                    evidence.point_ledger_id = ledger.id

    notify(
        appeal.student_id,
        "Appeal decision",
        f"Your appeal was {appeal.status}. {comments}",
        "info",
        link_url="/student/appeals",
    )
    audit(user.id, f"appeal.{action}", target_type="Appeal", target_id=appeal.id)
    db.session.commit()
    return ok(_appeal_payload(appeal))


@router.get("/point-adjustments")
def point_adjustments(
    status: Optional[str] = Query(None),
    page: int = Query(1),
    per_page: int = Query(20),
    user: User = Depends(require_roles("faculty", "coordinator", "admin")),
):
    scoped = _scope_ids(user)
    query = PointAdjustmentRequest.query
    if scoped is not None:
        query = query.filter(PointAdjustmentRequest.student_id.in_(scoped or [-1]))
    if status:
        query = query.filter(PointAdjustmentRequest.status == status)
    query = query.order_by(PointAdjustmentRequest.created_at.desc())
    paged = paginate(query, page=page, per_page=per_page)
    return ok([_adjustment_payload(r) for r in paged["items"]], meta=paged["meta"])


@router.post("/point-adjustments")
def create_adjustment(
    payload: CreateAdjustmentPayload,
    user: User = Depends(require_roles("faculty", "coordinator", "admin")),
):
    student_id = payload.student_id
    student = db.session.get(User, student_id)
    if student is None or student.role != "student":
        raise ApiError("Student not found.", 404, "not_found")
    _assert_in_scope(user, student_id)

    request_type = (payload.request_type or "other").strip()
    if request_type not in {"assessment_correction", "task_recount", "bonus", "penalty_reversal", "other"}:
        raise ApiError("Choose a valid request type.", 400, "invalid_type")
    reason = (payload.reason or "").strip()
    if len(reason) < 5:
        raise ApiError("Provide a reason.", 400, "invalid_reason")
    current = points_breakdown(student_id)["total"]
    requested = payload.requested_points if payload.requested_points is not None else current

    row = PointAdjustmentRequest(
        student_id=student_id,
        request_type=request_type,
        current_points=current,
        requested_points=requested,
        reason=reason,
        requested_by=user.id,
        status="pending",
    )
    db.session.add(row)
    db.session.commit()
    return ok(_adjustment_payload(row), 201)


@router.post("/point-adjustments/{adjustment_id}/review")
def review_adjustment(
    adjustment_id: int,
    payload: ReviewAdjustmentPayload,
    user: User = Depends(require_roles("faculty", "admin")),
):
    row = db.session.get(PointAdjustmentRequest, adjustment_id)
    if row is None:
        raise ApiError("Adjustment request not found.", 404, "not_found")
    _assert_in_scope(user, row.student_id)
    if row.status != "pending":
        raise ApiError("This request has already been reviewed.", 409, "already_reviewed")

    decision = (payload.decision or "").strip().lower()
    if decision not in {"approved", "rejected"}:
        raise ApiError("Decision must be approved or rejected.", 400, "invalid_decision")
    notes = (payload.review_notes or "").strip()

    row.status = decision
    row.reviewed_by = user.id
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
            created_by=user.id,
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

    audit(user.id, f"point_adjustment.{decision}", target_type="PointAdjustmentRequest", target_id=row.id)
    db.session.commit()
    return ok(_adjustment_payload(row))


@router.get("/requests")
def request_inbox(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1),
    per_page: int = Query(20),
    user: User = Depends(require_roles("faculty", "coordinator", "admin")),
):
    scoped = _scope_ids(user)
    query = StudentRequest.query
    if scoped is not None:
        query = query.filter(StudentRequest.student_id.in_(scoped or [-1]))
    if status:
        query = query.filter(StudentRequest.status == status)
    if category:
        query = query.filter(StudentRequest.category == category)
    query = query.order_by(StudentRequest.updated_at.desc())
    paged = paginate(query, page=page, per_page=per_page)
    return ok(
        [
            {
                "id": r.id,
                "student": r.student.name if r.student else None,
                "register_number": r.student.register_number if r.student else None,
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


@router.get("/analytics")
def analytics(user: User = Depends(require_roles("faculty", "coordinator", "admin"))):
    from app.fastapi.routers.coordinator import analytics as coord_analytics
    return coord_analytics(user)


@router.get("/assessments")
def list_faculty_assessments(user: User = Depends(require_roles("faculty", "coordinator", "admin"))):
    ids = domain_ids_for(user) if user.role != "admin" else None
    query = Assessment.query
    if ids is not None:
        query = query.filter(Assessment.domain_id.in_(ids or [-1]))
    rows = query.order_by(Assessment.created_at.desc()).all()
    return ok([assessment_public(a) for a in rows])


@router.get("/authorizations")
def list_authorizations(user: User = Depends(require_roles("faculty", "coordinator", "admin"))):
    auths = AssessmentAuthorization.query.order_by(AssessmentAuthorization.created_at.desc()).all()
    return ok([authorization_public(a) for a in auths])


@router.post("/assessments/{assessment_id}/authorize-student")
def authorize_student(
    assessment_id: int,
    payload: AuthorizeStudentPayload,
    user: User = Depends(require_roles("faculty", "coordinator", "admin")),
):
    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None:
        raise ApiError("Assessment not found.", 404, "not_found")
    student = db.session.get(User, payload.student_id)
    if student is None or student.role != "student":
        raise ApiError("Student not found.", 404, "student_not_found")
    _assert_in_scope(user, student.id)

    reason = (payload.reason or "Faculty override authorization").strip()
    extra_attempts = payload.extra_attempts or 1
    valid_until = (now_utc() + timedelta(minutes=payload.valid_minutes)) if payload.valid_minutes else None

    auth = AssessmentAuthorization(
        assessment_id=assessment.id,
        student_id=student.id,
        authorized_by=user.id,
        authorization_type="student_unlock",
        extra_attempts=extra_attempts,
        valid_until=valid_until,
        reason=reason,
        is_active=True,
    )
    db.session.add(auth)
    audit(
        user.id,
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
        link_url="/student/assessments",
    )
    db.session.commit()
    return ok(authorization_public(auth), 201)


@router.post("/assessments/{assessment_id}/open-proctor")
def open_proctor(
    assessment_id: int,
    payload: OpenProctorPayload,
    user: User = Depends(require_roles("faculty", "coordinator", "admin")),
):
    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None:
        raise ApiError("Assessment not found.", 404, "not_found")
    reason = (payload.reason or "Proctored in-person session opened").strip()
    valid_until = (now_utc() + timedelta(minutes=payload.valid_minutes)) if payload.valid_minutes else None

    if assessment.status != "published":
        assessment.status = "published"
        if not assessment.published_at:
            assessment.published_at = now_utc()

    auth = AssessmentAuthorization(
        assessment_id=assessment.id,
        student_id=None,
        authorized_by=user.id,
        authorization_type="proctor_open",
        extra_attempts=0,
        valid_until=valid_until,
        reason=reason,
        is_active=True,
    )
    db.session.add(auth)
    audit(
        user.id,
        "assessment.proctor_open",
        target_type="Assessment",
        target_id=assessment.id,
        description=f"Proctor opened assessment '{assessment.title}': {reason}",
    )
    db.session.commit()
    return ok(authorization_public(auth), 201)


@router.delete("/authorizations/{auth_id}")
def revoke_authorization(auth_id: int, user: User = Depends(require_roles("faculty", "coordinator", "admin"))):
    auth = db.session.get(AssessmentAuthorization, auth_id)
    if auth is None:
        raise ApiError("Authorization record not found.", 404, "not_found")
    auth.is_active = False
    audit(
        user.id,
        "assessment.auth_revoked",
        target_type="AssessmentAuthorization",
        target_id=auth.id,
        description=f"Revoked authorization for assessment {auth.assessment_id}",
    )
    db.session.commit()
    return ok({"message": "Authorization revoked."})
