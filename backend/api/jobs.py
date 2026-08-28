"""
Job description + ranking endpoints (project documentation Section 4.4, FR-02/FR-04)
"""

from __future__ import annotations
from flask import Blueprint, request, jsonify, current_app, g

from extensions import db
from models import JobDescriptionModel, MatchResult as MatchResultModel, RecruiterFeedback
from services import create_job_description, run_ranking_for_job, get_ranked_results
from upload_validation import validate_upload, UploadValidationError
from nlp_pipeline.parser import parse_resume, ResumeParseError
from auth import require_auth

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


def _get_owned_job(job_id: int):
    """Section 8.2 Security Testing: verify access control between recruiter
    accounts. A JD is only visible/actionable by the recruiter who created
    it. Returns (job_or_None, error_response_or_None)."""
    jd = db.session.get(JobDescriptionModel, job_id)
    if jd is None:
        return None, (jsonify(error=f"No job description with id {job_id}."), 404)
    if jd.created_by_recruiter_id != g.recruiter_id:
        return None, (jsonify(error="You don't have access to this job description."), 403)
    return jd, None


@jobs_bp.post("")
@require_auth
def create_job():
    """Accepts either JSON {"title", "text"} or a multipart file upload
    (field name 'jd_file') plus a 'title' form field -- FR-02 allows either."""
    if request.files:
        f = request.files.get("jd_file")
        title = request.form.get("title", "").strip()
        if f is None or not title:
            return jsonify(error="File upload requires both 'jd_file' and 'title'."), 400
        content = f.read()
        try:
            validate_upload(f.filename, content)
        except UploadValidationError as e:
            return jsonify(error=str(e)), 400

        import tempfile, os
        suffix = "." + f.filename.rsplit(".", 1)[1].lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            parsed = parse_resume(tmp_path)
        except ResumeParseError as e:
            return jsonify(error=str(e)), 400
        finally:
            os.unlink(tmp_path)
        raw_text = parsed.raw_text
    else:
        body = request.get_json(silent=True) or {}
        title = (body.get("title") or "").strip()
        raw_text = (body.get("text") or "").strip()
        if not title or not raw_text:
            return jsonify(error="JSON body requires non-empty 'title' and 'text'."), 400

    jd = create_job_description(title, raw_text, created_by_recruiter_id=g.recruiter_id)
    return jsonify(jd.to_dict()), 201


@jobs_bp.get("")
@require_auth
def list_jobs():
    query = JobDescriptionModel.query.filter_by(created_by_recruiter_id=g.recruiter_id)
    if request.args.get("active_only", "").lower() in ("true", "1"):
        query = query.filter_by(status="active")
    jobs = query.order_by(JobDescriptionModel.created_at.desc()).all()
    shortlist_threshold = current_app.config.get("SHORTLIST_THRESHOLD", 80.0)

    out = []
    for j in jobs:
        d = j.to_dict()
        matches = MatchResultModel.query.filter_by(jd_id=j.id).all()
        match_ids = [m.id for m in matches]
        
        latest_decisions = {}
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
                latest_decisions[f.match_result_id] = f.decision

        d["stats"] = {
            "total_candidates": len(matches),
            "top_score": max((m.composite_score for m in matches), default=0.0),
            "shortlisted_count": sum(1 for m in matches if m.composite_score >= shortlist_threshold),
            "hired_count": sum(1 for dec in latest_decisions.values() if dec == "hired"),
            "rejected_count": sum(1 for dec in latest_decisions.values() if dec == "rejected"),
        }
        out.append(d)

    return jsonify(jobs=out)


@jobs_bp.patch("/<int:job_id>/status")
@require_auth
def update_status(job_id: int):
    jd, error = _get_owned_job(job_id)
    if error:
        return error
    body = request.get_json(silent=True) or {}
    new_status = (body.get("status") or "").strip().lower()
    if new_status not in ("active", "paused", "closed"):
        return jsonify(error="Status must be one of: active, paused, closed"), 400
    jd.status = new_status
    db.session.commit()
    return jsonify(jd.to_dict()), 200


@jobs_bp.delete("/<int:job_id>")
@require_auth
def delete_job(job_id: int):
    jd, error = _get_owned_job(job_id)
    if error:
        return error
    from services import delete_job_description
    delete_job_description(job_id)
    return jsonify(message=f"Job {job_id} deleted successfully."), 200


@jobs_bp.post("/<int:job_id>/rank")
@require_auth
def rank_job(job_id: int):
    jd, error = _get_owned_job(job_id)
    if error:
        return error

    body = request.get_json(silent=True) or {}
    candidate_ids = body.get("candidate_ids")
    if candidate_ids and not isinstance(candidate_ids, list):
        candidate_ids = None

    results = run_ranking_for_job(jd, candidate_ids=candidate_ids)
    if not results:
        return jsonify(
            jd_id=job_id,
            ranked=0,
            message="No candidates found to rank. Upload resumes first.",
        ), 200

    return jsonify(jd_id=job_id, ranked=len(results))


@jobs_bp.get("/<int:job_id>/results")
@require_auth
def job_results(job_id: int):
    jd, error = _get_owned_job(job_id)
    if error:
        return error

    shortlist_threshold = current_app.config["SHORTLIST_THRESHOLD"]
    rows = get_ranked_results(job_id)

    # Attach existing recruiter feedback decisions
    match_ids = [row.id for row in rows]
    latest_decisions = {}
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
            latest_decisions[f.match_result_id] = f.decision

    results = []
    for i, row in enumerate(rows):
        d = row.to_dict(rank_position=i + 1, mask_pii=True)
        d["shortlisted"] = d["composite_score"] >= shortlist_threshold
        d["decision"] = latest_decisions.get(row.id, None)
        results.append(d)

    # Section 8.3: a JD with zero strong matches must produce a clear signal,
    # not an ambiguous empty/weird screen.
    no_strong_matches = len(results) == 0 or all(
        r["confidence"] != "High Confidence Match" and r["composite_score"] < shortlist_threshold
        for r in results
    )

    return jsonify(
        jd=jd.to_dict(),
        results=results,
        no_strong_matches=no_strong_matches,
        total=len(results),
    )
