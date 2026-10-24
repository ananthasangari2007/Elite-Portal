"""Serialization, formatting, pagination, and response helpers for FastAPI."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi.responses import JSONResponse
from sqlalchemy import func

from app import db
from app.fastapi.auth import ApiError
from app.models.assessment import Assessment
from app.models.domain import LearningMaterial
from app.services.portal import iso, to_local


def ok(data: Any = None, status: int = 200, **extra) -> JSONResponse:
    """Standard success response format: {"data": ...}"""
    payload = {"data": data}
    payload.update(extra)
    return JSONResponse(status_code=status, content=payload)


def fail(message: str, status: int = 400, code: str = "bad_request", details: Any = None) -> JSONResponse:
    """Standard error response format: {"error": {"code": ..., "message": ...}}"""
    body = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body)


def get_int(
    value: Any,
    default: Optional[int] = None,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
    name: str = "value",
    min_val: Optional[int] = None,
    max_val: Optional[int] = None,
) -> Optional[int]:
    if minimum is None and min_val is not None:
        minimum = min_val
    if maximum is None and max_val is not None:
        maximum = max_val
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ApiError(f"{name} must be a number.", 400, "invalid_field")
    if minimum is not None and parsed < minimum:
        raise ApiError(f"{name} must be at least {minimum}.", 400, "invalid_field")
    if maximum is not None and parsed > maximum:
        raise ApiError(f"{name} must be at most {maximum}.", 400, "invalid_field")
    return parsed


def parse_dt(value: Any, name: str = "date") -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            text = str(value).replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
        except ValueError:
            raise ApiError(f"{name} must be a valid ISO-8601 date/time.", 400, "invalid_field")
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def paginate(query, page: int = 1, per_page: int = 20, max_per_page: int = 100):
    page = max(page, 1)
    per_page = min(max(per_page, 1), max_per_page)
    total = query.order_by(None).count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": items,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": math.ceil(total / per_page) if per_page else 0,
        },
    }


# ── Serializers ───────────────────────────────────────────────────────────
def user_public(user) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "register_number": user.register_number,
        "phone_number": user.phone_number,
        "department": user.department,
        "year": user.year,
        "section": user.section,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "linkedin_url": user.linkedin_url,
        "github_url": user.github_url,
        "leetcode_url": user.leetcode_url,
        "preferred_domain": user.preferred_domain,
        "profile_completed": user.profile_completed,
        "approval_status": user.approval_status,
        "is_active_account": user.is_active_account,
        "last_login": iso(user.last_login),
        "created_at": iso(user.created_at),
    }


def domain_public(domain, include_counts: bool = True) -> dict:
    data = {
        "id": domain.id,
        "code": domain.code,
        "name": domain.name,
        "description": domain.description,
        "icon": domain.icon,
        "color": domain.color,
        "is_compulsory": domain.is_compulsory,
        "is_active": domain.is_active,
        "enrollment_limit": domain.enrollment_limit,
        "domain_change_allowed_until": iso(domain.domain_change_allowed_until),
    }
    if include_counts:
        data["student_count"] = getattr(domain, "student_count", 0)
        data["published_days"] = getattr(domain, "published_days_count", 0)
        try:
            data["assessment_count"] = domain.assessments.count()
        except Exception:
            data["assessment_count"] = 0
    return data


def material_public(material, include_url: bool = True) -> dict:
    return {
        "id": material.id,
        "learning_day_id": material.learning_day_id,
        "title": material.title,
        "material_type": material.material_type,
        "description": material.description,
        "url": material.url if include_url else None,
        "file_key": material.file_key if include_url else None,
        "file_size": material.file_size,
        "file_size_display": material.file_size_display,
        "file_name": material.file_name,
        "duration_minutes": material.duration_minutes,
        "display_order": material.display_order,
        "status": material.status,
        "tags": material.tags or [],
        "created_at": iso(material.created_at),
    }


def batch_day_counts(day_ids: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    """Batch count materials and assessments for a list of day IDs in 2 queries (prevents N+1)."""
    if not day_ids:
        return {}, {}
    mat_counts = dict(
        db.session.query(LearningMaterial.learning_day_id, func.count(LearningMaterial.id))
        .filter(LearningMaterial.learning_day_id.in_(day_ids))
        .group_by(LearningMaterial.learning_day_id)
        .all()
    )
    asm_counts = dict(
        db.session.query(Assessment.learning_day_id, func.count(Assessment.id))
        .filter(Assessment.learning_day_id.in_(day_ids))
        .group_by(Assessment.learning_day_id)
        .all()
    )
    return mat_counts, asm_counts


def day_public(
    day,
    include_materials: bool = False,
    materials=None,
    precomputed_mat_count: Optional[int] = None,
    precomputed_asm_count: Optional[int] = None,
) -> dict:
    data = {
        "id": day.id,
        "domain_id": day.domain_id,
        "day_number": day.day_number,
        "title": day.title,
        "description": day.description,
        "learning_objectives": day.learning_objectives,
        "status": day.status,
        "is_locked": day.is_locked,
        "prerequisite_day_id": day.prerequisite_day_id,
        "published_at": iso(day.published_at),
        "created_at": iso(day.created_at),
        "updated_at": iso(day.updated_at),
        "material_count": (
            precomputed_mat_count
            if precomputed_mat_count is not None
            else (day.materials.count() if hasattr(day.materials, "count") else len(day.materials))
        ),
        "assessment_count": (
            precomputed_asm_count
            if precomputed_asm_count is not None
            else (day.assessments.count() if hasattr(day.assessments, "count") else len(day.assessments))
        ),
    }
    if include_materials:
        data["materials"] = [
            material_public(m) for m in (materials if materials is not None else day.materials.all())
        ]
    return data


def question_public(question, include_answers: bool = False) -> dict:
    data = {
        "id": question.id,
        "assessment_id": question.assessment_id,
        "question_type": question.question_type,
        "question_text": question.question_text,
        "marks": question.marks,
        "display_order": question.display_order,
        "constraints": question.constraints,
        "sample_input": question.sample_input,
        "sample_output": question.sample_output,
        "options": [
            {
                "id": o.id,
                "option_text": o.option_text,
                "display_order": o.display_order,
                **({"is_correct": o.is_correct} if include_answers else {}),
            }
            for o in sorted(question.options, key=lambda x: x.display_order)
        ],
        "sample_test_cases": [
            {
                "id": t.id,
                "input_data": t.input_data,
                "expected_output": t.expected_output,
                "points": t.points,
            }
            for t in sorted(question.test_cases, key=lambda x: x.display_order)
            if t.is_sample
        ],
    }
    if include_answers:
        data["test_cases"] = [
            {
                "id": t.id,
                "input_data": t.input_data,
                "expected_output": t.expected_output,
                "points": t.points,
                "is_sample": t.is_sample,
            }
            for t in sorted(question.test_cases, key=lambda x: x.display_order)
        ]
        data["explanation"] = question.explanation
    return data


def assessment_public(assessment, include_questions: bool = False, include_answers: bool = False) -> dict:
    data = {
        "id": assessment.id,
        "domain_id": assessment.domain_id,
        "domain": assessment.domain.name if assessment.domain else None,
        "learning_day_id": assessment.learning_day_id,
        "learning_day": assessment.learning_day.title if assessment.learning_day else None,
        "title": assessment.title,
        "description": assessment.description,
        "assessment_type": assessment.assessment_type,
        "grading_mode": getattr(assessment, "grading_mode", "automatic") or "automatic",
        "attendance_points": getattr(assessment, "attendance_points", 5) or 0,
        "allowed_languages": getattr(assessment, "allowed_languages", None) or [],
        "total_marks": assessment.total_marks,
        "time_limit_minutes": assessment.time_limit_minutes,
        "max_attempts": assessment.max_attempts,
        "shuffle_options": assessment.shuffle_options,
        "shuffle_questions": assessment.shuffle_questions,
        "show_results_after": assessment.show_results_after,
        "show_correct_answers": assessment.show_correct_answers,
        "status": assessment.status,
        "scheduled_start": iso(assessment.scheduled_start),
        "scheduled_end": iso(assessment.scheduled_end),
        "instructions": assessment.instructions,
        "available": assessment.is_available,
        "question_count": len(assessment.questions),
        "published_at": iso(assessment.published_at),
        "created_at": iso(assessment.created_at),
    }
    if include_questions:
        data["questions"] = [question_public(q, include_answers) for q in assessment.questions]
    return data


def attempt_public(attempt, include_detail: bool = False) -> dict:
    data = {
        "id": attempt.id,
        "assessment_id": attempt.assessment_id,
        "assessment": attempt.assessment.title if attempt.assessment else None,
        "assessment_type": attempt.assessment.assessment_type if attempt.assessment else None,
        "allowed_languages": getattr(attempt.assessment, "allowed_languages", None) or [],
        "student_id": attempt.student_id,
        "student": attempt.student.name if attempt.student else None,
        "register_number": attempt.student.register_number if attempt.student else None,
        "status": attempt.status,
        "started_at": iso(attempt.started_at),
        "submitted_at": iso(attempt.submitted_at),
        "graded_at": iso(attempt.graded_at),
        "score": attempt.score,
        "total_marks": attempt.total_marks,
        "feedback": attempt.feedback,
        "time_taken_seconds": attempt.time_taken_seconds,
        "attended": attempt.attended,
        "locked_points": attempt.locked_points,
        "attendance_points": attempt.attendance_points,
        "total_points_awarded": attempt.total_points_awarded,
        "points_rule_applied": attempt.points_rule_applied,
    }
    if include_detail:
        data["answers"] = [
            {
                "question_id": a.question_id,
                "selected_option_id": a.selected_option_id,
                "marked_for_review": a.marked_for_review,
                "is_correct": a.is_correct,
                "marks_awarded": a.marks_awarded,
            }
            for a in attempt.answers
        ]
        data["coding_submissions"] = [
            {
                "id": c.id,
                "question_id": c.question_id,
                "language": c.language,
                "code": c.code,
                "status": c.status,
                "test_results": c.test_results or [],
                "marks_awarded": c.marks_awarded,
            }
            for c in attempt.coding_submissions
        ]
        data["integrity_flags"] = attempt.integrity_flags or []
    return data


def authorization_public(auth) -> dict:
    return {
        "id": auth.id,
        "assessment_id": auth.assessment_id,
        "assessment_title": auth.assessment.title if auth.assessment else None,
        "student_id": auth.student_id,
        "student_name": auth.student.name if auth.student else "All Students",
        "student_register_number": auth.student.register_number if auth.student else None,
        "authorized_by": auth.authorized_by,
        "authorizer_name": auth.authorizer.name if auth.authorizer else None,
        "authorization_type": auth.authorization_type,
        "extra_attempts": auth.extra_attempts,
        "valid_until": iso(auth.valid_until),
        "reason": auth.reason,
        "is_active": auth.is_active,
        "created_at": iso(auth.created_at),
    }


def evidence_public(evidence) -> dict:
    return {
        "id": evidence.id,
        "task_id": evidence.task_id,
        "task": evidence.task.title if evidence.task else None,
        "student_id": evidence.student_id,
        "student": evidence.student.name if evidence.student else None,
        "register_number": evidence.student.register_number if evidence.student else None,
        "evidence_type": evidence.evidence_type,
        "file_key": evidence.file_key,
        "file_name": evidence.file_name,
        "file_size": evidence.file_size,
        "file_type": evidence.file_type,
        "link_url": evidence.link_url,
        "notes": evidence.notes,
        "submission_date": evidence.submission_date.isoformat() if evidence.submission_date else None,
        "status": evidence.status,
        "reviewed_by": evidence.reviewed_by,
        "reviewed_at": iso(evidence.reviewed_at),
        "reviewer_feedback": evidence.reviewer_feedback,
        "points_awarded": evidence.points_awarded,
        "submitted_at": iso(evidence.submitted_at),
    }


def local_date(dt) -> Optional[str]:
    value = to_local(dt)
    return value.isoformat() if value else None
