"""Admin API — users, domains, content registry, Elite Tasks, announcements, settings, audit."""
from __future__ import annotations

import json
import secrets
import string
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from app.fastapi.auth import require_roles
from app.fastapi.database import db
from app.fastapi.utils import (
    ApiError,
    assessment_public,
    day_public,
    domain_public,
    get_int,
    iso,
    material_public,
    ok,
    paginate,
    parse_dt,
    user_public,
)
from app.models import (
    Announcement,
    Assessment,
    AssessmentAuthorization,
    AuditLog,
    Domain,
    DomainAssignment,
    EliteTask,
    LearningDay,
    LearningMaterial,
    StudentDomainEnrollment,
    SystemSetting,
    User,
)
from app.services.portal import admin_dashboard, audit, domain_ids_for, notify, now_utc

router = APIRouter(prefix="/api/v1", tags=["admin"])

DEFAULT_SETTINGS = {
    "institution_timezone": ("Asia/Kolkata", "string", "Institutional display timezone"),
    "max_optional_domains": ("2", "integer", "Maximum optional primary domains a student may pick"),
    "daily_task_limit": ("1", "integer", "Elite Task submissions allowed per student per business day"),
    "task_points_require_approval": ("true", "boolean", "Award task points only after approval"),
    "assessment_attempt_default": ("1", "integer", "Default allowed attempts for new assessments"),
    "upload_max_mb": ("25", "integer", "Maximum upload size in MB"),
    "evidence_retention_days": ("365", "integer", "Evidence retention period in days"),
    "notifications_enabled": ("true", "boolean", "Enable in-app notifications"),
}


def _temp_password():
    alphabet = string.ascii_letters + string.digits
    return "Elite@" + "".join(secrets.choice(alphabet) for _ in range(8))


def _assign_domains(user, domain_ids, assignment_type, actor_id=None):
    if user.role not in {"coordinator", "faculty"}:
        return
    wanted = {int(x) for x in domain_ids}
    existing = DomainAssignment.query.filter_by(user_id=user.id, assignment_type=assignment_type).all()
    for a in existing:
        if a.domain_id not in wanted:
            db.session.delete(a)
    for domain_id in wanted:
        if Domain.query.get(domain_id) is None:
            continue
        found = DomainAssignment.query.filter_by(
            user_id=user.id, domain_id=domain_id, assignment_type=assignment_type
        ).first()
        if not found:
            db.session.add(
                DomainAssignment(
                    domain_id=domain_id,
                    user_id=user.id,
                    assignment_type=assignment_type,
                    assigned_by=actor_id,
                )
            )


@router.get("/admin/dashboard")
def dashboard(current_user: User = Depends(require_roles("admin"))):
    return ok(admin_dashboard())


# ── Users ─────────────────────────────────────────────────────────────────
@router.get("/admin/users")
def users(
    request: Request,
    role: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1),
    per_page: int = Query(25),
    current_user: User = Depends(require_roles("admin")),
):
    query = User.query
    if role:
        query = query.filter(User.role == role)
    if department:
        query = query.filter(User.department == department)
    if status == "active":
        query = query.filter(User.is_active_account.is_(True))
    elif status == "inactive":
        query = query.filter(User.is_active_account.is_(False))
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (User.name.ilike(term)) | (User.email.ilike(term)) | (User.register_number.ilike(term))
        )
    query = query.order_by(User.role.asc(), User.name.asc())
    paged = paginate(query, page=page, per_page=per_page, default_per_page=25)

    items = []
    for u in paged["items"]:
        data = user_public(u)
        data["domains"] = [
            {"id": a.domain.id, "name": a.domain.name, "type": a.assignment_type}
            for a in DomainAssignment.query.filter_by(user_id=u.id).all()
        ]
        items.append(data)
    return ok(items, meta=paged["meta"])


