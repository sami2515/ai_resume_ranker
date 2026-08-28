"""
Service layer bridging the Flask API to the pipeline + database.
---------------------------------------------------------------------
Keeps blueprints thin: they parse the HTTP request, call one of these
functions, and serialize the result. All resume/JD-processing and
ranking logic that needs the database lives here.

Async uploads (Section 4.1/7.1 Phase 5, NFR-01/NFR-02): batches at or
above config.ASYNC_UPLOAD_THRESHOLD are queued through Celery/Redis so a
large bulk upload doesn't block the request; smaller batches -- and any
batch where the broker turns out to be unreachable -- process inline. That
inline fallback is deliberate, not a placeholder: project documentation
Section 13's tech-debt register calls it out by name as the fix for "no
graceful degraded mode if Redis/Celery fails mid-demo."
"""

from __future__ import annotations
import base64
from functools import lru_cache
import json
from pathlib import Path

from extensions import db
from models import (
    Candidate, JobDescriptionModel, MatchResult as MatchResultModel,
    RecruiterFeedback, UploadJob, ScoringWeights,
)
from upload_validation import validate_upload, UploadValidationError
from nlp_pipeline.extractor import CandidateProfile
from nlp_pipeline.jd_parser import parse_job_description
from nlp_pipeline.matching_engine import (
    JobDescription as JobDescriptionDC,
    rank_candidates,
    confidence_label,
)
from nlp_pipeline.reweighting import (
    ScoreStats, propose_weights, InsufficientFeedbackError,
    FeedbackExample, propose_weights_trained, InsufficientTrainingDataError,
    DEFAULT_KEYWORD_WEIGHT, DEFAULT_SEMANTIC_WEIGHT,
)
from nlp_pipeline.evaluation import evaluate_single_job, aggregate_metrics, should_promote_weights
from tasks import _process_resume_upload_impl

REPO_ROOT = Path(__file__).resolve().parent.parent


def _broker_available() -> bool:
    """One short, bounded-timeout connection check per batch -- not per file.
    A dead broker must fail fast (demo-acceptable, not a multi-second hang
    per file) and must never take the upload endpoint down with it."""
    try:
        from celery_app import celery_app
        conn = celery_app.connection()
        conn.ensure_connection(max_retries=1, timeout=1.5)
        conn.close()
        return True
    except Exception:  # noqa: BLE001 -- deliberately broad: any broker/connection failure degrades gracefully
        return False


def _enqueue(job_id: int, filename: str, content: bytes, storage_dir: Path) -> bool:
    try:
        from celery_app import process_resume_upload_task
        content_b64 = base64.b64encode(content).decode()
        process_resume_upload_task.delay(job_id, filename, content_b64, str(storage_dir))
        return True
    except Exception:  # noqa: BLE001
        return False


def process_resume_upload_batch(
    files: list[tuple[str, bytes]],
    storage_dir: Path,
    recruiter_id: int,
    async_threshold: int,
) -> list[dict]:
    """Validates and creates an UploadJob row for every file up front (so the
    response always carries a job_id per file, even for immediate
    rejections), then either enqueues each job asynchronously or processes
    it inline, depending on batch size and broker availability."""
    use_async = len(files) >= async_threshold and _broker_available()
    results = []

    for filename, content in files:
        job = UploadJob(filename=filename, recruiter_id=recruiter_id, status="queued")
        db.session.add(job)
        db.session.commit()

        try:
            validate_upload(filename, content)
        except UploadValidationError as e:
            job.status = "error"
            job.error = str(e)
            db.session.commit()
            results.append(job.to_dict())
            continue

        if use_async and _enqueue(job.id, filename, content, storage_dir):
            results.append(job.to_dict())  # status still "queued"
            continue

        # Synchronous: small batch, broker unavailable, or this particular
        # enqueue call failed after the batch-level check passed.
        _process_resume_upload_impl(job.id, filename, content, str(storage_dir))
        db.session.refresh(job)
        results.append(job.to_dict())

    return results


def candidate_to_profile(candidate: Candidate) -> CandidateProfile:
    """Reconstruct a CandidateProfile dataclass from a persisted Candidate row
    so it can be fed back into the pipeline's scoring functions without
    re-parsing the original file."""
    return CandidateProfile(
        filename=candidate.resume_filename,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        skills=candidate.skills or [],
        education=candidate.education or [],
        certifications=candidate.certifications or [],
        experience_years=candidate.experience_years or 0.0,
        raw_text=candidate.raw_text or "",
    )


