"""
Domain Coordinator Blueprint — Elite Portal
Manages domain content, learning days, assessments, submissions, and student progress.
"""
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint, abort, flash, jsonify, redirect, render_template,
    request, url_for
)
from flask_login import current_user, login_required
from sqlalchemy import desc, func

from app import db
from app.models import (
    User, Domain, DomainAssignment, StudentDomainEnrollment,
    LearningDay, LearningMaterial, ContentCompletion,
    Assessment, AssessmentQuestion, AssessmentOption, TestCase,
    AssessmentAttempt, PointLedger, Notification, AuditLog,
    EliteTask, TaskEvidence,
)

coordinator_bp = Blueprint("coordinator", __name__, url_prefix="/c")


def coordinator_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != "coordinator":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def get_my_domains():
    """Return domains assigned to the current coordinator."""
    assignments = DomainAssignment.query.filter_by(
        user_id=current_user.id, assignment_type="coordinator"
    ).all()
    domain_ids = [a.domain_id for a in assignments]
    return Domain.query.filter(Domain.id.in_(domain_ids)).all()


def assert_domain_access(domain_id):
    """Abort 403 if current coordinator is not assigned to this domain."""
    assignment = DomainAssignment.query.filter_by(
        user_id=current_user.id,
        domain_id=domain_id,
        assignment_type="coordinator",
    ).first()
    if not assignment:
        abort(403)


# ── Dashboard ──────────────────────────────────────────────────────────────

@coordinator_bp.route("/dashboard")
@coordinator_required
def dashboard():
    my_domains = get_my_domains()
    domain_ids = [d.id for d in my_domains]

    enrolled_students = StudentDomainEnrollment.query.filter(
        StudentDomainEnrollment.domain_id.in_(domain_ids),
        StudentDomainEnrollment.is_active == True,
    ).count()

    published_days = LearningDay.query.filter(
        LearningDay.domain_id.in_(domain_ids),
        LearningDay.status == "published",
    ).count()

    assessments_submitted = AssessmentAttempt.query.join(Assessment).filter(
        Assessment.domain_id.in_(domain_ids),
        AssessmentAttempt.status.in_(["submitted", "graded"]),
    ).count()

    pending_grading = AssessmentAttempt.query.join(Assessment).filter(
        Assessment.domain_id.in_(domain_ids),
        AssessmentAttempt.status == "submitted",
    ).count()

    pending_evidences = TaskEvidence.query.join(EliteTask).filter(
        EliteTask.domain_id.in_(domain_ids),
        TaskEvidence.status == "pending",
    ).count()

    # Student progress by day
    progress_data = []
    primary_domain = my_domains[0] if my_domains else None
    if primary_domain:
        days = primary_domain.learning_days.filter_by(status="published").all()
        for day in days[:7]:
            completed = ContentCompletion.query.filter_by(
                learning_day_id=day.id, is_day_complete=True
            ).count()
            in_progress = ContentCompletion.query.filter_by(
                learning_day_id=day.id, is_day_complete=False
            ).count()
            total_enrolled = StudentDomainEnrollment.query.filter_by(
                domain_id=primary_domain.id, is_active=True
            ).count()
            not_started = max(total_enrolled - completed - in_progress, 0)
            progress_data.append({
                "day": f"Day {day.day_number}",
                "completed": completed,
                "in_progress": in_progress,
                "not_started": not_started,
            })

    # Recent activity
    recent_attempts = AssessmentAttempt.query.join(Assessment).filter(
        Assessment.domain_id.in_(domain_ids),
    ).order_by(desc(AssessmentAttempt.submitted_at)).limit(10).all()

    return render_template(
        "coordinator/dashboard.html",
        my_domains=my_domains,
        enrolled_students=enrolled_students,
        published_days=published_days,
        assessments_submitted=assessments_submitted,
        pending_grading=pending_grading,
        pending_evidences=pending_evidences,
        progress_data=progress_data,
        recent_attempts=recent_attempts,
        primary_domain=primary_domain,
    )


