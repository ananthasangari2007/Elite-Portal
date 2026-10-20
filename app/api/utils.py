"""Shared helpers for the versioned Elite Portal JSON API."""
from __future__ import annotations

import math
import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import jsonify, request, session
from flask_login import current_user

from app.services.portal import iso, to_local


class ApiError(Exception):
    def __init__(self, message, status=400, code="bad_request", details=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.details = details


def ok(data=None, status=200, **extra):
    payload = {"data": data}
    payload.update(extra)
    return jsonify(payload), status


def fail(message, status=400, code="bad_request", details=None):
    body = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return jsonify(body), status


def require_roles(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                raise ApiError("Authentication required.", 401, "unauthenticated")
            if not current_user.is_active_account:
                raise ApiError("This account has been deactivated.", 403, "account_inactive")
            if roles and current_user.role not in roles:
                raise ApiError("You do not have permission to perform this action.", 403, "forbidden")
            return view(*args, **kwargs)

        return wrapped

    return decorator


def json_body(required=True):
    data = request.get_json(silent=True)
    if data is None:
        if required:
            raise ApiError("A JSON body is required.", 400, "invalid_body")
        return {}
    if not isinstance(data, dict):
        raise ApiError("The JSON body must be an object.", 400, "invalid_body")
    return data


def get_int(value, default=None, minimum=None, maximum=None, name="value"):
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


def parse_dt(value, name="date"):
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


def paginate(query, default_per_page=20, max_per_page=100):
    page = max(get_int(request.args.get("page"), 1, 1, name="page"), 1)
    per_page = get_int(request.args.get("per_page"), default_per_page, 1, max_per_page, "per_page")
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


def csrf_token():
    token = session.get("api_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["api_csrf"] = token
    return token


def require_csrf():
    expected = session.get("api_csrf")
    supplied = request.headers.get("X-CSRF-Token")
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        raise ApiError("Invalid or missing CSRF token.", 403, "csrf_failed")


# ── Serializers ───────────────────────────────────────────────────────────
def user_public(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "register_number": user.register_number,
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


def domain_public(domain, include_counts=True):
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
        data["student_count"] = domain.student_count
        data["published_days"] = domain.published_days_count
        data["assessment_count"] = domain.assessments.count()
    return data


def material_public(material, include_url=True):
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


def day_public(day, include_materials=False, materials=None):
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
        "material_count": day.materials.count(),
        "assessment_count": day.assessments.count(),
    }
    if include_materials:
        data["materials"] = [
            material_public(m) for m in (materials if materials is not None else day.materials.all())
        ]
    return data


def question_public(question, include_answers=False):
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


def assessment_public(assessment, include_questions=False, include_answers=False):
    data = {
        "id": assessment.id,
        "domain_id": assessment.domain_id,
        "domain": assessment.domain.name if assessment.domain else None,
        "learning_day_id": assessment.learning_day_id,
        "learning_day": assessment.learning_day.title if assessment.learning_day else None,
        "title": assessment.title,
        "description": assessment.description,
        "assessment_type": assessment.assessment_type,
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
        "question_count": len(assessment.questions),
        "published_at": iso(assessment.published_at),
        "created_at": iso(assessment.created_at),
    }
    if include_questions:
        data["questions"] = [question_public(q, include_answers) for q in assessment.questions]
    return data


def attempt_public(attempt, include_detail=False):
    data = {
        "id": attempt.id,
        "assessment_id": attempt.assessment_id,
        "assessment": attempt.assessment.title,
        "assessment_type": attempt.assessment.assessment_type,
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


def evidence_public(evidence):
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


def local_date(dt):
    """Display helper exposed for clients that want the institutional date."""
    value = to_local(dt)
    return value.isoformat() if value else None