# Job category (Section 5.4: the feedback loop re-weights "per job
# category"). Matched against the dataset's own role categories (project
# documentation Section 1.4); order matters since e.g. "Senior Business
# Systems Analyst" should hit "business analyst" before any looser catch.
CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    ("business analyst", "Business Analyst"),
    ("business systems analyst", "Business Analyst"),
    ("full stack", "Full Stack Developer"),
    ("fullstack", "Full Stack Developer"),
    ("project manager", "Project Manager"),
    ("program manager", "Project Manager"),
    ("scrum master", "Project Manager"),
    ("software engineer", "Software Engineer"),
    ("software developer", "Software Engineer"),
    ("java developer", "Software Engineer"),
    ("developer", "Software Engineer"),
]


def infer_job_category(title: str) -> str:
    lowered = title.lower()
    for keyword, category in CATEGORY_KEYWORDS:
        if keyword in lowered:
            return category
    return "General"


def create_job_description(title: str, raw_text: str, created_by_recruiter_id: int) -> JobDescriptionModel:
    parsed = parse_job_description(title, raw_text)
    jd = JobDescriptionModel(
        title=parsed.title,
        raw_text=parsed.raw_text,
        required_skills=parsed.required_skills,
        min_experience=parsed.min_experience,
        category=infer_job_category(parsed.title),
        created_by_recruiter_id=created_by_recruiter_id,
        status="active",
    )
    db.session.add(jd)
    db.session.commit()
    return jd


def update_job_status(jd_id: int, status: str) -> JobDescriptionModel | None:
    jd = db.session.get(JobDescriptionModel, jd_id)
    if not jd:
        return None
    jd.status = status
    db.session.commit()
    return jd


def delete_job_description(jd_id: int) -> bool:
    jd = db.session.get(JobDescriptionModel, jd_id)
    if not jd:
        return False
    matches = MatchResultModel.query.filter_by(jd_id=jd_id).all()
    match_ids = [m.id for m in matches]
    if match_ids:
        RecruiterFeedback.query.filter(RecruiterFeedback.match_result_id.in_(match_ids)).delete(synchronize_session=False)
        MatchResultModel.query.filter_by(jd_id=jd_id).delete(synchronize_session=False)
    db.session.delete(jd)
    db.session.commit()
    return True


def get_active_weights(category: str) -> tuple[float, float]:
    row = ScoringWeights.query.filter_by(category=category, status="active").order_by(
        ScoringWeights.created_at.desc()
    ).first()
    if row is None:
        return DEFAULT_KEYWORD_WEIGHT, DEFAULT_SEMANTIC_WEIGHT
    return row.keyword_weight, row.semantic_weight


def run_ranking_for_job(jd_row: JobDescriptionModel, candidate_ids: list[int] | None = None) -> list[MatchResultModel]:
    """Runs the matching engine against uploaded candidates (either specified IDs or all)
    and upserts MatchResult rows for this JD. Returns the persisted rows (unordered;
    call get_ranked_results for the tie-broken, ranked view)."""
    if candidate_ids:
        candidates = Candidate.query.filter(Candidate.id.in_(candidate_ids)).all()
    else:
        candidates = Candidate.query.all()

    if not candidates:
        return []

    profiles = [candidate_to_profile(c) for c in candidates]
    jd_dc = JobDescriptionDC(
        title=jd_row.title,
        raw_text=jd_row.raw_text,
        required_skills=jd_row.required_skills or [],
        min_experience=jd_row.min_experience or 0.0,
    )
    keyword_weight, semantic_weight = get_active_weights(jd_row.category)
    results = rank_candidates(profiles, jd_dc, keyword_weight=keyword_weight, semantic_weight=semantic_weight)
    by_filename = {c.resume_filename: c for c in candidates}

    persisted = []
    for r in results:
        candidate = by_filename[r.candidate_filename]
        row = MatchResultModel.query.filter_by(candidate_id=candidate.id, jd_id=jd_row.id).first()
        if row is None:
            row = MatchResultModel(candidate_id=candidate.id, jd_id=jd_row.id)
            db.session.add(row)
        row.keyword_score = r.keyword_score
        row.semantic_score = r.semantic_score
        row.composite_score = r.composite_score
        row.matched_skills = r.matched_skills
        row.missing_skills = r.missing_skills
        row.confidence = r.confidence
        persisted.append(row)

    db.session.commit()
    return persisted


def get_ranked_results(jd_id: int) -> list[MatchResultModel]:
    """Deterministic ranked view (Section 8.3 tie-break): composite score desc,
    semantic score desc, then upload recency (earlier upload wins) as the
    final tiebreaker."""
    rows = (
        MatchResultModel.query.join(Candidate, MatchResultModel.candidate_id == Candidate.id)
        .filter(MatchResultModel.jd_id == jd_id)
        .all()
    )
    rows.sort(
        key=lambda r: (
            -r.composite_score,
            -r.semantic_score,
            r.candidate.created_at or 0,
            r.candidate_id,
        )
    )
    return rows


# ---------------------------------------------------------- feedback re-weighting