# ── Content Management ─────────────────────────────────────────────────────

@coordinator_bp.route("/domain/<int:domain_id>/content")
@coordinator_required
def content(domain_id):
    assert_domain_access(domain_id)
    domain = Domain.query.get_or_404(domain_id)
    days = domain.learning_days.order_by(LearningDay.day_number.asc()).all()
    return render_template(
        "coordinator/content.html",
        domain=domain,
        days=days,
        my_domains=get_my_domains(),
    )


@coordinator_bp.route("/domain/<int:domain_id>/day/new", methods=["GET", "POST"])
@coordinator_required
def new_day(domain_id):
    assert_domain_access(domain_id)
    domain = Domain.query.get_or_404(domain_id)

    if request.method == "POST":
        step = request.form.get("step", "1")
        if step == "1":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            objectives = request.form.get("learning_objectives", "").strip()
            if not title:
                flash("Day title is required.", "warning")
                return render_template("coordinator/day_wizard.html", domain=domain, step=1, my_domains=get_my_domains())

            # Get next day number
            last = domain.learning_days.order_by(desc(LearningDay.day_number)).first()
            next_num = (last.day_number + 1) if last else 1

            day = LearningDay(
                domain_id=domain_id,
                day_number=next_num,
                title=title,
                description=description,
                learning_objectives=objectives,
                status="draft",
                created_by=current_user.id,
            )
            db.session.add(day)
            db.session.commit()
            flash(f"Day {next_num}: {title} created.", "success")
            return redirect(url_for("coordinator.edit_day", domain_id=domain_id, day_id=day.id))

    return render_template("coordinator/day_wizard.html", domain=domain, step=1, my_domains=get_my_domains())


@coordinator_bp.route("/domain/<int:domain_id>/day/<int:day_id>/edit", methods=["GET", "POST"])
@coordinator_required
def edit_day(domain_id, day_id):
    assert_domain_access(domain_id)
    domain = Domain.query.get_or_404(domain_id)
    day = LearningDay.query.filter_by(id=day_id, domain_id=domain_id).first_or_404()

    if request.method == "POST":
        action = request.form.get("action")
        day.title = request.form.get("title", day.title).strip()
        day.description = request.form.get("description", "").strip()
        day.learning_objectives = request.form.get("learning_objectives", "").strip()
        day.updated_at = datetime.utcnow()

        if action == "publish":
            day.status = "published"
            day.published_at = datetime.utcnow()
            flash(f"Day {day.day_number} published!", "success")
        elif action == "draft":
            day.status = "draft"
            flash("Saved as draft.", "info")
        elif action == "lock":
            day.status = "locked"
            day.is_locked = True
            flash("Day locked.", "info")

        db.session.commit()
        return redirect(url_for("coordinator.content", domain_id=domain_id))

    return render_template(
        "coordinator/edit_day.html",
        domain=domain,
        day=day,
        my_domains=get_my_domains(),
    )


@coordinator_bp.route("/domain/<int:domain_id>/day/<int:day_id>/material/add", methods=["GET", "POST"])
@coordinator_required
def add_material(domain_id, day_id):
    assert_domain_access(domain_id)
    domain = Domain.query.get_or_404(domain_id)
    day = LearningDay.query.filter_by(id=day_id, domain_id=domain_id).first_or_404()

    if request.method == "POST":
        mat_type = request.form.get("material_type", "link")
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        url_val = request.form.get("url", "").strip()
        duration = request.form.get("duration_minutes", type=int)

        file_key = None
        file_name = None
        file_size = None

        if mat_type in ("pdf", "code"):
            f = request.files.get("material_file")
            if f and f.filename:
                from app.services.storage import upload_file
                result = upload_file(f, folder="materials")
                if result:
                    file_key = result["key"]
                    file_name = result["name"]
                    file_size = result["size"]

        last_order = db.session.query(func.max(LearningMaterial.display_order)).filter_by(
            learning_day_id=day_id
        ).scalar() or 0

        mat = LearningMaterial(
            learning_day_id=day_id,
            title=title,
            material_type=mat_type,
            description=description,
            url=url_val or None,
            file_key=file_key,
            file_name=file_name,
            file_size=file_size,
            duration_minutes=duration,
            display_order=last_order + 1,
            status="published",
            created_by=current_user.id,
        )
        db.session.add(mat)
        db.session.commit()
        flash(f"Material '{title}' added.", "success")
        return redirect(url_for("coordinator.edit_day", domain_id=domain_id, day_id=day_id))

    return render_template(
        "coordinator/add_material.html",
        domain=domain,
        day=day,
        my_domains=get_my_domains(),
    )


