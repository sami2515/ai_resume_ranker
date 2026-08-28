"""Quick end-to-end sanity test: parse a batch of real resumes from the
organizer dataset, rank them against a sample JD, and print the result.
Run from repo root: python backend/scripts/quick_test.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # backend/

from nlp_pipeline import parse_resume, extract_profile, rank_candidates, semantic_backend_name
from nlp_pipeline.jd_parser import parse_job_description
from nlp_pipeline.parser import ResumeParseError

DATASET_DIR = Path(__file__).resolve().parents[2] / "datasets" / "resumes"

JD_TITLE = "Senior Business Analyst"
JD_TEXT = """
We are looking for a Senior Business Analyst with 5+ years of experience.
Responsibilities include requirements gathering, stakeholder management,
business process modeling, and use case development. Must have strong
SQL skills and experience working in Agile/Scrum environments. PMP or
CBAP certification is a plus.
"""

def main():
    print(f"Semantic backend in use: {semantic_backend_name()}\n")

    files = sorted(DATASET_DIR.glob("*.docx"))[:40]  # sample for a quick test
    print(f"Parsing {len(files)} resumes from the organizer dataset...")

    profiles = []
    errors = []
    t0 = time.time()
    for f in files:
        try:
            resume = parse_resume(f)
            profile = extract_profile(resume)
            profiles.append(profile)
        except ResumeParseError as e:
            errors.append((f.name, str(e)))
    elapsed = time.time() - t0
    print(f"Parsed {len(profiles)} resumes successfully in {elapsed:.1f}s "
          f"({elapsed/max(1,len(files)):.2f}s/resume). {len(errors)} errors.")
    for name, err in errors:
        print(f"  ERROR parsing {name}: {err}")

    jd = parse_job_description(JD_TITLE, JD_TEXT)
    print(f"\nJD: {JD_TITLE}")
    print(f"Extracted required skills: {jd.required_skills}")
    print(f"Min experience: {jd.min_experience}\n")

    t0 = time.time()
    results = rank_candidates(profiles, jd)
    rank_time = time.time() - t0
    print(f"Ranked {len(results)} candidates in {rank_time:.2f}s\n")

    print(f"{'Rank':<5}{'Candidate':<25}{'Composite':<11}{'Keyword':<9}{'Semantic':<9}{'Confidence'}")
    for i, r in enumerate(results[:10], 1):
        name = (r.candidate_name or r.candidate_filename)[:23]
        print(f"{i:<5}{name:<25}{r.composite_score:<11}{r.keyword_score:<9}{r.semantic_score:<9}{r.confidence}")

    top = results[0]
    print(f"\n--- Explainability sample: {top.candidate_name or top.candidate_filename} ---")
    print(f"Matched skills: {top.matched_skills}")
    print(f"Missing skills: {top.missing_skills}")
    print(f"Experience (est. years): {top.experience_years}")


if __name__ == "__main__":
    main()