@router.post("/admin/users")
async def create_user(
    request: Request,
    current_user: User = Depends(require_roles("admin")),
):
    data = await request.json() if (await request.body()) else {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    role = (data.get("role") or "student").strip().lower()
    if len(name) < 2:
        raise ApiError("Please provide a name.", 400, "invalid_name")
    if "@" not in email:
        raise ApiError("Please provide a valid email.", 400, "invalid_email")
    if role not in {"student", "coordinator", "faculty", "admin"}:
        raise ApiError("Invalid role.", 400, "invalid_role")
    if User.query.filter_by(email=email).first():
        raise ApiError("A user with this email already exists.", 409, "email_exists")

    password = data.get("password") or _temp_password()
    user = User(
        name=name,
        email=email,
        role=role,
        approval_status="approved",
        register_number=(data.get("register_number") or None),
        department=data.get("department"),
        year=get_int(data.get("year"), None, name="year"),
        section=data.get("section"),
        profile_completed=role != "student" or bool(data.get("profile_completed")),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    _assign_domains(user, data.get("domain_ids") or [], assignment_type="coordinator" if role == "coordinator" else "faculty", actor_id=current_user.id)
    audit(current_user.id, "user.create", target_type="User", target_id=user.id, new_value={"role": role, "email": email})
    db.session.commit()
    return ok({"user": user_public(user), "temporary_password": password if not data.get("password") else None}, 201)


@router.patch("/admin/users/{user_id}")
async def update_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
):
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("User not found.", 404, "not_found")
    data = await request.json() if (await request.body()) else {}
    before = user_public(user)
    for field in ("name", "department", "section", "register_number", "bio"):
        if field in data:
            setattr(user, field, data[field])
    if "year" in data:
        user.year = get_int(data.get("year"), None, name="year")
    if "role" in data:
        role = data["role"].strip().lower()
        if role not in {"student", "coordinator", "faculty", "admin"}:
            raise ApiError("Invalid role.", 400, "invalid_role")
        if user.id == current_user.id and role != "admin":
            raise ApiError("You cannot change your own admin role.", 400, "invalid_role")
        user.role = role
    if "approval_status" in data and data["approval_status"] in {"pending", "approved", "rejected"}:
        user.approval_status = data["approval_status"]
    if "is_active_account" in data:
        user.is_active_account = bool(data["is_active_account"])
    if "domain_ids" in data:
        _assign_domains(user, data["domain_ids"], assignment_type="coordinator" if user.role == "coordinator" else "faculty", actor_id=current_user.id)
    audit(current_user.id, "user.update", target_type="User", target_id=user.id, old_value=before, new_value=user_public(user))
    db.session.commit()
    return ok(user_public(user))


@router.post("/admin/users/{user_id}/toggle-active")
def toggle_active(
    user_id: int,
    current_user: User = Depends(require_roles("admin")),
):
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("User not found.", 404, "not_found")
    if user.id == current_user.id:
        raise ApiError("You cannot deactivate your own account.", 400, "invalid_action")
    user.is_active_account = not user.is_active_account
    audit(
        current_user.id,
        "user.activate" if user.is_active_account else "user.deactivate",
        target_type="User",
        target_id=user.id,
        new_value={"is_active_account": user.is_active_account},
    )
    db.session.commit()
    return ok(user_public(user))


@router.post("/admin/users/{user_id}/approve")
def approve_user(
    user_id: int,
    current_user: User = Depends(require_roles("admin")),
):
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("User not found.", 404, "not_found")
    user.approval_status = "approved"
    audit(current_user.id, "user.approve", target_type="User", target_id=user.id)
    notify(user.id, "Account approved", "Your Elite Portal account has been approved.", "success")
    db.session.commit()
    return ok(user_public(user))


@router.post("/admin/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    current_user: User = Depends(require_roles("admin")),
):
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("User not found.", 404, "not_found")
    password = _temp_password()
    user.set_password(password)
    audit(current_user.id, "user.reset_password", target_type="User", target_id=user.id)
    db.session.commit()
    return ok({"temporary_password": password})


# ── Domains ───────────────────────────────────────────────────────────────
@router.get("/admin/domains")
def domains(current_user: User = Depends(require_roles("admin"))):
    rows = Domain.query.order_by(Domain.is_compulsory.desc(), Domain.name).all()
    result = []
    for d in rows:
        data = domain_public(d)
        data["coordinators"] = [
            a.user.name for a in DomainAssignment.query.filter_by(domain_id=d.id, assignment_type="coordinator").all()
        ]
        data["faculty"] = [
            a.user.name for a in DomainAssignment.query.filter_by(domain_id=d.id, assignment_type="faculty").all()
        ]
        data["enrollments"] = d.enrollments.count()
        result.append(data)
    return ok(result)


@router.post("/admin/domains")
async def create_domain(
    request: Request,
    current_user: User = Depends(require_roles("admin")),
):
    data = await request.json() if (await request.body()) else {}
    code = (data.get("code") or "").strip().upper()
    name = (data.get("name") or "").strip()
    if len(code) < 2 or len(name) < 3:
        raise ApiError("A domain needs a code and a name.", 400, "invalid_domain")
    if Domain.query.filter_by(code=code).first():
        raise ApiError("A domain with this code already exists.", 409, "code_exists")

    domain = Domain(
        code=code,
        name=name,
        description=data.get("description"),
        icon=data.get("icon") or "book",
        color=data.get("color") or "#4f46e5",
        is_compulsory=bool(data.get("is_compulsory")),
        is_active=bool(data.get("is_active", True)),
        enrollment_limit=get_int(data.get("enrollment_limit"), None, name="enrollment_limit"),
        domain_change_allowed_until=parse_dt(data.get("domain_change_allowed_until"), "domain_change_allowed_until"),
        created_by=current_user.id,
    )
    db.session.add(domain)
    audit(current_user.id, "domain.create", target_type="Domain", new_value={"code": code})
    db.session.commit()
    return ok(domain_public(domain), 201)


@router.patch("/admin/domains/{domain_id}")
async def update_domain(
    domain_id: int,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
):
    domain = db.session.get(Domain, domain_id)
    if domain is None:
        raise ApiError("Domain not found.", 404, "not_found")
    data = await request.json() if (await request.body()) else {}
    before = domain_public(domain)
    for field in ("name", "description", "icon", "color"):
        if field in data:
            setattr(domain, field, data[field])
    if "is_compulsory" in data:
        domain.is_compulsory = bool(data["is_compulsory"])
    if "is_active" in data:
        domain.is_active = bool(data["is_active"])
    if "enrollment_limit" in data:
        domain.enrollment_limit = get_int(data.get("enrollment_limit"), None, name="enrollment_limit")
    if "domain_change_allowed_until" in data:
        domain.domain_change_allowed_until = parse_dt(data.get("domain_change_allowed_until"), "domain_change_allowed_until")
    audit(current_user.id, "domain.update", target_type="Domain", target_id=domain.id, old_value=before, new_value=domain_public(domain))
    db.session.commit()
    return ok(domain_public(domain))


@router.post("/admin/domains/{domain_id}/toggle-active")
def toggle_domain(
    domain_id: int,
    current_user: User = Depends(require_roles("admin")),
):
    domain = db.session.get(Domain, domain_id)
    if domain is None:
        raise ApiError("Domain not found.", 404, "not_found")
    domain.is_active = not domain.is_active
    audit(current_user.id, "domain.archive" if not domain.is_active else "domain.activate", target_type="Domain", target_id=domain.id)
    db.session.commit()
    return ok(domain_public(domain))


# ── Content registry ──────────────────────────────────────────────────────
@router.get("/admin/content")
def content_registry(
    type: Optional[str] = Query(None),
    domain_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1),
    per_page: int = Query(30),
    current_user: User = Depends(require_roles("admin")),
):
    query = (
        LearningMaterial.query.join(LearningDay, LearningDay.id == LearningMaterial.learning_day_id)
        .order_by(LearningDay.domain_id.asc(), LearningDay.day_number.asc(), LearningMaterial.display_order.asc())
    )
    if type and type != "all":
        query = query.filter(LearningMaterial.material_type == type)
    if domain_id:
        query = query.filter(LearningDay.domain_id == domain_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(LearningMaterial.title.ilike(term))
    paged = paginate(query, page=page, per_page=per_page, default_per_page=30)
    items = []
    for m in paged["items"]:
        data = material_public(m)
        data.update(
            {
                "domain_id": m.learning_day.domain_id,
                "domain": m.learning_day.domain.name,
                "day_number": m.learning_day.day_number,
                "day_title": m.learning_day.title,
            }
        )
        items.append(data)
    return ok(items, meta=paged["meta"])


# ── Assessment registry ───────────────────────────────────────────────────
@router.get("/admin/assessments")
def assessment_registry(
    domain_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    page: int = Query(1),
    per_page: int = Query(20),
    current_user: User = Depends(require_roles("admin")),
):
    query = Assessment.query
    if domain_id:
        query = query.filter(Assessment.domain_id == domain_id)
    if status:
        query = query.filter(Assessment.status == status)
    if type:
        query = query.filter(Assessment.assessment_type == type)
    query = query.order_by(Assessment.created_at.desc())
    paged = paginate(query, page=page, per_page=per_page)
    return ok([assessment_public(a) for a in paged["items"]], meta=paged["meta"])


@router.post("/admin/assessments/{assessment_id}/reopen")
async def reopen_assessment(
    assessment_id: int,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
):
    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None:
        raise ApiError("Assessment not found.", 404, "not_found")
    data = await request.json() if (await request.body()) else {}
    assessment.status = "published"
    if data.get("scheduled_end"):
        assessment.scheduled_end = parse_dt(data.get("scheduled_end"), "scheduled_end")
    audit(
        current_user.id,
        "assessment.reopen",
        target_type="Assessment",
        target_id=assessment.id,
        description="Assessment reopened (permission-restricted)",
    )
    db.session.commit()
    return ok(assessment_public(assessment))


@router.post("/admin/assessments/{assessment_id}/auto-release")
def auto_release_assessment(
    assessment_id: int,
    current_user: User = Depends(require_roles("admin")),
):
    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None:
        raise ApiError("Assessment not found.", 404, "not_found")
    assessment.status = "published"
    if not assessment.published_at:
        assessment.published_at = now_utc()
    auth = AssessmentAuthorization(
        assessment_id=assessment.id,
        student_id=None,
        authorized_by=current_user.id,
        authorization_type="admin_release",
        extra_attempts=0,
        reason="Admin auto-release override",
        is_active=True,
    )
    db.session.add(auth)
    audit(
        current_user.id,
        "assessment.auto_release",
        target_type="Assessment",
        target_id=assessment.id,
        description=f"Assessment '{assessment.title}' auto-released by admin",
    )
    db.session.commit()
    return ok({"message": "Assessment auto-released.", "assessment": assessment_public(assessment)})


# ── Elite Tasks ───────────────────────────────────────────────────────────
def _task_payload(task):
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "instructions": task.instructions,
        "domain_id": task.domain_id,
        "domain": task.domain.name if task.domain else None,
        "category": task.category,
        "potential_points": task.potential_points,
        "allowed_evidence_formats": task.allowed_evidence_formats or [],
        "status": task.status,
        "due_date": iso(task.due_date),
        "publish_at": iso(task.publish_at),
        "submission_count": task.evidences.count(),
        "approved_count": task.evidences.filter_by(status="approved").count(),
        "pending_count": task.evidences.filter_by(status="pending").count(),
    }


