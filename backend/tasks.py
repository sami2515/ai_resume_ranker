"""
Celery tasks (project documentation Section 4.1/7.1 Phase 5, NFR-01/NFR-02)
----------------------------------------------------------------------------
The actual work is in _process_resume_upload_impl(), a plain function that
assumes it's already running inside a Flask app context -- it doesn't know
or care whether that context came from a real HTTP request, a Celery
worker's FlaskContextTask wrapper, or a test calling it directly inside
`with app.app_context():`. That separation is what makes this testable
without a real Redis broker or worker process (see tests/test_async.py).

process_resume_upload_task() is the thin Celery-registered wrapper that
production/dev actually calls via .delay().
"""

from __future__ import annotations
import base64

from extensions import db
from models import UploadJob, Candidate
from upload_validation import file_hash
from crypto_utils import encrypt_bytes
from nlp_pipeline.parser import parse_resume, ResumeParseError
from nlp_pipeline.extractor import extract_profile
from ml.classify import classify_resume_category


def _process_resume_upload_impl(job_id: int, filename: str, content: bytes, storage_dir_str: str) -> None:
    from pathlib import Path
    import uuid

    job = db.session.get(UploadJob, job_id)
    if job is None:
        return  # job row vanished (e.g. deleted) -- nothing to update

    job.status = "processing"
    db.session.commit()

    storage_dir = Path(storage_dir_str)
    storage_dir.mkdir(parents=True, exist_ok=True)

    digest = file_hash(content)
    existing = Candidate.query.filter_by(file_hash=digest).first()
    if existing is not None:
        job.status = "duplicate"
        job.candidate_id = existing.id
        db.session.commit()
        return

    ext = "." + filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    stored_path = storage_dir / f"{uuid.uuid4().hex}{ext}"
    stored_path.write_bytes(content)

    try:
        parsed = parse_resume(stored_path)
        parsed.filename = filename  # see services.py's identical comment -- avoid the UUID-name bug
        profile = extract_profile(parsed)
    except ResumeParseError as e:
        try:
            stored_path.unlink(missing_ok=True)
        except OSError:
            pass
        job.status = "error"
        job.error = str(e)
        db.session.commit()
        return

    stored_path.write_bytes(encrypt_bytes(content))

    candidate = Candidate(
        resume_filename=filename,
        stored_path=str(stored_path),
        file_hash=digest,
        full_name=profile.full_name,
        email=profile.email,
        phone=profile.phone,
        skills=profile.skills,
        education=profile.education,
        certifications=profile.certifications,
        experience_years=profile.experience_years,
        raw_text=profile.raw_text,
        predicted_category=classify_resume_category(profile.raw_text),
    )
    db.session.add(candidate)
    db.session.flush()  # assigns candidate.id without committing yet

    job.status = "created"
    job.candidate_id = candidate.id
    db.session.commit()


def register_tasks(celery_app):
    """Registers the Celery-callable task against the given app. Called from
    celery_app.py so the task exists under a stable name regardless of
    which module imports celery_app first."""

    @celery_app.task(name="tasks.process_resume_upload_task", bind=True, max_retries=2)
    def process_resume_upload_task(self, job_id: int, filename: str, content_b64: str, storage_dir_str: str):
        content = base64.b64decode(content_b64)
        try:
            _process_resume_upload_impl(job_id, filename, content, storage_dir_str)
        except Exception as exc:  # noqa: BLE001 -- a worker-side crash must still resolve the job, not hang it "processing" forever
            db.session.rollback()
            job = db.session.get(UploadJob, job_id)
            if job is not None:
                job.status = "error"
                job.error = f"Internal processing error: {exc}"
                db.session.commit()
            raise

    return process_resume_upload_task
