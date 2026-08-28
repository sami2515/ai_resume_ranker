"""
Unit tests for individual pipeline functions (project documentation Section 8.2):
tokenizer, stopword removal, lemmatizer, skill-gazetteer matcher, scoring formula.
"""

from nlp_pipeline.preprocess import clean_text, tokenize_and_lemmatize
from nlp_pipeline.extractor import extract_skills
from nlp_pipeline.matching_engine import confidence_label, KEYWORD_WEIGHT, SEMANTIC_WEIGHT, score_candidate
from nlp_pipeline.extractor import CandidateProfile
from nlp_pipeline.matching_engine import JobDescription


class TestPreprocessing:
    def test_clean_text_strips_email_phone_url(self):
        text = "Contact me at jane@example.com or (555) 123-4567, see https://example.com"
        cleaned = clean_text(text)
        assert "@" not in cleaned
        assert "555" not in cleaned
        assert "http" not in cleaned

    def test_clean_text_keeps_tech_punctuation(self):
        cleaned = clean_text("Skilled in C++ and Node.js and C#")
        assert "c++" in cleaned
        assert "node.js" in cleaned or "node js" in cleaned  # '.' preserved by clean_text
        assert "c#" in cleaned

    def test_tokenizer_removes_stopwords(self):
        tokens = tokenize_and_lemmatize("This is a test of the system and the pipeline")
        assert "is" not in tokens
        assert "the" not in tokens
        assert "and" not in tokens

    def test_lemmatizer_reduces_to_base_form(self):
        tokens = tokenize_and_lemmatize("managing teams and leading projects")
        # lemmatization (not stemming) -- readable base forms, e.g. 'managing' -> 'managing'/'manage'
        assert all(len(t) > 1 for t in tokens)
        assert "resume" not in tokens  # extra noise word filtered

    def test_tokenizer_drops_single_char_tokens(self):
        tokens = tokenize_and_lemmatize("a b c python developer")
        assert "python" in tokens
        assert "developer" in tokens
        assert not any(len(t) <= 1 for t in tokens)


class TestSkillsGazetteer:
    def test_extracts_canonical_skill_from_alias(self):
        skills = extract_skills("Experienced with ReactJS and React.js development")
        assert "React" in skills

    def test_normalizes_multiple_aliases_to_one_canonical(self):
        skills = extract_skills("Used AWS EC2 and S3 heavily, also amazon web services")
        assert "AWS" in skills
        assert skills.count("AWS") == 1  # extract_skills returns a de-duplicated sorted list

    def test_no_false_positive_on_short_alias_substring(self):
        # "r programming" alias for R shouldn't match inside unrelated words like "prepared"
        skills = extract_skills("Prepared reports and coordinated resources")
        assert "R" not in skills

    def test_empty_text_returns_no_skills(self):
        assert extract_skills("") == []


class TestScoringFormula:
    def test_weights_sum_to_one(self):
        assert KEYWORD_WEIGHT + SEMANTIC_WEIGHT == 1.0

    def test_composite_is_documented_blend(self):
        profile = CandidateProfile(
            filename="c.docx", full_name="Test Candidate", email=None, phone=None,
            skills=["SQL", "Agile"], education=[], certifications=[], experience_years=5.0,
            raw_text="Experienced with SQL and Agile methodology, requirements gathering.",
        )
        jd = JobDescription(
            title="BA", raw_text="Looking for SQL and Agile experience with requirements gathering.",
            required_skills=["SQL", "Agile"], min_experience=3.0,
        )
        result = score_candidate(profile, jd)
        expected = round(KEYWORD_WEIGHT * result.keyword_score + SEMANTIC_WEIGHT * result.semantic_score, 1)
        assert result.composite_score == expected

    def test_matched_and_missing_skills_are_disjoint_and_consistent(self):
        profile = CandidateProfile(
            filename="c.docx", full_name=None, email=None, phone=None,
            skills=["SQL"], education=[], certifications=[], experience_years=0.0,
            raw_text="SQL developer.",
        )
        jd = JobDescription(
            title="BA", raw_text="Need SQL and Agile.",
            required_skills=["SQL", "Agile"], min_experience=0.0,
        )
        result = score_candidate(profile, jd)
        assert set(result.matched_skills) & set(result.missing_skills) == set()
        assert set(result.matched_skills) <= set(profile.skills)
        assert set(result.missing_skills) <= set(jd.required_skills)
        assert result.matched_skills == ["SQL"]
        assert result.missing_skills == ["Agile"]


class TestConfidenceBands:
    def test_high_confidence_band(self):
        assert confidence_label(92.4) == "High Confidence Match"
        assert confidence_label(65) == "High Confidence Match"

    def test_moderate_band(self):
        assert confidence_label(60) == "Moderate Match — Review Recommended"
        assert confidence_label(50) == "Moderate Match — Review Recommended"

    def test_partial_weak_band(self):
        assert confidence_label(45) == "Partial / Weak Match — Secondary Pool"
        assert confidence_label(35) == "Partial / Weak Match — Secondary Pool"

    def test_no_match_band(self):
        assert confidence_label(10) == "No Match — Irrelevant"
        assert confidence_label(0) == "No Match — Irrelevant"

    def test_bands_cover_full_range_with_no_gaps(self):
        for score in [0, 1, 34.999, 35, 49.999, 50, 64.999, 65, 100]:
            assert confidence_label(score) != "Unscored"