# ── Assessment Builder ─────────────────────────────────────────────────────

@coordinator_bp.route("/domain/<int:domain_id>/assessments")
@coordinator_required
def assessments(domain_id):
    assert_domain_access(domain_id)
    domain = Domain.query.get_or_404(domain_id)
    items = Assessment.query.filter_by(domain_id=domain_id).order_by(
        desc(Assessment.created_at)
    ).all()
    return render_template(
        "coordinator/assessments.html",
        domain=domain,
        assessments=items,
        my_domains=get_my_domains(),
    )


@coordinator_bp.route("/domain/<int:domain_id>/assessments/new", methods=["GET", "POST"])
@coordinator_required
def new_assessment(domain_id):
    assert_domain_access(domain_id)
    domain = Domain.query.get_or_404(domain_id)

    if request.method == "POST":
        step = request.form.get("step", "1")
        if step == "1":
            title = request.form.get("title", "").strip()
            a_type = request.form.get("assessment_type", "mcq")
            day_id = request.form.get("learning_day_id", type=int)
            instructions = request.form.get("instructions", "").strip()
            time_limit = request.form.get("time_limit_minutes", type=int)
            max_attempts = request.form.get("max_attempts", 1, type=int)

            if not title:
                flash("Assessment title is required.", "warning")
                days = domain.learning_days.filter_by(status="published").all()
                return render_template("coordinator/new_assessment.html", domain=domain, days=days, my_domains=get_my_domains())

            assessment = Assessment(
                domain_id=domain_id,
                learning_day_id=day_id or None,
                title=title,
                assessment_type=a_type,
                instructions=instructions,
                time_limit_minutes=time_limit,
                max_attempts=max_attempts,
                status="draft",
                created_by=current_user.id,
            )
            db.session.add(assessment)
            db.session.commit()
            flash(f"Assessment '{title}' created.", "success")
            return redirect(url_for("coordinator.edit_assessment", domain_id=domain_id, assessment_id=assessment.id))

    days = domain.learning_days.filter_by(status="published").all()
    return render_template(
        "coordinator/new_assessment.html",
        domain=domain,
        days=days,
        my_domains=get_my_domains(),
    )


@coordinator_bp.route("/domain/<int:domain_id>/assessments/<int:assessment_id>/edit", methods=["GET", "POST"])
@coordinator_required
def edit_assessment(domain_id, assessment_id):
    assert_domain_access(domain_id)
    domain = Domain.query.get_or_404(domain_id)
    assessment = Assessment.query.filter_by(id=assessment_id, domain_id=domain_id).first_or_404()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "publish":
            assessment.status = "published"
            assessment.published_at = datetime.utcnow()
            flash("Assessment published!", "success")
        elif action == "draft":
            assessment.status = "draft"
            flash("Saved as draft.", "info")
        assessment.total_marks = sum(q.marks for q in assessment.questions)
        db.session.commit()
        return redirect(url_for("coordinator.assessments", domain_id=domain_id))

    return render_template(
        "coordinator/edit_assessment.html",
        domain=domain,
        assessment=assessment,
        my_domains=get_my_domains(),
    )


