"""Shared API — uploads, private requests, notifications, public config."""
from __future__ import annotations

from flask import Blueprint, current_app, redirect, request, send_file
from flask_login import current_user

from app import db
from app.api.utils import ApiError, get_int, iso, json_body, ok, require_roles
from app.models import Notification, RequestMessage, StudentRequest, TaskEvidence
from app.services.portal import can_access_domain, notify, now_utc
from app.services.storage import file_url, local_exists, read_local, r2_configured, save_file, ALLOWED_EXTENSIONS

common_api = Blueprint("api_common", __name__, url_prefix="/api/v1")


@common_api.get("/public/config")
def public_config():
    return ok(
        {
            "institution": current_app.config.get("INSTITUTION_NAME"),
            "batch": current_app.config.get("BATCH_NAME"),
            "timezone": current_app.config.get("INSTITUTION_TIMEZONE"),
            "max_optional_domains": current_app.config.get("MAX_OPTIONAL_DOMAINS", 2),
            "login_options": [
                {"key": "student", "label": "Student Login", "description": "Access learning, assessments, Elite Tasks, and points."},
                {"key": "coordinator", "label": "Domain Coordinator Login", "description": "Manage domain content, learning days, assessments, and submissions."},
                {"key": "faculty", "label": "Faculty Coordinator Login", "description": "Review grading, appeals, student requests, and point adjustments."},
                {"key": "admin", "label": "Admin Login", "description": "Manage users, domains, platform settings, and reports."},
            ],
            "storage": "r2" if r2_configured() else "local",
        }
    )


@common_api.get("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "error"
    return ok({"status": "ok" if database == "ok" else "degraded", "database": database})


@common_api.post("/uploads")
@require_roles("student", "coordinator", "faculty", "admin")
def upload():
    if "file" not in request.files:
        raise ApiError("No file was provided.", 400, "missing_file")
    file_storage = request.files["file"]
    folder = request.form.get("folder") or "general"
    if current_user.role == "student":
        folder = "evidence"
    max_bytes = current_app.config.get("MAX_UPLOAD_BYTES", 25 * 1024 * 1024)
    file_storage.stream.seek(0, 2)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size <= 0:
        raise ApiError("The uploaded file is empty.", 400, "empty_file")
    if size > max_bytes:
        raise ApiError(f"Files must be {max_bytes // (1024 * 1024)} MB or smaller.", 400, "file_too_large")
    try:
        meta = save_file(file_storage, folder=folder)
    except ValueError as exc:
        raise ApiError(str(exc), 400, "invalid_file") from exc
    return ok(meta, 201)


@common_api.get("/files/<path:key>")
def download(key):
    is_public = key.startswith("avatars/") or key.startswith("materials/")
    if not is_public:
        if not current_user.is_authenticated:
            raise ApiError("Authentication required.", 401, "unauthenticated")
        if not _can_read_key(key):
            raise ApiError("You do not have access to this file.", 403, "forbidden")

    if r2_configured():
        url = file_url(key)
        if not url:
            raise ApiError("File could not be retrieved.", 502, "storage_error")
        return redirect(url)

    try:
        path = read_local(key)
    except (ValueError, FileNotFoundError):
        raise ApiError("File not found.", 404, "not_found")
    return send_file(path, as_attachment=False, download_name=path.name)


def _can_read_key(key: str) -> bool:
    if current_user.role in ("admin", "faculty", "coordinator"):
        return True
    if key.startswith("materials/") or key.startswith("avatars/"):
        return True
    if key.startswith("evidence/"):
        row = TaskEvidence.query.filter_by(file_key=key).first()
        if row is None:
            return False
        return row.student_id == current_user.id
    return current_user.role == "student" and key.startswith(f"evidence/{current_user.id}/")


# ── Private request conversations ─────────────────────────────────────────
def _request_access(row: StudentRequest):
    if current_user.role == "admin":
        return True
    if current_user.role == "student":
        return row.student_id == current_user.id
    if current_user.role in ("faculty", "coordinator"):
        from app.services.portal import scoped_student_ids

        scoped = scoped_student_ids(current_user)
        return scoped is None or row.student_id in scoped
    return False


def _serialize_request(row: StudentRequest, include_messages=True):
    data = {
        "id": row.id,
        "student_id": row.student_id,
        "student": row.student.name,
        "register_number": row.student.register_number,
        "category": row.category,
        "subject": row.subject,
        "status": row.status,
        "handler": row.handler.name if row.handler else None,
        "created_at": iso(row.created_at),
        "updated_at": iso(row.updated_at),
        "resolved_at": iso(row.resolved_at),
    }
    if include_messages:
        data["messages"] = [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "sender": m.sender.name if m.sender else "System",
                "sender_role": m.sender.role if m.sender else None,
                "message": m.message,
                "is_internal": m.is_internal,
                "created_at": iso(m.created_at),
            }
            for m in row.messages
            if not m.is_internal or current_user.role != "student"
        ]
    return data