@router.get("/admin/tasks")
def tasks(
    status: Optional[str] = Query(None),
    page: int = Query(1),
    per_page: int = Query(20),
    current_user: User = Depends(require_roles("admin")),
):
    query = EliteTask.query.order_by(EliteTask.created_at.desc())
    if status:
        query = query.filter(EliteTask.status == status)
    paged = paginate(query, page=page, per_page=per_page)
    return ok([_task_payload(t) for t in paged["items"]], meta=paged["meta"])


@router.post("/admin/tasks")
async def create_task(
    request: Request,
    current_user: User = Depends(require_roles("admin")),
):
    data = await request.json() if (await request.body()) else {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    if len(title) < 3:
        raise ApiError("Please provide a task title.", 400, "invalid_title")
    if len(description) < 5:
        raise ApiError("Please describe the task.", 400, "invalid_description")

    task = EliteTask(
        title=title,
        description=description,
        instructions=data.get("instructions"),
        domain_id=get_int(data.get("domain_id"), None, name="domain_id"),
        category=(data.get("category") or "general"),
        potential_points=get_int(data.get("potential_points"), 100, 1, name="potential_points"),
        allowed_evidence_formats=data.get("allowed_evidence_formats") or ["pdf", "image", "zip", "link"],
        status=data.get("status") if data.get("status") in {"draft", "active", "upcoming", "completed"} else "draft",
        due_date=parse_dt(data.get("due_date"), "due_date"),
        publish_at=parse_dt(data.get("publish_at"), "publish_at"),
        created_by=current_user.id,
    )
    db.session.add(task)
    audit(current_user.id, "task.create", target_type="EliteTask", new_value={"title": title})
    db.session.commit()
    return ok(_task_payload(task), 201)


@router.patch("/admin/tasks/{task_id}")
async def update_task(
    task_id: int,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
):
    task = db.session.get(EliteTask, task_id)
    if task is None:
        raise ApiError("Task not found.", 404, "not_found")
    data = await request.json() if (await request.body()) else {}
    for field in ("title", "description", "instructions", "category", "allowed_evidence_formats"):
        if field in data:
            setattr(task, field, data[field])
    if "domain_id" in data:
        task.domain_id = get_int(data.get("domain_id"), None, name="domain_id")
    if "potential_points" in data:
        task.potential_points = get_int(data.get("potential_points"), task.potential_points, 1, name="potential_points")
    if "status" in data and data["status"] in {"draft", "active", "upcoming", "completed"}:
        task.status = data["status"]
    if "due_date" in data:
        task.due_date = parse_dt(data.get("due_date"), "due_date")
    if "publish_at" in data:
        task.publish_at = parse_dt(data.get("publish_at"), "publish_at")
    task.updated_at = now_utc()
    audit(current_user.id, "task.update", target_type="EliteTask", target_id=task.id)
    db.session.commit()
    return ok(_task_payload(task))


# ── Announcements ─────────────────────────────────────────────────────────
def _announcement_payload(a):
    return {
        "id": a.id,
        "title": a.title,
        "content": a.content,
        "category": a.category,
        "target_audience": a.target_audience,
        "target_domain_id": a.target_domain_id,
        "target_domain": a.target_domain.name if a.target_domain else None,
        "status": a.status,
        "publish_at": iso(a.publish_at),
        "expires_at": iso(a.expires_at),
        "created_by": a.creator.name if a.creator else None,
        "created_at": iso(a.created_at),
    }


def _fan_out_announcement(row):
    audience_roles = {
        "all": ["student", "coordinator", "faculty", "admin"],
        "students": ["student"],
        "coordinators": ["coordinator"],
        "faculty": ["faculty"],
        "admin": ["admin"],
    }.get(row.target_audience, ["student"])

    query = User.query.filter(User.role.in_(audience_roles), User.is_active_account.is_(True))
    if row.target_domain_id:
        domain = db.session.get(Domain, row.target_domain_id)
        if domain and "student" in audience_roles:
            student_ids = [
                e.student_id
                for e in StudentDomainEnrollment.query.filter_by(domain_id=domain.id, is_active=True).all()
            ]
            query = query.filter(User.id.in_(student_ids or [-1]))
    for user in query.limit(500).all():
        notify(user.id, row.title, row.content[:280], "info", link_url="/announcements")


@router.get("/admin/announcements")
def announcements(
    status: Optional[str] = Query(None),
    page: int = Query(1),
    per_page: int = Query(20),
    current_user: User = Depends(require_roles("admin")),
):
    query = Announcement.query.order_by(Announcement.created_at.desc())
    if status:
        query = query.filter(Announcement.status == status)
    paged = paginate(query, page=page, per_page=per_page)
    return ok([_announcement_payload(a) for a in paged["items"]], meta=paged["meta"])


@router.post("/admin/announcements")
async def create_announcement(
    request: Request,
    current_user: User = Depends(require_roles("admin")),
):
    data = await request.json() if (await request.body()) else {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    if len(title) < 3 or len(content) < 5:
        raise ApiError("A title and content are required.", 400, "invalid_announcement")
    audience = data.get("target_audience") if data.get("target_audience") in {"all", "students", "coordinators", "faculty", "admin"} else "all"
    row = Announcement(
        title=title,
        content=content,
        category=data.get("category") or "general",
        target_audience=audience,
        target_domain_id=get_int(data.get("target_domain_id"), None, name="target_domain_id"),
        status=data.get("status") if data.get("status") in {"draft", "published", "archived"} else "draft",
        publish_at=parse_dt(data.get("publish_at"), "publish_at"),
        expires_at=parse_dt(data.get("expires_at"), "expires_at"),
        created_by=current_user.id,
    )
    db.session.add(row)
    db.session.flush()
    if row.status == "published":
        _fan_out_announcement(row)
    audit(current_user.id, "announcement.create", target_type="Announcement", target_id=row.id)
    db.session.commit()
    return ok(_announcement_payload(row), 201)


@router.patch("/admin/announcements/{announcement_id}")
async def update_announcement(
    announcement_id: int,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
):
    row = db.session.get(Announcement, announcement_id)
    if row is None:
        raise ApiError("Announcement not found.", 404, "not_found")
    was_published = row.status == "published"
    data = await request.json() if (await request.body()) else {}
    for field in ("title", "content", "category", "target_audience", "status"):
        if field in data:
            setattr(row, field, data[field])
    if "target_domain_id" in data:
        row.target_domain_id = get_int(data.get("target_domain_id"), None, name="target_domain_id")
    if "publish_at" in data:
        row.publish_at = parse_dt(data.get("publish_at"), "publish_at")
    if "expires_at" in data:
        row.expires_at = parse_dt(data.get("expires_at"), "expires_at")
    if row.status == "published" and not was_published:
        _fan_out_announcement(row)
    audit(current_user.id, "announcement.update", target_type="Announcement", target_id=row.id)
    db.session.commit()
    return ok(_announcement_payload(row))


# ── Settings ──────────────────────────────────────────────────────────────
def _setting_value(row):
    if row.value_type == "integer":
        try:
            return int(row.value)
        except (TypeError, ValueError):
            return row.value
    if row.value_type == "boolean":
        return str(row.value).lower() in {"true", "1", "yes"}
    if row.value_type == "json":
        try:
            return json.loads(row.value)
        except (TypeError, ValueError):
            return row.value
    return row.value


def _coerce(value, value_type):
    if value_type == "integer":
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if value_type == "boolean":
        return str(value).lower() in {"true", "1", "yes"}
    return value


@router.get("/admin/settings")
def get_settings(current_user: User = Depends(require_roles("admin"))):
    existing = {s.key: s for s in SystemSetting.query.all()}
    result = []
    for key, (value, value_type, description) in DEFAULT_SETTINGS.items():
        if key in existing:
            row = existing[key]
            result.append({"key": key, "value": _setting_value(row), "value_type": row.value_type, "description": row.description})
        else:
            result.append({"key": key, "value": _coerce(value, value_type), "value_type": value_type, "description": description})
    for key, row in existing.items():
        if key not in DEFAULT_SETTINGS:
            result.append({"key": key, "value": _setting_value(row), "value_type": row.value_type, "description": row.description})
    return ok(result)


@router.put("/admin/settings")
async def update_settings(
    request: Request,
    current_user: User = Depends(require_roles("admin")),
):
    data = await request.json() if (await request.body()) else {}
    updates = data.get("settings") if isinstance(data.get("settings"), dict) else data
    if not isinstance(updates, dict):
        raise ApiError("Provide a settings object.", 400, "invalid_payload")
    for key, value in updates.items():
        value_type = DEFAULT_SETTINGS.get(key, (None, "string", None))[1]
        row = SystemSetting.query.filter_by(key=key).first()
        if row is None:
            row = SystemSetting(key=key, value_type=value_type)
            db.session.add(row)
        row.value = str(value).lower() if isinstance(value, bool) else str(value)
        row.value_type = row.value_type or value_type
        row.updated_by = current_user.id
        row.updated_at = now_utc()
    audit(current_user.id, "settings.update", new_value=updates)
    db.session.commit()
    return ok({"message": "Settings saved."})


# ── Audit logs ────────────────────────────────────────────────────────────
@router.get("/admin/audit-logs")
def audit_logs(
    action: Optional[str] = Query(None),
    actor_id: Optional[int] = Query(None),
    page: int = Query(1),
    per_page: int = Query(40),
    current_user: User = Depends(require_roles("admin")),
):
    query = AuditLog.query.order_by(AuditLog.created_at.desc())
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)
    paged = paginate(query, page=page, per_page=per_page, default_per_page=40)
    return ok(
        [
            {
                "id": r.id,
                "actor": r.actor.name if r.actor else "System",
                "actor_role": r.actor.role if r.actor else None,
                "action": r.action,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "description": r.description,
                "old_value": r.old_value,
                "new_value": r.new_value,
                "created_at": iso(r.created_at),
            }
            for r in paged["items"]
        ],
        meta=paged["meta"],
    )
