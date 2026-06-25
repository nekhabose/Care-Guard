"""
Password hashing for dashboard staff accounts.

Uses bcrypt directly (no passlib) for clean Python 3.14 compatibility. bcrypt
caps inputs at 72 bytes; we hard-reject longer secrets rather than silently
truncate, so two different long passwords can never collide to the same hash.
"""
from __future__ import annotations

import bcrypt

_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash (utf-8 string) for storage."""
    raw = password.encode("utf-8")
    if len(raw) > _MAX_BYTES:
        raise ValueError("Password must be at most 72 bytes")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time check of a plaintext password against a stored hash."""
    raw = password.encode("utf-8")
    if len(raw) > _MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


__all__ = ["hash_password", "verify_password"]
