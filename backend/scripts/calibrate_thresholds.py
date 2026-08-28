"""
Confidence-band threshold calibration (ML Training Master Plan Section 3)
---------------------------------------------------------------------------
SBERT stays pretrained and frozen (Section 3's whole point: 231 resumes is
far too little to fine-tune a sentence embedding model without overfitting
to this exact dataset's vocabulary). The legitimate, lower-risk "training"
left to do is calibration: the composite-score cutoffs that currently
split candidates into High/Moderate/Weak confidence bands (80/55, fixed in
nlp_pipeline/matching_engine.py) were set by judgment, not measured.

Methodology: for each candidate threshold t in the sweep, treat every
candidate with composite_score >= t as "predicted relevant" and score that
prediction against docs/validation_labels.json's real relevant/not-relevant
judgments -- precision, recall, and F1 of that cutoff, aggregated over
every labeled JD. This calibrates the SHORTLIST_THRESHOLD / band boundary
against real labeled data without touching the model itself.

This script does NOT modify matching_engine.py's live CONFIDENCE_BANDS --
it prints a table so the team can make a deliberate, evidence-backed choice
(and only then, if they choose to, edit the constant by hand).

Usage (from repo root):
    python backend/scripts/calibrate_thresholds.py
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from nlp_pipeline import parse_resume, extract_profile, rank_candidates
from nlp_pipeline.jd_parser import parse_job_description
from nlp_pipeline.parser import ResumeParseError

LABELS_PATH = REPO_ROOT / "docs" / "validation_labels.json"
TEMPLATE_PATH = REPO_ROOT / "docs" / "validation_labels_template.json"
DATASET_DIR = REPO_ROOT / "datasets" / "resumes"

THRESHOLD_SWEEP = list(range(30, 91, 5))


def main():
    if not LABELS_PATH.exists():
        print(f"No labeled validation set found at {LABELS_PATH}.")
        print(f"Copy {TEMPLATE_PATH.name} to validation_labels.json and fill in "
              f"'relevant_candidates' per JD (Section 12.1) before running this -- "
              f"calibration needs the same real labeled data ranking evaluation does.")
        return

    labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    jobs = [j for j in labels.get("jobs", []) if j.get("relevant_candidates")]
    if not jobs:
        print("validation_labels.json exists but no job has labeled relevant_candidates yet.")
        return

    print("Parsing full resume dataset...")
    files = sorted(DATASET_DIR.glob("*.docx"))
    profiles = []
    for f in files:
        try:
            profiles.append(extract_profile(parse_resume(f)))
        except ResumeParseError:
            continue
    print(f"Parsed {len(profiles)}/{len(files)} resumes.\n")

    n_labeled = sum(len(j["relevant_candidates"]) for j in jobs)
    print(f"Sweeping thresholds against {len(jobs)} labeled JD(s), {n_labeled} labeled resumes total.\n")

    scored_by_job = []
    for job in jobs:
        jd_text = (REPO_ROOT / job["jd_file"]).read_text(encoding="utf-8")
        jd = parse_job_description(job["title"], jd_text)
        ranked = rank_candidates(profiles, jd)
        scored_by_job.append((set(job["relevant_candidates"]), ranked))

    print(f"{'threshold':>10} {'precision':>10} {'recall':>10} {'f1':>10} {'n_flagged':>10}")
    best = None
    for t in THRESHOLD_SWEEP:
        tp = fp = fn = 0
        n_flagged = 0
        for relevant, ranked in scored_by_job:
            for r in ranked:
                predicted_relevant = r.composite_score >= t
                n_flagged += predicted_relevant
                is_relevant = r.candidate_filename in relevant
                if predicted_relevant and is_relevant:
                    tp += 1
                elif predicted_relevant and not is_relevant:
                    fp += 1
                elif not predicted_relevant and is_relevant:
                    fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        print(f"{t:>10} {precision:>10.3f} {recall:>10.3f} {f1:>10.3f} {n_flagged:>10}")
        if best is None or f1 > best[1]:
            best = (t, f1)

    print(f"\nHighest-F1 threshold in this sweep: {best[0]} (F1={best[1]:.3f}), "
          f"measured on {n_labeled} labeled resumes across {len(jobs)} JD(s).")
    print("This is a starting point for a deliberate choice, not an automatic override -- "
          "state the validation-set size next to this number wherever it's quoted (Section 5.3), "
          "and re-run once the validation set grows.")


if __name__ == "__main__":
    main()
