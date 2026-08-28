"""
Job Description Parsing (project documentation Section 5.1, Step 5)
------------------------------------------------------------------------
Runs the identical skill-extraction pipeline used on resumes against the
JD text, so both sides of the comparison are processed consistently
(same gazetteer, same normalization) -- this is what the design doc calls
out explicitly in Section 5.1 as a correctness requirement, not just an
implementation convenience: if resumes and JDs were parsed differently,
skill names could fail to match purely due to inconsistent normalization.
"""

from __future__ import annotations
import re

from .extractor import extract_skills
from .matching_engine import JobDescription

MIN_EXPERIENCE_RE = re.compile(r"(\d+)\s*\+?\s*(?:years|yrs)", re.IGNORECASE)


def parse_job_description(title: str, raw_text: str) -> JobDescription:
    skills = extract_skills(raw_text)
    exp_match = MIN_EXPERIENCE_RE.search(raw_text)
    min_experience = float(exp_match.group(1)) if exp_match else 0.0
    return JobDescription(
        title=title,
        raw_text=raw_text,
        required_skills=skills,
        min_experience=min_experience,
    )
