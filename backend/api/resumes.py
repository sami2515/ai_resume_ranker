"""
Resume upload endpoints (project documentation Section 4.4, FR-01)
"""

from __future__ import annotations
import io
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app, send_file, g

from extensions import db
from models import Candidate, UploadJob
from services import process_resume_upload_batch
from auth import require_auth
from crypto_utils import decrypt_bytes

resumes_bp = Blueprint("resumes", __name__, url_prefix="/api/resumes")


@resumes_bp.post("/upload")
@require_auth
def upload_resumes():
    files = request.files.getlist("resumes") or request.files.getlist("files")
    if not files:
        return jsonify(error="No files uploaded. Send one or more files under the 'resumes' field."), 400

    storage_dir = current_app.config["STORAGE_DIR"]
    threshold = current_app.config["ASYNC_UPLOAD_THRESHOLD"]
    file_data = [(f.filename, f.read()) for f in files]

    results = process_resume_upload_batch(file_data, storage_dir, g.recruiter_id, threshold)

    summary = {
        "total": len(results),
        "queued": sum(1 for r in results if r["status"] == "queued"),
        "created": sum(1 for r in results if r["status"] == "created"),
        "duplicates": sum(1 for r in results if r["status"] == "duplicate"),
        "errors": sum(1 for r in results if r["status"] == "error"),
    }
    return jsonify(results=results, summary=summary), 201


@resumes_bp.get("/jobs/<int:job_id>/status")
@require_auth
def upload_job_status(job_id: int):
    """Poll an upload's progress -- 'queued'/'processing' while a Celery
    worker is still parsing it (async, large-batch path), 'created'/
    'duplicate'/'error' once resolved (which, for small/synchronous
    batches, is already true by the time /upload responds)."""
    job = db.session.get(UploadJob, job_id)
    if job is None:
        return jsonify(error=f"No upload job with id {job_id}."), 404
    return jsonify(job.to_dict())


@resumes_bp.get("/<int:candidate_id>/download")
@require_auth
def download_resume(candidate_id: int):
    """FR-07: view/download the original resume file of a candidate.
    Files are encrypted at rest (NFR-04) -- decrypted in memory, never
    written back to disk in plaintext."""
    candidate = db.session.get(Candidate, candidate_id)
    if candidate is None:
        return jsonify(error=f"No candidate with id {candidate_id}."), 404

    try:
        encrypted = Path(candidate.stored_path).read_bytes()
    except FileNotFoundError:
        # FR-07 edge case: the file was deleted or moved on the server after
        # upload -- a clean, user-safe "unavailable" state, not a broken
        # download link / uncaught 500.
        return jsonify(error="This resume file is no longer available on the server. "
                              "It may have been deleted or moved."), 404
    plaintext = decrypt_bytes(encrypted)
    filename = candidate.resume_filename or "resume"
    ext = Path(filename).suffix.lower()
    mime = (
        "application/pdf" if ext == ".pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if ext == ".docx"
        else "application/octet-stream"
    )
    return send_file(
        io.BytesIO(plaintext),
        download_name=filename,
        as_attachment=True,
        mimetype=mime,
    )


@resumes_bp.delete("/<int:candidate_id>")
@require_auth
def delete_candidate(candidate_id: int):
    """Section 12.6: a basic 'delete candidate data' action, satisfying a
    minimal right-to-deletion principle. Removes the DB row, the encrypted
    file on disk, and any dependent match results / feedback."""
    from models import MatchResult, RecruiterFeedback, UploadJob

    candidate = db.session.get(Candidate, candidate_id)
    if candidate is None:
        return jsonify(error=f"No candidate with id {candidate_id}."), 404

    match_ids = [m.id for m in MatchResult.query.filter_by(candidate_id=candidate_id).all()]
    if match_ids:
        RecruiterFeedback.query.filter(RecruiterFeedback.match_result_id.in_(match_ids)).delete(
            synchronize_session=False
        )
        MatchResult.query.filter_by(candidate_id=candidate_id).delete(synchronize_session=False)

    # Null out the dangling reference rather than deleting the job row --
    # the fact that an upload happened is an audit trail, not "candidate
    # data" in the Section 12.6 sense, so it survives the candidate's deletion.
    UploadJob.query.filter_by(candidate_id=candidate_id).update({"candidate_id": None})

    Path(candidate.stored_path).unlink(missing_ok=True)
    db.session.delete(candidate)
    db.session.commit()
    return jsonify(deleted=True, candidate_id=candidate_id)
