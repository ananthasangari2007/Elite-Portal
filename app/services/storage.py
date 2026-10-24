"""Durable file storage: Cloudflare R2 (S3-compatible) with a local dev fallback."""
from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", "gif", "webp",
    "zip", "rar", "7z", "doc", "docx", "ppt", "pptx",
    "xls", "xlsx", "csv", "txt", "md", "json",
    "py", "js", "ts", "tsx", "java", "c", "cpp", "cs", "ipynb",
    "mp4", "webm", "mp3",
}


import logging

_logger = logging.getLogger("elite_portal.storage")


def _cfg():
    try:
        if current_app:
            return current_app.config
    except Exception:
        pass
    from config import Config

    class CfgDict(dict):
        def __getitem__(self, key):
            val = getattr(Config, key, None)
            if val is None:
                raise KeyError(key)
            return val

        def get(self, key, default=None):
            return getattr(Config, key, default)

    return CfgDict()


def _get_logger():
    try:
        if current_app:
            return current_app.logger
    except Exception:
        pass
    return _logger


def r2_configured() -> bool:
    cfg = _cfg()
    return bool(cfg.get("R2_ENDPOINT_URL") and cfg.get("R2_ACCESS_KEY_ID") and cfg.get("R2_SECRET_ACCESS_KEY"))


def _client():
    import boto3
    from botocore.config import Config

    cfg = _cfg()
    return boto3.client(
        "s3",
        endpoint_url=cfg["R2_ENDPOINT_URL"],
        aws_access_key_id=cfg["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _local_root() -> Path:
    cfg = _cfg()
    root_str = cfg.get("UPLOAD_FOLDER")
    if root_str:
        root = Path(root_str)
    else:
        root = Path.cwd() / "instance" / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_upload(file_storage):
    if not file_storage or not file_storage.filename:
        raise ValueError("No file was provided.")
    safe_name = secure_filename(file_storage.filename)
    extension = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type '.{extension}' is not allowed.")
    return safe_name, extension


def save_file(file_storage, folder: str = "general") -> dict:
    safe_name, extension = validate_upload(file_storage)
    folder = secure_filename(folder or "general") or "general"
    key = f"{folder}/{uuid4().hex}_{safe_name}"
    content_type = file_storage.mimetype or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"

    if r2_configured():
        client = _client()
        extra = {"ContentType": content_type}
        bucket = _cfg()["R2_BUCKET_NAME"]
        client.upload_fileobj(file_storage.stream, bucket, key, ExtraArgs=extra)
        size = file_storage.content_length or 0
        if not size:
            head = client.head_object(Bucket=bucket, Key=key)
            size = head.get("ContentLength", 0)
        storage = "r2"
    else:
        destination = _local_root() / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_storage.save(destination)
        size = destination.stat().st_size
        storage = "local"

    preview = file_url(key)
    return {
        "key": key,
        "file_key": key,
        "file_name": safe_name,
        "file_size": size,
        "file_type": content_type,
        "storage": storage,
        "url": preview,
        "preview_url": preview,
    }


def file_url(key: str, expires: int = 3600) -> str | None:
    if not key:
        return None
    if r2_configured():
        try:
            return _client().generate_presigned_url(
                "get_object",
                Params={"Bucket": _cfg()["R2_BUCKET_NAME"], "Key": key},
                ExpiresIn=expires,
            )
        except Exception:
            _get_logger().exception("Could not sign R2 URL")
            return None
    return f"/api/v1/files/{key}"


def read_local(key: str):
    root = _local_root().resolve()
    target = (root / key).resolve()
    if root not in target.parents and target != root:
        raise ValueError("Invalid file path.")
    if not target.exists():
        raise FileNotFoundError(key)
    return target


def local_exists(key: str) -> bool:
    try:
        return read_local(key).exists()
    except (ValueError, FileNotFoundError):
        return False


def delete_file(key: str):
    if r2_configured():
        try:
            _client().delete_object(Bucket=_cfg()["R2_BUCKET_NAME"], Key=key)
        except Exception:
            _get_logger().exception("Could not delete R2 object %s", key)
        return
    try:
        os.remove(read_local(key))
    except (ValueError, FileNotFoundError, OSError):
        pass
