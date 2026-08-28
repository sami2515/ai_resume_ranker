"""
Feedback-loop re-weighting endpoints (project documentation Section 5.4/12.3, FR-10)
"""

from __future__ import annotations
from flask import Blueprint, request, jsonify

from models import ScoringWeights
from services import run_reweighting_for_category, run_trained_reweighting_for_category
from auth import require_auth

feedback_bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")


@feedback_bp.post("/reweight")
@require_auth
def reweight():
    """Triggers the Section 5.4 re-weighting step for one job category.
    Not gated to a specific recruiter's own data -- this is a platform-wide
    learning step over all recruiters' feedback for the category (this
    project has no admin/RBAC tier; see README for that scope note)."""
    body = request.get_json(silent=True) or {}
    category = (body.get("category") or "").strip()
    if not category:
        return jsonify(error="'category' is required."), 400

    result = run_reweighting_for_category(category)
    status_code = 200 if result["status"] != "insufficient_feedback" else 422
    return jsonify(result), status_code


@feedback_bp.post("/reweight-trained")
@require_auth
def reweight_trained():
    """ML Training Master Plan Section 4: the optional trained-model
    upgrade path -- a real 2-feature logistic regression instead of the
    fixed-step heuristic, gated on far more feedback data (Section 4.2),
    but promoted through the identical Section 12.3 regression check as
    /reweight. Inert (returns 422) until a category has at least
    MIN_SAMPLES_FOR_TRAINED_REWEIGHT real hired+rejected examples."""
    body = request.get_json(silent=True) or {}
    category = (body.get("category") or "").strip()
    if not category:
        return jsonify(error="'category' is required."), 400

    result = run_trained_reweighting_for_category(category)
    status_code = 200 if result["status"] != "insufficient_feedback" else 422
    return jsonify(result), status_code


@feedback_bp.get("/active")
@require_auth
def get_active_scoring_weights():
    """Returns currently active scoring weights across known job categories."""
    from services import get_active_weights
    categories = ["General", "Business Analyst", "Full Stack Developer", "Project Manager", "Software Engineer"]
    active_map = {}
    for cat in categories:
        kw, sem = get_active_weights(cat)
        active_map[cat] = {"keyword_weight": kw, "semantic_weight": sem}
    return jsonify(active_weights=active_map)


@feedback_bp.get("/weights")
@require_auth
def list_weights():
    """Full audit trail (Section 12.3): every proposal this category has
    ever had, promoted or not, so a weight change is always traceable to
    the feedback and regression check that produced it."""
    category = request.args.get("category")
    query = ScoringWeights.query
    if category:
        query = query.filter_by(category=category)
    rows = query.order_by(ScoringWeights.created_at.desc()).all()
    return jsonify(weights=[r.to_dict() for r in rows])
