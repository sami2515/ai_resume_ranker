"""
Feedback-loop re-weighting orchestration tests (Section 5.4/12.3) -- the
DB-facing half. The heuristic itself is tested in isolation in
test_reweighting.py; these tests cover the API surface, the audit trail,
and (critically) that a labeled validation set gates whether a proposal is
ever actually applied.
"""
import io
import pytest


def _upload_and_rank(client, sample_resume_files, title="Senior Business Analyst",
                      text="Business Analyst needing SQL and stakeholder management skills."):
    client.post(
        "/api/resumes/upload",
        data={"resumes": [(io.BytesIO(f.read_bytes()), f.name) for f in sample_resume_files]},
        content_type="multipart/form-data",
    )
    jd_resp = client.post("/api/jobs", json={"title": title, "text": text})
    jd_id = jd_resp.get_json()["id"]
    client.post(f"/api/jobs/{jd_id}/rank")
    results = client.get(f"/api/jobs/{jd_id}/results").get_json()["results"]
    return jd_id, results


class TestJobCategoryInference:
    def test_business_analyst_title_gets_categorized(self, client, sample_resume_files):
        jd_id, _ = _upload_and_rank(client, sample_resume_files[:1], title="Senior Business Analyst")
        jobs = client.get("/api/jobs").get_json()["jobs"]
        jd = next(j for j in jobs if j["id"] == jd_id)
        assert jd["category"] == "Business Analyst"

    def test_unmatched_title_falls_back_to_general(self, client, sample_resume_files):
        jd_id, _ = _upload_and_rank(client, sample_resume_files[:1], title="Chief Widget Officer",
                                     text="Widget-related responsibilities.")
        jobs = client.get("/api/jobs").get_json()["jobs"]
        jd = next(j for j in jobs if j["id"] == jd_id)
        assert jd["category"] == "General"


