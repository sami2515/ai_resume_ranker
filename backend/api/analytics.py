"""
Analytics dashboard endpoint (project documentation Section 4.4/4.5)
"""

from __future__ import annotations
from collections import Counter
from flask import Blueprint, jsonify, g

from models import Candidate, JobDescriptionModel, MatchResult as MatchResultModel, RecruiterFeedback
from auth import require_auth

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


@analytics_bp.get("/overview")
@require_auth
def analytics_overview():
    # Candidates (the resume pool) are shared org-wide by design; jobs and
    # everything derived from them (matches, feedback) are scoped to the
    # requesting recruiter's own jobs -- consistent with the access-control
    # model on /api/jobs.
    candidates = Candidate.query.all()
    jobs = JobDescriptionModel.query.filter_by(created_by_recruiter_id=g.recruiter_id).all()
    own_job_ids = [j.id for j in jobs]
    matches = MatchResultModel.query.filter(MatchResultModel.jd_id.in_(own_job_ids)).all() if own_job_ids else []

    skill_counts = Counter()
    for c in candidates:
        skill_counts.update(c.skills or [])

    score_distribution = {"high_confidence": 0, "moderate": 0, "weak": 0}
    for m in matches:
        if m.confidence == "High Confidence Match":
            score_distribution["high_confidence"] += 1
        elif (m.confidence or "").startswith("Moderate"):
            score_distribution["moderate"] += 1
        else:
            score_distribution["weak"] += 1

    match_ids = [m.id for m in matches]
    # Latest decision per match_result wins (a recruiter may change their mind).
    latest_decision_by_match = {}
    if match_ids:
        feedback_rows = (
            RecruiterFeedback.query.filter(RecruiterFeedback.match_result_id.in_(match_ids))
            .order_by(RecruiterFeedback.created_at)
            .all()
        )
        for f in feedback_rows:
            latest_decision_by_match[f.match_result_id] = f.decision
    decisions = latest_decision_by_match.values()
    hiring_funnel = {
        "matches_computed": len(matches),
        "reviewed": len(latest_decision_by_match),
        "hired": sum(1 for d in decisions if d == "hired"),
        "rejected": sum(1 for d in decisions if d == "rejected"),
        "pending": max(len(matches) - len(latest_decision_by_match), 0),
    }

    return jsonify(
        total_candidates=len(candidates),
        total_jobs=len(jobs),
        total_matches_computed=len(matches),
        score_distribution=score_distribution,
        top_skills=[{"skill": s, "count": n} for s, n in skill_counts.most_common(10)],
        hiring_funnel=hiring_funnel,
    )
