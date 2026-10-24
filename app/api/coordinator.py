"""Domain Coordinator API — content, assessments, submissions, grading, analytics."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, Response, request
from flask_login import current_user
from sqlalchemy import func

from app import db
from app.api.utils import (
    ApiError,
    assessment_public,
    attempt_public,
    day_public,
    domain_public,
    get_int,
    iso,
    json_body,
    material_public,
    ok,
    paginate,
    parse_dt,
    question_public,
    require_roles,
)
from app.models import (
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentOption,
    AssessmentQuestion,
    ContentCompletion,
    Domain,
    GradingHistory,
    LearningDay,
    LearningMaterial,
    StudentDomainEnrollment,
    TestCase,
    User,
)
from app.services.portal import (
    apply_betting_points,
    audit,
    can_manage_domain,
    coordinator_dashboard,
    domain_ids_for,
    domain_progress,
    iso as iso_dt,
    notify,
    now_utc,
    points_breakdown,
    student_ids_in_domains,
)

coordinator_api = Blueprint("api_coordinator", __name__, url_prefix="/api/v1")


def _domain_or_404(domain_id):
    domain = db.session.get(Domain, domain_id)
    if domain is None:
        raise ApiError("Domain not found.", 404, "not_found")
    if not can_manage_domain(current_user, domain.id):
        raise ApiError("You do not manage this domain.", 403, "forbidden")
    return domain


def _day_or_404(day_id):
    day = db.session.get(LearningDay, day_id)
    if day is None:
        raise ApiError("Learning day not found.", 404, "not_found")
    _domain_or_404(day.domain_id)
    return day


def _assessment_or_404(assessment_id):
    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None:
        raise ApiError("Assessment not found.", 404, "not_found")
    _domain_or_404(assessment.domain_id)
    return assessment


@coordinator_api.get("/coordinator/dashboard")
@require_roles("coordinator", "admin")
def dashboard():
    return ok(coordinator_dashboard(current_user))


@coordinator_api.get("/coordinator/domains")
@require_roles("coordinator", "admin")
def domains():
    if current_user.role == "admin":
        rows = Domain.query.order_by(Domain.name).all()
    else:
        ids = domain_ids_for(current_user, "coordinator")
        rows = Domain.query.filter(Domain.id.in_(ids or [-1])).order_by(Domain.name).all()
    return ok([domain_public(d) for d in rows])


# ── Learning days ─────────────────────────────────────────────────────────
@coordinator_api.get("/coordinator/domains/<int:domain_id>/days")
@require_roles("coordinator", "admin")
def list_days(domain_id):
    domain = _domain_or_404(domain_id)
    rows = (
        LearningDay.query.filter_by(domain_id=domain.id)
        .order_by(LearningDay.day_number.asc())
        .all()
    )
    return ok({"domain": domain_public(domain), "days": [day_public(d) for d in rows]})


@coordinator_api.post("/coordinator/domains/<int:domain_id>/days")
@require_roles("coordinator", "admin")
def create_day(domain_id):
    domain = _domain_or_404(domain_id)
    data = json_body()
    title = (data.get("title") or "").strip()
    if len(title) < 3:
        raise ApiError("Please provide a day title.", 400, "invalid_title")

    next_number = (
        db.session.query(func.coalesce(func.max(LearningDay.day_number), 0))
        .filter(LearningDay.domain_id == domain.id)
        .scalar()
        or 0
    ) + 1

    day = LearningDay(
        domain_id=domain.id,
        day_number=next_number,
        title=title,
        description=data.get("description"),
        learning_objectives=data.get("learning_objectives"),
        status="draft",
        prerequisite_day_id=get_int(data.get("prerequisite_day_id"), None, name="prerequisite_day_id"),
        created_by=current_user.id,
    )
    db.session.add(day)
    audit(current_user.id, "content.day_create", target_type="LearningDay", description=f"Created day in {domain.code}")
    db.session.commit()
    return ok(day_public(day), 201)


@coordinator_api.patch("/coordinator/days/<int:day_id>")
@require_roles("coordinator", "admin")
def update_day(day_id):
    day = _day_or_404(day_id)
    data = json_body()
    for field in ("title", "description", "learning_objectives"):
        if field in data:
            setattr(day, field, data[field])
    if "prerequisite_day_id" in data:
        day.prerequisite_day_id = get_int(data.get("prerequisite_day_id"), None, name="prerequisite_day_id")
    if "is_locked" in data:
        day.is_locked = bool(data["is_locked"])
    if "status" in data:
        status = data["status"]
        if status not in {"draft", "published", "locked", "archived"}:
            raise ApiError("Invalid day status.", 400, "invalid_status")
        day.status = status
        if status == "published" and not day.published_at:
            day.published_at = now_utc()
    if not day.title or len(day.title.strip()) < 3:
        raise ApiError("Please provide a day title.", 400, "invalid_title")
    day.updated_at = now_utc()
    db.session.commit()
    return ok(day_public(day))


@coordinator_api.post("/coordinator/days/<int:day_id>/publish")
@require_roles("coordinator", "admin")
def publish_day(day_id):
    day = _day_or_404(day_id)
    if day.materials.count() == 0:
        raise ApiError("Add at least one learning material before publishing.", 400, "empty_day")
    day.status = "published"
    day.is_locked = False
    day.published_at = now_utc()
    audit(current_user.id, "content.day_publish", target_type="LearningDay", target_id=day.id)
    db.session.commit()
    return ok(day_public(day))


@coordinator_api.post("/coordinator/days/<int:day_id>/lock")
@require_roles("coordinator", "admin")
def lock_day(day_id):
    day = _day_or_404(day_id)
    data = json_body(required=False)
    day.is_locked = bool(data.get("locked", True))
    if day.is_locked and day.status == "published":
        day.status = "locked"
    elif not day.is_locked and day.status == "locked":
        day.status = "published"
    db.session.commit()
    return ok(day_public(day))


@coordinator_api.post("/coordinator/days/reorder")
@require_roles("coordinator", "admin")
def reorder_days():
    data = json_body()
    domain_id = get_int(data.get("domain_id"), name="domain_id")
    _domain_or_404(domain_id)
    ordered = data.get("ordered_ids") or []
    if not isinstance(ordered, list):
        raise ApiError("ordered_ids must be a list.", 400, "invalid_payload")
    days = {d.id: d for d in LearningDay.query.filter_by(domain_id=domain_id).all()}
    for index, day_id in enumerate(ordered, start=1):
        day = days.get(int(day_id))
        if day is None:
            continue
        day.day_number = -index
    db.session.flush()
    for index, day_id in enumerate(ordered, start=1):
        day = days.get(int(day_id))
        if day:
            day.day_number = index
    db.session.commit()
    return ok({"message": "Days reordered."})


@coordinator_api.delete("/coordinator/days/<int:day_id>")
@require_roles("coordinator", "admin")
def archive_day(day_id):
    day = _day_or_404(day_id)
    day.status = "archived"
    audit(current_user.id, "content.day_archive", target_type="LearningDay", target_id=day.id)
    db.session.commit()
    return ok({"message": "Learning day archived."})


# ── Materials ─────────────────────────────────────────────────────────────
@coordinator_api.post("/coordinator/days/<int:day_id>/materials")
@require_roles("coordinator", "admin")
def add_material(day_id):
    day = _day_or_404(day_id)
    data = json_body()
    title = (data.get("title") or "").strip()
    material_type = (data.get("material_type") or "").strip().lower()
    if len(title) < 2:
        raise ApiError("Please provide a material title.", 400, "invalid_title")
    if material_type not in {"video", "pdf", "code", "link", "problem"}:
        raise ApiError("Choose a valid material type.", 400, "invalid_type")

    order = (day.materials.count() or 0) + 1
    material = LearningMaterial(
        learning_day_id=day.id,
        title=title,
        material_type=material_type,
        description=data.get("description"),
        url=data.get("url"),
        file_key=data.get("file_key"),
        file_size=data.get("file_size"),
        file_name=data.get("file_name"),
        duration_minutes=get_int(data.get("duration_minutes"), None, name="duration_minutes"),
        display_order=get_int(data.get("display_order"), order, name="display_order"),
        status=data.get("status") if data.get("status") in {"draft", "published"} else "published",
        tags=data.get("tags") or [],
        created_by=current_user.id,
    )
    if material_type in {"video", "link"} and not material.url:
        raise ApiError("A URL is required for videos and links.", 400, "missing_url")
    if material_type in {"pdf", "code"} and not material.file_key and not material.url:
        raise ApiError("Upload a file or provide a URL.", 400, "missing_file")
    db.session.add(material)
    db.session.commit()
    return ok(material_public(material), 201)


@coordinator_api.patch("/coordinator/materials/<int:material_id>")
@require_roles("coordinator", "admin")
def update_material(material_id):
    material = db.session.get(LearningMaterial, material_id)
    if material is None:
        raise ApiError("Material not found.", 404, "not_found")
    _domain_or_404(material.learning_day.domain_id)
    data = json_body()
    for field in ("title", "description", "url", "file_key", "file_name", "status", "tags"):
        if field in data:
            setattr(material, field, data[field])
    if "duration_minutes" in data:
        material.duration_minutes = get_int(data.get("duration_minutes"), None, name="duration_minutes")
    if "display_order" in data:
        material.display_order = get_int(data.get("display_order"), material.display_order, name="display_order")
    material.updated_at = now_utc()
    db.session.commit()
    return ok(material_public(material))


@coordinator_api.delete("/coordinator/materials/<int:material_id>")
@require_roles("coordinator", "admin")
def delete_material(material_id):
    material = db.session.get(LearningMaterial, material_id)
    if material is None:
        raise ApiError("Material not found.", 404, "not_found")
    _domain_or_404(material.learning_day.domain_id)
    db.session.delete(material)
    db.session.commit()
    return ok({"message": "Material removed."})


# ── Assessments ───────────────────────────────────────────────────────────
@coordinator_api.get("/coordinator/domains/<int:domain_id>/assessments")
@require_roles("coordinator", "admin")
def list_assessments(domain_id):
    domain = _domain_or_404(domain_id)
    rows = (
        Assessment.query.filter_by(domain_id=domain.id)
        .order_by(Assessment.created_at.desc())
        .all()
    )
    return ok({"domain": domain_public(domain), "assessments": [assessment_public(a) for a in rows]})


def _apply_questions(assessment, questions_payload):
    for q_index, q in enumerate(questions_payload, start=1):
        qtype = (q.get("question_type") or "mcq").strip().lower()
        if qtype not in {"mcq", "coding"}:
            raise ApiError("Question type must be mcq or coding.", 400, "invalid_question")
        text = (q.get("question_text") or "").strip()
        if len(text) < 3:
            raise ApiError("Each question needs text.", 400, "invalid_question")
        question = AssessmentQuestion(
            assessment_id=assessment.id,
            question_type=qtype,
            question_text=text,
            marks=get_int(q.get("marks"), 1, 1, name="marks"),
            display_order=get_int(q.get("display_order"), q_index, name="display_order"),
            constraints=q.get("constraints"),
            sample_input=q.get("sample_input"),
            sample_output=q.get("sample_output"),
            explanation=q.get("explanation"),
        )
        db.session.add(question)
        db.session.flush()

        if qtype == "mcq":
            options = q.get("options") or []
            if len(options) < 2:
                raise ApiError("MCQ questions need at least two options.", 400, "invalid_options")
            for o_index, option in enumerate(options, start=1):
                db.session.add(
                    AssessmentOption(
                        question_id=question.id,
                        option_text=(option.get("option_text") or "").strip() or f"Option {o_index}",
                        is_correct=bool(option.get("is_correct")),
                        display_order=o_index,
                    )
                )
        else:
            for t_index, case in enumerate(q.get("test_cases") or [], start=1):
                db.session.add(
                    TestCase(
                        question_id=question.id,
                        input_data=case.get("input_data"),
                        expected_output=case.get("expected_output") or "",
                        points=get_int(case.get("points"), 0, 0, name="points"),
                        is_sample=bool(case.get("is_sample")),
                        display_order=t_index,
                    )
                )


@coordinator_api.post("/coordinator/assessments")
@require_roles("coordinator", "admin")
def create_assessment():
    data = json_body()
    domain_id = get_int(data.get("domain_id"), name="domain_id")
    _domain_or_404(domain_id)
    title = (data.get("title") or "").strip()
    if len(title) < 3:
        raise ApiError("Please provide an assessment title.", 400, "invalid_title")
    assessment_type = (data.get("assessment_type") or "mcq").strip().lower()
    if assessment_type not in {"mcq", "coding", "betting"}:
        raise ApiError("Assessment type must be mcq, coding or betting.", 400, "invalid_type")

    questions = data.get("questions") or []
    computed_marks = sum(get_int(q.get("marks"), 1, 1, name="marks") for q in questions) if questions else 0
    total_marks = get_int(data.get("total_marks"), computed_marks, 0, name="total_marks")

    assessment = Assessment(
        domain_id=domain_id,
        learning_day_id=get_int(data.get("learning_day_id"), None, name="learning_day_id"),
        title=title,
        description=data.get("description"),
        assessment_type=assessment_type,
        grading_mode=(data.get("grading_mode") or "automatic").strip().lower(),
        attendance_points=get_int(data.get("attendance_points"), 5, 0, name="attendance_points"),
        allowed_languages=data.get("allowed_languages") or [],
        total_marks=total_marks,
        time_limit_minutes=get_int(data.get("time_limit_minutes"), None, 1, name="time_limit_minutes"),
        max_attempts=get_int(data.get("max_attempts"), 1, 1, name="max_attempts"),
        shuffle_options=bool(data.get("shuffle_options")),
        shuffle_questions=bool(data.get("shuffle_questions")),
        show_results_after=data.get("show_results_after") if data.get("show_results_after") in {"submission", "grading", "never"} else "submission",
        show_correct_answers=bool(data.get("show_correct_answers")),
        status=data.get("status") if data.get("status") in {"draft", "published", "scheduled"} else "draft",
        scheduled_start=parse_dt(data.get("scheduled_start"), "scheduled_start"),
        scheduled_end=parse_dt(data.get("scheduled_end"), "scheduled_end"),
        instructions=data.get("instructions"),
        created_by=current_user.id,
    )
    if assessment.status == "published":
        assessment.published_at = now_utc()
    db.session.add(assessment)
    db.session.flush()
    if questions:
        _apply_questions(assessment, questions)
        if total_marks == 0:
            assessment.total_marks = sum(q.marks for q in assessment.questions)
    audit(current_user.id, "assessment.create", target_type="Assessment", target_id=assessment.id, description=title)
    db.session.commit()
    return ok(assessment_public(assessment, include_questions=True, include_answers=True), 201)


@coordinator_api.get("/coordinator/assessments/<int:assessment_id>")
@require_roles("coordinator", "admin")
def get_assessment(assessment_id):
    assessment = _assessment_or_404(assessment_id)
    return ok(assessment_public(assessment, include_questions=True, include_answers=True))


@coordinator_api.patch("/coordinator/assessments/<int:assessment_id>")
@require_roles("coordinator", "admin")
def update_assessment(assessment_id):
    assessment = _assessment_or_404(assessment_id)
    data = json_body()
    for field in ("title", "description", "instructions"):
        if field in data:
            setattr(assessment, field, data[field])
    if "grading_mode" in data and data["grading_mode"] in {"automatic", "manual"}:
        assessment.grading_mode = data["grading_mode"]
    if "attendance_points" in data:
        assessment.attendance_points = get_int(data.get("attendance_points"), 5, 0, name="attendance_points")
    if "allowed_languages" in data:
        assessment.allowed_languages = data.get("allowed_languages") or []
    if "total_marks" in data:
        assessment.total_marks = get_int(data.get("total_marks"), assessment.total_marks, 0, name="total_marks")
    if "time_limit_minutes" in data:
        assessment.time_limit_minutes = get_int(data.get("time_limit_minutes"), None, 1, name="time_limit_minutes")
    if "max_attempts" in data:
        assessment.max_attempts = get_int(data.get("max_attempts"), assessment.max_attempts, 1, name="max_attempts")
    for field in ("shuffle_options", "shuffle_questions", "show_correct_answers"):
        if field in data:
            setattr(assessment, field, bool(data[field]))
    if "show_results_after" in data and data["show_results_after"] in {"submission", "grading", "never"}:
        assessment.show_results_after = data["show_results_after"]
    if "scheduled_start" in data:
        assessment.scheduled_start = parse_dt(data.get("scheduled_start"), "scheduled_start")
    if "scheduled_end" in data:
        assessment.scheduled_end = parse_dt(data.get("scheduled_end"), "scheduled_end")
    if "status" in data and data["status"] in {"draft", "published", "scheduled", "closed"}:
        assessment.status = data["status"]
        if data["status"] == "published" and not assessment.published_at:
            assessment.published_at = now_utc()
    assessment.updated_at = now_utc()

    if "questions" in data and isinstance(data["questions"], list):
        for question in list(assessment.questions):
            db.session.delete(question)
        db.session.flush()
        _apply_questions(assessment, data["questions"])
        if not assessment.total_marks:
            assessment.total_marks = sum(q.marks for q in assessment.questions)

    if not assessment.title or len(assessment.title.strip()) < 3:
        raise ApiError("Please provide an assessment title.", 400, "invalid_title")
    db.session.commit()
    return ok(assessment_public(assessment, include_questions=True, include_answers=True))


@coordinator_api.post("/coordinator/assessments/<int:assessment_id>/publish")
@require_roles("coordinator", "admin")
def publish_assessment(assessment_id):
    assessment = _assessment_or_404(assessment_id)
    if len(assessment.questions) == 0:
        raise ApiError("Add at least one question before publishing.", 400, "empty_assessment")
    if assessment.total_marks <= 0:
        raise ApiError("Total marks must be greater than zero.", 400, "invalid_marks")
    assessment.status = "published"
    assessment.published_at = now_utc()
    audit(current_user.id, "assessment.publish", target_type="Assessment", target_id=assessment.id)
    db.session.commit()
    return ok(assessment_public(assessment))


@coordinator_api.post("/coordinator/assessments/<int:assessment_id>/close")
@require_roles("coordinator", "admin")
def close_assessment(assessment_id):
    assessment = _assessment_or_404(assessment_id)
    assessment.status = "closed"
    audit(current_user.id, "assessment.close", target_type="Assessment", target_id=assessment.id)
    db.session.commit()
    return ok(assessment_public(assessment))


# ── Submissions & grading ─────────────────────────────────────────────────
@coordinator_api.get("/coordinator/submissions")
@require_roles("coordinator", "faculty", "admin")
def submissions():
    domain_ids = domain_ids_for(current_user) if current_user.role != "admin" else None
    query = (
        AssessmentAttempt.query.join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
        .filter(AssessmentAttempt.status.in_(["submitted", "graded"]))
    )
    if domain_ids is not None:
        query = query.filter(Assessment.domain_id.in_(domain_ids or [-1]))
    if request.args.get("status"):
        query = query.filter(AssessmentAttempt.status == request.args["status"])
    if request.args.get("domain_id"):
        query = query.filter(Assessment.domain_id == get_int(request.args["domain_id"]))
    if request.args.get("assessment_id"):
        query = query.filter(AssessmentAttempt.assessment_id == get_int(request.args["assessment_id"]))
    if request.args.get("type"):
        query = query.filter(Assessment.assessment_type == request.args["type"])
    if request.args.get("student"):
        term = f"%{request.args['student'].strip()}%"
        query = query.join(User, User.id == AssessmentAttempt.student_id).filter(
            (User.name.ilike(term)) | (User.register_number.ilike(term))
        )
    if request.args.get("date"):
        try:
            day = datetime.fromisoformat(request.args["date"]).date()
            start = datetime.combine(day, datetime.min.time())
            query = query.filter(
                AssessmentAttempt.submitted_at >= start,
                AssessmentAttempt.submitted_at < start + timedelta(days=1),
            )
        except ValueError:
            raise ApiError("Invalid date filter.", 400, "invalid_date")

    query = query.order_by(AssessmentAttempt.submitted_at.desc())
    paged = paginate(query)
    return ok([attempt_public(a) for a in paged["items"]], meta=paged["meta"])


@coordinator_api.get("/coordinator/submissions/<int:attempt_id>")
@require_roles("coordinator", "faculty", "admin")
def submission_detail(attempt_id):
    attempt = db.session.get(AssessmentAttempt, attempt_id)
    if attempt is None:
        raise ApiError("Submission not found.", 404, "not_found")
    if current_user.role != "admin" and attempt.assessment.domain_id not in domain_ids_for(current_user):
        raise ApiError("You do not have access to this submission.", 403, "forbidden")

    detail = attempt_public(attempt, include_detail=True)
    detail["questions"] = [
        {
            **question_public(q, include_answers=True),
            "answer": next(
                (
                    {
                        "selected_option_id": a.selected_option_id,
                        "is_correct": a.is_correct,
                        "marks_awarded": a.marks_awarded,
                        "marked_for_review": a.marked_for_review,
                    }
                    for a in attempt.answers
                    if a.question_id == q.id
                ),
                None,
            ),
        }
        for q in attempt.assessment.questions
    ]
    detail["grading_history"] = [
        {
            "id": h.id,
            "action": h.action,
            "score": h.score,
            "previous_score": h.previous_score,
            "feedback": h.feedback,
            "grader": h.grader.name if h.grader else "System",
            "created_at": iso(h.created_at),
        }
        for h in GradingHistory.query.filter_by(attempt_id=attempt.id).order_by(GradingHistory.created_at.desc()).all()
    ]
    return ok(detail)


def _record_grading(attempt, action, previous_score, feedback):
    db.session.add(
        GradingHistory(
            attempt_id=attempt.id,
            graded_by=current_user.id,
            action=action,
            score=attempt.score,
            previous_score=previous_score,
            feedback=feedback,
        )
    )


@coordinator_api.post("/coordinator/submissions/<int:attempt_id>/grade")
@require_roles("coordinator", "faculty", "admin")
def grade_submission(attempt_id):
    attempt = db.session.get(AssessmentAttempt, attempt_id)
    if attempt is None:
        raise ApiError("Submission not found.", 404, "not_found")
    if current_user.role != "admin" and attempt.assessment.domain_id not in domain_ids_for(current_user):
        raise ApiError("You do not have access to this submission.", 403, "forbidden")
    if attempt.status == "in_progress":
        raise ApiError("This attempt has not been submitted yet.", 409, "not_submitted")

    data = json_body()
    previous_score = attempt.score

    if "answer_scores" in data and isinstance(data["answer_scores"], list):
        score = 0
        for entry in data["answer_scores"]:
            qid = get_int(entry.get("question_id"), name="question_id")
            marks = get_int(entry.get("marks_awarded"), 0, 0, name="marks_awarded")
            answer = AssessmentAnswer.query.filter_by(attempt_id=attempt.id, question_id=qid).first()
            if answer is None:
                answer = AssessmentAnswer(attempt_id=attempt.id, question_id=qid)
                db.session.add(answer)
            question = db.session.get(AssessmentQuestion, qid)
            if question and marks > question.marks:
                raise ApiError("Awarded marks cannot exceed the question marks.", 400, "invalid_marks")
            answer.marks_awarded = marks
            answer.is_correct = bool(marks > 0)
            score += marks
        attempt.score = score
    elif "score" in data:
        score = get_int(data.get("score"), 0, 0, name="score")
        if score > (attempt.total_marks or attempt.assessment.total_marks or 0):
            raise ApiError("Score cannot exceed total marks.", 400, "invalid_score")
        attempt.score = score
    else:
        raise ApiError("Provide a score or answer scores.", 400, "missing_score")

    attempt.feedback = data.get("feedback", attempt.feedback)
    attempt.status = "graded"
    attempt.graded_at = now_utc()
    attempt.graded_by = current_user.id
    _record_grading(attempt, "graded" if previous_score is None else "updated", previous_score, attempt.feedback)

    if attempt.assessment.assessment_type != "betting" and attempt.score and attempt.score > 0:
        from app.services.portal import award_points

        award_points(
            student_id=attempt.student_id,
            points=attempt.score,
            transaction_type="assessment",
            reference_type="AssessmentAttempt",
            reference_id=attempt.id,
            domain_id=attempt.assessment.domain_id,
            description=f"Assessment score: {attempt.assessment.title}",
            created_by=current_user.id,
        )
    notify(
        attempt.student_id,
        "Assessment graded",
        f"Your submission for “{attempt.assessment.title}” was graded.",
        "success",
        link_url=f"/student/assessments/{attempt.assessment_id}",
    )
    audit(current_user.id, "grade.submit", target_type="AssessmentAttempt", target_id=attempt.id)
    db.session.commit()
    return ok(attempt_public(attempt, include_detail=True))


@coordinator_api.post("/coordinator/submissions/<int:attempt_id>/attendance")
@require_roles("coordinator", "admin")
def set_attendance(attempt_id):
    attempt = db.session.get(AssessmentAttempt, attempt_id)
    if attempt is None:
        raise ApiError("Submission not found.", 404, "not_found")
    _domain_or_404(attempt.assessment.domain_id)
    if attempt.assessment.assessment_type != "betting":
        raise ApiError("Attendance scoring applies to betting assessments only.", 400, "not_betting")

    data = json_body()
    previous_score = attempt.score
    attempt.attended = bool(data.get("attended", True))
    if "score" in data:
        attempt.score = get_int(data.get("score"), 0, 0, name="score")
    from app.services.portal import find_ledger_entry, reverse_points

    existing = find_ledger_entry(attempt.student_id, "betting_assessment", "AssessmentAttempt", attempt.id)
    if existing is not None:
        reverse_points(existing, current_user.id)
    attempt.total_points_awarded = 0
    attempt.status = "graded"
    attempt.graded_at = now_utc()
    attempt.graded_by = current_user.id
    rule = apply_betting_points(attempt, created_by=current_user.id)
    _record_grading(attempt, "betting_adjusted", previous_score, data.get("feedback"))
    audit(current_user.id, "grade.betting_adjust", target_type="AssessmentAttempt", target_id=attempt.id, new_value=rule)
    db.session.commit()
    return ok({"attempt": attempt_public(attempt), "rule": rule})


@coordinator_api.post("/coordinator/submissions/<int:attempt_id>/request-changes")
@require_roles("coordinator", "faculty", "admin")
def request_changes(attempt_id):
    attempt = db.session.get(AssessmentAttempt, attempt_id)
    if attempt is None:
        raise ApiError("Submission not found.", 404, "not_found")
    if current_user.role != "admin" and attempt.assessment.domain_id not in domain_ids_for(current_user):
        raise ApiError("You do not have access to this submission.", 403, "forbidden")
    data = json_body()
    feedback = (data.get("feedback") or "").strip()
    if len(feedback) < 5:
        raise ApiError("Explain what the student should change.", 400, "invalid_feedback")
    attempt.feedback = feedback
    _record_grading(attempt, "change_requested", attempt.score, feedback)
    notify(
        attempt.student_id,
        "Changes requested",
        f"Your submission for “{attempt.assessment.title}” needs changes.",
        "warning",
        link_url=f"/student/assessments/{attempt.assessment_id}",
    )
    db.session.commit()
    return ok(attempt_public(attempt))


# ── Students & analytics ──────────────────────────────────────────────────
@coordinator_api.get("/coordinator/students")
@require_roles("coordinator", "faculty", "admin")
def students():
    domain_ids = domain_ids_for(current_user) if current_user.role != "admin" else [d.id for d in Domain.query.all()]
    if request.args.get("domain_id"):
        domain_id = get_int(request.args["domain_id"])
        if current_user.role != "admin" and domain_id not in domain_ids:
            raise ApiError("You do not have access to this domain.", 403, "forbidden")
        domain_ids = [domain_id]

    student_ids = student_ids_in_domains(domain_ids)
    query = User.query.filter(User.role == "student", User.id.in_(student_ids or [-1]))
    if request.args.get("search"):
        term = f"%{request.args['search'].strip()}%"
        query = query.filter((User.name.ilike(term)) | (User.register_number.ilike(term)) | (User.email.ilike(term)))
    query = query.order_by(User.name.asc())
    paged = paginate(query, default_per_page=25)

    items = []
    for student in paged["items"]:
        progress = [domain_progress(student.id, d_id) for d_id in domain_ids]
        completed = sum(p["completed_days"] for p in progress)
        published = sum(p["published_days"] for p in progress)
        items.append(
            {
                "id": student.id,
                "name": student.name,
                "email": student.email,
                "register_number": student.register_number,
                "department": student.department,
                "status": "active" if student.is_active_account else "inactive",
                "completed_days": completed,
                "published_days": published,
                "completion_percent": round(completed / published * 100) if published else 0,
                **points_breakdown(student.id),
                "assessment_attempts": AssessmentAttempt.query.filter(
                    AssessmentAttempt.student_id == student.id,
                    AssessmentAttempt.status.in_(["submitted", "graded"]),
                ).count(),
            }
        )
    return ok(items, meta=paged["meta"])


@coordinator_api.get("/coordinator/students/<int:student_id>")
@require_roles("coordinator", "faculty", "admin")
def student_detail(student_id):
    student = db.session.get(User, student_id)
    if student is None or student.role != "student":
        raise ApiError("Student not found.", 404, "not_found")
    domain_ids = domain_ids_for(current_user) if current_user.role != "admin" else [d.id for d in Domain.query.all()]
    if current_user.role != "admin" and student.id not in student_ids_in_domains(domain_ids):
        raise ApiError("You do not have access to this student.", 403, "forbidden")

    attempts = (
        AssessmentAttempt.query.filter(
            AssessmentAttempt.student_id == student.id,
            AssessmentAttempt.status.in_(["submitted", "graded"]),
        )
        .order_by(AssessmentAttempt.submitted_at.desc())
        .all()
    )
    return ok(
        {
            "student": {
                "id": student.id,
                "name": student.name,
                "email": student.email,
                "register_number": student.register_number,
                "department": student.department,
                "year": student.year,
                "section": student.section,
                "status": "active" if student.is_active_account else "inactive",
            },
            "domains": [
                {"domain_id": d_id, "domain": db.session.get(Domain, d_id).name, **domain_progress(student.id, d_id)}
                for d_id in domain_ids
                if StudentDomainEnrollment.query.filter_by(
                    student_id=student.id, domain_id=d_id, is_active=True
                ).first()
            ],
            "points": points_breakdown(student.id),
            "assessments": [attempt_public(a) for a in attempts],
        }
    )


@coordinator_api.get("/coordinator/analytics")
@require_roles("coordinator", "faculty", "admin")
def analytics():
    domain_ids = domain_ids_for(current_user) if current_user.role != "admin" else [d.id for d in Domain.query.all()]
    student_ids = student_ids_in_domains(domain_ids)
    assessment_ids = [a.id for a in Assessment.query.filter(Assessment.domain_id.in_(domain_ids or [-1])).all()]

    attempts = AssessmentAttempt.query.filter(
        AssessmentAttempt.assessment_id.in_(assessment_ids or [-1]),
        AssessmentAttempt.status.in_(["submitted", "graded"]),
    ).all()
    graded = [a for a in attempts if a.score is not None and a.total_marks]
    avg_score = round(sum(a.score for a in graded) / len(graded), 1) if graded else 0

    learning = []
    for d_id in domain_ids:
        domain = db.session.get(Domain, d_id)
        published = LearningDay.query.filter_by(domain_id=d_id, status="published").count()
        completions = (
            db.session.query(func.count(ContentCompletion.id))
            .join(LearningDay, LearningDay.id == ContentCompletion.learning_day_id)
            .filter(LearningDay.domain_id == d_id, ContentCompletion.is_day_complete.is_(True))
            .scalar()
            or 0
        )
        possible = published * max(len(student_ids), 1)
        learning.append(
            {
                "domain_id": d_id,
                "domain": domain.name if domain else "—",
                "published_days": published,
                "completions": int(completions),
                "completion_percent": round(completions / possible * 100) if possible else 0,
            }
        )

    status_counts = {"submitted": 0, "graded": 0}
    for a in attempts:
        status_counts[a.status] = status_counts.get(a.status, 0) + 1

    return ok(
        {
            "totals": {
                "students": len(student_ids),
                "assessments": len(assessment_ids),
                "submissions": len(attempts),
                "average_score_percent": avg_score,
            },
            "learning": learning,
            "status_counts": status_counts,
            "grading_workload": [
                {
                    "domain": db.session.get(Domain, d_id).name,
                    "pending": AssessmentAttempt.query.filter(
                        AssessmentAttempt.assessment_id.in_(
                            [a.id for a in Assessment.query.filter_by(domain_id=d_id).all()] or [-1]
                        ),
                        AssessmentAttempt.status == "submitted",
                    ).count(),
                }
                for d_id in domain_ids
            ],
        }
    )


@coordinator_api.get("/coordinator/students/progress")
@require_roles("coordinator", "faculty", "admin")
def student_progress():
    domain_ids = domain_ids_for(current_user) if current_user.role != "admin" else [d.id for d in Domain.query.all()]
    student_ids = student_ids_in_domains(domain_ids)

    query = User.query.filter(User.role == "student", User.id.in_(student_ids or [-1]))

    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter((User.name.ilike(like)) | (User.register_number.ilike(like)) | (User.email.ilike(like)))

    dept = request.args.get("department")
    if dept and dept != "all":
        query = query.filter(User.department == dept)

    query = query.order_by(User.name.asc())
    paged = paginate(query, default_per_page=20, max_per_page=100)

    domain_day_counts = {
        d_id: LearningDay.query.filter_by(domain_id=d_id, status="published").count()
        for d_id in domain_ids
    }

    items = []
    for s in paged["items"]:
        enrolled = (
            StudentDomainEnrollment.query.filter(
                StudentDomainEnrollment.student_id == s.id,
                StudentDomainEnrollment.is_active == True,
                StudentDomainEnrollment.domain_id.in_(domain_ids or [-1]),
            ).all()
        )
        enrolled_domain_ids = [e.domain_id for e in enrolled]
        enrolled_domain_names = [e.domain.name for e in enrolled if e.domain]

        total_days = sum(domain_day_counts.get(did, 0) for did in enrolled_domain_ids)
        completed_days = (
            ContentCompletion.query.join(LearningDay, LearningDay.id == ContentCompletion.learning_day_id)
            .filter(
                ContentCompletion.student_id == s.id,
                ContentCompletion.is_day_complete == True,
                LearningDay.domain_id.in_(enrolled_domain_ids or [-1]),
            )
            .count()
        )
        pct = round((completed_days / total_days) * 100) if total_days > 0 else 0
        attempts_count = AssessmentAttempt.query.join(Assessment, Assessment.id == AssessmentAttempt.assessment_id).filter(
            AssessmentAttempt.student_id == s.id,
            Assessment.domain_id.in_(enrolled_domain_ids or [-1]),
        ).count()

        items.append({
            "id": s.id,
            "name": s.name,
            "register_number": s.register_number,
            "email": s.email,
            "department": s.department,
            "domains": enrolled_domain_names,
            "total_days": total_days,
            "completed_days": completed_days,
            "completion_percent": pct,
            "assessments_taken": attempts_count,
            "total_points": points_breakdown(s.id)["total"],
        })

    return ok(items, meta=paged["meta"])


@coordinator_api.get("/coordinator/exports/students.csv")
@require_roles("coordinator", "faculty", "admin")
def export_students():
    domain_ids = domain_ids_for(current_user) if current_user.role != "admin" else [d.id for d in Domain.query.all()]
    student_ids = student_ids_in_domains(domain_ids)
    rows = User.query.filter(User.role == "student", User.id.in_(student_ids or [-1])).order_by(User.name).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Name", "Register Number", "Email", "Department", "Total Points"])
    for s in rows:
        writer.writerow([s.name, s.register_number or "", s.email, s.department or "", points_breakdown(s.id)["total"]])
    audit(current_user.id, "export.students")
    db.session.commit()
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students.csv"},
    )


@coordinator_api.get("/coordinator/exports/submissions.csv")
@require_roles("coordinator", "faculty", "admin")
def export_submissions():
    domain_ids = domain_ids_for(current_user) if current_user.role != "admin" else [d.id for d in Domain.query.all()]
    rows = (
        AssessmentAttempt.query.join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
        .filter(
            Assessment.domain_id.in_(domain_ids or [-1]),
            AssessmentAttempt.status.in_(["submitted", "graded"]),
        )
        .order_by(AssessmentAttempt.submitted_at.desc())
        .all()
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Student", "Register Number", "Assessment", "Domain", "Type", "Status", "Score", "Total", "Submitted"])
    for a in rows:
        writer.writerow([
            a.student.name,
            a.student.register_number or "",
            a.assessment.title,
            a.assessment.domain.name,
            a.assessment.assessment_type,
            a.status,
            a.score if a.score is not None else "",
            a.total_marks or a.assessment.total_marks,
            iso_dt(a.submitted_at),
        ])
    audit(current_user.id, "export.submissions")
    db.session.commit()
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=submissions.csv"},
    )
