"""
Auth endpoints (project documentation Section 3.4/4.1, NFR-04)
"""

from __future__ import annotations
import re
from flask import Blueprint, request, jsonify, g

from extensions import db
from models import Recruiter
from auth import hash_password, verify_password, issue_token, require_auth

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@auth_bp.post("/register")
def register():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    full_name = (body.get("full_name") or "").strip()

    if not EMAIL_RE.match(email):
        return jsonify(error="A valid email is required."), 400
    if len(password) < 8:
        return jsonify(error="Password must be at least 8 characters."), 400
    if full_name and re.search(r"\d", full_name):
        return jsonify(error="Full name cannot contain numbers."), 400
    if Recruiter.query.filter_by(email=email).first() is not None:
        return jsonify(error="An account with this email already exists."), 409

    recruiter = Recruiter(email=email, password_hash=hash_password(password), full_name=full_name or None)
    db.session.add(recruiter)
    db.session.commit()

    token = issue_token(recruiter.id, recruiter.email)
    return jsonify(token=token, recruiter=recruiter.to_dict()), 201


@auth_bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    recruiter = Recruiter.query.filter_by(email=email).first()
    # Constant-shape response whether the email doesn't exist or the password
    # is wrong -- doesn't leak which accounts exist.
    if recruiter is None or not verify_password(password, recruiter.password_hash):
        return jsonify(error="Invalid email or password."), 401

    token = issue_token(recruiter.id, recruiter.email)
    return jsonify(token=token, recruiter=recruiter.to_dict())


@auth_bp.get("/me")
@require_auth
def me():
    recruiter = db.session.get(Recruiter, g.recruiter_id)
    if recruiter is None:
        return jsonify(error="Recruiter not found."), 404
    return jsonify(recruiter.to_dict())
