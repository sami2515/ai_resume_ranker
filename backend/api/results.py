"""
Feedback loop endpoint (project documentation Section 4.4/5.4, FR-10)
"""

from __future__ import annotations
from flask import Blueprint, request, jsonify, g

from extensions import db
from models import MatchResult as MatchResultModel, RecruiterFeedback
from auth import require_auth
from .jobs import _get_owned_job

results_bp = Blueprint("results", __name__, url_prefix="/api/results")

VALID_DECISIONS = {"hired", "rejected", "unreviewed", "clear"}


def _owned_match(match_result_id: int):
    match = db.session.get(MatchResultModel, match_result_id)
    if match is None:
        return None, (jsonify(error=f"No match result with id {match_result_id}."), 404)
    _jd, error = _get_owned_job(match.jd_id)
    if error:
        return None, error
    return match, None


@results_bp.post("/<int:match_result_id>/feedback")
@require_auth
def submit_feedback(match_result_id: int):
    match, error = _owned_match(match_result_id)
    if error:
        return error

    body = request.get_json(silent=True) or {}
    decision = (body.get("decision") or "").strip().lower()
    if decision not in VALID_DECISIONS:
        return jsonify(error=f"'decision' must be one of {sorted(VALID_DECISIONS)}."), 400

    if decision in ("unreviewed", "clear"):
        RecruiterFeedback.query.filter_by(
            match_result_id=match_result_id,
            recruiter_id=g.recruiter_id,
        ).delete()
        db.session.commit()
        return jsonify(match_result_id=match_result_id, decision="unreviewed"), 200

    feedback = RecruiterFeedback(
        match_result_id=match_result_id,
        decision=decision,
        # Always the authenticated recruiter, never client-supplied
        recruiter_id=g.recruiter_id,
    )
    db.session.add(feedback)
    db.session.commit()

    return jsonify(feedback.to_dict()), 201


@results_bp.get("/<int:match_result_id>/feedback")
@require_auth
def list_feedback(match_result_id: int):
    _match, error = _owned_match(match_result_id)
    if error:
        return error
    feedback = RecruiterFeedback.query.filter_by(match_result_id=match_result_id).all()
    return jsonify(feedback=[f.to_dict() for f in feedback])
