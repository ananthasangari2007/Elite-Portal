"""
Student Blueprint — Elite Portal
All student-facing routes: dashboard, learning, assessments, tasks, points, leaderboard, requests, profile.
"""
from datetime import datetime, date
from functools import wraps

from flask import (
    Blueprint, flash, jsonify, redirect, render_template,
    request, url_for, abort, current_app
)
from flask_login import current_user, login_required
from sqlalchemy import func, desc

from app import db
from app.models import (
    User, Domain, StudentDomainEnrollment, LearningDay,
    LearningMaterial, ContentCompletion, Assessment,
    AssessmentAttempt, AssessmentAnswer, AssessmentOption,
    EliteTask, TaskEvidence, PointLedger, PointAdjustmentRequest,
    Appeal, StudentRequest, RequestMessage, Announcement,
    Notification,
)

student_bp = Blueprint("student", __name__, url_prefix="/s")


def student_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != "student":
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ─────────────────────────────────────────────────────────────

@student_bp.route("/dashboard")
@student_required
def dashboard():
    # Total points
    total_pts = current_user.total_points()

    # Domain enrollments
    enrollments = StudentDomainEnrollment.query.filter_by(
        student_id=current_user.id, is_active=True
    ).all()
    enrolled_domain_ids = [e.domain_id for e in enrollments]

    # Completed learning days
    days_completed = ContentCompletion.query.filter_by(
        student_id=current_user.id, is_day_complete=True
    ).count()

    # Assessment stats
    assessments_completed = AssessmentAttempt.query.filter_by(
        student_id=current_user.id, status="graded"
    ).count()

    # Task streak (daily task evidences approved consecutively)
    streak = _calculate_daily_streak(current_user.id)

    # Progress per domain
    domain_progress = []
    for enrollment in enrollments:
        domain = enrollment.domain
        total_days = domain.learning_days.filter_by(status="published").count()
        completed_days = ContentCompletion.query.filter(
            ContentCompletion.student_id == current_user.id,
            ContentCompletion.learning_day_id.in_(
                [d.id for d in domain.learning_days.filter_by(status="published").all()]
            ),
            ContentCompletion.is_day_complete == True
        ).count()
        domain_progress.append({
            "domain": domain,
            "total": total_days,
            "completed": completed_days,
            "percent": int(completed_days / total_days * 100) if total_days > 0 else 0,
        })

    # Today's elite tasks
    today_tasks = EliteTask.query.filter_by(status="active").order_by(
        EliteTask.due_date.asc()
    ).limit(5).all()

    # Recent activity (recent point ledger entries)
    recent_activity = PointLedger.query.filter_by(
        student_id=current_user.id
    ).order_by(desc(PointLedger.created_at)).limit(5).all()

    # Upcoming assessments
    upcoming_assessments = Assessment.query.filter(
        Assessment.domain_id.in_(enrolled_domain_ids),
        Assessment.status == "published",
        Assessment.scheduled_start >= datetime.utcnow(),
    ).order_by(Assessment.scheduled_start.asc()).limit(5).all()

    # Unread notifications
    unread_count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()

    # Recent announcements
    announcements = Announcement.query.filter(
        Announcement.status == "published",
        db.or_(
            Announcement.target_audience == "all",
            Announcement.target_audience == "students",
        )
    ).order_by(desc(Announcement.created_at)).limit(3).all()

    return render_template(
        "student/dashboard.html",
        total_pts=total_pts,
        days_completed=days_completed,
        assessments_completed=assessments_completed,
        streak=streak,
        domain_progress=domain_progress,
        today_tasks=today_tasks,
        recent_activity=recent_activity,
        upcoming_assessments=upcoming_assessments,
        unread_count=unread_count,
        announcements=announcements,
    )