@common_api.get("/requests/<int:request_id>")
@require_roles("student", "coordinator", "faculty", "admin")
def request_detail(request_id):
    row = db.session.get(StudentRequest, request_id)
    if row is None:
        raise ApiError("Request not found.", 404, "not_found")
    if not _request_access(row):
        raise ApiError("You do not have access to this request.", 403, "forbidden")
    return ok(_serialize_request(row))


@common_api.post("/requests/<int:request_id>/messages")
@require_roles("student", "coordinator", "faculty", "admin")
def post_message(request_id):
    row = db.session.get(StudentRequest, request_id)
    if row is None:
        raise ApiError("Request not found.", 404, "not_found")
    if not _request_access(row):
        raise ApiError("You do not have access to this request.", 403, "forbidden")

    data = json_body()
    message = (data.get("message") or "").strip()
    if len(message) < 1:
        raise ApiError("Message cannot be empty.", 400, "invalid_message")
    if len(message) > 5000:
        raise ApiError("Message is too long.", 400, "invalid_message")
    is_internal = bool(data.get("is_internal")) and current_user.role != "student"

    msg = RequestMessage(
        request_id=row.id,
        sender_id=current_user.id,
        message=message,
        is_internal=is_internal,
    )
    db.session.add(msg)
    row.updated_at = now_utc()
    if row.status == "open" and current_user.role != "student":
        row.status = "in_progress"
        row.assigned_to = row.assigned_to or current_user.id
    if current_user.role != "student" and not is_internal:
        notify(
            row.student_id,
            "New reply to your request",
            f"{current_user.name} replied to “{row.subject}”.",
            "info",
            link_url=f"/student/requests/{row.id}",
        )
    db.session.commit()
    return ok(_serialize_request(row), 201)


@common_api.patch("/requests/<int:request_id>/status")
@require_roles("coordinator", "faculty", "admin")
def update_request_status(request_id):
    row = db.session.get(StudentRequest, request_id)
    if row is None:
        raise ApiError("Request not found.", 404, "not_found")
    if not _request_access(row):
        raise ApiError("You do not have access to this request.", 403, "forbidden")
    data = json_body()
    status = (data.get("status") or "").strip()
    if status not in {"open", "in_progress", "resolved", "closed"}:
        raise ApiError("Invalid request status.", 400, "invalid_status")
    row.status = status
    row.assigned_to = row.assigned_to or current_user.id
    if status in {"resolved", "closed"}:
        row.resolved_at = now_utc()
    db.session.commit()
    return ok(_serialize_request(row))


# ── Notifications ─────────────────────────────────────────────────────────
@common_api.post("/notifications/<int:notification_id>/read")
@require_roles("student", "coordinator", "faculty", "admin")
def mark_notification(notification_id):
    row = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
    if row is None:
        raise ApiError("Notification not found.", 404, "not_found")
    row.is_read = True
    db.session.commit()
    return ok({"read": True})


@common_api.post("/notifications/read-all")
@require_roles("student", "coordinator", "faculty", "admin")
def mark_all_notifications():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return ok({"message": "All notifications marked as read."})


@common_api.get("/config/uploads")
@require_roles("student", "coordinator", "faculty", "admin")
def upload_config():
    return ok(
        {
            "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
            "max_bytes": current_app.config.get("MAX_UPLOAD_BYTES", 25 * 1024 * 1024),
            "storage": "r2" if r2_configured() else "local",
        }
    )
