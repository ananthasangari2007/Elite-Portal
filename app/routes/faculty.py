"""
Faculty Coordinator Blueprint — Elite Portal
Review grading, appeals, point adjustments, student requests, and analytics.
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
    LearningDay, ContentCompletion, Assessment, AssessmentAttempt,
    EliteTask, TaskEvidence, PointLedger, PointAdjustmentRequest,
    Appeal, StudentRequest, RequestMessage, Notification, AuditLog,
)

faculty_bp = Blueprint("faculty", __name__, url_prefix="/f")


def faculty_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != "faculty":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def get_my_domains():
    """Return domains assigned to the current faculty member."""
    assignments = DomainAssignment.query.filter_by(
        user_id=current_user.id,
        assignment_type="faculty",
    ).all()
    domain_ids = [a.domain_id for a in assignments]
    # Faculty with no specific assignment can see all domains
    if not domain_ids:
        return Domain.query.filter_by(is_active=True).all()
    return Domain.query.filter(Domain.id.in_(domain_ids)).all()


def get_my_domain_ids():
    domains = get_my_domains()
    return [d.id for d in domains]


# ── Dashboard ──────────────────────────────────────────────────────────────

@faculty_bp.route("/dashboard")
@faculty_required
def dashboard():
    domain_ids = get_my_domain_ids()

    total_students = User.query.filter_by(role="student", is_active_account=True).count()
    pending_grading = AssessmentAttempt.query.join(Assessment).filter(
        Assessment.domain_id.in_(domain_ids),
        AssessmentAttempt.status == "submitted",
    ).count()
    open_appeals = Appeal.query.filter_by(status="open").count()
    pending_adjustments = PointAdjustmentRequest.query.filter_by(status="pending").count()

    # Domain overview
    domain_overview = []
    for domain in get_my_domains():
        enrolled = StudentDomainEnrollment.query.filter_by(
            domain_id=domain.id, is_active=True
        ).count()
        days = domain.published_days_count
        total_days = domain.learning_days.count()
        completion_rate = 0
        if enrolled > 0 and total_days > 0:
            total_possible = enrolled * total_days
            completed = ContentCompletion.query.join(LearningDay).filter(
                LearningDay.domain_id == domain.id,
                ContentCompletion.is_day_complete == True,
            ).count()
            completion_rate = int(completed / total_possible * 100) if total_possible > 0 else 0

        domain_overview.append({
            "domain": domain,
            "enrolled": enrolled,
            "published_days": days,
            "completion_rate": completion_rate,
        })

    # Recent activity
    recent_appeals = Appeal.query.order_by(desc(Appeal.created_at)).limit(5).all()
    recent_adjustments = PointAdjustmentRequest.query.order_by(
        desc(PointAdjustmentRequest.created_at)
    ).limit(5).all()
    recent_requests = StudentRequest.query.filter_by(status="open").order_by(
        desc(StudentRequest.created_at)
    ).limit(5).all()

    return render_template(
        "faculty/dashboard.html",
        total_students=total_students,
        pending_grading=pending_grading,
        open_appeals=open_appeals,
        pending_adjustments=pending_adjustments,
        domain_overview=domain_overview,
        recent_appeals=recent_appeals,
        recent_adjustments=recent_adjustments,
        recent_requests=recent_requests,
        my_domains=get_my_domains(),
    )


# ── My Domains ─────────────────────────────────────────────────────────────

@faculty_bp.route("/domains")
@faculty_required
def my_domains():
    domains = get_my_domains()
    domain_stats = []
    for domain in domains:
        enrolled = StudentDomainEnrollment.query.filter_by(
            domain_id=domain.id, is_active=True
        ).count()
        published_days = domain.published_days_count
        assessments_count = Assessment.query.filter_by(domain_id=domain.id).count()
        avg_score = db.session.query(func.avg(AssessmentAttempt.score)).join(Assessment).filter(
            Assessment.domain_id == domain.id,
            AssessmentAttempt.status == "graded",
            AssessmentAttempt.score.isnot(None),
        ).scalar()
        domain_stats.append({
            "domain": domain,
            "enrolled": enrolled,
            "published_days": published_days,
            "assessments": assessments_count,
            "avg_score": round(float(avg_score), 1) if avg_score else 0,
        })

    return render_template(
        "faculty/domains.html",
        domain_stats=domain_stats,
        my_domains=get_my_domains(),
    )


# ── Review & Grading Queue ─────────────────────────────────────────────────

@faculty_bp.route("/grading")
@faculty_required
def grading():
    domain_ids = get_my_domain_ids()
    tab = request.args.get("tab", "pending")
    domain_filter = request.args.get("domain", type=int)
    a_type_filter = request.args.get("type", "all")
    search = request.args.get("q", "").strip()

    status_map = {
        "pending": ["submitted"],
        "in_review": ["submitted"],
        "completed": ["graded"],
    }
    statuses = status_map.get(tab, ["submitted"])

    query = AssessmentAttempt.query.join(Assessment).filter(
        Assessment.domain_id.in_(domain_ids),
        AssessmentAttempt.status.in_(statuses),
    )

    if domain_filter:
        query = query.filter(Assessment.domain_id == domain_filter)
    if a_type_filter != "all":
        query = query.filter(Assessment.assessment_type == a_type_filter)
    if search:
        query = query.join(User, User.id == AssessmentAttempt.student_id).filter(
            db.or_(User.name.ilike(f"%{search}%"), User.register_number.ilike(f"%{search}%"))
        )

    attempts = query.order_by(desc(AssessmentAttempt.submitted_at)).paginate(
        page=request.args.get("page", 1, type=int), per_page=20
    )

    pending_count = AssessmentAttempt.query.join(Assessment).filter(
        Assessment.domain_id.in_(domain_ids),
        AssessmentAttempt.status == "submitted",
    ).count()
    completed_count = AssessmentAttempt.query.join(Assessment).filter(
        Assessment.domain_id.in_(domain_ids),
        AssessmentAttempt.status == "graded",
    ).count()

    return render_template(
        "faculty/grading.html",
        attempts=attempts,
        tab=tab,
        my_domains=get_my_domains(),
        domain_filter=domain_filter,
        a_type_filter=a_type_filter,
        search=search,
        pending_count=pending_count,
        completed_count=completed_count,
    )


@faculty_bp.route("/grading/<int:attempt_id>", methods=["GET", "POST"])
@faculty_required
def grade_attempt(attempt_id):
    attempt = AssessmentAttempt.query.get_or_404(attempt_id)

    if request.method == "POST":
        action = request.form.get("action")
        score = request.form.get("score", type=int)
        feedback = request.form.get("feedback", "").strip()

        attempt.score = score
        attempt.feedback = feedback
        attempt.graded_by = current_user.id
        attempt.graded_at = datetime.utcnow()

        if action == "submit_grade":
            attempt.status = "graded"
            # Award points
            if score is not None and score > 0:
                ledger = PointLedger(
                    student_id=attempt.student_id,
                    points=score,
                    transaction_type="assessment",
                    reference_type="AssessmentAttempt",
                    reference_id=attempt.id,
                    domain_id=attempt.assessment.domain_id,
                    description=f"Assessment graded: {attempt.assessment.title} ({score}/{attempt.total_marks})",
                    created_by=current_user.id,
                )
                db.session.add(ledger)
            note = Notification(
                user_id=attempt.student_id,
                title="Assessment Graded",
                message=f"{attempt.assessment.title} has been graded. Score: {score}/{attempt.total_marks}",
                notification_type="info",
            )
            db.session.add(note)
            flash("Grade submitted and student notified.", "success")
        elif action == "request_changes":
            flash("Grade saved as draft.", "info")
        else:
            flash("Draft saved.", "info")

        db.session.commit()
        return redirect(url_for("faculty.grading"))

    return render_template(
        "faculty/grade_attempt.html",
        attempt=attempt,
        my_domains=get_my_domains(),
    )


# ── Appeals ────────────────────────────────────────────────────────────────

@faculty_bp.route("/appeals")
@faculty_required
def appeals():
    domain_ids = get_my_domain_ids()
    tab = request.args.get("tab", "open")
    status_map = {
        "open": "open",
        "in_review": "in_review",
        "resolved": "resolved",
        "rejected": "rejected",
    }
    status = status_map.get(tab, "open")
    search = request.args.get("q", "").strip()

    query = Appeal.query.filter_by(status=status)
    if search:
        query = query.join(User, User.id == Appeal.student_id).filter(
            db.or_(User.name.ilike(f"%{search}%"), User.register_number.ilike(f"%{search}%"))
        )

    appeals_list = query.order_by(desc(Appeal.created_at)).paginate(
        page=request.args.get("page", 1, type=int), per_page=20
    )

    counts = {
        "open": Appeal.query.filter_by(status="open").count(),
        "in_review": Appeal.query.filter_by(status="in_review").count(),
        "resolved": Appeal.query.filter_by(status="resolved").count(),
        "rejected": Appeal.query.filter_by(status="rejected").count(),
    }

    return render_template(
        "faculty/appeals.html",
        appeals=appeals_list,
        tab=tab,
        counts=counts,
        search=search,
        my_domains=get_my_domains(),
    )


@faculty_bp.route("/appeals/<int:appeal_id>/review", methods=["GET", "POST"])
@faculty_required
def review_appeal(appeal_id):
    appeal = Appeal.query.get_or_404(appeal_id)

    if request.method == "POST":
        action = request.form.get("action")
        comments = request.form.get("review_comments", "").strip()
        new_score = request.form.get("new_score", type=int)

        appeal.review_comments = comments
        appeal.assigned_to = current_user.id

        if action in ("resolve", "reject"):
            appeal.status = "resolved" if action == "resolve" else "rejected"
            appeal.decision = request.form.get("decision", "upheld")
            appeal.new_score = new_score
            appeal.resolved_by = current_user.id
            appeal.resolved_at = datetime.utcnow()

            if action == "resolve" and new_score is not None and appeal.attempt:
                old_score = appeal.attempt.score or 0
                diff = new_score - old_score
                if diff != 0:
                    appeal.attempt.score = new_score
                    # Log ledger entry for grade change
                    ledger = PointLedger(
                        student_id=appeal.student_id,
                        points=diff,
                        transaction_type="adjustment",
                        reference_type="Appeal",
                        reference_id=appeal.id,
                        description=f"Appeal resolved: score adjusted from {old_score} to {new_score}",
                        created_by=current_user.id,
                        is_override=True,
                        override_reason=comments,
                    )
                    db.session.add(ledger)

            note = Notification(
                user_id=appeal.student_id,
                title=f"Appeal {appeal.status.title()}",
                message=f"Your appeal has been {appeal.status}. {comments}",
                notification_type="success" if action == "resolve" else "error",
            )
            db.session.add(note)
            flash(f"Appeal {appeal.status}.", "success")
        else:
            appeal.status = "in_review"
            flash("Appeal marked as In Review.", "info")

        db.session.commit()
        return redirect(url_for("faculty.appeals"))

    return render_template(
        "faculty/review_appeal.html",
        appeal=appeal,
        my_domains=get_my_domains(),
    )


# ── Point Adjustments ──────────────────────────────────────────────────────

@faculty_bp.route("/point-adjustments")
@faculty_required
def point_adjustments():
    tab = request.args.get("tab", "pending")
    status_map = {"pending": "pending", "approved": "approved", "rejected": "rejected"}
    status = status_map.get(tab, "pending")

    adjustments = PointAdjustmentRequest.query.filter_by(status=status).order_by(
        desc(PointAdjustmentRequest.created_at)
    ).paginate(page=request.args.get("page", 1, type=int), per_page=20)

    counts = {
        "pending": PointAdjustmentRequest.query.filter_by(status="pending").count(),
        "approved": PointAdjustmentRequest.query.filter_by(status="approved").count(),
        "rejected": PointAdjustmentRequest.query.filter_by(status="rejected").count(),
    }

    return render_template(
        "faculty/point_adjustments.html",
        adjustments=adjustments,
        tab=tab,
        counts=counts,
        my_domains=get_my_domains(),
    )


@faculty_bp.route("/point-adjustments/<int:adj_id>/review", methods=["POST"])
@faculty_required
def review_adjustment(adj_id):
    adj = PointAdjustmentRequest.query.get_or_404(adj_id)
    action = request.form.get("action")
    notes = request.form.get("review_notes", "").strip()

    adj.reviewed_by = current_user.id
    adj.review_notes = notes
    adj.reviewed_at = datetime.utcnow()

    if action == "approve":
        adj.status = "approved"
        diff = adj.requested_points - adj.current_points
        ledger = PointLedger(
            student_id=adj.student_id,
            points=diff,
            transaction_type="adjustment",
            reference_type="PointAdjustmentRequest",
            reference_id=adj.id,
            description=f"Point adjustment approved: {adj.request_type}. {notes}",
            created_by=current_user.id,
            is_override=True,
            override_reason=notes,
        )
        db.session.add(ledger)
        db.session.flush()
        adj.point_ledger_id = ledger.id

        note = Notification(
            user_id=adj.student_id,
            title="Point Adjustment Approved",
            message=f"Your point adjustment request was approved. Change: {diff:+d} points",
            notification_type="success",
        )
        db.session.add(note)
        flash(f"Adjustment approved. {diff:+d} points applied.", "success")
    elif action == "reject":
        adj.status = "rejected"
        note = Notification(
            user_id=adj.student_id,
            title="Point Adjustment Rejected",
            message=f"Your point adjustment request was rejected. {notes}",
            notification_type="error",
        )
        db.session.add(note)
        flash("Adjustment rejected.", "info")

    db.session.commit()
    return redirect(url_for("faculty.point_adjustments"))


# ── Student Requests ───────────────────────────────────────────────────────

@faculty_bp.route("/requests")
@faculty_required
def student_requests():
    tab = request.args.get("tab", "open")
    search = request.args.get("q", "").strip()

    query = StudentRequest.query
    if tab != "all":
        query = query.filter_by(status=tab)
    if search:
        query = query.join(User, User.id == StudentRequest.student_id).filter(
            db.or_(User.name.ilike(f"%{search}%"), StudentRequest.subject.ilike(f"%{search}%"))
        )

    reqs = query.order_by(desc(StudentRequest.created_at)).paginate(
        page=request.args.get("page", 1, type=int), per_page=20
    )

    counts = {
        "open": StudentRequest.query.filter_by(status="open").count(),
        "in_progress": StudentRequest.query.filter_by(status="in_progress").count(),
        "resolved": StudentRequest.query.filter_by(status="resolved").count(),
    }

    return render_template(
        "faculty/student_requests.html",
        requests=reqs,
        tab=tab,
        counts=counts,
        search=search,
        my_domains=get_my_domains(),
    )


@faculty_bp.route("/requests/<int:req_id>", methods=["GET", "POST"])
@faculty_required
def request_conversation(req_id):
    req = StudentRequest.query.get_or_404(req_id)

    if request.method == "POST":
        action = request.form.get("action")
        message_text = request.form.get("message", "").strip()
        new_status = request.form.get("status")

        if message_text:
            msg = RequestMessage(
                request_id=req.id,
                sender_id=current_user.id,
                message=message_text,
            )
            db.session.add(msg)
            req.updated_at = datetime.utcnow()

            note = Notification(
                user_id=req.student_id,
                title="Response to your request",
                message=f"A response was added to your request: {req.subject}",
                notification_type="info",
                link_url=url_for("student.request_detail", request_id=req.id),
            )
            db.session.add(note)

        if new_status and new_status in ("open", "in_progress", "resolved", "closed"):
            req.status = new_status
            if new_status == "resolved":
                req.resolved_at = datetime.utcnow()

        req.assigned_to = current_user.id
        db.session.commit()
        flash("Response sent.", "success")
        return redirect(url_for("faculty.request_conversation", req_id=req_id))

    return render_template(
        "faculty/request_conversation.html",
        req=req,
        my_domains=get_my_domains(),
    )


# ── Students Management ────────────────────────────────────────────────────

@faculty_bp.route("/students")
@faculty_required
def students():
    domain_ids = get_my_domain_ids()
    domain_filter = request.args.get("domain", type=int)
    search = request.args.get("q", "").strip()

    query = User.query.filter_by(role="student", is_active_account=True)
    if search:
        query = query.filter(
            db.or_(User.name.ilike(f"%{search}%"), User.register_number.ilike(f"%{search}%"))
        )

    students_list = query.order_by(User.name.asc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=30
    )

    return render_template(
        "faculty/students.html",
        students=students_list,
        my_domains=get_my_domains(),
        domain_filter=domain_filter,
        search=search,
    )


# ── Analytics ──────────────────────────────────────────────────────────────

@faculty_bp.route("/analytics")
@faculty_required
def analytics():
    domain_ids = get_my_domain_ids()
    my_domains = get_my_domains()

    total_students = User.query.filter_by(role="student", is_active_account=True).count()

    # Average completion rate
    total_possible = 0
    total_completed = 0
    for domain in my_domains:
        enrolled = StudentDomainEnrollment.query.filter_by(
            domain_id=domain.id, is_active=True
        ).count()
        days = domain.learning_days.filter_by(status="published").count()
        possible = enrolled * days
        completed = ContentCompletion.query.join(LearningDay).filter(
            LearningDay.domain_id == domain.id,
            ContentCompletion.is_day_complete == True,
        ).count()
        total_possible += possible
        total_completed += completed

    avg_completion = int(total_completed / total_possible * 100) if total_possible > 0 else 0

    avg_score = db.session.query(func.avg(AssessmentAttempt.score)).join(Assessment).filter(
        Assessment.domain_id.in_(domain_ids),
        AssessmentAttempt.status == "graded",
    ).scalar()
    avg_score = round(float(avg_score), 1) if avg_score else 0

    total_submissions = AssessmentAttempt.query.join(Assessment).filter(
        Assessment.domain_id.in_(domain_ids),
    ).count()

    return render_template(
        "faculty/analytics.html",
        my_domains=my_domains,
        total_students=total_students,
        avg_completion=avg_completion,
        avg_score=avg_score,
        total_submissions=total_submissions,
    )