@coordinator_bp.route("/domain/<int:domain_id>/assessments/<int:assessment_id>/question/add", methods=["POST"])
@coordinator_required
def add_question(domain_id, assessment_id):
    assert_domain_access(domain_id)
    assessment = Assessment.query.filter_by(id=assessment_id, domain_id=domain_id).first_or_404()

    q_type = request.form.get("question_type", "mcq")
    q_text = request.form.get("question_text", "").strip()
    marks = request.form.get("marks", 1, type=int)

    if not q_text:
        flash("Question text is required.", "warning")
        return redirect(url_for("coordinator.edit_assessment", domain_id=domain_id, assessment_id=assessment_id))

    last_order = db.session.query(func.max(AssessmentQuestion.display_order)).filter_by(
        assessment_id=assessment_id
    ).scalar() or 0

    question = AssessmentQuestion(
        assessment_id=assessment_id,
        question_type=q_type,
        question_text=q_text,
        marks=marks,
        display_order=last_order + 1,
        constraints=request.form.get("constraints", "").strip() or None,
        sample_input=request.form.get("sample_input", "").strip() or None,
        sample_output=request.form.get("sample_output", "").strip() or None,
    )
    db.session.add(question)
    db.session.flush()

    # Add MCQ options
    if q_type == "mcq":
        correct_idx = request.form.get("correct_option", type=int)
        for i in range(1, 6):
            opt_text = request.form.get(f"option_{i}", "").strip()
            if opt_text:
                opt = AssessmentOption(
                    question_id=question.id,
                    option_text=opt_text,
                    is_correct=(i - 1 == correct_idx),
                    display_order=i,
                )
                db.session.add(opt)

    assessment.total_marks = sum(q.marks for q in assessment.questions) + marks
    db.session.commit()
    flash("Question added.", "success")
    return redirect(url_for("coordinator.edit_assessment", domain_id=domain_id, assessment_id=assessment_id))


# ── Submissions & Grading ──────────────────────────────────────────────────

@coordinator_bp.route("/submissions")
@coordinator_required
def submissions():
    my_domains = get_my_domains()
    domain_ids = [d.id for d in my_domains]

    status_filter = request.args.get("status", "all")
    domain_filter = request.args.get("domain", type=int)
    search = request.args.get("q", "").strip()

    query = AssessmentAttempt.query.join(Assessment).filter(
        Assessment.domain_id.in_(domain_ids),
        AssessmentAttempt.status.in_(["submitted", "graded"]),
    )

    if status_filter != "all":
        query = query.filter(AssessmentAttempt.status == status_filter)
    if domain_filter:
        query = query.filter(Assessment.domain_id == domain_filter)
    if search:
        query = query.join(User, User.id == AssessmentAttempt.student_id).filter(
            db.or_(User.name.ilike(f"%{search}%"), User.register_number.ilike(f"%{search}%"))
        )

    attempts = query.order_by(desc(AssessmentAttempt.submitted_at)).paginate(
        page=request.args.get("page", 1, type=int), per_page=20
    )

    return render_template(
        "coordinator/submissions.html",
        attempts=attempts,
        my_domains=my_domains,
        status_filter=status_filter,
        domain_filter=domain_filter,
        search=search,
    )


@coordinator_bp.route("/submissions/<int:attempt_id>/grade", methods=["GET", "POST"])
@coordinator_required
def grade_submission(attempt_id):
    attempt = AssessmentAttempt.query.get_or_404(attempt_id)
    assert_domain_access(attempt.assessment.domain_id)

    if request.method == "POST":
        action = request.form.get("action", "save_draft")
        score = request.form.get("score", type=int)
        feedback = request.form.get("feedback", "").strip()

        attempt.score = score
        attempt.feedback = feedback
        attempt.graded_by = current_user.id
        attempt.graded_at = datetime.utcnow()

        if action == "submit_grade":
            attempt.status = "graded"
            flash("Grade submitted.", "success")
        else:
            flash("Draft saved.", "info")

        db.session.commit()
        return redirect(url_for("coordinator.submissions"))

    return render_template(
        "coordinator/grade_submission.html",
        attempt=attempt,
        my_domains=get_my_domains(),
    )


