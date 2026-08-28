"""
Fairness & bias testing (project documentation Section 12.5)
----------------------------------------------------------------------
Methodology: take a real resume, produce an otherwise-identical copy with
only the candidate's name changed to one commonly associated with a
different gender or racial/ethnic group, score both against the same JD,
and check the composite score shift stays within a small tolerance.

This is the standard "correspondence/audit study" design used in hiring-
bias research -- most famously Bertrand & Mullainathan, "Are Emily and
Greg More Employable Than Lakisha and Jamal? A Field Experiment on Labor
Market Discrimination" (American Economic Review, 2004), which sent
otherwise-identical resumes under names independently validated (via
Massachusetts birth records and perception surveys) as strongly
associated with a given race, and measured the callback-rate gap. The
name pairs below are drawn from that paper's validated lists, which is
why they're used here rather than an arbitrary internal guess at
name/demographic association -- the whole point of the design is that the
name-to-group association is externally validated, not assumed.

Important framing (put this in the report, not just here): a score-shift
check like this does NOT prove the system is unbiased. It only tests one
specific, cheap-to-audit failure mode -- literal name leakage into a score
that should depend on qualifications, not identity. A model can pass this
check and still encode bias in subtler ways (e.g., via which skills or
phrasing correlate with which schools/neighborhoods). Report it as exactly
what it is: one honest, bounded check, not a certification.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, replace

from .extractor import CandidateProfile
from .matching_engine import JobDescription, MatchResult, score_candidate

# (name_a, name_b, category) -- name_a/name_b are deliberately symmetric
# swaps, not "default" vs "variant"; which one replaces the original in a
# given resume is arbitrary and doesn't imply either is the baseline.
#
# Gender pairs: matched first names, unrelated to race/ethnicity, isolating
# gender as the single changed variable.
#
# Race/ethnicity pairs: first + last name combinations independently
# validated as strongly White- or Black-associated by Bertrand &
# Mullainathan (2004), Table II/III (perceived race match rate >90% for
# each name in their survey). Included here to test the same failure mode
# their field experiment measured in human recruiters, applied to this
# system's automated scoring instead.
NAME_PAIRS: list[tuple[str, str, str]] = [
    # -- gender --
    ("James Whitfield", "Jennifer Whitfield", "gender"),
    ("Michael Donovan", "Michelle Donovan", "gender"),
    ("Robert Chen", "Roberta Chen", "gender"),
    ("David Okafor", "Diana Okafor", "gender"),
    # -- race/ethnicity (Bertrand & Mullainathan 2004 validated name lists) --
    ("Brad Baker", "Jamal Baker", "race_ethnicity"),
    ("Emily Walsh", "Lakisha Walsh", "race_ethnicity"),
    ("Greg Sullivan", "Darnell Sullivan", "race_ethnicity"),
    ("Allison Meyer", "Ebony Meyer", "race_ethnicity"),
    ("Todd Pearson", "Tremayne Pearson", "race_ethnicity"),
    ("Kristen Schaefer", "Latoya Schaefer", "race_ethnicity"),
]

TOLERANCE_POINTS = 2.0  # Section 12.5's suggested tolerance


@dataclass
class FairnessPairResult:
    resume_filename: str
    category: str
    name_a: str
    name_b: str
    score_a: float
    score_b: float

    @property
    def delta(self) -> float:
        return round(abs(self.score_a - self.score_b), 2)

    @property
    def passed(self) -> bool:
        return self.delta <= TOLERANCE_POINTS


def swap_name_in_text(raw_text: str, original_name: str, new_name: str) -> str:
    """Replaces occurrences of the detected name with the swap name. Falls
    back to prepending the new name as a header line if the detected name
    can't be found verbatim (e.g. it was a 'CandidateNNN' dataset id, not
    an actual name) -- the resume still needs *a* name in the text for the
    swap to mean anything."""
    if original_name and original_name in raw_text:
        return raw_text.replace(original_name, new_name)
    return f"{new_name}\n{raw_text}"


def make_fairness_variant(profile: CandidateProfile, new_name: str) -> CandidateProfile:
    """A copy of `profile` with only the name changed -- skills, education,
    experience, certifications all stay identical, since those are what a
    fair scoring system should actually respond to."""
    original_name = profile.full_name or ""
    swapped_text = swap_name_in_text(profile.raw_text, original_name, new_name)
    return replace(profile, full_name=new_name, raw_text=swapped_text)


def run_fairness_pair(profile: CandidateProfile, jd: JobDescription, name_a: str, name_b: str, category: str) -> FairnessPairResult:
    variant_a = make_fairness_variant(profile, name_a)
    variant_b = make_fairness_variant(profile, name_b)

    result_a = score_candidate(variant_a, jd)
    result_b = score_candidate(variant_b, jd)

    return FairnessPairResult(
        resume_filename=profile.filename,
        category=category,
        name_a=name_a,
        name_b=name_b,
        score_a=result_a.composite_score,
        score_b=result_b.composite_score,
    )


def run_fairness_suite(
    profiles: list[CandidateProfile],
    jd: JobDescription,
    name_pairs: list[tuple[str, str, str]] | None = None,
) -> list[FairnessPairResult]:
    """Runs one name-pair per profile, cycling through name_pairs so a run
    with e.g. 10 profiles and 10 pairs covers each pair once."""
    pairs = name_pairs or NAME_PAIRS
    results = []
    for i, profile in enumerate(profiles):
        name_a, name_b, category = pairs[i % len(pairs)]
        results.append(run_fairness_pair(profile, jd, name_a, name_b, category))
    return results