def _calculate_daily_streak(student_id):
    """Calculate consecutive approved daily task days."""
    approved_dates = db.session.query(TaskEvidence.submission_date).filter(
        TaskEvidence.student_id == student_id,
        TaskEvidence.status == "approved",
    ).order_by(desc(TaskEvidence.submission_date)).all()

    if not approved_dates:
        return 0

    dates = [r.submission_date for r in approved_dates]
    streak = 0
    check_date = date.today()

    for d in dates:
        if d == check_date:
            streak += 1
            check_date = _prev_business_day(check_date)
        elif d < check_date:
            break

    return streak


def _prev_business_day(d):
    from datetime import timedelta
    d = d - timedelta(days=1)
    while d.weekday() >= 5:  # Saturday=5, Sunday=6
        d = d - timedelta(days=1)
    return d


# ── Domain Selection ───────────────────────────────────────────────────────

@student_bp.route("/domains")
@student_required
def domain_selection():
    all_domains = Domain.query.filter_by(is_active=True).all()
    enrolled_ids = {
        e.domain_id for e in StudentDomainEnrollment.query.filter_by(
            student_id=current_user.id, is_active=True
        ).all()
    }
    max_optional = current_app.config.get("MAX_OPTIONAL_DOMAINS", 2)
    optional_enrolled = sum(
        1 for d in all_domains
        if d.id in enrolled_ids and not d.is_compulsory
    )
    return render_template(
        "student/domain_selection.html",
        domains=all_domains,
        enrolled_ids=enrolled_ids,
        max_optional=max_optional,
        optional_enrolled=optional_enrolled,
    )


@student_bp.route("/domains/enroll", methods=["POST"])
@student_required
def enroll_domain():
    domain_id = request.form.get("domain_id", type=int)
    if not domain_id:
        flash("Invalid domain.", "danger")
        return redirect(url_for("student.domain_selection"))

    domain = Domain.query.get_or_404(domain_id)
    max_optional = current_app.config.get("MAX_OPTIONAL_DOMAINS", 2)

    existing = StudentDomainEnrollment.query.filter_by(
        student_id=current_user.id, domain_id=domain_id
    ).first()

    if existing:
        if existing.is_active:
            flash(f"You are already enrolled in {domain.name}.", "info")
        else:
            flash("Domain enrollment is inactive. Contact your coordinator.", "warning")
        return redirect(url_for("student.domain_selection"))

    if not domain.is_compulsory:
        optional_count = StudentDomainEnrollment.query.join(Domain).filter(
            StudentDomainEnrollment.student_id == current_user.id,
            StudentDomainEnrollment.is_active == True,
            Domain.is_compulsory == False,
        ).count()
        if optional_count >= max_optional:
            flash(
                f"You can select a maximum of {max_optional} optional domain(s). "
                "Contact your faculty coordinator to change domains.",
                "warning"
            )
            return redirect(url_for("student.domain_selection"))

    enrollment = StudentDomainEnrollment(
        student_id=current_user.id,
        domain_id=domain_id,
        enrolled_by=current_user.id,
    )
    db.session.add(enrollment)
    db.session.commit()
    flash(f"Enrolled in {domain.name} successfully!", "success")
    return redirect(url_for("student.domain_selection"))


# ── Learning Path ──────────────────────────────────────────────────────────

@student_bp.route("/learning")
@student_required
def learning():
    enrollments = StudentDomainEnrollment.query.filter_by(
        student_id=current_user.id, is_active=True
    ).all()
    return render_template("student/learning.html", enrollments=enrollments)