# ── Evidence Review ────────────────────────────────────────────────────────

@coordinator_bp.route("/evidence")
@coordinator_required
def evidence_list():
    my_domains = get_my_domains()
    domain_ids = [d.id for d in my_domains]

    status_filter = request.args.get("status", "pending")
    evidences = TaskEvidence.query.join(EliteTask).filter(
        db.or_(
            EliteTask.domain_id.in_(domain_ids),
            EliteTask.domain_id.is_(None),
        ),
        TaskEvidence.status == status_filter if status_filter != "all" else True,
    ).order_by(desc(TaskEvidence.submitted_at)).paginate(
        page=request.args.get("page", 1, type=int), per_page=20
    )

    return render_template(
        "coordinator/evidence_list.html",
        evidences=evidences,
        my_domains=my_domains,
        status_filter=status_filter,
    )


@coordinator_bp.route("/evidence/<int:evidence_id>/review", methods=["POST"])
@coordinator_required
def review_evidence(evidence_id):
    evidence = TaskEvidence.query.get_or_404(evidence_id)
    action = request.form.get("action")  # approve | reject
    feedback = request.form.get("feedback", "").strip()

    evidence.reviewed_by = current_user.id
    evidence.reviewed_at = datetime.utcnow()
    evidence.reviewer_feedback = feedback

    if action == "approve":
        evidence.status = "approved"
        evidence.points_awarded = evidence.task.potential_points

        # Award points via ledger
        ledger = PointLedger(
            student_id=evidence.student_id,
            points=evidence.points_awarded,
            transaction_type="task_approval",
            reference_type="TaskEvidence",
            reference_id=evidence.id,
            description=f"Elite Task approved: {evidence.task.title}",
            created_by=current_user.id,
        )
        db.session.add(ledger)
        db.session.flush()
        evidence.point_ledger_id = ledger.id

        # Notify student
        note = Notification(
            user_id=evidence.student_id,
            title="Task Approved! 🎉",
            message=f"Your evidence for '{evidence.task.title}' was approved. +{evidence.points_awarded} points!",
            notification_type="success",
            link_url=url_for("student.tasks"),
        )
        db.session.add(note)
        flash(f"Evidence approved. {evidence.points_awarded} points awarded.", "success")
    elif action == "reject":
        evidence.status = "rejected"
        evidence.points_awarded = 0
        note = Notification(
            user_id=evidence.student_id,
            title="Task Evidence Rejected",
            message=f"Your evidence for '{evidence.task.title}' was rejected. Reason: {feedback}",
            notification_type="error",
        )
        db.session.add(note)
        flash("Evidence rejected.", "info")

    db.session.commit()
    return redirect(url_for("coordinator.evidence_list"))


# ── Students ───────────────────────────────────────────────────────────────

@coordinator_bp.route("/students")
@coordinator_required
def students():
    my_domains = get_my_domains()
    domain_ids = [d.id for d in my_domains]
    domain_filter = request.args.get("domain", type=int) or (domain_ids[0] if domain_ids else None)
    search = request.args.get("q", "").strip()

    query = User.query.join(
        StudentDomainEnrollment,
        StudentDomainEnrollment.student_id == User.id
    ).filter(
        StudentDomainEnrollment.domain_id == domain_filter,
        StudentDomainEnrollment.is_active == True,
        User.role == "student",
    ) if domain_filter else User.query.filter_by(role="student")

    if search:
        query = query.filter(
            db.or_(User.name.ilike(f"%{search}%"), User.register_number.ilike(f"%{search}%"))
        )

    students_list = query.order_by(User.name.asc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=30
    )

    return render_template(
        "coordinator/students.html",
        students=students_list,
        my_domains=my_domains,
        domain_filter=domain_filter,
        search=search,
    )
