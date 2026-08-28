"""
Model evaluation runner (project documentation Section 12.1-12.2)
-----------------------------------------------------------------------
Computes Precision@5, Precision@10, NDCG@10, and MRR against a validation
ground-truth dataset, and reports them against target metrics.

This script expects ground-truth relevance labels in docs/validation_labels.json
(use docs/validation_labels_template.json as reference). Run this once
domain validation labels are populated.

Usage (from repo root):
    python backend/scripts/evaluate_ranking.py
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
from nlp_pipeline.evaluation import evaluate_single_job, aggregate_metrics, METRIC_TARGETS

LABELS_PATH = REPO_ROOT / "docs" / "validation_labels.json"
TEMPLATE_PATH = REPO_ROOT / "docs" / "validation_labels_template.json"
DATASET_DIR = REPO_ROOT / "datasets" / "resumes"


def main():
    if not LABELS_PATH.exists():
        print(f"No labeled validation set found at {LABELS_PATH}.")
        print(f"Copy {TEMPLATE_PATH.name} to validation_labels.json and fill in "
              f"'relevant_candidates' per JD (Section 12.1) before running this.")
        return

    labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    jobs = labels.get("jobs", [])
    if not any(j.get("relevant_candidates") for j in jobs):
        print("validation_labels.json exists but no job has any labeled relevant_candidates yet. "
              "Nothing to evaluate.")
        return

    print("Parsing full resume dataset...")
    files = sorted(DATASET_DIR.glob("*.docx"))
    profiles = []
    for f in files:
        try:
            profiles.append(extract_profile(parse_resume(f)))
        except ResumeParseError as e:
            print(f"  skipping {f.name}: {e}")
    print(f"Parsed {len(profiles)}/{len(files)} resumes.\n")

    per_job_metrics = []
    for job in jobs:
        relevant = set(job.get("relevant_candidates") or [])
        if not relevant:
            print(f"Skipping '{job['title']}' -- no labels yet.")
            continue

        jd_text = (REPO_ROOT / job["jd_file"]).read_text(encoding="utf-8")
        jd = parse_job_description(job["title"], jd_text)
        ranked = rank_candidates(profiles, jd)
        ranked_ids = [r.candidate_filename for r in ranked]

        metrics = evaluate_single_job(ranked_ids, relevant)
        per_job_metrics.append(metrics)
        print(f"{job['title']}: P@5={metrics['precision_at_5']:.2f} "
              f"P@10={metrics['precision_at_10']:.2f} "
              f"NDCG@10={metrics['ndcg_at_10']:.2f} "
              f"RR={metrics['reciprocal_rank']:.2f}")

    if not per_job_metrics:
        return

    agg = aggregate_metrics(per_job_metrics)
    print(f"\n--- Aggregate over {len(per_job_metrics)} labeled JD(s) (validation-set size: "
          f"{sum(len(j.get('relevant_candidates') or []) for j in jobs)} labeled resumes) ---")
    for key, target in METRIC_TARGETS.items():
        value = agg[key]
        status = "PASS" if value >= target else "BELOW TARGET"
        print(f"  {key:<16} {value:.3f}  (target >= {target})  [{status}]")


if __name__ == "__main__":
    main()