def _gather_feedback_stats(category: str) -> tuple[ScoreStats, ScoreStats]:
    """Average keyword/semantic score of hired vs. rejected candidates for
    a category, using the latest decision per match result (a recruiter
    may change their mind -- same rule as api/analytics.py's hiring funnel)."""
    matches = (
        MatchResultModel.query
        .join(JobDescriptionModel, MatchResultModel.jd_id == JobDescriptionModel.id)
        .filter(JobDescriptionModel.category == category)
        .all()
    )
    match_by_id = {m.id: m for m in matches}
    if not match_by_id:
        return ScoreStats(0, 0, 0), ScoreStats(0, 0, 0)

    latest_decision: dict[int, str] = {}
    feedback_rows = (
        RecruiterFeedback.query
        .filter(RecruiterFeedback.match_result_id.in_(match_by_id.keys()))
        .order_by(RecruiterFeedback.created_at)
        .all()
    )
    for f in feedback_rows:
        latest_decision[f.match_result_id] = f.decision

    buckets = {"hired": ([], []), "rejected": ([], [])}
    for match_id, decision in latest_decision.items():
        if decision not in buckets:
            continue
        m = match_by_id[match_id]
        kw_list, sem_list = buckets[decision]
        kw_list.append(m.keyword_score)
        sem_list.append(m.semantic_score)

    def _stats(kw_list: list[float], sem_list: list[float]) -> ScoreStats:
        n = len(kw_list)
        if n == 0:
            return ScoreStats(0, 0, 0)
        return ScoreStats(avg_keyword=sum(kw_list) / n, avg_semantic=sum(sem_list) / n, count=n)

    hired = _stats(*buckets["hired"])
    rejected = _stats(*buckets["rejected"])
    return hired, rejected


@lru_cache(maxsize=1)
def _get_validation_profiles():
    from nlp_pipeline import parse_resume, extract_profile
    from nlp_pipeline.parser import ResumeParseError

    dataset_dir = REPO_ROOT / "datasets" / "resumes"
    profiles = []
    for f in sorted(dataset_dir.glob("*.docx")):
        try:
            profiles.append(extract_profile(parse_resume(f)))
        except ResumeParseError:
            continue
    return tuple(profiles)


def _evaluate_weights_on_validation_set(keyword_weight: float, semantic_weight: float) -> EvaluationResult | None:
    labels_path = REPO_ROOT / "docs" / "validation_labels.json"
    if not labels_path.exists():
        return None
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    jobs = [j for j in labels.get("jobs", []) if j.get("relevant_candidates")]
    if not jobs:
        return None

    profiles = list(_get_validation_profiles())

    per_job_metrics = []
    for job in jobs:
        relevant = set(job["relevant_candidates"])
        jd_text = (REPO_ROOT / job["jd_file"]).read_text(encoding="utf-8")
        jd = parse_job_description(job["title"], jd_text)
        ranked = rank_candidates(profiles, jd, keyword_weight=keyword_weight, semantic_weight=semantic_weight)
        ranked_ids = [r.candidate_filename for r in ranked]
        per_job_metrics.append(evaluate_single_job(ranked_ids, relevant))

    return aggregate_metrics(per_job_metrics)


def _gather_feedback_examples(category: str) -> list[FeedbackExample]:
    """Same latest-decision-per-match-result logic as _gather_feedback_stats,
    but returns one row per feedback example (with candidate_id) instead of
    pre-aggregated stats -- what the Section 4 trained-model upgrade needs
    to fit on, and to split by candidate rather than by row (Section 4.2)."""
    matches = (
        MatchResultModel.query
        .join(JobDescriptionModel, MatchResultModel.jd_id == JobDescriptionModel.id)
        .filter(JobDescriptionModel.category == category)
        .all()
    )
    match_by_id = {m.id: m for m in matches}
    if not match_by_id:
        return []

    latest_decision: dict[int, str] = {}
    feedback_rows = (
        RecruiterFeedback.query
        .filter(RecruiterFeedback.match_result_id.in_(match_by_id.keys()))
        .order_by(RecruiterFeedback.created_at)
        .all()
    )
    for f in feedback_rows:
        latest_decision[f.match_result_id] = f.decision

    examples = []
    for match_id, decision in latest_decision.items():
        if decision not in ("hired", "rejected"):
            continue
        m = match_by_id[match_id]
        examples.append(FeedbackExample(
            candidate_id=m.candidate_id, keyword_score=m.keyword_score,
            semantic_score=m.semantic_score, decision=decision,
        ))
    return examples


