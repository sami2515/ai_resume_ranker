// API client (project documentation Section 4.4) -- one function per backend
// endpoint. Vite's dev-server proxy (vite.config.js) forwards /api to Flask,
// so these are always same-origin relative paths.

const BASE = "/api";
const TOKEN_KEY = "resume_ranker_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// Every protected route needs the Authorization header attached, and a 401
// anywhere means the token is missing/expired -- broadcast that once here
// instead of repeating 401-handling in every call site. App.jsx listens for
// this event to drop back to the login screen.
async function authedFetch(path, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;

  const resp = await fetch(`${BASE}${path}`, { ...options, headers });
  if (resp.status === 401) {
    clearToken();
    window.dispatchEvent(new Event("auth:unauthorized"));
  }
  return resp;
}

async function asJson(resp) {
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(body.error || `Request failed (${resp.status})`);
  }
  return body;
}

export async function register({ email, password, fullName }) {
  const resp = await fetch(`${BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name: fullName }),
  });
  const body = await asJson(resp);
  setToken(body.token);
  return body.recruiter;
}

export async function login({ email, password }) {
  const resp = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const body = await asJson(resp);
  setToken(body.token);
  return body.recruiter;
}

export function logout() {
  clearToken();
}

export async function getCurrentRecruiter() {
  const resp = await authedFetch("/auth/me");
  return asJson(resp);
}

// One request for the whole batch -- large batches (>= the backend's
// ASYNC_UPLOAD_THRESHOLD) get queued through Celery/Redis server-side and
// come back with status "queued" per file; small batches are already
// resolved by the time this returns. Either way every file gets a job_id,
// so the caller can poll uploadJobStatus() for whichever ones aren't done.
export async function uploadResumeBatch(files) {
  const form = new FormData();
  files.forEach((f) => form.append("resumes", f));
  const resp = await authedFetch("/resumes/upload", { method: "POST", body: form });
  const body = await asJson(resp);
  return body.results;
}

export async function uploadJobStatus(jobId) {
  const resp = await authedFetch(`/resumes/jobs/${jobId}/status`);
  return asJson(resp);
}

export async function createJob({ title, text }) {
  const resp = await authedFetch("/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, text }),
  });
  return asJson(resp);
}

export async function createJobWithFile({ title, file }) {
  const form = new FormData();
  form.append("title", title);
  form.append("jd_file", file);
  const resp = await authedFetch("/jobs", {
    method: "POST",
    body: form,
  });
  return asJson(resp);
}

export async function listJobs(activeOnly = false) {
  const qs = activeOnly ? "?active_only=true" : "";
  const resp = await authedFetch(`/jobs${qs}`);
  return asJson(resp);
}

export async function updateJobStatus(jobId, status) {
  const resp = await authedFetch(`/jobs/${jobId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  return asJson(resp);
}

export async function deleteJob(jobId) {
  const resp = await authedFetch(`/jobs/${jobId}`, {
    method: "DELETE",
  });
  return asJson(resp);
}

export async function rankJob(jobId, candidateIds = null) {
  const options = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  };
  if (candidateIds && Array.isArray(candidateIds) && candidateIds.length > 0) {
    options.body = JSON.stringify({ candidate_ids: candidateIds });
  }
  const resp = await authedFetch(`/jobs/${jobId}/rank`, options);
  return asJson(resp);
}

export async function getJobResults(jobId) {
  const resp = await authedFetch(`/jobs/${jobId}/results`);
  return asJson(resp);
}

export async function explainCandidate(candidateId, jobId) {
  const resp = await authedFetch(`/candidates/${candidateId}/explain?job_id=${jobId}`);
  return asJson(resp);
}

// Screen 4 -- Candidate Profile (master doc Section 3.6): the only call that
// returns unmasked contact info, reached only via an explicit action.
export async function getCandidateProfile(candidateId, jobId) {
  const qs = jobId ? `?job_id=${jobId}` : "";
  const resp = await authedFetch(`/candidates/${candidateId}/profile${qs}`);
  return asJson(resp);
}

export async function searchCandidates(params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== "" && v !== null)
  );
  const resp = await authedFetch(`/candidates/search?${query.toString()}`);
  return asJson(resp);
}

export async function getPipeline(params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== "" && v !== null)
  );
  const resp = await authedFetch(`/candidates/pipeline?${query.toString()}`);
  return asJson(resp);
}

export async function submitFeedback(matchResultId, decision) {
  const resp = await authedFetch(`/results/${matchResultId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  return asJson(resp);
}

export async function getActiveWeights() {
  const resp = await authedFetch("/feedback/active");
  return asJson(resp);
}

export async function getWeightsHistory(category) {
  const qs = category ? `?category=${encodeURIComponent(category)}` : "";
  const resp = await authedFetch(`/feedback/weights${qs}`);
  return asJson(resp);
}

export async function triggerReweight(category) {
  const resp = await authedFetch("/feedback/reweight", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category }),
  });
  // 422 = insufficient feedback — backend returns a JSON body with status/reason,
  // not a hard error. Return it as a normal result so UI can show a friendly message.
  if (resp.status === 422) {
    const body = await resp.json().catch(() => ({}));
    return { status: "insufficient_feedback", reason: body.reason || body.error || "Not enough hired/rejected decisions yet. Mark at least 6 candidates as Hired or Rejected first, then retry.", ...body };
  }
  return asJson(resp);
}

// Plain <a href> can't carry an Authorization header, so exports/downloads
// fetch the file as a blob and trigger the save via a throwaway object URL
// instead of linking straight to the API route.
async function downloadBlob(path, fallbackName) {
  const resp = await authedFetch(path);
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.error || `Download failed (${resp.status})`);
  }
  const disposition = resp.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : fallbackName;

  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function exportJob(jobId, format) {
  return downloadBlob(`/export/${jobId}?format=${format}`, `ranked_candidates_job${jobId}.${format === "pdf" ? "pdf" : "xlsx"}`);
}

export function downloadResume(candidateId, filename) {
  return downloadBlob(`/resumes/${candidateId}/download`, filename || "resume");
}

export async function deleteCandidate(candidateId) {
  const resp = await authedFetch(`/resumes/${candidateId}`, { method: "DELETE" });
  return asJson(resp);
}

export async function getAnalytics() {
  const resp = await authedFetch("/analytics/overview");
  return asJson(resp);
}

export async function getHealth() {
  const resp = await fetch(`${BASE}/health`);
  return asJson(resp);
}
