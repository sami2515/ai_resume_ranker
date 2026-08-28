"""
Named Entity Recognition & Skill-Set Extraction
(project documentation Section 5.1, Steps 3-4)
-------------------------------------------------
Combines spaCy's statistical NER (for names, organizations, dates) with the
custom skills gazetteer (skills_gazetteer.py) for reliable, domain-specific
skill extraction -- since generic NER models routinely miss tech skill
tokens that never appeared often in their general-purpose training data.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from functools import lru_cache

import spacy

from .skills_gazetteer import ALIAS_LOOKUP, ALL_CANONICAL_SKILLS
from .parser import ParsedResume

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Supports: US (123-456-7890), Pakistan (+92-300-1234567, 03001234567),
# UAE (+971-50-1234567), UK (+44 ...), and general international (+XX ...).
PHONE_RE = re.compile(
    r"""
    (?:
        \+\d{1,3}[\s.\-]?\d{2,4}[\s.\-]?\d{4,5}[\s.\-]?\d{4,6}  # international: +92 300 1234567, +44 7911 123456
    |
        0\d{2,3}[\s.\-]?\d{3,4}[\s.\-]?\d{4,5}    # Pakistani/local: 0300-1234567, 021-12345678
    |
        \(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}      # US: (123) 456-7890
    )
    """,
    re.VERBOSE,
)

YEAR_RANGE_RE = re.compile(
    r"(?P<start>(19|20)\d{2})\s*(?:-|\u2013|\u2014|to)\s*"
    r"(?P<end>(19|20)\d{2}|present|current|till\s+date|to\s+date|till\s+today|ongoing|now)",
    re.IGNORECASE,
)


@dataclass
class CandidateProfile:
    filename: str
    full_name: str | None
    email: str | None
    phone: str | None
    skills: list[str] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    experience_years: float = 0.0
    raw_text: str = ""


@lru_cache(maxsize=1)
def _load_spacy_model():
    """
    Loads the largest available spaCy English model. Prefers `en_core_web_md`
    (has real static word vectors, needed for semantic similarity fallback --
    see matching_engine.py) and falls back to `en_core_web_sm` if `md` isn't
    installed, degrading semantic matching to keyword-only in that case.
    """
    for model_name in ("en_core_web_md", "en_core_web_sm"):
        try:
            return spacy.load(model_name), model_name
        except OSError:
            continue
    try:
        spacy.cli.download("en_core_web_sm")
        return spacy.load("en_core_web_sm"), "en_core_web_sm"
    except Exception:
        pass
    raise RuntimeError(
        "No spaCy English model is installed. Run:\n"
        "  python -m spacy download en_core_web_sm\n"
        "or install en_core_web_md for better semantic matching."
    )


def get_nlp():
    nlp, _ = _load_spacy_model()
    return nlp


def active_model_name() -> str:
    _, name = _load_spacy_model()
    return name


def extract_contact_info(text: str) -> tuple[str | None, str | None]:
    email_match = EMAIL_RE.search(text)
    phone_match = PHONE_RE.search(text)
    return (email_match.group(0) if email_match else None,
            phone_match.group(0) if phone_match else None)


NAME_STOPLIST_PHRASES = {
    "professional summary", "summary", "objective", "career objective", "profile",
    "professional profile", "executive summary", "personal summary", "summary of qualifications",
    "core competencies", "technical skills", "skills summary", "career summary",
}

CANDIDATE_ID_RE = re.compile(r"\bcandidate[\s_-]*\d+\b", re.IGNORECASE)


def _looks_like_a_name(line: str) -> bool:
    """Heuristic checks for whether a short line is plausibly a person's name."""
    clean = line.strip().strip(":,")
    if not clean or any(ch.isdigit() for ch in clean) or "@" in clean:
        return False
    if clean.lower() in NAME_STOPLIST_PHRASES:
        return False
    words = clean.split()
    if not (1 <= len(words) <= 5):
        return False
    # Reject all-caps section-header-style lines (e.g. "PROFESSIONAL SUMMARY")
    # but allow initials/short all-caps suffixes like "PMP" as a trailing token.
    alpha_words = [w for w in words if w.isalpha()]
    if not alpha_words:
        return False
    if all(w.isupper() and len(w) > 3 for w in alpha_words):
        return False
    return True


