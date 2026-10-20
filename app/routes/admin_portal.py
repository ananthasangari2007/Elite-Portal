"""
Admin Portal Blueprint — Elite Portal
Platform-wide management: users, domains, content, assessments, tasks, announcements, settings, audit logs.
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
    LearningDay, LearningMaterial, Assessment, AssessmentAttempt,
    EliteTask, TaskEvidence, PointLedger, PointAdjustmentRequest,
    Appeal, StudentRequest, Announcement, Notification,
    AuditLog, SystemSetting,
)

admin_portal_bp = Blueprint("admin_portal", __name__, url_prefix="/admin")


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def log_action(action, target_type=None, target_id=None, description=None,
               old_value=None, new_value=None):
    """Record an immutable audit log entry."""
    entry = AuditLog(
        actor_id=current_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        description=description,
        old_value=old_value,
        new_value=new_value,
        ip_address=request.remote_addr,
    )
    db.session.add(entry)


# ── Dashboard ──────────────────────────────────────────────────────────────

@admin_portal_bp.route("/dashboard")
@admin_required
def dashboard():
    total_students = User.query.filter_by(role="student").count()
    total_faculty = User.query.filter(
        User.role.in_(["coordinator", "faculty"])
    ).count()
    total_assessments = Assessment.query.count()
    total_submissions = AssessmentAttempt.query.filter(
        AssessmentAttempt.status.in_(["submitted", "graded"])
    ).count()

    pending_approvals = {
        "point_adjustments": PointAdjustmentRequest.query.filter_by(status="pending").count(),
        "task_evidences": TaskEvidence.query.filter_by(status="pending").count(),
        "appeals": Appeal.query.filter_by(status="open").count(),
        "student_registrations": User.query.filter_by(role="student", approval_status="pending").count(),
    }

    # System status (basic checks)
    system_status = [
        {"name": "Database", "status": "Operational", "ok": True},
        {"name": "File Storage", "status": "Check R2 config", "ok": False},
        {"name": "Email", "status": "Not configured" if not _mail_configured() else "Operational",
         "ok": _mail_configured()},
    ]

    # Platform activity chart data (recent weeks)
    from datetime import timedelta
    weeks_data = []
    for week_offset in range(3, -1, -1):
        start = datetime.utcnow() - timedelta(weeks=week_offset + 1)
        end = datetime.utcnow() - timedelta(weeks=week_offset)
        label = f"Week {4 - week_offset}"
        new_users = User.query.filter(
            User.created_at >= start, User.created_at < end
        ).count()
        new_assessments = Assessment.query.filter(
            Assessment.created_at >= start, Assessment.created_at < end
        ).count()
        new_submissions = AssessmentAttempt.query.filter(
            AssessmentAttempt.started_at >= start, AssessmentAttempt.started_at < end
        ).count()
        weeks_data.append({
            "label": label,
            "users": new_users,
            "assessments": new_assessments,
            "submissions": new_submissions,
        })

    # Recent activity
    recent_logs = AuditLog.query.order_by(desc(AuditLog.created_at)).limit(10).all()
    recent_registrations = User.query.filter_by(role="student").order_by(
        desc(User.created_at)
    ).limit(5).all()

    return render_template(
        "admin/dashboard.html",
        total_students=total_students,
        total_faculty=total_faculty,
        total_assessments=total_assessments,
        total_submissions=total_submissions,
        pending_approvals=pending_approvals,
        system_status=system_status,
        weeks_data=weeks_data,
        recent_logs=recent_logs,
        recent_registrations=recent_registrations,
    )


def _mail_configured():
    from flask import current_app
    return bool(current_app.config.get("MAIL_SERVER"))


# ── User Management ────────────────────────────────────────────────────────

@admin_portal_bp.route("/users")
@admin_required
def users():
    tab = request.args.get("tab", "all")
    role_filter = request.args.get("role", "all")
    status_filter = request.args.get("status", "all")
    search = request.args.get("q", "").strip()

    query = User.query
    if role_filter != "all":
        query = query.filter_by(role=role_filter)
    if status_filter == "active":
        query = query.filter_by(is_active_account=True)
    elif status_filter == "inactive":
        query = query.filter_by(is_active_account=False)
    elif status_filter == "pending":
        query = query.filter_by(approval_status="pending")
    if search:
        query = query.filter(
            db.or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.register_number.ilike(f"%{search}%"),
            )
        )

    users_paginated = query.order_by(User.created_at.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=20
    )

    counts = {
        "all": User.query.count(),
        "students": User.query.filter_by(role="student").count(),
        "faculty": User.query.filter_by(role="faculty").count(),
        "coordinators": User.query.filter_by(role="coordinator").count(),
        "admins": User.query.filter_by(role="admin").count(),
    }

    return render_template(
        "admin/users.html",
        users=users_paginated,
        tab=tab,
        role_filter=role_filter,
        status_filter=status_filter,
        search=search,
        counts=counts,
    )


@admin_portal_bp.route("/users/create", methods=["GET", "POST"])
@admin_required
def create_user():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "student")
        password = request.form.get("password", "")
        register_number = request.form.get("register_number", "").strip()
        department = request.form.get("department", "").strip()

        if not name or not email or not password:
            flash("Name, email, and password are required.", "warning")
            return render_template("admin/create_user.html")

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return render_template("admin/create_user.html")

        user = User(
            name=name,
            email=email,
            role=role,
            approval_status="approved",
            profile_completed=True,
            register_number=register_number or None,
            department=department or None,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        log_action("user.create", "User", user.id,
                   f"Created {role} account for {email}")
        db.session.commit()
        flash(f"User {name} ({role}) created.", "success")
        return redirect(url_for("admin_portal.users"))

    return render_template("admin/create_user.html")


@admin_portal_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        old_role = user.role
        old_status = user.is_active_account

        user.name = request.form.get("name", user.name).strip()
        user.role = request.form.get("role", user.role)
        user.department = request.form.get("department", "").strip() or None
        user.register_number = request.form.get("register_number", "").strip() or None
        user.is_active_account = request.form.get("is_active") == "on"
        user.approval_status = request.form.get("approval_status", user.approval_status)

        new_password = request.form.get("new_password", "").strip()
        if new_password and len(new_password) >= 8:
            user.set_password(new_password)
            log_action("user.password_reset", "User", user.id,
                       f"Admin reset password for {user.email}")

        if user.role != old_role:
            log_action("user.role_change", "User", user.id,
                       f"Role changed from {old_role} to {user.role}",
                       old_value={"role": old_role}, new_value={"role": user.role})
        if user.is_active_account != old_status:
            action = "user.activate" if user.is_active_account else "user.deactivate"
            log_action(action, "User", user.id,
                       f"Account {'activated' if user.is_active_account else 'deactivated'}")

        db.session.commit()
        flash(f"User {user.name} updated.", "success")
        return redirect(url_for("admin_portal.users"))

    all_domains = Domain.query.filter_by(is_active=True).all()
    domain_assignments = DomainAssignment.query.filter_by(user_id=user.id).all()

    return render_template(
        "admin/edit_user.html",
        user=user,
        all_domains=all_domains,
        domain_assignments=domain_assignments,
    )


@admin_portal_bp.route("/users/<int:user_id>/approve", methods=["POST"])
@admin_required
def approve_user(user_id):
    user = User.query.get_or_404(user_id)
    action = request.form.get("action")
    if action == "approve":
        user.approval_status = "approved"
        user.is_active_account = True
        flash(f"Account for {user.name} approved.", "success")
        log_action("user.approve", "User", user_id, f"Approved student {user.email}")
        # Enroll in DSA automatically
        dsa = Domain.query.filter_by(code="DSA", is_compulsory=True).first()
        if dsa:
            existing = StudentDomainEnrollment.query.filter_by(
                student_id=user_id, domain_id=dsa.id
            ).first()
            if not existing:
                enrollment = StudentDomainEnrollment(
                    student_id=user_id,
                    domain_id=dsa.id,
                    enrolled_by=current_user.id,
                )
                db.session.add(enrollment)
    elif action == "reject":
        user.approval_status = "rejected"
        user.is_active_account = False
        flash(f"Account for {user.name} rejected.", "info")
        log_action("user.reject", "User", user_id, f"Rejected student {user.email}")

    db.session.commit()
    return redirect(url_for("admin_portal.users"))


# ── Domain Management ──────────────────────────────────────────────────────

@admin_portal_bp.route("/domains")
@admin_required
def domains():
    all_domains = Domain.query.order_by(Domain.is_compulsory.desc(), Domain.name.asc()).all()
    domain_stats = []
    for d in all_domains:
        enrolled = StudentDomainEnrollment.query.filter_by(domain_id=d.id, is_active=True).count()
        coordinators = DomainAssignment.query.filter_by(
            domain_id=d.id, assignment_type="coordinator"
        ).count()
        domain_stats.append({
            "domain": d,
            "enrolled": enrolled,
            "coordinators": coordinators,
            "days": d.learning_days.count(),
            "assessments": Assessment.query.filter_by(domain_id=d.id).count(),
        })

    return render_template("admin/domains.html", domain_stats=domain_stats)


@admin_portal_bp.route("/domains/create", methods=["GET", "POST"])
@admin_required
def create_domain():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        is_compulsory = request.form.get("is_compulsory") == "on"

        if not code or not name:
            flash("Code and name are required.", "warning")
            return render_template("admin/create_domain.html")

        if Domain.query.filter_by(code=code).first():
            flash("Domain code already exists.", "danger")
            return render_template("admin/create_domain.html")

        domain = Domain(
            code=code, name=name, description=description,
            is_compulsory=is_compulsory, is_active=True,
            created_by=current_user.id,
        )
        db.session.add(domain)
        db.session.flush()
        log_action("domain.create", "Domain", domain.id, f"Created domain {code}")
        db.session.commit()
        flash(f"Domain {name} created.", "success")
        return redirect(url_for("admin_portal.domains"))

    return render_template("admin/create_domain.html")


@admin_portal_bp.route("/domains/<int:domain_id>/assign", methods=["POST"])
@admin_required
def assign_domain(domain_id):
    domain = Domain.query.get_or_404(domain_id)
    user_id = request.form.get("user_id", type=int)
    assignment_type = request.form.get("assignment_type", "coordinator")
    action = request.form.get("action", "add")

    user = User.query.get_or_404(user_id)

    if action == "add":
        existing = DomainAssignment.query.filter_by(
            domain_id=domain_id, user_id=user_id, assignment_type=assignment_type
        ).first()
        if not existing:
            assignment = DomainAssignment(
                domain_id=domain_id, user_id=user_id,
                assignment_type=assignment_type,
                assigned_by=current_user.id,
            )
            db.session.add(assignment)
            log_action("domain.assign", "Domain", domain_id,
                       f"Assigned {user.email} as {assignment_type} to {domain.code}")
            db.session.commit()
            flash(f"{user.name} assigned as {assignment_type} to {domain.name}.", "success")
    elif action == "remove":
        DomainAssignment.query.filter_by(
            domain_id=domain_id, user_id=user_id, assignment_type=assignment_type
        ).delete()
        log_action("domain.unassign", "Domain", domain_id,
                   f"Removed {user.email} as {assignment_type} from {domain.code}")
        db.session.commit()
        flash(f"{user.name} removed from {domain.name}.", "info")

    return redirect(url_for("admin_portal.edit_domain", domain_id=domain_id))


@admin_portal_bp.route("/domains/<int:domain_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_domain(domain_id):
    domain = Domain.query.get_or_404(domain_id)

    if request.method == "POST":
        domain.name = request.form.get("name", domain.name).strip()
        domain.description = request.form.get("description", "").strip()
        domain.is_active = request.form.get("is_active") == "on"
        domain.enrollment_limit = request.form.get("enrollment_limit", type=int)
        db.session.commit()
        flash(f"Domain {domain.name} updated.", "success")
        return redirect(url_for("admin_portal.domains"))

    coordinators = User.query.filter_by(role="coordinator").all()
    faculty_members = User.query.filter_by(role="faculty").all()
    assignments = DomainAssignment.query.filter_by(domain_id=domain_id).all()

    return render_template(
        "admin/edit_domain.html",
        domain=domain,
        coordinators=coordinators,
        faculty_members=faculty_members,
        assignments=assignments,
    )


# ── Assessment Management ──────────────────────────────────────────────────

@admin_portal_bp.route("/assessments")
@admin_required
def assessments():
    domain_filter = request.args.get("domain", type=int)
    status_filter = request.args.get("status", "all")
    type_filter = request.args.get("type", "all")
    search = request.args.get("q", "").strip()

    query = Assessment.query
    if domain_filter:
        query = query.filter_by(domain_id=domain_filter)
    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    if type_filter != "all":
        query = query.filter_by(assessment_type=type_filter)
    if search:
        query = query.filter(Assessment.title.ilike(f"%{search}%"))

    items = query.order_by(desc(Assessment.created_at)).paginate(
        page=request.args.get("page", 1, type=int), per_page=20
    )
    all_domains = Domain.query.filter_by(is_active=True).all()

    return render_template(
        "admin/assessments.html",
        assessments=items,
        all_domains=all_domains,
        domain_filter=domain_filter,
        status_filter=status_filter,
        type_filter=type_filter,
        search=search,
    )


@admin_portal_bp.route("/assessments/<int:assessment_id>/reopen", methods=["POST"])
@admin_required
def reopen_assessment(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    reason = request.form.get("reason", "").strip()
    if not reason:
        flash("A reason is required to reopen an assessment.", "warning")
        return redirect(url_for("admin_portal.assessments"))

    old_status = assessment.status
    assessment.status = "published"
    assessment.scheduled_end = None
    log_action("assessment.reopen", "Assessment", assessment_id,
               f"Reopened assessment: {assessment.title}. Reason: {reason}",
               old_value={"status": old_status}, new_value={"status": "published"})
    db.session.commit()
    flash(f"Assessment '{assessment.title}' reopened.", "success")
    return redirect(url_for("admin_portal.assessments"))


# ── Elite Tasks Management ─────────────────────────────────────────────────

@admin_portal_bp.route("/tasks")
@admin_required
def elite_tasks():
    tab = request.args.get("tab", "all")
    query = EliteTask.query
    if tab != "all":
        query = query.filter_by(status=tab)
    items = query.order_by(desc(EliteTask.created_at)).paginate(
        page=request.args.get("page", 1, type=int), per_page=20
    )
    all_domains = Domain.query.filter_by(is_active=True).all()
    return render_template(
        "admin/elite_tasks.html",
        tasks=items,
        tab=tab,
        all_domains=all_domains,
    )


@admin_portal_bp.route("/tasks/create", methods=["GET", "POST"])
@admin_required
def create_elite_task():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        instructions = request.form.get("instructions", "").strip()
        domain_id = request.form.get("domain_id", type=int)
        potential_points = request.form.get("potential_points", 100, type=int)
        category = request.form.get("category", "general")
        due_date_str = request.form.get("due_date")
        status = request.form.get("status", "active")

        due_date = None
        if due_date_str:
            try:
                due_date = datetime.fromisoformat(due_date_str)
            except ValueError:
                pass

        task = EliteTask(
            title=title,
            description=description,
            instructions=instructions,
            domain_id=domain_id or None,
            potential_points=potential_points,
            category=category,
            status=status,
            due_date=due_date,
            created_by=current_user.id,
        )
        db.session.add(task)
        db.session.flush()
        log_action("task.create", "EliteTask", task.id, f"Created elite task: {title}")
        db.session.commit()
        flash(f"Elite Task '{title}' created.", "success")
        return redirect(url_for("admin_portal.elite_tasks"))

    all_domains = Domain.query.filter_by(is_active=True).all()
    return render_template("admin/create_elite_task.html", all_domains=all_domains)


# ── Announcements ──────────────────────────────────────────────────────────

@admin_portal_bp.route("/announcements")
@admin_required
def announcements():
    tab = request.args.get("tab", "all")
    query = Announcement.query
    if tab != "all":
        query = query.filter_by(status=tab)
    items = query.order_by(desc(Announcement.created_at)).paginate(
        page=request.args.get("page", 1, type=int), per_page=20
    )
    return render_template("admin/announcements.html", announcements=items, tab=tab)


@admin_portal_bp.route("/announcements/create", methods=["GET", "POST"])
@admin_required
def create_announcement():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        category = request.form.get("category", "general")
        target = request.form.get("target_audience", "all")
        status = request.form.get("status", "published")
        domain_id = request.form.get("target_domain_id", type=int)

        ann = Announcement(
            title=title,
            content=content,
            category=category,
            target_audience=target,
            target_domain_id=domain_id or None,
            status=status,
            created_by=current_user.id,
        )
        db.session.add(ann)

        if status == "published":
            _broadcast_announcement(ann)

        db.session.commit()
        flash(f"Announcement '{title}' created.", "success")
        return redirect(url_for("admin_portal.announcements"))

    all_domains = Domain.query.filter_by(is_active=True).all()
    return render_template("admin/create_announcement.html", all_domains=all_domains)


def _broadcast_announcement(ann):
    """Send notifications to target audience for a published announcement."""
    query = User.query.filter_by(is_active_account=True)
    if ann.target_audience == "students":
        query = query.filter_by(role="student")
    elif ann.target_audience == "coordinators":
        query = query.filter_by(role="coordinator")
    elif ann.target_audience == "faculty":
        query = query.filter_by(role="faculty")
    elif ann.target_audience == "admin":
        query = query.filter_by(role="admin")
    # "all" — no filter

    for user in query.all():
        note = Notification(
            user_id=user.id,
            title=f"📢 {ann.title}",
            message=ann.content[:200],
            notification_type="info",
        )
        db.session.add(note)


# ── Point Adjustments (Admin Review) ──────────────────────────────────────

@admin_portal_bp.route("/point-adjustments")
@admin_required
def point_adjustments():
    tab = request.args.get("tab", "pending")
    adjustments = PointAdjustmentRequest.query.filter_by(
        status=tab if tab != "all" else PointAdjustmentRequest.status
    ).order_by(desc(PointAdjustmentRequest.created_at)).paginate(
        page=request.args.get("page", 1, type=int), per_page=20
    )
    counts = {
        "pending": PointAdjustmentRequest.query.filter_by(status="pending").count(),
        "approved": PointAdjustmentRequest.query.filter_by(status="approved").count(),
        "rejected": PointAdjustmentRequest.query.filter_by(status="rejected").count(),
    }
    return render_template(
        "admin/point_adjustments.html",
        adjustments=adjustments,
        tab=tab,
        counts=counts,
    )


# ── System Settings ────────────────────────────────────────────────────────

@admin_portal_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        key = request.form.get("key")
        value = request.form.get("value", "").strip()

        setting = SystemSetting.query.filter_by(key=key).first()
        if setting:
            old_val = setting.value
            setting.value = value
            setting.updated_by = current_user.id
            log_action("setting.update", "SystemSetting", setting.id,
                       f"Updated setting {key}",
                       old_value={"value": old_val}, new_value={"value": value})
        else:
            setting = SystemSetting(key=key, value=value, updated_by=current_user.id)
            db.session.add(setting)
            log_action("setting.create", "SystemSetting", None,
                       f"Created setting {key}")

        db.session.commit()
        flash(f"Setting '{key}' updated.", "success")

    all_settings = SystemSetting.query.order_by(SystemSetting.key.asc()).all()
    return render_template("admin/settings.html", settings=all_settings)


# ── Audit Logs ─────────────────────────────────────────────────────────────

@admin_portal_bp.route("/audit-logs")
@admin_required
def audit_logs():
    action_filter = request.args.get("action", "")
    actor_id = request.args.get("actor", type=int)
    search = request.args.get("q", "").strip()

    query = AuditLog.query
    if action_filter:
        query = query.filter(AuditLog.action.ilike(f"%{action_filter}%"))
    if actor_id:
        query = query.filter_by(actor_id=actor_id)
    if search:
        query = query.filter(AuditLog.description.ilike(f"%{search}%"))

    logs = query.order_by(desc(AuditLog.created_at)).paginate(
        page=request.args.get("page", 1, type=int), per_page=30
    )

    return render_template("admin/audit_logs.html", logs=logs, action_filter=action_filter)


# ── Analytics ──────────────────────────────────────────────────────────────

@admin_portal_bp.route("/analytics")
@admin_required
def analytics():
    total_students = User.query.filter_by(role="student").count()
    avg_completion = 0
    avg_score = db.session.query(func.avg(AssessmentAttempt.score)).filter(
        AssessmentAttempt.status == "graded"
    ).scalar()
    avg_score = round(float(avg_score), 1) if avg_score else 0
    total_submissions = AssessmentAttempt.query.count()
    total_points = db.session.query(func.coalesce(func.sum(PointLedger.points), 0)).scalar() or 0

    all_domains = Domain.query.filter_by(is_active=True).all()
    domain_distribution = []
    for d in all_domains:
        enrolled = StudentDomainEnrollment.query.filter_by(domain_id=d.id, is_active=True).count()
        domain_distribution.append({"name": d.name, "count": enrolled})

    return render_template(
        "admin/analytics.html",
        total_students=total_students,
        avg_score=avg_score,
        total_submissions=total_submissions,
        total_points=int(total_points),
        domain_distribution=domain_distribution,
        all_domains=all_domains,
    )
