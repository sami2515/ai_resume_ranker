"""
Auth + access control tests (project documentation Section 3.4/4.1/8.2, NFR-04).
Security Testing (Section 8.2): "Auth bypass attempts... verify access
control between recruiter accounts."
"""
import io


class TestRegisterLogin:
    def test_register_returns_token_and_never_leaks_password(self, anon_client):
        resp = anon_client.post("/api/auth/register", json={
            "email": "new@example.com", "password": "supersecret123", "full_name": "New Recruiter",
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert "token" in body
        assert body["recruiter"]["email"] == "new@example.com"
        assert "password" not in body["recruiter"]
        assert "password_hash" not in body["recruiter"]

    def test_register_rejects_short_password(self, anon_client):
        resp = anon_client.post("/api/auth/register", json={"email": "x@example.com", "password": "short"})
        assert resp.status_code == 400

    def test_register_rejects_invalid_email(self, anon_client):
        resp = anon_client.post("/api/auth/register", json={"email": "not-an-email", "password": "longenough123"})
        assert resp.status_code == 400

    def test_register_rejects_name_with_numbers(self, anon_client):
        resp = anon_client.post("/api/auth/register", json={"email": "num@example.com", "password": "longenough123", "full_name": "Sarah123"})
        assert resp.status_code == 400
        assert "numbers" in resp.get_json()["error"].lower()

    def test_register_rejects_duplicate_email(self, anon_client):
        anon_client.post("/api/auth/register", json={"email": "dup@example.com", "password": "longenough123"})
        resp = anon_client.post("/api/auth/register", json={"email": "dup@example.com", "password": "longenough123"})
        assert resp.status_code == 409

    def test_login_with_correct_password_succeeds(self, anon_client):
        anon_client.post("/api/auth/register", json={"email": "login@example.com", "password": "correcthorse123"})
        resp = anon_client.post("/api/auth/login", json={"email": "login@example.com", "password": "correcthorse123"})
        assert resp.status_code == 200
        assert "token" in resp.get_json()

    def test_login_with_wrong_password_rejected(self, anon_client):
        anon_client.post("/api/auth/register", json={"email": "login2@example.com", "password": "correcthorse123"})
        resp = anon_client.post("/api/auth/login", json={"email": "login2@example.com", "password": "wrongpassword"})
        assert resp.status_code == 401

    def test_login_with_nonexistent_email_rejected(self, anon_client):
        resp = anon_client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "whatever123"})
        assert resp.status_code == 401

    def test_me_endpoint_returns_current_recruiter(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.get_json()["email"] == client.recruiter["email"]


class TestProtectedRoutesRejectUnauthenticated:
    def test_upload_without_token_rejected(self, anon_client):
        resp = anon_client.post("/api/resumes/upload", data={}, content_type="multipart/form-data")
        assert resp.status_code == 401

    def test_jobs_list_without_token_rejected(self, anon_client):
        assert anon_client.get("/api/jobs").status_code == 401

    def test_create_job_without_token_rejected(self, anon_client):
        resp = anon_client.post("/api/jobs", json={"title": "X", "text": "some text"})
        assert resp.status_code == 401

    def test_analytics_without_token_rejected(self, anon_client):
        assert anon_client.get("/api/analytics/overview").status_code == 401

    def test_malformed_token_rejected(self, anon_client):
        anon_client.environ_base["HTTP_AUTHORIZATION"] = "Bearer not-a-real-token"
        assert anon_client.get("/api/jobs").status_code == 401

    def test_missing_bearer_prefix_rejected(self, anon_client):
        anon_client.environ_base["HTTP_AUTHORIZATION"] = "just-a-token"
        assert anon_client.get("/api/jobs").status_code == 401

    def test_health_does_not_require_auth(self, anon_client):
        assert anon_client.get("/api/health").status_code == 200


class TestCrossRecruiterAccessControl:
    """The specific scenario Section 8.2 calls out by name."""

    def test_recruiter_cannot_view_another_recruiters_job_results(self, client, second_client):
        jd_id = client.post("/api/jobs", json={"title": "X", "text": "Python developer needed"}).get_json()["id"]

        resp = second_client.get(f"/api/jobs/{jd_id}/results")
        assert resp.status_code == 403

    def test_recruiter_cannot_rank_another_recruiters_job(self, client, second_client):
        jd_id = client.post("/api/jobs", json={"title": "X", "text": "Python developer needed"}).get_json()["id"]

        resp = second_client.post(f"/api/jobs/{jd_id}/rank")
        assert resp.status_code == 403

    def test_recruiter_cannot_export_another_recruiters_job(self, client, second_client):
        jd_id = client.post("/api/jobs", json={"title": "X", "text": "Python developer needed"}).get_json()["id"]

        resp = second_client.get(f"/api/export/{jd_id}?format=excel")
        assert resp.status_code == 403

    def test_job_list_is_scoped_per_recruiter(self, client, second_client):
        client.post("/api/jobs", json={"title": "Mine", "text": "Python developer needed"})
        second_client.post("/api/jobs", json={"title": "Theirs", "text": "Java developer needed"})

        mine = client.get("/api/jobs").get_json()["jobs"]
        theirs = second_client.get("/api/jobs").get_json()["jobs"]
        assert all(j["title"] == "Mine" for j in mine)
        assert all(j["title"] == "Theirs" for j in theirs)

    def test_recruiter_cannot_explain_candidate_against_another_recruiters_job(
        self, client, second_client, sample_resume_files
    ):
        client.post(
            "/api/resumes/upload",
            data={"resumes": (io.BytesIO(sample_resume_files[0].read_bytes()), sample_resume_files[0].name)},
            content_type="multipart/form-data",
        )
        jd_id = client.post("/api/jobs", json={"title": "X", "text": "Python developer needed"}).get_json()["id"]
        client.post(f"/api/jobs/{jd_id}/rank")
        candidate_id = client.get(f"/api/jobs/{jd_id}/results").get_json()["results"][0]["candidate_id"]

        resp = second_client.get(f"/api/candidates/{candidate_id}/explain?job_id={jd_id}")
        assert resp.status_code == 403

    def test_recruiter_cannot_submit_feedback_on_another_recruiters_match(
        self, client, second_client, sample_resume_files
    ):
        client.post(
            "/api/resumes/upload",
            data={"resumes": (io.BytesIO(sample_resume_files[0].read_bytes()), sample_resume_files[0].name)},
            content_type="multipart/form-data",
        )
        jd_id = client.post("/api/jobs", json={"title": "X", "text": "Python developer needed"}).get_json()["id"]
        client.post(f"/api/jobs/{jd_id}/rank")
        match_id = client.get(f"/api/jobs/{jd_id}/results").get_json()["results"][0]["id"]

        resp = second_client.post(f"/api/results/{match_id}/feedback", json={"decision": "hired"})
        assert resp.status_code == 403

    def test_feedback_recorded_under_authenticated_recruiter_not_client_supplied_id(
        self, client, sample_resume_files
    ):
        """Regression test for the fixed spoofing gap: recruiter_id used to be
        read straight from the request body."""
        client.post(
            "/api/resumes/upload",
            data={"resumes": (io.BytesIO(sample_resume_files[0].read_bytes()), sample_resume_files[0].name)},
            content_type="multipart/form-data",
        )
        jd_id = client.post("/api/jobs", json={"title": "X", "text": "Python developer needed"}).get_json()["id"]
        client.post(f"/api/jobs/{jd_id}/rank")
        match_id = client.get(f"/api/jobs/{jd_id}/results").get_json()["results"][0]["id"]

        resp = client.post(
            f"/api/results/{match_id}/feedback",
            json={"decision": "hired", "recruiter_id": 99999},  # attempted spoof
        )
        assert resp.status_code == 201
        assert resp.get_json()["recruiter_id"] == client.recruiter["id"]  # not 99999

    def test_analytics_scoped_to_own_jobs_only(self, client, second_client, sample_resume_files):
        client.post(
            "/api/resumes/upload",
            data={"resumes": (io.BytesIO(sample_resume_files[0].read_bytes()), sample_resume_files[0].name)},
            content_type="multipart/form-data",
        )
        jd_id = client.post("/api/jobs", json={"title": "X", "text": "Python developer needed"}).get_json()["id"]
        client.post(f"/api/jobs/{jd_id}/rank")

        their_analytics = second_client.get("/api/analytics/overview").get_json()
        assert their_analytics["total_jobs"] == 0
        assert their_analytics["total_matches_computed"] == 0


class TestEncryptionAtRest:
    def test_candidate_email_not_stored_as_plaintext_in_db(self, app, client, sample_resume_files):
        client.post(
            "/api/resumes/upload",
            data={"resumes": (io.BytesIO(sample_resume_files[0].read_bytes()), sample_resume_files[0].name)},
            content_type="multipart/form-data",
        )
        with app.app_context():
            from models import Candidate
            candidate = Candidate.query.first()
            if candidate.email:  # not every sample resume has an extractable email
                assert candidate.email not in (candidate.email_encrypted or "")
                assert "@" not in (candidate.email_encrypted or "")

    def test_resume_file_on_disk_is_not_plaintext_docx(self, app, client, sample_resume_files):
        f = sample_resume_files[0]
        client.post(
            "/api/resumes/upload",
            data={"resumes": (io.BytesIO(f.read_bytes()), f.name)},
            content_type="multipart/form-data",
        )
        with app.app_context():
            from models import Candidate
            candidate = Candidate.query.first()
            from pathlib import Path
            on_disk = Path(candidate.stored_path).read_bytes()
            assert not on_disk.startswith(b"PK\x03\x04")  # not a raw docx/zip anymore

    def test_password_hash_is_not_the_plaintext_password(self, app, client):
        with app.app_context():
            from models import Recruiter
            recruiter = Recruiter.query.filter_by(email=client.recruiter["email"]).first()
            assert recruiter.password_hash != "testpass123"
            assert recruiter.password_hash.startswith("$2b$")  # bcrypt hash prefix


class TestDeleteCandidate:
    def test_delete_removes_candidate_and_cascades(self, app, client, sample_resume_files):
        f = sample_resume_files[0]
        upload_resp = client.post(
            "/api/resumes/upload",
            data={"resumes": (io.BytesIO(f.read_bytes()), f.name)},
            content_type="multipart/form-data",
        )
        candidate_id = upload_resp.get_json()["results"][0]["candidate_id"]
        job_id = upload_resp.get_json()["results"][0]["job_id"]
        jd_id = client.post("/api/jobs", json={"title": "X", "text": "Python developer needed"}).get_json()["id"]
        client.post(f"/api/jobs/{jd_id}/rank")

        resp = client.delete(f"/api/resumes/{candidate_id}")
        assert resp.status_code == 200
        assert resp.get_json()["deleted"] is True

        assert client.get(f"/api/resumes/{candidate_id}/download").status_code == 404

        # the upload job record survives as an audit trail, but its
        # candidate_id reference is nulled out rather than left dangling
        job_status = client.get(f"/api/resumes/jobs/{job_id}/status").get_json()
        assert job_status["candidate_id"] is None

        with app.app_context():
            from models import MatchResult
            assert MatchResult.query.filter_by(candidate_id=candidate_id).count() == 0

    def test_delete_nonexistent_candidate_returns_404(self, client):
        assert client.delete("/api/resumes/999999").status_code == 404