def run_reweighting_for_category(category: str) -> dict:
    """Section 5.4/12.3: proposes new keyword/semantic weights for a
    category from recruiter feedback (the default, heuristic path), and --
    only if a labeled validation set exists -- applies them exclusively
    when they don't regress Precision@5/NDCG@10 beyond tolerance. Every
    attempt is logged to ScoringWeights (promoted, rejected, or never-
    attempted-without-a-validation-set) for a full audit trail; ranking
    behavior for this category never changes silently."""
    current_kw, current_sem = get_active_weights(category)
    hired_stats, rejected_stats = _gather_feedback_stats(category)

    try:
        proposal = propose_weights(category, hired_stats, rejected_stats, current_kw, current_sem)
    except InsufficientFeedbackError as e:
        return {"status": "insufficient_feedback", "message": str(e), "category": category}

    return _apply_reweight_proposal(category, current_kw, current_sem, proposal)


def run_trained_reweighting_for_category(category: str) -> dict:
    """ML Training Master Plan Section 4: the optional upgrade from a hand-
    picked nudge to a genuinely trained 2-feature logistic regression.
    Goes through the exact same _apply_reweight_proposal (and therefore the
    exact same Section 12.3 regression-gated promotion) as the heuristic
    path -- fitting a model doesn't exempt it from that safety net."""
    current_kw, current_sem = get_active_weights(category)
    examples = _gather_feedback_examples(category)

    try:
        proposal = propose_weights_trained(category, examples, current_kw, current_sem)
    except InsufficientTrainingDataError as e:
        return {"status": "insufficient_feedback", "message": str(e), "category": category}

    return _apply_reweight_proposal(category, current_kw, current_sem, proposal)


def _apply_reweight_proposal(category: str, current_kw: float, current_sem: float, proposal) -> dict:
    no_change = (
        proposal.proposed_keyword_weight == current_kw
        and proposal.proposed_semantic_weight == current_sem
    )
    if no_change:
        row = ScoringWeights(
            category=category, keyword_weight=current_kw, semantic_weight=current_sem,
            status="no_change", reason=proposal.reason,
            hired_count=proposal.hired_count, rejected_count=proposal.rejected_count,
        )
        db.session.add(row)
        db.session.commit()
        return {"status": "no_change", "message": proposal.reason, "weights": row.to_dict()}

    baseline_metrics = _evaluate_weights_on_validation_set(current_kw, current_sem)
    if baseline_metrics is None:
        reason = (
            proposal.reason + " NOT applied: no labeled validation set exists to verify this doesn't "
            "regress ranking quality (Section 12.1). Copy docs/validation_labels_template.json to "
            "validation_labels.json, label it, and re-run to enable safe auto-promotion."
        )
        row = ScoringWeights(
            category=category,
            keyword_weight=proposal.proposed_keyword_weight,
            semantic_weight=proposal.proposed_semantic_weight,
            status="proposed_no_validation_set",
            reason=reason,
            hired_count=proposal.hired_count, rejected_count=proposal.rejected_count,
        )
        db.session.add(row)
        db.session.commit()
        return {"status": "proposed_no_validation_set", "message": reason, "weights": row.to_dict()}

    new_metrics = _evaluate_weights_on_validation_set(
        proposal.proposed_keyword_weight, proposal.proposed_semantic_weight
    )
    promote = should_promote_weights(new_metrics, baseline_metrics)

    if promote:
        ScoringWeights.query.filter_by(category=category, status="active").update({"status": "superseded"})
        row = ScoringWeights(
            category=category,
            keyword_weight=proposal.proposed_keyword_weight,
            semantic_weight=proposal.proposed_semantic_weight,
            status="active",
            reason=proposal.reason,
            precision_at_5=new_metrics["precision_at_5"], ndcg_at_10=new_metrics["ndcg_at_10"],
            hired_count=proposal.hired_count, rejected_count=proposal.rejected_count,
        )
        db.session.add(row)
        db.session.commit()
        return {
            "status": "promoted", "message": proposal.reason, "weights": row.to_dict(),
            "baseline_metrics": baseline_metrics, "new_metrics": new_metrics,
        }

    reason = (
        proposal.reason + f" REJECTED by the Section 12.3 regression check: validation metrics "
        f"regressed beyond tolerance (baseline={baseline_metrics}, new={new_metrics}). "
        f"Previous weights remain active for this category."
    )
    row = ScoringWeights(
        category=category,
        keyword_weight=proposal.proposed_keyword_weight,
        semantic_weight=proposal.proposed_semantic_weight,
        status="rejected_regression",
        reason=reason,
        precision_at_5=new_metrics["precision_at_5"], ndcg_at_10=new_metrics["ndcg_at_10"],
        hired_count=proposal.hired_count, rejected_count=proposal.rejected_count,
    )
    db.session.add(row)
    db.session.commit()
    return {
        "status": "rejected_regression", "message": reason, "weights": row.to_dict(),
        "baseline_metrics": baseline_metrics, "new_metrics": new_metrics,
    }
