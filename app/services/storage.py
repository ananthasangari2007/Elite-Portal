"""Durable file storage: Cloudflare R2 (S3-compatible) with a local dev fallback.

Framework-agnostic: ``save_file`` accepts a Starlette/FastAPI ``UploadFile`` (or any
object exposing ``filename`` + ``file``/``stream`` and an optional content type).
"""
from __future__ import annotations

import logging
import mimetypes
import os
import re
import unicodedata
from pathlib import Path
from uuid import uuid4

from config import Config

_logger = logging.getLogger("elite_portal.storage")

ALLOWED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", "gif", "webp",
    "zip", "rar", "7z", "doc", "docx", "ppt", "pptx",
    "xls", "xlsx", "csv", "txt", "md", "json",
    "py", "js", "ts", "tsx", "java", "c", "cpp", "cs", "ipynb",
    "mp4", "webm", "mp3",
}

_FILENAME_STRIP = re.compile(r"[^A-Za-z0-9_.-]")
_WINDOWS_RESERVED = {
    "CON", "AUX", "COM1", "COM2", "COM3", "COM4", "LPT1", "LPT2", "LPT3", "PRN", "NUL",
}


class StorageError(RuntimeError):
    """Raised when the storage backend fails to persist a file."""


def secure_filename(filename: str) -> str:
    """Equivalent of werkzeug.utils.secure_filename (no Flask/Werkzeug dependency)."""
    filename = unicodedata.normalize("NFKD", filename or "").encode("ascii", "ignore").decode("ascii")
    for sep in (os.sep, os.path.altsep):
        if sep:
            filename = filename.replace(sep, " ")
    filename = str(_FILENAME_STRIP.sub("", "_".join(filename.split()))).strip("._")
    if os.name == "nt" and filename and filename.split(".")[0].upper() in _WINDOWS_RESERVED:
        filename = f"_{filename}"
    return filename


def _cfg(key: str, default=None):
    return getattr(Config, key, default)


def r2_configured() -> bool:
    return bool(_cfg("R2_ENDPOINT_URL") and _cfg("R2_ACCESS_KEY_ID") and _cfg("R2_SECRET_ACCESS_KEY"))


def _client():
    import boto3
    from botocore.config import Config as BotoConfig

    return boto3.client(
        "s3",
        endpoint_url=_cfg("R2_ENDPOINT_URL"),
        aws_access_key_id=_cfg("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_cfg("R2_SECRET_ACCESS_KEY"),
        config=BotoConfig(signature_version="s3v4", connect_timeout=10, read_timeout=60, retries={"max_attempts": 3}),
        region_name="auto",
    )


def _local_root() -> Path:
    root_str = _cfg("UPLOAD_FOLDER")
    root = Path(root_str) if root_str else Path.cwd() / "instance" / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _fileobj(upload):
    """Return the underlying binary file object for UploadFile / FileStorage-like objects."""
    return getattr(upload, "file", None) or getattr(upload, "stream", None)


def _content_type(upload, safe_name: str) -> str:
    return (
        getattr(upload, "content_type", None)
        or getattr(upload, "mimetype", None)
        or mimetypes.guess_type(safe_name)[0]
        or "application/octet-stream"
    )


def upload_size(upload) -> int:
    """Size in bytes of an upload, without consuming the stream."""
    fh = _fileobj(upload)
    if fh is None:
        return 0
    pos = fh.tell()
    fh.seek(0, os.SEEK_END)
    size = fh.tell()
    fh.seek(pos)
    return size


def validate_upload(upload, max_bytes: int | None = None, allowed: set[str] | None = None):
    if not upload or not getattr(upload, "filename", None):
        raise ValueError("No file was provided.")
    safe_name = secure_filename(upload.filename)
    extension = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    if extension not in (allowed or ALLOWED_EXTENSIONS):
        raise ValueError(f"File type '.{extension}' is not allowed.")
    if max_bytes is not None:
        size = upload_size(upload)
        if size <= 0:
            raise ValueError("The uploaded file is empty.")
        if size > max_bytes:
            raise ValueError(f"Files must be {max_bytes // (1024 * 1024)} MB or smaller.")
    return safe_name, extension


def save_file(upload, folder: str = "general") -> dict:
    """Persist an upload. Raises ValueError for invalid input, StorageError if the backend fails."""
    safe_name, _ = validate_upload(upload)
    folder = secure_filename(folder or "general") or "general"
    key = f"{folder}/{uuid4().hex}_{safe_name}"
    content_type = _content_type(upload, safe_name)
    fh = _fileobj(upload)
    if fh is None:
        raise ValueError("No file was provided.")
    fh.seek(0)

    if r2_configured():
        try:
            client = _client()
            bucket = _cfg("R2_BUCKET_NAME")
            size = upload_size(upload)
            client.upload_fileobj(fh, bucket, key, ExtraArgs={"ContentType": content_type})
            storage = "r2"
        except Exception as exc:  # network / credentials / quota
            _logger.exception("R2 upload failed for key %s", key)
            raise StorageError("The file could not be stored. Please try again.") from exc
    else:
        destination = _local_root() / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(destination, "wb") as out:
                while True:
                    chunk = fh.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
        except OSError as exc:
            _logger.exception("Local upload failed for key %s", key)
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
            raise StorageError("The file could not be stored. Please try again.") from exc
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
                Params={"Bucket": _cfg("R2_BUCKET_NAME"), "Key": key},
                ExpiresIn=expires,
            )
        except Exception:
            _logger.exception("Could not sign R2 URL")
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
            _client().delete_object(Bucket=_cfg("R2_BUCKET_NAME"), Key=key)
        except Exception:
            _logger.exception("Could not delete R2 object %s", key)
        return
    try:
        os.remove(read_local(key))
    except (ValueError, FileNotFoundError, OSError):
        pass
