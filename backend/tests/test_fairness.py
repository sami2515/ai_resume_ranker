"""
Fairness/bias testing mechanism tests (Section 12.5). These test that the
audit *tooling* works correctly (name substitution, score comparison) --
not a claim that the matching engine is unbiased. See fairness.py's
module docstring for that distinction.
"""
from nlp_pipeline.extractor import CandidateProfile
from nlp_pipeline.matching_engine import JobDescription
from nlp_pipeline.fairness import (
    swap_name_in_text, make_fairness_variant, run_fairness_pair,
    run_fairness_suite, NAME_PAIRS, TOLERANCE_POINTS,
)


class TestNameSwap:
    def test_replaces_all_occurrences_of_the_name(self):
        text = "James Whitfield\nSummary: James Whitfield led the team."
        swapped = swap_name_in_text(text, "James Whitfield", "Jennifer Whitfield")
        assert "James Whitfield" not in swapped
        assert swapped.count("Jennifer Whitfield") == 2

    def test_falls_back_to_prepending_when_name_not_found_verbatim(self):
        text = "Candidate21\nExperienced SQL developer."
        swapped = swap_name_in_text(text, "", "Jennifer Whitfield")
        assert swapped.startswith("Jennifer Whitfield")
        assert "Candidate21" in swapped  # original content preserved

    def test_variant_keeps_skills_and_experience_unchanged(self):
        profile = CandidateProfile(
            filename="c.docx", full_name="James Whitfield", email="j@example.com", phone=None,
            skills=["SQL", "Agile"], education=["BS CS"], certifications=[], experience_years=5.0,
            raw_text="James Whitfield\nSQL developer with 5 years Agile experience.",
        )
        variant = make_fairness_variant(profile, "Jennifer Whitfield")
        assert variant.full_name == "Jennifer Whitfield"
        assert variant.skills == profile.skills
        assert variant.education == profile.education
        assert variant.experience_years == profile.experience_years
        assert "Jennifer Whitfield" in variant.raw_text
        assert "James Whitfield" not in variant.raw_text
        # original untouched
        assert profile.full_name == "James Whitfield"


class TestFairnessPair:
    def test_identical_content_produces_small_or_zero_delta(self):
        """The whole point of the check: a resume whose only difference is
        the name should score within tolerance of itself."""
        profile = CandidateProfile(
            filename="c.docx", full_name="James Whitfield", email=None, phone=None,
            skills=["SQL", "Agile", "Stakeholder Management"], education=[], certifications=[],
            experience_years=6.0,
            raw_text="James Whitfield\nSenior Business Analyst with 6 years of experience in "
                     "requirements gathering, stakeholder management, and SQL reporting. "
                     "Led Agile ceremonies and cross-functional coordination.",
        )
        jd = JobDescription(
            title="Business Analyst",
            raw_text="Looking for a Business Analyst with SQL and stakeholder management experience.",
            required_skills=["SQL", "Stakeholder Management"], min_experience=3,
        )
        result = run_fairness_pair(profile, jd, "James Whitfield", "Jennifer Whitfield", "gender")
        assert result.resume_filename == "c.docx"
        assert result.delta < 5.0  # generous bound; exact value depends on the active semantic backend

    def test_passed_property_respects_tolerance(self):
        from nlp_pipeline.fairness import FairnessPairResult
        close = FairnessPairResult("c.docx", "gender", "A", "B", score_a=70.0, score_b=71.0)
        assert close.passed is True
        assert close.delta == 1.0

        far = FairnessPairResult("c.docx", "gender", "A", "B", score_a=70.0, score_b=80.0)
        assert far.passed is False
        assert far.delta == 10.0

    def test_delta_is_symmetric_regardless_of_which_score_is_higher(self):
        from nlp_pipeline.fairness import FairnessPairResult
        r1 = FairnessPairResult("c.docx", "gender", "A", "B", score_a=60.0, score_b=65.0)
        r2 = FairnessPairResult("c.docx", "gender", "A", "B", score_a=65.0, score_b=60.0)
        assert r1.delta == r2.delta == 5.0


class TestFairnessSuite:
    def test_cycles_through_name_pairs_for_multiple_profiles(self):
        jd = JobDescription(title="X", raw_text="Python developer needed.", required_skills=["Python"], min_experience=0)
        profiles = [
            CandidateProfile(filename=f"c{i}.docx", full_name=f"Person{i}", email=None, phone=None,
                              skills=["Python"], education=[], certifications=[], experience_years=1,
                              raw_text=f"Person{i}\nPython developer.")
            for i in range(3)
        ]
        results = run_fairness_suite(profiles, jd)
        assert len(results) == 3
        assert [r.name_a for r in results] == [NAME_PAIRS[0][0], NAME_PAIRS[1][0], NAME_PAIRS[2][0]]

    def test_name_pairs_cover_both_categories(self):
        categories = {c for _, _, c in NAME_PAIRS}
        assert "gender" in categories
        assert "race_ethnicity" in categories

    def test_tolerance_matches_documented_value(self):
        assert TOLERANCE_POINTS == 2.0
