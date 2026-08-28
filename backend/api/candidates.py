from __future__ import annotations
from flask import Blueprint, request, jsonify, current_app, g

from extensions import db
from models import Candidate, MatchResult as MatchResultModel, RecruiterFeedback, JobDescriptionModel
from auth import require_auth
from .jobs import _get_owned_job

candidates_bp = Blueprint("candidates", __name__, url_prefix="/api/candidates")


@candidates_bp.get("/<int:candidate_id>/explain")
@require_auth
def explain_candidate(candidate_id: int):
    """Explainability breakdown (Section 5.3) for one candidate against one JD.
    The design doc's endpoint signature doesn't carry a JD id, but explainability
    is inherently a (candidate, JD) pair -- so job_id is a required query param."""
    candidate = db.session.get(Candidate, candidate_id)
    if candidate is None:
        return jsonify(error=f"No candidate with id {candidate_id}."), 404

    job_id = request.args.get("job_id", type=int)
    if job_id is None:
        return jsonify(error="Query param 'job_id' is required to explain a match."), 400

    _jd, error = _get_owned_job(job_id)  # access control: can't probe another recruiter's job
    if error:
        return error

    match = MatchResultModel.query.filter_by(candidate_id=candidate_id, jd_id=job_id).first()
    if match is None:
        return jsonify(error=f"No ranking exists yet for candidate {candidate_id} against job {job_id}. "
                              f"Call POST /api/jobs/{job_id}/rank first."), 404

    return jsonify(
        candidate=candidate.to_dict(mask_pii=True),
        job_id=job_id,
        keyword_score=match.keyword_score,
        semantic_score=match.semantic_score,
        composite_score=match.composite_score,
        matched_skills=match.matched_skills or [],
        missing_skills=match.missing_skills or [],
        confidence=match.confidence,
        formula=f"0.4 x {match.keyword_score} + 0.6 x {match.semantic_score} = {match.composite_score}",
    )


@candidates_bp.get("/<int:candidate_id>/profile")
@require_auth
def candidate_profile(candidate_id: int):
    """Screen 4 -- Candidate Profile (master doc Section 3.6): the only place
    unmasked contact info appears, reached only via an explicit recruiter
    action, never as part of the ranked list, search, export, or the
    explainability drawer."""
    candidate = db.session.get(Candidate, candidate_id)
    if candidate is None:
        return jsonify(error=f"No candidate with id {candidate_id}."), 404

    data = candidate.to_dict(mask_pii=False)

    job_id = request.args.get("job_id", type=int)
    if job_id is not None:
        _jd, error = _get_owned_job(job_id)
        if error:
            return error
        match = MatchResultModel.query.filter_by(candidate_id=candidate_id, jd_id=job_id).first()
        if match is not None:
            data["composite_score"] = match.composite_score
            data["confidence"] = match.confidence

    return jsonify(data)