def extract_name(resume: ParsedResume, doc) -> str | None:
    """
    Name-extraction strategy, in priority order (tuned against the organizer
    dataset, which is anonymized: most files identify the candidate as
    'CandidateNNN' rather than a real name):

      1. An explicit "CandidateNNN" token anywhere in the first few lines
         or in the filename -- the dataset's own anonymized identifier and
         the most reliable signal available.
      2. The first non-empty line, IF it passes `_looks_like_a_name` (short,
         no digits/@, not a known section-header phrase like "Professional
         Summary", not an ALL-CAPS heading).
      3. A spaCy PERSON entity found within the first ~400 characters of
         the document (restricted to the top of the resume to avoid
         picking up tool/product names mentioned later, e.g. "Rational
         Rose", which spaCy's general-purpose NER sometimes mis-tags as
         PERSON).
      4. Fallback: a cleaned-up version of the filename.
    """
    head = "\n".join(resume.raw_text.strip().splitlines()[:4])
    id_match = CANDIDATE_ID_RE.search(head) or CANDIDATE_ID_RE.search(resume.filename)
    if id_match:
        return re.sub(r"[\s_-]+", "", id_match.group(0)).replace("candidate", "Candidate")

    first_line = resume.raw_text.strip().splitlines()[0].strip() if resume.raw_text.strip() else ""
    if _looks_like_a_name(first_line):
        return first_line

    top_doc = doc[: min(len(doc), 120)]  # restrict to top of document, roughly first ~400 chars
    for ent in top_doc.ents:
        if ent.label_ == "PERSON" and _looks_like_a_name(ent.text):
            return ent.text

    # Fallback: derive a readable label from the filename itself.
    stem = re.sub(r"[_\-]+", " ", resume.filename.rsplit(".", 1)[0]).strip()
    return stem or None


def extract_skills(text: str, sections: dict | None = None) -> list[str]:
    """
    Section-aware gazetteer-based skill extraction with degree-context guard:
    - Excludes 'education' section text to prevent degree titles (e.g. 'Bachelor of
      Visual Communication') from extracting false-positive skills ('Communication').
    - Applies a regex guard checking preceding words in a context window.
    """
    if sections and isinstance(sections, dict) and "education" in sections:
        # Build non-education text by combining all sections except education
        non_edu_parts = [v for k, v in sections.items() if k != "education"]
        scan_text = "\n".join(non_edu_parts) if non_edu_parts else text
    else:
        scan_text = text

    lowered = scan_text.lower()
    found = set()

    for alias, canonical in ALIAS_LOOKUP.items():
        pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        for match in re.finditer(pattern, lowered):
            start_pos = match.start()
            context_before = lowered[max(0, start_pos - 60):start_pos]
            # Check if keyword is preceded by degree indicators (e.g., 'Bachelor of', 'B.A. in', 'Major in')
            if re.search(r"\b(?:bachelor|b\.?a|b\.?s|b\.?sc|master|m\.?a|m\.?s|m\.?sc|degree|diploma|major|minor)\b(?:\s+(?:of|in|with))?\s*$", context_before):
                continue  # Discard match inside degree title context
            found.add(canonical)
            break

    return sorted(found)


def extract_education(sections: dict) -> list[str]:
    edu_text = sections.get("education", "")
    if not edu_text:
        return []
    # Split on lines / bullets, keep short entries that look like degree lines.
    lines = [ln.strip("\u2022- \t") for ln in edu_text.splitlines() if ln.strip()]
    return [ln for ln in lines if len(ln) < 120]


def extract_certifications(sections: dict) -> list[str]:
    cert_text = sections.get("certifications", "")
    if not cert_text:
        return []
    lines = [ln.strip("\u2022- \t") for ln in cert_text.splitlines() if ln.strip()]
    return [ln for ln in lines if len(ln) < 120]


def estimate_experience_years(text: str) -> float:
    """
    Sums the widest year ranges found in the resume as a rough proxy for
    total experience. This is a heuristic, not a guarantee -- flagged as a
    known limitation in the Technical Debt & Risk Register.
    """
    ranges = []
    for m in YEAR_RANGE_RE.finditer(text):
        start = int(m.group("start"))
        end_raw = m.group("end").lower()
        end = 2026 if end_raw in ("present", "current", "till date") else int(end_raw)
        if 1980 <= start <= end <= 2100:
            ranges.append((start, end))
    if not ranges:
        return 0.0
    earliest = min(r[0] for r in ranges)
    latest = max(r[1] for r in ranges)
    return float(max(0, latest - earliest))


def extract_profile(resume: ParsedResume) -> CandidateProfile:
    nlp = get_nlp()
    doc = nlp(resume.raw_text[:100_000])  # guard against pathologically large files

    email, phone = extract_contact_info(resume.raw_text)
    name = extract_name(resume, doc)
    skills = extract_skills(resume.raw_text, sections=resume.sections)
    education = extract_education(resume.sections)
    certifications = extract_certifications(resume.sections)
    exp_years = estimate_experience_years(resume.raw_text)

    return CandidateProfile(
        filename=resume.filename,
        full_name=name,
        email=email,
        phone=phone,
        skills=skills,
        education=education,
        certifications=certifications,
        experience_years=exp_years,
        raw_text=resume.raw_text,
    )
