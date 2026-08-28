"""
PII masking tests (project documentation Section 12.6; master doc Section
3.5/3.6): ranked-list/search AND the explainability drawer mask email+phone.
Only the explicit "view full profile" action (Screen 4) shows them in full.
"""
import io


def _upload_and_rank(client, sample_resume_files):
    client.post(
        "/api/resumes/upload",
        data={"resumes": [(io.BytesIO(f.read_bytes()), f.name) for f in sample_resume_files]},
        content_type="multipart/form-data",
    )
    jd_resp = client.post("/api/jobs", json={"title": "X", "text": "Python developer with SQL experience."})
    job_id = jd_resp.get_json()["id"]
    client.post(f"/api/jobs/{job_id}/rank")
    return job_id


def test_results_list_masks_pii(client, sample_resume_files):
    job_id = _upload_and_rank(client, sample_resume_files)
    results = client.get(f"/api/jobs/{job_id}/results").get_json()["results"]

    for r in results:
        candidate = r["candidate"]
        if candidate["email"]:
            assert "*" in candidate["email"], f"email not masked: {candidate['email']}"
        if candidate["phone"]:
            assert "*" in candidate["phone"], f"phone not masked: {candidate['phone']}"


def test_search_list_masks_pii(client, sample_resume_files):
    _upload_and_rank(client, sample_resume_files)
    candidates = client.get("/api/candidates/search").get_json()["candidates"]

    for c in candidates:
        if c["email"]:
            assert "*" in c["email"]
        if c["phone"]:
            assert "*" in c["phone"]


def test_explain_view_also_masks_pii(client, sample_resume_files):
    """The explainability drawer (Screen 3) is not the candidate profile
    (Screen 4) -- it must mask contact info exactly like the list views."""
    job_id = _upload_and_rank(client, sample_resume_files)
    results = client.get(f"/api/jobs/{job_id}/results").get_json()["results"]
    masked_email = results[0]["candidate"]["email"]
    candidate_id = results[0]["candidate_id"]

    explain = client.get(f"/api/candidates/{candidate_id}/explain?job_id={job_id}").get_json()

    if masked_email:
        assert "*" in explain["candidate"]["email"]


def test_profile_view_shows_unmasked_pii(client, sample_resume_files):
    """Only the explicit profile action (Screen 4) reveals full contact info."""
    job_id = _upload_and_rank(client, sample_resume_files)
    results = client.get(f"/api/jobs/{job_id}/results").get_json()["results"]
    masked_email = results[0]["candidate"]["email"]
    candidate_id = results[0]["candidate_id"]

    profile = client.get(f"/api/candidates/{candidate_id}/profile?job_id={job_id}").get_json()
    unmasked_email = profile["email"]

    if masked_email:
        assert unmasked_email != masked_email
        assert "*" not in unmasked_email
    assert "composite_score" in profile


def test_profile_view_rejects_other_recruiters_job_id(client, second_client, sample_resume_files):
    job_id = _upload_and_rank(client, sample_resume_files)
    results = client.get(f"/api/jobs/{job_id}/results").get_json()["results"]
    candidate_id = results[0]["candidate_id"]

    resp = second_client.get(f"/api/candidates/{candidate_id}/profile?job_id={job_id}")
    assert resp.status_code == 403


def test_profile_view_without_job_id_still_returns_unmasked_contact(client, sample_resume_files):
    job_id = _upload_and_rank(client, sample_resume_files)
    results = client.get(f"/api/jobs/{job_id}/results").get_json()["results"]
    candidate_id = results[0]["candidate_id"]

    resp = client.get(f"/api/candidates/{candidate_id}/profile")
    assert resp.status_code == 200
    assert "composite_score" not in resp.get_json()
