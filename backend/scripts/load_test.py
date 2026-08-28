"""
Load test (project documentation Section 8.2/12.7, NFR-01/NFR-02)
----------------------------------------------------------------------
Runs against a LIVE backend (real HTTP, real async pipeline if Celery/Redis
is running) -- not a direct function-call benchmark like quick_test.py.
Reports exactly what Section 12.7 asks for: p50/p95 per-resume latency,
total wall-clock time for the batch, and any failures observed, with real
numbers instead of an unverifiable "tested with 500+ resumes" claim.

Honesty note: the organizer dataset has 229 resumes, not 500+ (the SRS
text says "228"; the actual delivered dataset has one more file). This
script uploads all of them and reports the real number. If you need a
genuine 500+ data point, add synthetic filler resumes to datasets/resumes/
and say so explicitly in the report -- don't round up to "500+".

Usage:
    python backend/scripts/load_test.py [--base-url http://localhost:5000]

Requires a running backend (and, to actually exercise the async path
rather than its synchronous fallback, a running Celery worker + Redis --
see README "Async processing" section for how to start them locally).
"""

from __future__ import annotations
import argparse
import statistics
import sys
import time
import uuid
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / "datasets" / "resumes"

POLL_INTERVAL_S = 0.5
POLL_TIMEOUT_S = 600  # 10 minutes ceiling so a truly stuck run doesn't hang forever


def register(base_url: str) -> str:
    email = f"loadtest-{uuid.uuid4().hex[:8]}@example.com"
    resp = requests.post(f"{base_url}/api/auth/register", json={
        "email": email, "password": "loadtest12345", "full_name": "Load Test",
    })
    resp.raise_for_status()
    return resp.json()["token"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:5000")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    try:
        health = requests.get(f"{base_url}/api/health", timeout=5).json()
    except requests.RequestException as e:
        print(f"Backend not reachable at {base_url}: {e}")
        sys.exit(1)
    print(f"Backend healthy. Semantic engine: {health.get('semantic_backend')}\n")

    token = register(base_url)
    headers = {"Authorization": f"Bearer {token}"}

    files = sorted(DATASET_DIR.glob("*.docx"))
    if not files:
        print(f"No resumes found at {DATASET_DIR}")
        sys.exit(1)

    print(f"--- Phase 1: bulk upload ({len(files)} resumes -- the full organizer dataset; "
          f"NOT 500+, honestly reported as {len(files)}) ---")

    upload_files = [("resumes", (f.name, f.read_bytes())) for f in files]
    t0 = time.time()
    resp = requests.post(f"{base_url}/api/resumes/upload", headers=headers, files=upload_files, timeout=300)
    resp.raise_for_status()
    upload_request_s = time.time() - t0
    body = resp.json()
    jobs = body["results"]
    summary = body["summary"]

    queued_at_response = sum(1 for j in jobs if j["status"] == "queued")
    print(f"Upload request itself took {upload_request_s:.2f}s for {len(jobs)} files.")
    print(f"  {queued_at_response} came back 'queued' (async path engaged) -- "
          f"{'YES, Celery/Redis is doing real work' if queued_at_response > 0 else 'NO, fell back to synchronous (is a worker running?)'}")
    print(f"  Immediate summary: {summary}\n")

    print("--- Phase 2: polling until every upload job resolves ---")
    pending = {j["job_id"]: t0 for j in jobs}  # job_id -> upload-request start time, for latency calc
    resolved_at = {}
    final_status = {}
    poll_start = time.time()
    while pending and (time.time() - poll_start) < POLL_TIMEOUT_S:
        for job_id in list(pending.keys()):
            r = requests.get(f"{base_url}/api/resumes/jobs/{job_id}/status", headers=headers, timeout=10)
            r.raise_for_status()
            status = r.json()["status"]
            if status not in ("queued", "processing"):
                resolved_at[job_id] = time.time()
                final_status[job_id] = status
                del pending[job_id]
        if pending:
            time.sleep(POLL_INTERVAL_S)

    total_wall_clock_s = time.time() - t0
    if pending:
        print(f"WARNING: {len(pending)} jobs never resolved within the {POLL_TIMEOUT_S}s ceiling -- "
              f"treated as failures below.")
        for job_id in pending:
            final_status[job_id] = "timeout"

    latencies = [resolved_at[j["job_id"]] - t0 for j in jobs if j["job_id"] in resolved_at]
    status_counts = {}
    for s in final_status.values():
        status_counts[s] = status_counts.get(s, 0) + 1

    print(f"\nAll jobs resolved (or timed out) after {total_wall_clock_s:.1f}s total wall-clock.")
    print(f"Final status breakdown: {status_counts}")
    if latencies:
        latencies.sort()
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95) - 1] if len(latencies) > 1 else latencies[0]
        print(f"Per-resume latency (upload-request-start -> job resolved): "
              f"p50={p50:.2f}s  p95={p95:.2f}s  max={latencies[-1]:.2f}s")

    print("\n--- Phase 3: ranking latency against the full uploaded pool ---")
    jd_resp = requests.post(f"{base_url}/api/jobs", headers=headers, json={
        "title": "Senior Business Analyst",
        "text": "We are looking for a Senior Business Analyst with 5+ years of experience. "
                "Requirements gathering, stakeholder management, business process modeling, "
                "SQL, Agile/Scrum.",
    })
    jd_resp.raise_for_status()
    jd_id = jd_resp.json()["id"]

    t0 = time.time()
    rank_resp = requests.post(f"{base_url}/api/jobs/{jd_id}/rank", headers=headers, timeout=300)
    rank_s = time.time() - t0
    rank_resp.raise_for_status()
    ranked_count = rank_resp.json()["ranked"]

    t0 = time.time()
    results_resp = requests.get(f"{base_url}/api/jobs/{jd_id}/results", headers=headers, timeout=60)
    results_s = time.time() - t0
    results_resp.raise_for_status()

    print(f"Ranked {ranked_count} candidates against 1 JD in {rank_s:.2f}s "
          f"({rank_s / max(ranked_count, 1) * 1000:.0f}ms/candidate, batch-derived rate).")
    print(f"Fetched results ({results_resp.json()['total']} rows) in {results_s:.2f}s.")
    print(f"NFR-01 target: under 5s per resume. Batch-derived rate: "
          f"{'PASS' if rank_s / max(ranked_count, 1) < 5 else 'FAIL'} "
          f"(note: this is total-batch-time / count, not N independent single-resume calls -- "
          f"see script docstring).")

    print("\n--- Summary for the project report (Section 12.7) ---")
    print(f"Dataset size: {len(files)} resumes (organizer-provided; not 500+ -- see note above)")
    print(f"Bulk upload: {summary}")
    print(f"Total wall-clock, upload request through all jobs resolved: {total_wall_clock_s:.1f}s")
    if latencies:
        print(f"Per-resume latency: p50={p50:.2f}s p95={p95:.2f}s")
    print(f"Batch ranking: {ranked_count} candidates in {rank_s:.2f}s")
    failures = sum(v for k, v in status_counts.items() if k in ("error", "timeout"))
    print(f"Failures observed: {failures}")


if __name__ == "__main__":
    main()
