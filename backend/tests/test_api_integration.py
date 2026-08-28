"""
Integration test (project documentation Section 8.2): the full recruiter
journey end-to-end through the API -- upload, JD, rank, results, explain,
search, feedback, export, analytics.
"""

import io
import pytest


@pytest.mark.parametrize("sample_resume_files", [15], indirect=True)
def test_full_recruiter_journey(client, sample_resume_files):
    # 1. Upload resumes
    upload_resp = client.post(
        "/api/resumes/upload",
        data={"resumes": [(io.BytesIO(f.read_bytes()), f.name) for f in sample_resume_files]},
        content_type="multipart/form-data",
    )
    assert upload_resp.status_code == 201
    upload_body = upload_resp.get_json()
    assert upload_body["summary"]["created"] == len(sample_resume_files)
    assert upload_body["summary"]["errors"] == 0

    candidate_id = upload_body["results"][0]["candidate_id"]
    job_id = upload_body["results"][0]["job_id"]

    # upload job status + download
    status_resp = client.get(f"/api/resumes/jobs/{job_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.get_json()["status"] == "created"

    download_resp = client.get(f"/api/resumes/{candidate_id}/download")
    assert download_resp.status_code == 200

    # 2. Create JD
    jd_resp = client.post("/api/jobs", json={
        "title": "Senior Business Analyst",
        "text": "We are looking for a Senior Business Analyst with 5+ years of experience. "
                "Responsibilities include requirements gathering, stakeholder management, "
                "business process modeling, and use case development. Strong SQL skills "
                "and Agile/Scrum experience required.",
    })
    assert jd_resp.status_code == 201
    job_id = jd_resp.get_json()["id"]
    assert "SQL" in jd_resp.get_json()["required_skills"]

    # 3. Rank
    rank_resp = client.post(f"/api/jobs/{job_id}/rank")
    assert rank_resp.status_code == 200
    assert rank_resp.get_json()["ranked"] == len(sample_resume_files)

    # 4. Results -- ranked, sorted descending, rank_position assigned
    results_resp = client.get(f"/api/jobs/{job_id}/results")
    assert results_resp.status_code == 200
    results = results_resp.get_json()["results"]
    assert len(results) == len(sample_resume_files)
    scores = [r["composite_score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert [r["rank_position"] for r in results] == list(range(1, len(results) + 1))

    top_candidate_id = results[0]["candidate_id"]
    match_result_id = results[0]["id"]

    # 5. Explainability
    explain_resp = client.get(f"/api/candidates/{top_candidate_id}/explain?job_id={job_id}")
    assert explain_resp.status_code == 200
    explain_body = explain_resp.get_json()
    assert "matched_skills" in explain_body and "missing_skills" in explain_body
    assert explain_body["composite_score"] == results[0]["composite_score"]

    # explain without job_id -> 400
    assert client.get(f"/api/candidates/{top_candidate_id}/explain").status_code == 400

    # 6. Search / filter
    search_resp = client.get("/api/candidates/search?keyword=candidate")
    assert search_resp.status_code == 200

    scored_search_resp = client.get(f"/api/candidates/search?job_id={job_id}&min_score=0")
    assert scored_search_resp.status_code == 200
    assert scored_search_resp.get_json()["total"] == len(sample_resume_files)

    # 7. Feedback
    feedback_resp = client.post(f"/api/results/{match_result_id}/feedback", json={"decision": "hired"})
    assert feedback_resp.status_code == 201
    assert feedback_resp.get_json()["decision"] == "hired"

    invalid_feedback_resp = client.post(f"/api/results/{match_result_id}/feedback", json={"decision": "maybe"})
    assert invalid_feedback_resp.status_code == 400

    # 8. Export
    excel_resp = client.get(f"/api/export/{job_id}?format=excel")
    assert excel_resp.status_code == 200
    assert excel_resp.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    pdf_resp = client.get(f"/api/export/{job_id}?format=pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.mimetype == "application/pdf"

    # 9. Analytics
    analytics_resp = client.get("/api/analytics/overview")
    assert analytics_resp.status_code == 200
    analytics_body = analytics_resp.get_json()
    assert analytics_body["total_candidates"] == len(sample_resume_files)
    assert analytics_body["total_matches_computed"] == len(sample_resume_files)


def test_rank_with_no_candidates_uploaded_yet(client):
    jd_resp = client.post("/api/jobs", json={"title": "X", "text": "Some job description text here."})
    job_id = jd_resp.get_json()["id"]

    rank_resp = client.post(f"/api/jobs/{job_id}/rank")
    assert rank_resp.status_code == 200
    assert rank_resp.get_json()["ranked"] == 0

    results_resp = client.get(f"/api/jobs/{job_id}/results")
    assert results_resp.get_json()["results"] == []
    assert results_resp.get_json()["no_strong_matches"] is True


def test_404_for_missing_job_and_candidate(client):
    assert client.get("/api/jobs/999/results").status_code == 404
    assert client.post("/api/jobs/999/rank").status_code == 404
    assert client.get("/api/candidates/999/explain?job_id=1").status_code == 404
    assert client.get("/api/resumes/jobs/999/status").status_code == 404
    assert client.get("/api/nonexistent-route").status_code == 404