@student_bp.route("/learning/<int:domain_id>")
@student_required
def learning_domain(domain_id):
    domain = Domain.query.get_or_404(domain_id)
    enrollment = StudentDomainEnrollment.query.filter_by(
        student_id=current_user.id, domain_id=domain_id, is_active=True
    ).first()
    if not enrollment:
        flash("You are not enrolled in this domain.", "warning")
        return redirect(url_for("student.domain_selection"))

    published_days = domain.learning_days.filter_by(status="published").all()
    completed_day_ids = {
        c.learning_day_id
        for c in ContentCompletion.query.filter_by(
            student_id=current_user.id, is_day_complete=True
        ).all()
    }

    total = len(published_days)
    completed_count = sum(1 for d in published_days if d.id in completed_day_ids)
    percent = int(completed_count / total * 100) if total > 0 else 0

    return render_template(
        "student/learning_domain.html",
        domain=domain,
        days=published_days,
        completed_day_ids=completed_day_ids,
        percent=percent,
        total=total,
        completed_count=completed_count,
    )


@student_bp.route("/learning/<int:domain_id>/day/<int:day_id>")
@student_required
def learning_day_view(domain_id, day_id):
    domain = Domain.query.get_or_404(domain_id)
    day = LearningDay.query.filter_by(id=day_id, domain_id=domain_id, status="published").first_or_404()

    enrollment = StudentDomainEnrollment.query.filter_by(
        student_id=current_user.id, domain_id=domain_id, is_active=True
    ).first()
    if not enrollment:
        abort(403)

    completion = ContentCompletion.query.filter_by(
        student_id=current_user.id, learning_day_id=day_id
    ).first()

    materials = day.materials.filter_by(status="published").all()
    assessments = Assessment.query.filter_by(
        learning_day_id=day_id, status="published"
    ).all()

    return render_template(
        "student/learning_day.html",
        domain=domain,
        day=day,
        materials=materials,
        assessments=assessments,
        completion=completion,
    )


@student_bp.route("/learning/<int:domain_id>/day/<int:day_id>/complete", methods=["POST"])
@student_required
def complete_day(domain_id, day_id):
    day = LearningDay.query.filter_by(id=day_id, domain_id=domain_id, status="published").first_or_404()

    enrollment = StudentDomainEnrollment.query.filter_by(
        student_id=current_user.id, domain_id=domain_id, is_active=True
    ).first()
    if not enrollment:
        abort(403)

    completion = ContentCompletion.query.filter_by(
        student_id=current_user.id, learning_day_id=day_id
    ).first()

    if completion and completion.is_day_complete:
        flash("This day is already marked as completed.", "info")
    else:
        if not completion:
            completion = ContentCompletion(
                student_id=current_user.id,
                learning_day_id=day_id,
            )
            db.session.add(completion)
        completion.is_day_complete = True
        completion.completed_at = datetime.utcnow()
        db.session.commit()
        flash(f"Day {day.day_number}: {day.title} marked as completed!", "success")

    return redirect(url_for("student.learning_domain", domain_id=domain_id))


# ── Learning Materials ─────────────────────────────────────────────────────

@student_bp.route("/materials")
@student_required
def materials():
    enrolled_domain_ids = [
        e.domain_id for e in StudentDomainEnrollment.query.filter_by(
            student_id=current_user.id, is_active=True
        ).all()
    ]
    filter_type = request.args.get("type", "all")
    filter_domain = request.args.get("domain", type=int)
    search = request.args.get("q", "").strip()

    query = LearningMaterial.query.join(LearningDay).filter(
        LearningDay.domain_id.in_(enrolled_domain_ids),
        LearningDay.status == "published",
        LearningMaterial.status == "published",
    )

    if filter_type != "all":
        query = query.filter(LearningMaterial.material_type == filter_type)
    if filter_domain:
        query = query.filter(LearningDay.domain_id == filter_domain)
    if search:
        query = query.filter(LearningMaterial.title.ilike(f"%{search}%"))

    mats = query.order_by(
        LearningDay.day_number.asc(),
        LearningMaterial.display_order.asc()
    ).all()

    enrolled_domains = Domain.query.filter(
        Domain.id.in_(enrolled_domain_ids)
    ).all()

    return render_template(
        "student/materials.html",
        materials=mats,
        filter_type=filter_type,
        filter_domain=filter_domain,
        search=search,
        enrolled_domains=enrolled_domains,
    )


