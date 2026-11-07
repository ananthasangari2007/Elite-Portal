"""Approved-student roster integration (Google Apps Script web app).

Optional and disabled unless ``ROSTER_APPS_SCRIPT_URL`` is set. When enabled, the
roster is authoritative for student eligibility: registration (and register-number
changes) are accepted only for active roster entries, and an unavailable roster fails
closed (HTTP 503) rather than admitting unverified students.

Apps Script contract (POST, JSON body):
    request:  {"action": "lookup", "register_number": "<normalized>", "secret": "<shared secret>"}
    response: {"ok": true,  "student": {"register_number", "name", "email", "department", "active"}}
              {"ok": false, "error": "not_found"}            -> not eligible
              {"ok": false, "error": "<anything else>"}      -> treated as unavailable
Only single-record lookups are supported; the full roster is never fetched or exposed.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request

logger = logging.getLogger("elite_portal.roster")

_cache: dict[str, tuple[float, dict | None]] = {}
_lock = threading.Lock()


class RosterUnavailable(RuntimeError):
    """The roster service could not give a definitive answer."""


def roster_enabled() -> bool:
    return bool(os.getenv("ROSTER_APPS_SCRIPT_URL", "").strip())


def normalize_register_number(value: str | None) -> str:
    """Remove all whitespace and upper-case (register numbers are alphanumeric IDs)."""
    return re.sub(r"\s+", "", value or "").upper()


def _ttl() -> int:
    return int(os.getenv("ROSTER_CACHE_SECONDS", "600"))


def lookup_student(register_number: str) -> dict | None:
    """Return the active roster record for ``register_number`` or None if not eligible.

    Raises RosterUnavailable on timeouts, auth/quota errors or malformed responses.
    """
    rn = normalize_register_number(register_number)
    if not rn:
        return None
    now = time.monotonic()
    with _lock:
        hit = _cache.get(rn)
        if hit and hit[0] > now:
            return hit[1]

    url = os.getenv("ROSTER_APPS_SCRIPT_URL", "").strip()
    body = json.dumps(
        {"action": "lookup", "register_number": rn, "secret": os.getenv("ROSTER_SHARED_SECRET", "")}
    ).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    timeout = float(os.getenv("ROSTER_TIMEOUT_SECONDS", "8"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (configured https URL)
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        logger.warning("Roster lookup failed: %s", exc.__class__.__name__)
        raise RosterUnavailable("The student roster could not be reached.") from exc

    if not isinstance(payload, dict):
        raise RosterUnavailable("Unexpected roster response.")
    if not payload.get("ok"):
        if payload.get("error") == "not_found":
            record = None
        else:
            logger.warning("Roster service error: %s", str(payload.get("error"))[:80])
            raise RosterUnavailable("The student roster returned an error.")
    else:
        student = payload.get("student") or {}
        if normalize_register_number(student.get("register_number")) != rn:
            raise RosterUnavailable("Roster returned a mismatched record.")
        active = student.get("active", True)
        record = (
            {
                "register_number": rn,
                "name": (student.get("name") or "").strip(),
                "email": (student.get("email") or "").strip().lower(),
                "department": (student.get("department") or "").strip() or None,
            }
            if active is True or str(active).lower() in {"true", "yes", "active", "1"}
            else None
        )

    with _lock:
        if len(_cache) > 5000:
            _cache.clear()
        _cache[rn] = (now + _ttl(), record)
    return record


def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return ""
    local, domain = email.split("@", 1)
    return f"{local[:2]}{'*' * max(len(local) - 2, 1)}@{domain}"