@candidates_bp.get("/pipeline")
@require_auth
def candidate_pipeline():
    """Hiring Pipeline view: returns candidate decisions across all owned jobs
    or a specific job, categorized by status (hired, rejected, shortlisted, pending)."""
    job_id = request.args.get("job_id", type=int)
    status_filter = request.args.get("status", "").strip().lower()

    if job_id is not None:
        jd, error = _get_owned_job(job_id)
        if error:
            return error
        owned_jobs = [jd]
    else:
        owned_jobs = JobDescriptionModel.query.filter_by(created_by_recruiter_id=g.recruiter_id).all()

    owned_job_ids = [j.id for j in owned_jobs]
    job_map = {j.id: j for j in owned_jobs}
    shortlist_threshold = current_app.config.get("SHORTLIST_THRESHOLD", 80.0)

    if not owned_job_ids:
        return jsonify(
            summary={"total_reviewed": 0, "hired_count": 0, "rejected_count": 0, "shortlisted_count": 0, "pending_count": 0},
            items=[],
        )

    matches = MatchResultModel.query.filter(MatchResultModel.jd_id.in_(owned_job_ids)).all()
    match_ids = [m.id for m in matches]

    # Latest feedback per match_result
    latest_feedbacks = {}
    if match_ids:
        feedback_rows = (
            RecruiterFeedback.query.filter(
                RecruiterFeedback.match_result_id.in_(match_ids),
                RecruiterFeedback.recruiter_id == g.recruiter_id,
            )
            .order_by(RecruiterFeedback.created_at.asc())
            .all()
        )
        for f in feedback_rows:
            latest_feedbacks[f.match_result_id] = f

    hired_items = []
    rejected_items = []
    shortlisted_items = []
    pending_items = []

    for m in matches:
        fb = latest_feedbacks.get(m.id)
        decision = fb.decision if fb else None
        jd = job_map.get(m.jd_id)
        
        item = {
            "match_result_id": m.id,
            "candidate_id": m.candidate_id,
            "job_id": m.jd_id,
            "job_title": jd.title if jd else "Unknown Job",
            "job_category": jd.category if jd else "General",
            "candidate": m.candidate.to_dict(mask_pii=True) if m.candidate else None,
            "composite_score": m.composite_score,
            "keyword_score": m.keyword_score,
            "semantic_score": m.semantic_score,
            "matched_skills": m.matched_skills or [],
            "missing_skills": m.missing_skills or [],
            "confidence": m.confidence,
            "decision": decision,
            "decision_date": fb.created_at.isoformat() if fb and fb.created_at else None,
            "shortlisted": m.composite_score >= shortlist_threshold,
        }

        if decision == "hired":
            hired_items.append(item)
        elif decision == "rejected":
            rejected_items.append(item)
        elif m.composite_score >= shortlist_threshold:
            shortlisted_items.append(item)
        else:
            pending_items.append(item)

    all_items = hired_items + rejected_items + shortlisted_items + pending_items

    if status_filter == "hired":
        filtered_items = hired_items
    elif status_filter == "rejected":
        filtered_items = rejected_items
    elif status_filter == "shortlisted":
        filtered_items = shortlisted_items
    elif status_filter == "pending":
        filtered_items = pending_items
    elif status_filter == "reviewed":
        filtered_items = hired_items + rejected_items
    else:
        filtered_items = all_items

    # Sort filtered items by composite score descending
    filtered_items.sort(key=lambda x: x["composite_score"], reverse=True)

    return jsonify(
        summary={
            "total_reviewed": len(hired_items) + len(rejected_items),
            "hired_count": len(hired_items),
            "rejected_count": len(rejected_items),
            "shortlisted_count": len(shortlisted_items),
            "pending_count": len(pending_items),
            "total_matches": len(matches),
        },
        items=filtered_items,
    )


@candidates_bp.get("/search")
@require_auth
def search_candidates():
    """FR-05: search/filter by keyword, skill, experience range, score threshold, category.
    'job_id' + 'min_score' only apply once that JD has been ranked."""
    query = Candidate.query

    keyword = request.args.get("keyword", "").strip().lower()
    skill = request.args.get("skill", "").strip()
    category = request.args.get("category", "").strip()
    min_experience = request.args.get("min_experience", type=float)
    max_experience = request.args.get("max_experience", type=float)
    job_id = request.args.get("job_id", type=int)
    min_score = request.args.get("min_score", type=float)

    candidates = query.all()

    if keyword:
        candidates = [
            c for c in candidates
            if keyword in (c.full_name or "").lower()
            or keyword in (c.resume_filename or "").lower()
            or any(keyword in s.lower() for s in (c.skills or []))
            or (c.predicted_category and keyword in c.predicted_category.lower())
        ]
    if skill:
        candidates = [c for c in candidates if skill in (c.skills or [])]
    if category:
        candidates = [c for c in candidates if (c.predicted_category or "").lower() == category.lower()]
    if min_experience is not None:
        candidates = [c for c in candidates if (c.experience_years or 0) >= min_experience]
    if max_experience is not None:
        candidates = [c for c in candidates if (c.experience_years or 0) <= max_experience]

    if job_id is not None:
        _jd, error = _get_owned_job(job_id)
        if error:
            return error
        matches = {m.candidate_id: m for m in MatchResultModel.query.filter_by(jd_id=job_id).all()}
        out = []
        for c in candidates:
            m = matches.get(c.id)
            if m is None:
                continue
            if min_score is not None and m.composite_score < min_score:
                continue
            d = c.to_dict(mask_pii=True)
            d["composite_score"] = m.composite_score
            d["confidence"] = m.confidence
            out.append(d)
        out.sort(key=lambda d: d["composite_score"], reverse=True)
        return jsonify(candidates=out, total=len(out))

    return jsonify(candidates=[c.to_dict(mask_pii=True) for c in candidates], total=len(candidates))
