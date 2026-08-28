"""
Authentication (project documentation Section 3.4/4.1, NFR-04)
--------------------------------------------------------------------
JWT bearer tokens + bcrypt password hashing, as specified in the design
doc's chosen stack. Every API route except /api/auth/register,
/api/auth/login, and /api/health requires a valid token.

JWT secret: JWT_SECRET env var in production/Docker. For local dev, same
pattern as crypto_utils.py -- generated once and cached at
backend/instance/jwt_secret.key (gitignored).
"""

from __future__ import annotations
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt as pyjwt
from flask import request, jsonify, g

import config

TOKEN_TTL = timedelta(hours=8)
ALGORITHM = "HS256"


def _get_secret() -> str:
    env_secret = os.environ.get("JWT_SECRET")
    if env_secret:
        return env_secret

    # Looked up dynamically (not imported as a top-level constant) so that
    # tests can point config.INSTANCE_DIR at a tmp_path and get a fresh
    # secret per test run, isolated from the real backend/instance dir.
    config.INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    secret_file = config.INSTANCE_DIR / "jwt_secret.key"
    if secret_file.exists():
        return secret_file.read_text()
    secret = secrets.token_hex(32)
    secret_file.write_text(secret)
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def issue_token(recruiter_id: int, email: str) -> str:
    payload = {
        "sub": str(recruiter_id),
        "email": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + TOKEN_TTL,
    }
    return pyjwt.encode(payload, _get_secret(), algorithm=ALGORITHM)


class TokenError(Exception):
    pass


def decode_token(token: str) -> dict:
    try:
        return pyjwt.decode(token, _get_secret(), algorithms=[ALGORITHM])
    except pyjwt.ExpiredSignatureError as exc:
        raise TokenError("Token expired. Please log in again.") from exc
    except pyjwt.InvalidTokenError as exc:
        raise TokenError("Invalid token.") from exc


def require_auth(view_func):
    """Rejects the request with 401 unless a valid 'Authorization: Bearer <token>'
    header is present. On success, sets g.recruiter_id / g.recruiter_email."""

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify(error="Missing or malformed Authorization header."), 401
        token = header.removeprefix("Bearer ").strip()
        try:
            payload = decode_token(token)
        except TokenError as e:
            return jsonify(error=str(e)), 401

        g.recruiter_id = int(payload["sub"])
        g.recruiter_email = payload["email"]
        return view_func(*args, **kwargs)

    return wrapper
