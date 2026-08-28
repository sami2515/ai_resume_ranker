"""
Data model (project documentation Section 4.3)
--------------------------------------------------
Mirrors the four core entities from the design doc. A few operational
fields are added beyond the doc's table (file_hash for duplicate detection
per Section 8.3, stored_path for resume download per FR-07) since the doc
lists the *conceptual* schema, not every implementation column.

Embeddings are not persisted yet -- Section 4.3 lists them for fast
re-ranking at scale, which is out of scope until the async/Celery layer
(Phase 5) makes re-ranking-without-re-parsing worth the complexity.
"""

from __future__ import annotations
from datetime import datetime, timezone

from extensions import db
from crypto_utils import encrypt_text, decrypt_text


def _utcnow():
    return datetime.now(timezone.utc)


class Recruiter(db.Model):
    __tablename__ = "recruiter"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self) -> dict:
        return {"id": self.id, "email": self.email, "full_name": self.full_name}


def _mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    visible = local[:2]
    return f"{visible}{'*' * max(len(local) - 2, 1)}@{domain}"


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return phone
    digits_only = "".join(ch for ch in phone if ch.isdigit())
    if len(digits_only) < 4:
        return "*" * len(phone)
    return "*" * (len(phone) - 4) + phone[-4:]


class Candidate(db.Model):
    __tablename__ = "candidate"

    id = db.Column(db.Integer, primary_key=True)
    resume_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    file_hash = db.Column(db.String(64), nullable=False, index=True)  # SHA-256, for duplicate detection

    full_name = db.Column(db.String(255))
    # NFR-04/Section 12.6: PII stored encrypted at rest, not plaintext.
    # Fernet ciphertext is longer than the source string, hence Text not
    # String -- and the columns are named *_encrypted so nothing accidentally
    # reads them directly instead of through the email/phone properties below.
    email_encrypted = db.Column(db.Text)
    phone_encrypted = db.Column(db.Text)
    skills = db.Column(db.JSON, default=list)
    education = db.Column(db.JSON, default=list)
    certifications = db.Column(db.JSON, default=list)
    experience_years = db.Column(db.Float, default=0.0)
    raw_text = db.Column(db.Text)
    # ML Training Master Plan Section 2: predicted by the offline-trained
    # resume category classifier (scripts/train_classifier.py) at upload
    # time. Null until that model has actually been trained on real
    # labeled data -- never guessed by a fallback rule, matching the same
    # "report what's actually active" honesty as the semantic backend.
    predicted_category = db.Column(db.String(64))

    created_at = db.Column(db.DateTime, default=_utcnow)

    @property
    def email(self) -> str | None:
        return decrypt_text(self.email_encrypted)

    @email.setter
    def email(self, value: str | None) -> None:
        self.email_encrypted = encrypt_text(value)

    @property
    def phone(self) -> str | None:
        return decrypt_text(self.phone_encrypted)

    @phone.setter
    def phone(self, value: str | None) -> None:
        self.phone_encrypted = encrypt_text(value)

    def to_dict(self, include_text: bool = False, mask_pii: bool = False) -> dict:
        """mask_pii (Section 12.6): the ranked-list / search views mask email
        and phone to reduce incidental exposure during screen-shares/demos;
        the single-candidate explain/detail view shows them in full."""
        d = {
            "id": self.id,
            "resume_filename": self.resume_filename,
            "full_name": self.full_name,
            "email": _mask_email(self.email) if mask_pii else self.email,
            "phone": _mask_phone(self.phone) if mask_pii else self.phone,
            "skills": self.skills or [],
            "education": self.education or [],
            "certifications": self.certifications or [],
            "experience_years": self.experience_years,
            "predicted_category": self.predicted_category,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_text:
            d["raw_text"] = self.raw_text
        return d


class JobDescriptionModel(db.Model):
    __tablename__ = "job_description"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    raw_text = db.Column(db.Text, nullable=False)
    required_skills = db.Column(db.JSON, default=list)
    min_experience = db.Column(db.Float, default=0.0)
    category = db.Column(db.String(100), nullable=False, default="General", index=True)
    created_by_recruiter_id = db.Column(db.Integer, db.ForeignKey("recruiter.id"), nullable=False)
    status = db.Column(db.String(32), default="active", nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status or "active",
            "category": self.category,
            "required_skills": self.required_skills or [],
            "min_experience": self.min_experience,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MatchResult(db.Model):
    __tablename__ = "match_result"
    __table_args__ = (db.UniqueConstraint("candidate_id", "jd_id", name="uq_match_candidate_jd"),)

    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidate.id"), nullable=False)
    jd_id = db.Column(db.Integer, db.ForeignKey("job_description.id"), nullable=False)

    keyword_score = db.Column(db.Float, nullable=False)
    semantic_score = db.Column(db.Float, nullable=False)
    composite_score = db.Column(db.Float, nullable=False)
    matched_skills = db.Column(db.JSON, default=list)
    missing_skills = db.Column(db.JSON, default=list)
    confidence = db.Column(db.String(64))

    created_at = db.Column(db.DateTime, default=_utcnow)

    candidate = db.relationship("Candidate")

    def to_dict(self, rank_position: int | None = None, mask_pii: bool = False) -> dict:
        d = {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "jd_id": self.jd_id,
            "keyword_score": self.keyword_score,
            "semantic_score": self.semantic_score,
            "composite_score": self.composite_score,
            "matched_skills": self.matched_skills or [],
            "missing_skills": self.missing_skills or [],
            "confidence": self.confidence,
        }
        if rank_position is not None:
            d["rank_position"] = rank_position
        if self.candidate is not None:
            d["candidate"] = self.candidate.to_dict(mask_pii=mask_pii)
        return d


class RecruiterFeedback(db.Model):
    __tablename__ = "recruiter_feedback"

    id = db.Column(db.Integer, primary_key=True)
    match_result_id = db.Column(db.Integer, db.ForeignKey("match_result.id"), nullable=False)
    decision = db.Column(db.String(20), nullable=False)  # "hired" | "rejected"
    # Set from the authenticated request (g.recruiter_id), never trusted from
    # the client body -- a client-supplied recruiter_id would let anyone
    # attribute feedback to someone else's account.
    recruiter_id = db.Column(db.Integer, db.ForeignKey("recruiter.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "match_result_id": self.match_result_id,
            "decision": self.decision,
            "recruiter_id": self.recruiter_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UploadJob(db.Model):
    """Async upload tracking (Section 4.1/7.1 Phase 5, NFR-02). Created at
    upload time -- before a Candidate necessarily exists -- so the client can
    poll status while a Celery worker parses the file in the background.
    For small/synchronous batches this still gets created, just already
    resolved to its final status by the time the response is sent."""

    __tablename__ = "upload_job"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    recruiter_id = db.Column(db.Integer, db.ForeignKey("recruiter.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="queued")  # queued|processing|created|duplicate|error
    error = db.Column(db.Text)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidate.id"))
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    candidate = db.relationship("Candidate")

    def to_dict(self) -> dict:
        d = {
            "job_id": self.id,
            "filename": self.filename,
            "status": self.status,
            "error": self.error,
            "candidate_id": self.candidate_id,
        }
        if self.candidate is not None:
            d["candidate"] = self.candidate.to_dict()
        return d


class ScoringWeights(db.Model):
    """Feedback-loop weight history (Section 5.4/12.3, tech-debt register:
    'No model/weight versioning for the feedback loop' -- Critical). Every
    proposal is recorded, promoted or not, so the active weights for a
    category are always traceable to the feedback and regression check
    that produced them. Rows are never deleted -- `status` tells the story:
      "active"                    -- currently used for ranking this category
      "superseded"                -- was active, replaced by a later promotion
      "rejected_regression"       -- proposed, but degraded validation metrics -> rolled back
      "proposed_no_validation_set" -- proposed, but never applied (see services.py)
    """

    __tablename__ = "scoring_weights"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False, index=True)
    keyword_weight = db.Column(db.Float, nullable=False)
    semantic_weight = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), nullable=False)
    reason = db.Column(db.Text)  # human-readable explanation from the proposal/regression check
    precision_at_5 = db.Column(db.Float)  # validation-set metrics at proposal time, if a validation set existed
    ndcg_at_10 = db.Column(db.Float)
    hired_count = db.Column(db.Integer)
    rejected_count = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "keyword_weight": self.keyword_weight,
            "semantic_weight": self.semantic_weight,
            "status": self.status,
            "reason": self.reason,
            "precision_at_5": self.precision_at_5,
            "ndcg_at_10": self.ndcg_at_10,
            "hired_count": self.hired_count,
            "rejected_count": self.rejected_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
