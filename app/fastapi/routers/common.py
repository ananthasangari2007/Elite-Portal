"""Shared common API endpoints: config, health, files, requests, notifications."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import text

from app import db
from app.fastapi.auth import ApiError, get_current_user, get_current_user_optional, require_roles
from app.fastapi.utils import iso, ok
from app.models.platform import Notification, RequestMessage, StudentRequest, TaskEvidence
from app.models.user import User
from app.services.portal import notify, now_utc
from app.services.storage import (
    ALLOWED_EXTENSIONS,
    file_url,
    r2_configured,
    read_local,
    save_file,
)
from config import Config

logger = logging.getLogger("elite_portal.common_router")

router = APIRouter(prefix="/api/v1", tags=["common"])


class MessagePayload(BaseModel):
    message: Optional[str] = None
    is_internal: Optional[bool] = False


class RequestStatusPayload(BaseModel):
    status: Optional[str] = None


def _can_read_key(user: Optional[User], key: str) -> bool:
    if key.startswith("materials/") or key.startswith("avatars/"):
        return True
    if not user:
        return False
    if user.role in ("admin", "faculty", "coordinator"):
        return True
    if key.startswith("evidence/"):
        row = TaskEvidence.query.filter_by(file_key=key).first()
        if row is None:
            return False
        return row.student_id == user.id
    return user.role == "student" and key.startswith(f"evidence/{user.id}/")


def _request_access(user: User, row: StudentRequest) -> bool:
    if user.role == "admin":
        return True
    if user.role == "student":
        return row.student_id == user.id
    if user.role in ("faculty", "coordinator"):
        from app.services.portal import scoped_student_ids
        scoped = scoped_student_ids(user)
        return scoped is None or row.student_id in scoped
    return False


def _serialize_request(user: User, row: StudentRequest, include_messages: bool = True) -> dict:
    data = {
        "id": row.id,
        "student_id": row.student_id,
        "student": row.student.name if row.student else None,
        "register_number": row.student.register_number if row.student else None,
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
            if not m.is_internal or user.role != "student"
        ]
    return data


@router.get("/public/config")
def public_config():
    return ok(
        {
            "institution": getattr(Config, "INSTITUTION_NAME", "Francis Xavier Engineering College"),
            "batch": getattr(Config, "BATCH_NAME", "Elite Batch 2025-2029"),
            "timezone": getattr(Config, "INSTITUTION_TIMEZONE", "Asia/Kolkata"),
            "max_optional_domains": int(getattr(Config, "MAX_OPTIONAL_DOMAINS", 2)),
            "login_options": [
                {"key": "student", "label": "Student Login", "description": "Access learning, assessments, Elite Tasks, and points."},
                {"key": "coordinator", "label": "Domain Coordinator Login", "description": "Manage domain content, learning days, assessments, and submissions."},
                {"key": "faculty", "label": "Faculty Coordinator Login", "description": "Review grading, appeals, student requests, and point adjustments."},
                {"key": "admin", "label": "Admin Login", "description": "Manage users, domains, platform settings, and reports."},
            ],
            "storage": "r2" if r2_configured() else "local",
        }
    )


@router.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "error"
    return ok({"status": "ok" if database == "ok" else "degraded", "database": database})


@router.post("/uploads")
def upload(
    request: Request,
    file: UploadFile = File(...),
    folder: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
):
    target_folder = folder or "general"
    if user.role == "student":
        target_folder = "evidence"

    max_bytes = int(getattr(Config, "MAX_UPLOAD_BYTES", 25 * 1024 * 1024))
    try:
        meta = save_file(file, folder=target_folder)
    except ValueError as exc:
        raise ApiError(str(exc), 400, "invalid_file") from exc
    return ok(meta, 201)


@router.get("/files/{key:path}")
def download(key: str, request: Request):
    user = get_current_user_optional(request)
    if not _can_read_key(user, key):
        if not user:
            raise ApiError("Authentication required.", 401, "unauthenticated")
        raise ApiError("You do not have access to this file.", 403, "forbidden")

    if r2_configured():
        url = file_url(key)
        if not url:
            raise ApiError("File could not be retrieved.", 502, "storage_error")
        return RedirectResponse(url)

    try:
        path = read_local(key)
    except (ValueError, FileNotFoundError):
        raise ApiError("File not found.", 404, "not_found")
    return FileResponse(path, filename=path.name)


@router.get("/requests/{request_id}")
def request_detail(request_id: int, user: User = Depends(get_current_user)):
    row = db.session.get(StudentRequest, request_id)
    if row is None:
        raise ApiError("Request not found.", 404, "not_found")
    if not _request_access(user, row):
        raise ApiError("You do not have access to this request.", 403, "forbidden")
    return ok(_serialize_request(user, row))


@router.post("/requests/{request_id}/messages")
def post_message(request_id: int, payload: MessagePayload, user: User = Depends(get_current_user)):
    row = db.session.get(StudentRequest, request_id)
    if row is None:
        raise ApiError("Request not found.", 404, "not_found")
    if not _request_access(user, row):
        raise ApiError("You do not have access to this request.", 403, "forbidden")

    message = (payload.message or "").strip()
    if len(message) < 1:
        raise ApiError("Message cannot be empty.", 400, "invalid_message")
    if len(message) > 5000:
        raise ApiError("Message is too long.", 400, "invalid_message")
    is_internal = bool(payload.is_internal) and user.role != "student"

    msg = RequestMessage(
        request_id=row.id,
        sender_id=user.id,
        message=message,
        is_internal=is_internal,
    )
    db.session.add(msg)
    row.updated_at = now_utc()
    if row.status == "open" and user.role != "student":
        row.status = "in_progress"
        row.assigned_to = row.assigned_to or user.id
    if user.role != "student" and not is_internal:
        notify(
            row.student_id,
            "New reply to your request",
            f"{user.name} replied to “{row.subject}”.",
            "info",
            link_url=f"/student/requests/{row.id}",
        )
    db.session.commit()
    return ok(_serialize_request(user, row), 201)


@router.patch("/requests/{request_id}/status")
def update_request_status(
    request_id: int,
    payload: RequestStatusPayload,
    user: User = Depends(require_roles("coordinator", "faculty", "admin")),
):
    row = db.session.get(StudentRequest, request_id)
    if row is None:
        raise ApiError("Request not found.", 404, "not_found")
    if not _request_access(user, row):
        raise ApiError("You do not have access to this request.", 403, "forbidden")

    status = (payload.status or "").strip()
    if status not in {"open", "in_progress", "resolved", "closed"}:
        raise ApiError("Invalid request status.", 400, "invalid_status")
    row.status = status
    row.assigned_to = row.assigned_to or user.id
    if status in {"resolved", "closed"}:
        row.resolved_at = now_utc()
    db.session.commit()
    return ok(_serialize_request(user, row))


@router.post("/notifications/{notification_id}/read")
def mark_notification(notification_id: int, user: User = Depends(get_current_user)):
    row = Notification.query.filter_by(id=notification_id, user_id=user.id).first()
    if row is None:
        raise ApiError("Notification not found.", 404, "not_found")
    row.is_read = True
    db.session.commit()
    return ok({"read": True})


@router.post("/notifications/read-all")
def mark_all_notifications(user: User = Depends(get_current_user)):
    Notification.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return ok({"message": "All notifications marked as read."})


@router.get("/config/uploads")
def upload_config(user: User = Depends(get_current_user)):
    return ok(
        {
            "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
            "max_bytes": int(getattr(Config, "MAX_UPLOAD_BYTES", 25 * 1024 * 1024)),
            "storage": "r2" if r2_configured() else "local",
        }
    )
