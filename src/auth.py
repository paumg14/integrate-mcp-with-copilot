import base64
import getpass
import hashlib
import json
import os
import secrets
import time
from typing import Any

from fastapi import Depends, HTTPException, Request

SESSION_COOKIE = "mergington_session"
SESSION_TTL_SECONDS = 8 * 60 * 60
PASSWORD_ITERATIONS = 310_000
ALLOWED_ROLES = {"student", "staff"}
_sessions: dict[str, tuple[str, float]] = {}


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="Authentication required")


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty")

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    salt_text = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    digest_text = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt_text}${digest_text}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, expected_text = encoded_hash.split("$")
        iterations = int(iterations_text)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 1_000_000:
            return False

        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(
            expected_text + "=" * (-len(expected_text) % 4)
        )
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )
        return secrets.compare_digest(actual, expected)
    except (AttributeError, TypeError, ValueError):
        return False


def is_password_hash(encoded_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = encoded_hash.split("$")
        iterations = int(iterations_text)
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        digest = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
        return (
            algorithm == "pbkdf2_sha256"
            and 100_000 <= iterations <= 1_000_000
            and len(salt) >= 16
            and len(digest) == 32
        )
    except (AttributeError, TypeError, ValueError):
        return False


def load_users() -> dict[str, dict[str, str]]:
    raw_users = os.environ.get("SCHOOL_USERS_JSON", "")
    if not raw_users:
        raise HTTPException(status_code=503, detail="Authentication is not configured")

    try:
        configured_users: Any = json.loads(raw_users)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=503, detail="Authentication configuration is invalid"
        ) from exc

    if not isinstance(configured_users, dict) or not configured_users:
        raise HTTPException(status_code=503, detail="Authentication configuration is invalid")

    users: dict[str, dict[str, str]] = {}
    for email, user in configured_users.items():
        if (
            not isinstance(email, str)
            or "@" not in email
            or not isinstance(user, dict)
            or not isinstance(user.get("password_hash"), str)
            or not isinstance(user.get("role"), str)
            or user["role"] not in ALLOWED_ROLES
            or not is_password_hash(user["password_hash"])
        ):
            raise HTTPException(status_code=503, detail="Authentication configuration is invalid")
        users[email.strip().lower()] = {
            "password_hash": user["password_hash"],
            "role": user["role"],
        }

    return users


def authenticate_user(email: str, password: str) -> dict[str, str] | None:
    users = load_users()
    normalized_email = email.strip().lower()
    user = users.get(normalized_email)
    if not user or not verify_password(password, user["password_hash"]):
        return None
    return {"email": normalized_email, "role": user["role"]}


def create_session(email: str) -> str:
    now = time.time()
    expired_tokens = [token for token, (_, expiry) in _sessions.items() if expiry <= now]
    for token in expired_tokens:
        _sessions.pop(token, None)

    token = secrets.token_urlsafe(32)
    _sessions[token] = (email.strip().lower(), now + SESSION_TTL_SECONDS)
    return token


def revoke_session(token: str | None) -> None:
    if token:
        _sessions.pop(token, None)


def get_current_user(request: Request) -> dict[str, str]:
    token = request.cookies.get(SESSION_COOKIE)
    session = _sessions.get(token or "")
    if not session:
        raise _unauthorized()

    email, expires_at = session
    if expires_at <= time.time():
        revoke_session(token)
        raise _unauthorized()

    user = load_users().get(email)
    if not user:
        revoke_session(token)
        raise _unauthorized()

    return {"email": email, "role": user["role"]}


def require_student(
    current_user: dict[str, str] = Depends(get_current_user),
) -> dict[str, str]:
    if current_user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access required")
    return current_user


if __name__ == "__main__":
    print(hash_password(getpass.getpass("Password to hash: ")))
