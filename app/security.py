"""Password hashing compatible with existing Werkzeug-generated hashes.

Stored hashes look like ``scrypt:32768:8:1$<salt>$<hex>`` or
``pbkdf2:sha256:600000$<salt>$<hex>``. Existing rows keep verifying unchanged;
new hashes use scrypt with the same parameters Werkzeug 3 used.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import string

_SALT_CHARS = string.ascii_letters + string.digits
_DEFAULT_PBKDF2_ITERATIONS = 600_000


def _gen_salt(length: int = 16) -> str:
    return "".join(secrets.choice(_SALT_CHARS) for _ in range(length))


def _hash_internal(method: str, salt: str, password: str) -> tuple[str, str]:
    name, *args = method.split(":")
    salt_b = salt.encode()
    password_b = password.encode()

    if name == "scrypt":
        n = int(args[0]) if len(args) > 0 else 2**15
        r = int(args[1]) if len(args) > 1 else 8
        p = int(args[2]) if len(args) > 2 else 1
        digest = hashlib.scrypt(password_b, salt=salt_b, n=n, r=r, p=p, maxmem=132 * n * r * p, dklen=64)
        return digest.hex(), f"scrypt:{n}:{r}:{p}"
    if name == "pbkdf2":
        hash_name = args[0] if len(args) > 0 else "sha256"
        iterations = int(args[1]) if len(args) > 1 else _DEFAULT_PBKDF2_ITERATIONS
        digest = hashlib.pbkdf2_hmac(hash_name, password_b, salt_b, iterations)
        return digest.hex(), f"pbkdf2:{hash_name}:{iterations}"
    raise ValueError(f"Unsupported password hash method {name!r}")


def generate_password_hash(password: str, method: str = "scrypt", salt_length: int = 16) -> str:
    salt = _gen_salt(salt_length)
    hashed, actual_method = _hash_internal(method, salt, password)
    return f"{actual_method}${salt}${hashed}"


def check_password_hash(pwhash: str, password: str) -> bool:
    try:
        method, salt, hashval = (pwhash or "").split("$", 2)
        computed, _ = _hash_internal(method, salt, password or "")
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(computed, hashval)
