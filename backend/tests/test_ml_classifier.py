"""
Frozen-classifier loader tests (ML Training Master Plan Section 2.8).

No real trained artifact ships with this repo (Section 2.2's labeling
can't be faked), so the meaningful things to verify are: (1) the app
degrades to "not classified" rather than guessing when no artifact
exists, exactly like the SBERT-fallback pattern, and (2) once an artifact
*does* exist, it's actually used. Part (2) fits a tiny throwaway pipeline
on synthetic text inline -- that's testing the loading/prediction code
path, not claiming any real classification accuracy.
"""
import joblib
import pytest

import ml.classify as classify_module


@pytest.fixture(autouse=True)
def _reset_classifier_cache():
    classify_module._reset_cache_for_tests()
    yield
    classify_module._reset_cache_for_tests()


class TestNoArtifact:
    def test_classifier_available_is_false_without_an_artifact(self, tmp_path, monkeypatch):
        monkeypatch.setattr(classify_module, "ARTIFACT_PATH", tmp_path / "nonexistent.joblib")
        assert classify_module.classifier_available() is False

    def test_classify_returns_none_without_an_artifact(self, tmp_path, monkeypatch):
        monkeypatch.setattr(classify_module, "ARTIFACT_PATH", tmp_path / "nonexistent.joblib")
        assert classify_module.classify_resume_category("Experienced Java developer.") is None

    def test_classify_returns_none_for_empty_text_even_with_no_artifact(self, tmp_path, monkeypatch):
        monkeypatch.setattr(classify_module, "ARTIFACT_PATH", tmp_path / "nonexistent.joblib")
        assert classify_module.classify_resume_category("") is None


class TestWithArtifact:
    @pytest.fixture()
    def tiny_trained_pipeline(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline

        X = [
            "Java Spring Boot backend services microservices",
            "Java enterprise application development JVM",
            "React frontend and Node backend full stack development",
            "Full stack JavaScript TypeScript frontend backend",
        ]
        y = ["Java Developer", "Java Developer", "Full Stack Developer", "Full Stack Developer"]
        pipeline = Pipeline([("tfidf", TfidfVectorizer()), ("clf", LogisticRegression())])
        pipeline.fit(X, y)
        return pipeline

    def test_classify_uses_the_loaded_artifact(self, tmp_path, monkeypatch, tiny_trained_pipeline):
        artifact_path = tmp_path / "resume_category_classifier.joblib"
        joblib.dump(tiny_trained_pipeline, artifact_path)
        monkeypatch.setattr(classify_module, "ARTIFACT_PATH", artifact_path)

        assert classify_module.classifier_available() is True
        prediction = classify_module.classify_resume_category("Java Spring Boot microservices developer")
        assert prediction in ("Java Developer", "Full Stack Developer")  # a real prediction, not None

    def test_result_is_cached_across_calls(self, tmp_path, monkeypatch, tiny_trained_pipeline):
        artifact_path = tmp_path / "resume_category_classifier.joblib"
        joblib.dump(tiny_trained_pipeline, artifact_path)
        monkeypatch.setattr(classify_module, "ARTIFACT_PATH", artifact_path)

        classify_module.classify_resume_category("Java developer")
        artifact_path.unlink()  # if it re-read from disk now, this would break
        # still works because the model is cached in memory after first load
        assert classify_module.classify_resume_category("Java developer") is not None