# ── Assessments ────────────────────────────────────────────────────────────

@student_bp.route("/assessments")
@student_required
def assessments():
    enrolled_domain_ids = [
        e.domain_id for e in StudentDomainEnrollment.query.filter_by(
            student_id=current_user.id, is_active=True
        ).all()
    ]
    all_assessments = Assessment.query.filter(
        Assessment.domain_id.in_(enrolled_domain_ids),
        Assessment.status.in_(["published", "closed"]),
    ).order_by(desc(Assessment.created_at)).all()

    attempt_map = {}
    for a in all_assessments:
        attempts = AssessmentAttempt.query.filter_by(
            student_id=current_user.id, assessment_id=a.id
        ).order_by(desc(AssessmentAttempt.started_at)).all()
        attempt_map[a.id] = attempts

    return render_template(
        "student/assessments.html",
        assessments=all_assessments,
        attempt_map=attempt_map,
    )


@student_bp.route("/assessments/<int:assessment_id>/instructions")
@student_required
def assessment_instructions(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    _check_assessment_access(assessment)

    existing_attempts = AssessmentAttempt.query.filter_by(
        student_id=current_user.id, assessment_id=assessment_id
    ).count()

    if existing_attempts >= assessment.max_attempts:
        flash("You have used all allowed attempts for this assessment.", "warning")
        return redirect(url_for("student.assessments"))

    return render_template(
        "student/assessment_instructions.html",
        assessment=assessment,
        attempts_used=existing_attempts,
    )


@student_bp.route("/assessments/<int:assessment_id>/start", methods=["POST"])
@student_required
def start_assessment(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    _check_assessment_access(assessment)

    existing_attempts = AssessmentAttempt.query.filter_by(
        student_id=current_user.id, assessment_id=assessment_id
    ).count()

    if existing_attempts >= assessment.max_attempts:
        flash("No more attempts allowed.", "warning")
        return redirect(url_for("student.assessments"))

    attempt = AssessmentAttempt(
        assessment_id=assessment_id,
        student_id=current_user.id,
        status="in_progress",
        total_marks=assessment.total_marks,
        ip_address=request.remote_addr,
    )
    db.session.add(attempt)
    db.session.commit()

    if assessment.assessment_type == "coding":
        return redirect(url_for("student.take_coding", attempt_id=attempt.id))
    return redirect(url_for("student.take_mcq", attempt_id=attempt.id, question_num=1))


@student_bp.route("/assessments/attempt/<int:attempt_id>/mcq")
@student_required
def take_mcq(attempt_id):
    attempt = AssessmentAttempt.query.get_or_404(attempt_id)
    if attempt.student_id != current_user.id:
        abort(403)
    if attempt.status != "in_progress":
        return redirect(url_for("student.assessment_result", attempt_id=attempt_id))

    question_num = request.args.get("question_num", 1, type=int)
    questions = attempt.assessment.questions
    if not questions:
        flash("This assessment has no questions.", "warning")
        return redirect(url_for("student.assessments"))

    q_index = max(0, min(question_num - 1, len(questions) - 1))
    current_question = questions[q_index]

    saved_answer = AssessmentAnswer.query.filter_by(
        attempt_id=attempt_id, question_id=current_question.id
    ).first()

    answers_map = {
        a.question_id: a for a in AssessmentAnswer.query.filter_by(attempt_id=attempt_id).all()
    }

    time_limit = attempt.assessment.time_limit_minutes
    elapsed = (datetime.utcnow() - attempt.started_at).total_seconds()

    return render_template(
        "student/take_mcq.html",
        attempt=attempt,
        questions=questions,
        current_question=current_question,
        q_index=q_index,
        saved_answer=saved_answer,
        answers_map=answers_map,
        time_limit=time_limit,
        elapsed=elapsed,
    )


@student_bp.route("/assessments/attempt/<int:attempt_id>/mcq/save", methods=["POST"])
@student_required
def save_mcq_answer(attempt_id):
    attempt = AssessmentAttempt.query.get_or_404(attempt_id)
    if attempt.student_id != current_user.id or attempt.status != "in_progress":
        return jsonify({"ok": False}), 403

    question_id = request.form.get("question_id", type=int)
    option_id = request.form.get("option_id", type=int)
    mark_review = request.form.get("mark_review") == "1"

    existing = AssessmentAnswer.query.filter_by(
        attempt_id=attempt_id, question_id=question_id
    ).first()

    if existing:
        existing.selected_option_id = option_id
        existing.marked_for_review = mark_review
        existing.saved_at = datetime.utcnow()
    else:
        answer = AssessmentAnswer(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_option_id=option_id,
            marked_for_review=mark_review,
        )
        db.session.add(answer)

    db.session.commit()
    return jsonify({"ok": True})


@student_bp.route("/assessments/attempt/<int:attempt_id>/submit", methods=["POST"])
@student_required
def submit_assessment(attempt_id):
    attempt = AssessmentAttempt.query.get_or_404(attempt_id)
    if attempt.student_id != current_user.id or attempt.status != "in_progress":
        abort(403)

    # Auto-grade MCQ
    score = 0
    for answer in attempt.answers:
        if answer.selected_option_id:
            option = AssessmentOption.query.get(answer.selected_option_id)
            if option and option.is_correct:
                answer.is_correct = True
                answer.marks_awarded = answer.question.marks
                score += answer.question.marks
            else:
                answer.is_correct = False
                answer.marks_awarded = 0

    attempt.score = score
    attempt.status = "graded" if attempt.assessment.assessment_type == "mcq" else "submitted"
    attempt.submitted_at = datetime.utcnow()
    attempt.time_taken_seconds = int(
        (attempt.submitted_at - attempt.started_at).total_seconds()
    )

    # Apply betting assessment scoring if applicable
    if attempt.assessment.assessment_type == "betting":
        _apply_betting_points(attempt)

    db.session.commit()
    flash("Assessment submitted successfully!", "success")
    return redirect(url_for("student.assessment_result", attempt_id=attempt_id))


def _apply_betting_points(attempt):
    """Apply the institution-defined betting assessment scoring rules."""
    score = attempt.score or 0
    total = attempt.total_marks or 1
    percent = (score / total * 100) if total > 0 else 0

    if not attempt.attended:
        locked, attendance = 0, 0
        rule = "absent"
    elif score == 0:
        locked, attendance = 0, 50
        rule = "attended_zero"
    elif percent < 40:
        locked, attendance = 0, 100
        rule = "1_to_39"
    elif percent <= 80:
        locked, attendance = 350, 100
        rule = "40_to_80"
    else:
        locked, attendance = 700, 100
        rule = "above_80"

    attempt.locked_points = locked
    attempt.attendance_points = attendance
    attempt.total_points_awarded = locked + attendance
    attempt.points_rule_applied = rule

    if attempt.total_points_awarded > 0:
        ledger = PointLedger(
            student_id=attempt.student_id,
            points=attempt.total_points_awarded,
            transaction_type="betting_assessment",
            reference_type="AssessmentAttempt",
            reference_id=attempt.id,
            domain_id=attempt.assessment.domain_id,
            description=(
                f"Betting assessment: {attempt.assessment.title} "
                f"({locked} locked + {attendance} attendance)"
            ),
            created_by=attempt.student_id,
        )
        db.session.add(ledger)


@student_bp.route("/assessments/attempt/<int:attempt_id>/coding")
@student_required
def take_coding(attempt_id):
    attempt = AssessmentAttempt.query.get_or_404(attempt_id)
    if attempt.student_id != current_user.id:
        abort(403)
    if attempt.status != "in_progress":
        return redirect(url_for("student.assessment_result", attempt_id=attempt_id))

    return render_template("student/take_coding.html", attempt=attempt)


@student_bp.route("/assessments/attempt/<int:attempt_id>/result")
@student_required
def assessment_result(attempt_id):
    attempt = AssessmentAttempt.query.get_or_404(attempt_id)
    if attempt.student_id != current_user.id:
        abort(403)

    return render_template("student/assessment_result.html", attempt=attempt)


def _check_assessment_access(assessment):
    if not assessment.is_available and assessment.status != "published":
        flash("This assessment is not available.", "warning")
        return redirect(url_for("student.assessments"))


# ── Elite Tasks ────────────────────────────────────────────────────────────

@student_bp.route("/tasks")
@student_required
def tasks():
    tab = request.args.get("tab", "available")

    available = EliteTask.query.filter_by(status="active").order_by(
        EliteTask.due_date.asc()
    ).all()

    my_evidences = TaskEvidence.query.filter_by(student_id=current_user.id).all()
    submitted_ids = {e.task_id for e in my_evidences}

    evidence_by_task = {e.task_id: e for e in my_evidences}

    return render_template(
        "student/tasks.html",
        available_tasks=available,
        my_evidences=my_evidences,
        submitted_ids=submitted_ids,
        evidence_by_task=evidence_by_task,
        tab=tab,
    )


@student_bp.route("/tasks/<int:task_id>")
@student_required
def task_detail(task_id):
    task = EliteTask.query.get_or_404(task_id)
    my_evidence = TaskEvidence.query.filter_by(
        task_id=task_id, student_id=current_user.id
    ).first()
    return render_template(
        "student/task_detail.html",
        task=task,
        my_evidence=my_evidence,
    )


@student_bp.route("/tasks/<int:task_id>/submit", methods=["POST"])
@student_required
def submit_task(task_id):
    task = EliteTask.query.get_or_404(task_id)

    # Determine today's business date in Asia/Kolkata
    import pytz
    tz = pytz.timezone("Asia/Kolkata")
    today_ist = datetime.now(tz).date()

    # Enforce one submission per business day
    existing_today = TaskEvidence.query.filter_by(
        student_id=current_user.id,
        submission_date=today_ist,
    ).first()

    if existing_today:
        flash(
            "You have already submitted a daily task today (IST). "
            "Only one submission per business day is allowed.",
            "warning"
        )
        return redirect(url_for("student.tasks"))

    evidence_type = request.form.get("evidence_type", "link")
    link_url = request.form.get("link_url", "").strip()
    notes = request.form.get("notes", "").strip()

    file_key = None
    file_name = None
    file_size = None
    file_type = None

    if evidence_type == "file":
        f = request.files.get("evidence_file")
        if f and f.filename:
            from app.services.storage import upload_file
            result = upload_file(f, folder="evidence")
            if result:
                file_key = result["key"]
                file_name = result["name"]
                file_size = result["size"]
                file_type = result["content_type"]
            else:
                flash("File upload failed. Please try again.", "danger")
                return redirect(url_for("student.task_detail", task_id=task_id))
        else:
            flash("Please select a file to upload.", "warning")
            return redirect(url_for("student.task_detail", task_id=task_id))
    elif evidence_type == "link" and not link_url:
        flash("Please provide a link as evidence.", "warning")
        return redirect(url_for("student.task_detail", task_id=task_id))

    evidence = TaskEvidence(
        task_id=task_id,
        student_id=current_user.id,
        evidence_type=evidence_type,
        file_key=file_key,
        file_name=file_name,
        file_size=file_size,
        file_type=file_type,
        link_url=link_url,
        notes=notes,
        submission_date=today_ist,
        status="pending",
    )
    db.session.add(evidence)
    db.session.commit()

    flash(f"Task evidence submitted! Awaiting coordinator review.", "success")
    return redirect(url_for("student.tasks", tab="in_progress"))


# ── Points & Leaderboard ───────────────────────────────────────────────────

@student_bp.route("/points")
@student_required
def points():
    ledger = PointLedger.query.filter_by(
        student_id=current_user.id
    ).order_by(desc(PointLedger.created_at)).all()

    total = sum(e.points for e in ledger)
    return render_template(
        "student/points.html",
        ledger=ledger,
        total=total,
    )


@student_bp.route("/leaderboard")
@student_required
def leaderboard():
    tab = request.args.get("tab", "overall")
    domain_code = request.args.get("domain")
    period = request.args.get("period", "all")

    students = _build_leaderboard(tab, domain_code, period)

    # My rank
    my_rank = None
    for i, s in enumerate(students):
        if s["user_id"] == current_user.id:
            my_rank = i + 1
            break

    enrolled_domains = Domain.query.join(
        StudentDomainEnrollment,
        StudentDomainEnrollment.domain_id == Domain.id
    ).filter(
        StudentDomainEnrollment.student_id == current_user.id,
        StudentDomainEnrollment.is_active == True,
    ).all()

    return render_template(
        "student/leaderboard.html",
        students=students,
        my_rank=my_rank,
        tab=tab,
        domain_code=domain_code,
        period=period,
        enrolled_domains=enrolled_domains,
    )


def _build_leaderboard(tab, domain_code, period):
    from sqlalchemy import case
    from datetime import timedelta

    query = db.session.query(
        User.id.label("user_id"),
        User.name.label("name"),
        User.register_number.label("register_number"),
        User.department.label("department"),
        func.coalesce(func.sum(PointLedger.points), 0).label("points"),
    ).join(
        PointLedger, PointLedger.student_id == User.id, isouter=True
    ).filter(
        User.role == "student",
        User.is_active_account == True,
    )

    if domain_code:
        domain = Domain.query.filter_by(code=domain_code).first()
        if domain:
            query = query.filter(
                db.or_(PointLedger.domain_id == domain.id, PointLedger.id.is_(None))
            )

    if period == "monthly":
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        query = query.filter(
            db.or_(PointLedger.created_at >= month_start, PointLedger.id.is_(None))
        )

    results = query.group_by(User.id, User.name, User.register_number, User.department)\
        .order_by(desc("points"), User.name.asc()).limit(100).all()

    leaderboard = []
    for i, row in enumerate(results):
        # Count assessments and tasks
        assessment_count = AssessmentAttempt.query.filter_by(
            student_id=row.user_id, status="graded"
        ).count()
        task_count = TaskEvidence.query.filter_by(
            student_id=row.user_id, status="approved"
        ).count()
        leaderboard.append({
            "rank": i + 1,
            "user_id": row.user_id,
            "name": row.name,
            "register_number": row.register_number or "—",
            "department": row.department or "—",
            "points": int(row.points or 0),
            "assessments": assessment_count,
            "tasks": task_count,
        })

    return leaderboard


# ── Requests ───────────────────────────────────────────────────────────────

@student_bp.route("/requests")
@student_required
def requests_list():
    tab = request.args.get("tab", "all")
    query = StudentRequest.query.filter_by(student_id=current_user.id)
    if tab != "all":
        query = query.filter_by(status=tab)
    my_requests = query.order_by(desc(StudentRequest.created_at)).all()
    return render_template(
        "student/requests.html",
        requests=my_requests,
        tab=tab,
    )


@student_bp.route("/requests/new", methods=["GET", "POST"])
@student_required
def new_request():
    if request.method == "POST":
        category = request.form.get("category", "general")
        subject = request.form.get("subject", "").strip()
        message_text = request.form.get("message", "").strip()

        if not subject or not message_text:
            flash("Subject and message are required.", "warning")
            return render_template("student/new_request.html")

        req = StudentRequest(
            student_id=current_user.id,
            category=category,
            subject=subject,
        )
        db.session.add(req)
        db.session.flush()

        msg = RequestMessage(
            request_id=req.id,
            sender_id=current_user.id,
            message=message_text,
        )
        db.session.add(msg)
        db.session.commit()
        flash("Request submitted successfully!", "success")
        return redirect(url_for("student.request_detail", request_id=req.id))

    return render_template("student/new_request.html")


@student_bp.route("/requests/<int:request_id>")
@student_required
def request_detail(request_id):
    req = StudentRequest.query.filter_by(
        id=request_id, student_id=current_user.id
    ).first_or_404()
    return render_template("student/request_detail.html", req=req)


@student_bp.route("/requests/<int:request_id>/reply", methods=["POST"])
@student_required
def reply_request(request_id):
    req = StudentRequest.query.filter_by(
        id=request_id, student_id=current_user.id
    ).first_or_404()

    message_text = request.form.get("message", "").strip()
    if not message_text:
        flash("Message cannot be empty.", "warning")
        return redirect(url_for("student.request_detail", request_id=request_id))

    msg = RequestMessage(
        request_id=req.id,
        sender_id=current_user.id,
        message=message_text,
    )
    db.session.add(msg)
    req.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("student.request_detail", request_id=request_id))


# ── Announcements ──────────────────────────────────────────────────────────

@student_bp.route("/announcements")
@student_required
def announcements():
    category = request.args.get("category", "all")
    query = Announcement.query.filter(
        Announcement.status == "published",
        db.or_(
            Announcement.target_audience == "all",
            Announcement.target_audience == "students",
        )
    )
    if category != "all":
        query = query.filter_by(category=category)

    items = query.order_by(desc(Announcement.created_at)).all()
    return render_template("student/announcements.html", announcements=items, category=category)


# ── Profile ────────────────────────────────────────────────────────────────

@student_bp.route("/profile")
@student_required
def profile():
    total_points = current_user.total_points()
    assessments_done = AssessmentAttempt.query.filter_by(
        student_id=current_user.id, status="graded"
    ).count()
    tasks_done = TaskEvidence.query.filter_by(
        student_id=current_user.id, status="approved"
    ).count()
    enrolled_domains = Domain.query.join(
        StudentDomainEnrollment,
        StudentDomainEnrollment.domain_id == Domain.id
    ).filter(
        StudentDomainEnrollment.student_id == current_user.id,
        StudentDomainEnrollment.is_active == True,
    ).all()

    return render_template(
        "student/profile.html",
        total_points=total_points,
        assessments_done=assessments_done,
        tasks_done=tasks_done,
        enrolled_domains=enrolled_domains,
    )


@student_bp.route("/profile/save", methods=["POST"])
@student_required
def profile_save():
    current_user.name = request.form.get("name", current_user.name).strip()
    current_user.department = request.form.get("department", "").strip() or None
    current_user.year = request.form.get("year", type=int)
    current_user.section = request.form.get("section", "").strip() or None
    current_user.linkedin_url = request.form.get("linkedin_url", "").strip() or None
    current_user.github_url = request.form.get("github_url", "").strip() or None
    current_user.leetcode_url = request.form.get("leetcode_url", "").strip() or None
    current_user.bio = request.form.get("bio", "").strip() or None
    current_user.profile_completed = True
    db.session.commit()
    flash("Profile updated successfully!", "success")
    return redirect(url_for("student.profile"))


# ── Notifications (API) ────────────────────────────────────────────────────

@student_bp.route("/api/notifications")
@student_required
def api_notifications():
    notes = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(Notification.created_at)).limit(20).all()
    return jsonify([{
        "id": n.id,
        "title": n.title,
        "message": n.message,
        "type": n.notification_type,
        "url": n.link_url,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat(),
    } for n in notes])


@student_bp.route("/api/notifications/mark-read", methods=["POST"])
@student_required
def mark_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"ok": True})
