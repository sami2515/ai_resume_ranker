import io


def test_hiring_funnel_reflects_feedback(client, sample_resume_files):
    client.post(
        "/api/resumes/upload",
        data={"resumes": [(io.BytesIO(f.read_bytes()), f.name) for f in sample_resume_files]},
        content_type="multipart/form-data",
    )
    job_id = client.post("/api/jobs", json={"title": "X", "text": "Python developer."}).get_json()["id"]
    client.post(f"/api/jobs/{job_id}/rank")
    results = client.get(f"/api/jobs/{job_id}/results").get_json()["results"]

    client.post(f"/api/results/{results[0]['id']}/feedback", json={"decision": "hired"})
    client.post(f"/api/results/{results[1]['id']}/feedback", json={"decision": "rejected"})

    funnel = client.get("/api/analytics/overview").get_json()["hiring_funnel"]
    assert funnel["matches_computed"] == len(sample_resume_files)
    assert funnel["hired"] == 1
    assert funnel["rejected"] == 1
    assert funnel["reviewed"] == 2
    assert funnel["pending"] == len(sample_resume_files) - 2


def test_changed_decision_counts_only_latest(client, sample_resume_files):
    client.post(
        "/api/resumes/upload",
        data={"resumes": [(io.BytesIO(f.read_bytes()), f.name) for f in sample_resume_files]},
        content_type="multipart/form-data",
    )
    job_id = client.post("/api/jobs", json={"title": "X", "text": "Python developer."}).get_json()["id"]
    client.post(f"/api/jobs/{job_id}/rank")
    match_id = client.get(f"/api/jobs/{job_id}/results").get_json()["results"][0]["id"]

    client.post(f"/api/results/{match_id}/feedback", json={"decision": "rejected"})
    client.post(f"/api/results/{match_id}/feedback", json={"decision": "hired"})  # recruiter changed their mind

    funnel = client.get("/api/analytics/overview").get_json()["hiring_funnel"]
    assert funnel["reviewed"] == 1
    assert funnel["hired"] == 1
    assert funnel["rejected"] == 0
