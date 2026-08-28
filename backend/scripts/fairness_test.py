"""
Fairness/bias audit runner (project documentation Section 12.5)
----------------------------------------------------------------------
Produces the "Fairness Check" appendix data: for a sample of real resumes,
scores a name-swapped variant (gender or race/ethnicity association
changed, everything else identical) against the same JD, and reports the
composite-score delta and pass/fail against the +/-2 point tolerance.

See nlp_pipeline/fairness.py's module docstring for the methodology
source (Bertrand & Mullainathan 2004) and, importantly, what this check
does and doesn't prove -- read that before quoting a "PASS" as "the
system is unbiased" in the report.

Usage (from repo root):
    python backend/scripts/fairness_test.py [--sample-size 10] [--jd business_analyst]
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from nlp_pipeline import parse_resume, extract_profile
from nlp_pipeline.parser import ResumeParseError
from nlp_pipeline.jd_parser import parse_job_description
from nlp_pipeline.fairness import run_fairness_suite, NAME_PAIRS, TOLERANCE_POINTS

DATASET_DIR = REPO_ROOT / "datasets" / "resumes"
JD_DIR = REPO_ROOT / "datasets" / "test_jds"
REPORT_PATH = REPO_ROOT / "docs" / "fairness_check_report.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--jd", default="business_analyst",
                         help="basename (without .txt) of a file in datasets/test_jds/")
    args = parser.parse_args()

    jd_path = JD_DIR / f"{args.jd}.txt"
    if not jd_path.exists():
        print(f"No JD file at {jd_path}")
        sys.exit(1)
    jd_text = jd_path.read_text(encoding="utf-8")
    jd = parse_job_description(args.jd.replace("_", " ").title(), jd_text)

    files = sorted(DATASET_DIR.glob("*.docx"))[:args.sample_size]
    if len(files) < args.sample_size:
        print(f"WARNING: only {len(files)} resumes found, requested {args.sample_size}.")

    profiles = []
    for f in files:
        try:
            profiles.append(extract_profile(parse_resume(f)))
        except ResumeParseError as e:
            print(f"  skipping {f.name}: {e}")

    print(f"Fairness check: {len(profiles)} resumes x name-swap pairs, JD = '{jd.title}', "
          f"tolerance = +/-{TOLERANCE_POINTS} points\n")

    results = run_fairness_suite(profiles, jd)

    print(f"{'Resume':<35}{'Category':<15}{'Name A':<20}{'Name B':<20}{'Score A':<9}{'Score B':<9}{'Delta':<8}{'Result'}")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"{r.resume_filename[:33]:<35}{r.category:<15}{r.name_a[:18]:<20}{r.name_b[:18]:<20}"
              f"{r.score_a:<9}{r.score_b:<9}{r.delta:<8}{status}")

    passed = sum(1 for r in results if r.passed)
    print(f"\n{passed}/{len(results)} pairs within tolerance.")
    if passed < len(results):
        print("Failing pairs (report these honestly, don't drop them from the appendix):")
        for r in results:
            if not r.passed:
                print(f"  {r.resume_filename}: {r.name_a} ({r.score_a}) vs {r.name_b} ({r.score_b}), "
                      f"delta={r.delta} > {TOLERANCE_POINTS}")

    report = {
        "jd_title": jd.title,
        "tolerance_points": TOLERANCE_POINTS,
        "sample_size": len(results),
        "passed": passed,
        "pairs": [
            {
                "resume_filename": r.resume_filename, "category": r.category,
                "name_a": r.name_a, "name_b": r.name_b,
                "score_a": r.score_a, "score_b": r.score_b,
                "delta": r.delta, "passed": r.passed,
            }
            for r in results
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nFull report written to {REPORT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