class TestReweightEndpoint:
    def test_requires_category(self, client):
        resp = client.post("/api/feedback/reweight", json={})
        assert resp.status_code == 400

    def test_insufficient_feedback_returns_422(self, client, sample_resume_files):
        _upload_and_rank(client, sample_resume_files[:2], title="Business Analyst role")
        resp = client.post("/api/feedback/reweight", json={"category": "Business Analyst"})
        assert resp.status_code == 422
        assert resp.get_json()["status"] == "insufficient_feedback"

    @pytest.mark.parametrize("sample_resume_files", [10], indirect=True)
    def test_proposal_not_applied_without_validation_set(self, client, sample_resume_files):
        """Regression test for the Critical tech-debt item: a proposal must
        NEVER silently change active ranking behavior without a way to
        verify it doesn't regress quality."""
        jd_id, results = _upload_and_rank(client, sample_resume_files, title="Business Analyst role")
        # Need >= MIN_FEEDBACK_SAMPLES total, both directions, with a real gap
        # between hired/rejected scores to get a genuine (non-"too close to
        # call") proposal.
        for i, r in enumerate(results):
            decision = "hired" if i % 2 == 0 else "rejected"
            client.post(f"/api/results/{r['id']}/feedback", json={"decision": decision})

        resp = client.post("/api/feedback/reweight", json={"category": "Business Analyst"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] in ("proposed_no_validation_set", "no_change", "insufficient_feedback")
        if body["status"] == "proposed_no_validation_set":
            assert "no labeled validation set" in body["message"]
            # and the active weights must be untouched -- ranking again
            # should still be the default 0.4/0.6 blend
            active = client.get("/api/feedback/weights?category=Business Analyst").get_json()["weights"]
            assert not any(w["status"] == "active" for w in active)

    @pytest.mark.parametrize("sample_resume_files", [10], indirect=True)
    def test_audit_trail_records_every_attempt(self, client, sample_resume_files):
        jd_id, results = _upload_and_rank(client, sample_resume_files, title="Business Analyst role")
        for i, r in enumerate(results):
            decision = "hired" if i % 2 == 0 else "rejected"
            client.post(f"/api/results/{r['id']}/feedback", json={"decision": decision})

        client.post("/api/feedback/reweight", json={"category": "Business Analyst"})

        weights_resp = client.get("/api/feedback/weights?category=Business Analyst")
        assert weights_resp.status_code == 200
        rows = weights_resp.get_json()["weights"]
        assert len(rows) >= 1
        assert all(r["category"] == "Business Analyst" for r in rows)

    @pytest.mark.parametrize("sample_resume_files", [10], indirect=True)
    def test_weights_endpoint_without_category_returns_all(self, client, sample_resume_files):
        jd_id, results = _upload_and_rank(client, sample_resume_files, title="Business Analyst role")
        for i, r in enumerate(results):
            decision = "hired" if i % 2 == 0 else "rejected"
            client.post(f"/api/results/{r['id']}/feedback", json={"decision": decision})
        client.post("/api/feedback/reweight", json={"category": "Business Analyst"})

        resp = client.get("/api/feedback/weights")
        assert resp.status_code == 200
        assert isinstance(resp.get_json()["weights"], list)


class TestTrainedReweightEndpoint:
    """ML Training Master Plan Section 4 -- the optional trained-model
    upgrade path, gated on far more data than the heuristic and routed
    through the identical Section 12.3 promotion logic."""

    def test_requires_category(self, client):
        resp = client.post("/api/feedback/reweight-trained", json={})
        assert resp.status_code == 400

    @pytest.mark.parametrize("sample_resume_files", [10], indirect=True)
    def test_insufficient_data_returns_422_below_the_higher_gate(self, client, sample_resume_files):
        # 10 candidates is enough for the heuristic's floor but well below
        # the trained path's MIN_SAMPLES_FOR_TRAINED_REWEIGHT.
        jd_id, results = _upload_and_rank(client, sample_resume_files, title="Business Analyst role")
        for i, r in enumerate(results):
            decision = "hired" if i % 2 == 0 else "rejected"
            client.post(f"/api/results/{r['id']}/feedback", json={"decision": decision})

        resp = client.post("/api/feedback/reweight-trained", json={"category": "Business Analyst"})
        assert resp.status_code == 422
        assert resp.get_json()["status"] == "insufficient_feedback"

    @pytest.mark.timeout(300)
    @pytest.mark.parametrize("sample_resume_files", [40], indirect=True)
    def test_enough_data_reaches_the_same_promotion_pipeline_as_the_heuristic(self, client, sample_resume_files):
        """With >= MIN_SAMPLES_FOR_TRAINED_REWEIGHT feedback rows, the
        trained path must reach _apply_reweight_proposal and get logged to
        the same ScoringWeights audit trail -- proving it shares the
        Section 12.3 safety net rather than bypassing it (Section 4.2)."""
        jd_id, results = _upload_and_rank(client, sample_resume_files, title="Business Analyst role")
        for i, r in enumerate(results):
            decision = "hired" if i % 2 == 0 else "rejected"
            client.post(f"/api/results/{r['id']}/feedback", json={"decision": decision})

        resp = client.post("/api/feedback/reweight-trained", json={"category": "Business Analyst"})
        assert resp.status_code == 200
        body = resp.get_json()
        # never silently applied without going through the same gate the
        # heuristic path uses -- no validation set exists in this test env
        assert body["status"] in ("proposed_no_validation_set", "no_change")

        weights = client.get("/api/feedback/weights?category=Business Analyst").get_json()["weights"]
        assert len(weights) >= 1
        assert not any(w["status"] == "active" for w in weights)


class TestActiveWeightsDefaultBehavior:
    def test_ranking_uses_default_weights_when_no_override_exists(self, app, sample_resume_files):
        """Ensures the whole feature is additive: with no ScoringWeights row,
        ranking behavior is byte-identical to before this feature existed."""
        with app.app_context():
            from services import get_active_weights
            kw, sem = get_active_weights("Some Category With No History")
            assert kw == 0.4
            assert sem == 0.6


class TestPromotionPath:
    @pytest.mark.parametrize("sample_resume_files", [10], indirect=True)
    def test_regression_check_runs_and_decides_when_validation_set_exists(
        self, app, client, sample_resume_files, monkeypatch, tmp_path
    ):
        """With a (fake, minimal) validation set present, a real proposal must
        resolve to 'promoted' or 'rejected_regression' -- never silently skip
        the Section 12.3 safety check the way the no-validation-set path does."""
        import shutil
        import json as json_module

        fake_repo = tmp_path / "fake_repo"
        (fake_repo / "docs").mkdir(parents=True)
        (fake_repo / "datasets" / "resumes").mkdir(parents=True)
        (fake_repo / "datasets" / "test_jds").mkdir(parents=True)

        for f in sample_resume_files:
            shutil.copy(f, fake_repo / "datasets" / "resumes" / f.name)

        jd_text = "Business Analyst needing SQL and stakeholder management skills, Agile experience."
        (fake_repo / "datasets" / "test_jds" / "ba.txt").write_text(jd_text, encoding="utf-8")

        labels = {
            "jobs": [{
                "title": "Business Analyst",
                "jd_file": "datasets/test_jds/ba.txt",
                "relevant_candidates": [f.name for f in sample_resume_files[:3]],
            }]
        }
        (fake_repo / "docs" / "validation_labels.json").write_text(json_module.dumps(labels), encoding="utf-8")

        import services
        monkeypatch.setattr(services, "REPO_ROOT", fake_repo)

        jd_id, results = _upload_and_rank(client, sample_resume_files, title="Business Analyst role", text=jd_text)
        for i, r in enumerate(results):
            decision = "hired" if i % 2 == 0 else "rejected"
            client.post(f"/api/results/{r['id']}/feedback", json={"decision": decision})

        resp = client.post("/api/feedback/reweight", json={"category": "Business Analyst"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] in ("promoted", "rejected_regression", "no_change", "insufficient_feedback")
        if body["status"] in ("promoted", "rejected_regression"):
            assert "baseline_metrics" in body
            assert "new_metrics" in body
            assert "precision_at_5" in body["baseline_metrics"]

            if body["status"] == "promoted":
                active = client.get("/api/feedback/weights?category=Business Analyst").get_json()["weights"]
                assert any(w["status"] == "active" for w in active)
