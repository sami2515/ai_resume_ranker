# AI Resume Ranker

TechWiz 6 — Global AI-Based Tech Competition | AI and Machine Learning Mania
Theme: Smart Resume Ranker for Recruiters

An NLP/ML pipeline plus web application that parses resumes, extracts
structured candidate information, and ranks candidates against a job
description using a hybrid keyword + semantic matching engine, with a
full explainability breakdown per candidate. Full design rationale is in
[`docs/AI_Resume_Ranker_Project_Documentation.docx`](docs/AI_Resume_Ranker_Project_Documentation.docx);
the organizer's official requirements are in
[`docs/AI_Resume_Ranker_SRS_final.pdf`](docs/AI_Resume_Ranker_SRS_final.pdf).

## Team Information

- **Institute:** Aptech Learning - North Nazimabad
- **Team Members:**
  - Saba Noor (ML & NLP Lead)
  - Muhmmad Sami (Backend & API Lead)
  - Ghanyan (Frontend & UI Lead)
  - Sami UR Rehman (Data, Integration & Documentation Lead)

## Interactive Google Colab Notebooks

- **Dataset Exploration:** [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/sami2515/ai_resume_ranker/blob/main/notebooks/01_dataset_exploration.ipynb)
- **Resume Ranking Pipeline:** [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/sami2515/ai_resume_ranker/blob/main/notebooks/02_resume_ranking_pipeline.ipynb)

## Repository structure

```
README.md              -- Complete Markdown technical documentation & API specification
ReadMe.docx            -- TechWiz project submission document & assumptions
docker-compose.yml     -- One-command run for the full stack
backend/               -- Flask app, NLP pipeline, tests, models & security
frontend/              -- React recruitment dashboard (UI)
notebooks/             -- Jupyter / Google Colab interactive notebooks (public deliverable)
  ├── 01_dataset_exploration.ipynb
  └── 02_resume_ranking_pipeline.ipynb
datasets/              -- Organizer-provided resumes + test JD set
docs/                  -- Project documentation, SRS, test data notes, architecture
demo/                  -- Demo video & presentation assets
```

## Quick start (Docker — recommended)

```bash
docker-compose up --build
```

- Frontend: http://localhost:5173
- Backend health check: http://localhost:5000/api/health

## Manual local setup (without Docker)

Requires Python 3.11-3.13 and Node 18+.

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash; use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python -m spacy download en_core_web_md
python -c "import nltk; nltk.download('stopwords'); nltk.download('wordnet'); nltk.download('punkt'); nltk.download('punkt_tab')"
python app.py
```

```bash
cd frontend
npm install
npm run dev
```

### Smoke test

```bash
python backend/scripts/quick_test.py
```

Parses a sample of real resumes from `datasets/resumes/`, ranks them
against a sample "Senior Business Analyst" JD, and prints the ranked list
plus an explainability sample.

## API (Section 4.4)

Every route except `/api/health`, `/api/auth/register`, and `/api/auth/login`
requires `Authorization: Bearer <token>` (see "Auth & security" below).

| Method & Path | Purpose |
|---|---|
| `POST /api/auth/register` | Create a recruiter account — JSON `{email, password, full_name}`. Returns `{token, recruiter}`. |
| `POST /api/auth/login` | JSON `{email, password}`. Returns `{token, recruiter}`. |
| `GET /api/auth/me` | Current recruiter's profile. |
| `POST /api/resumes/upload` | Upload one or more resumes (multipart field `resumes`). Rejects corrupt/mis-typed/oversized files per-file without failing the batch; flags duplicates by content hash. Large batches queue through Celery/Redis (see "Async processing" below); returns a `job_id` per file either way. |
| `GET /api/resumes/jobs/{job_id}/status` | Poll one upload's progress — `queued`/`processing`/`created`/`duplicate`/`error`. |
| `GET /api/resumes/{id}/download` | Download the original resume file (FR-07), decrypted in memory. |
| `DELETE /api/resumes/{id}` | Delete a candidate's data — file, DB row, match results, feedback (Section 12.6 right-to-deletion). |
| `POST /api/jobs` | Create a JD — JSON `{title, text}` or multipart `jd_file` + `title`. Owned by the creating recruiter. |
| `GET /api/jobs` | List the requesting recruiter's own JDs. |
| `POST /api/jobs/{id}/rank` | Run the matching engine against every uploaded candidate. 403 if you don't own the JD. |
| `GET /api/jobs/{id}/results` | Ranked list, tie-broken deterministically, with a `no_strong_matches` flag. 403 if you don't own the JD. |
| `GET /api/candidates/{id}/explain?job_id={jd}` | Explainability breakdown for one candidate against one JD. 403 if you don't own the JD. |
| `GET /api/candidates/search` | Filter by `keyword`, `skill`, `min_experience`, `max_experience`, or `job_id`+`min_score`. |
| `POST /api/results/{id}/feedback` | Record a recruiter decision — JSON `{"decision": "hired" \| "rejected"}` (FR-10). Recorded under the authenticated recruiter, not a client-supplied id. |
| `POST /api/feedback/reweight` | Section 5.4 re-weighting step for one category — JSON `{category}`. See "Feedback loop & re-weighting" below. |
| `GET /api/feedback/weights` | Full weight-history audit trail (Section 12.3), optionally `?category=`. |
| `GET /api/export/{job_id}?format=excel\|pdf` | Export the ranked shortlist (FR-08). 403 if you don't own the JD. |
| `GET /api/analytics/overview` | Aggregate dashboard metrics, scoped to the requesting recruiter's own jobs. |

## Auth & security (Section 3.4/4.1, NFR-04)

- **JWT bearer tokens**, 8-hour expiry, `HS256`. `backend/auth.py`.
- **Passwords hashed with bcrypt** (`bcrypt.hashpw`), never stored or
  returned in plaintext.
- **Access control between recruiter accounts** (Section 8.2 Security
  Testing calls this out by name): job descriptions belong to the recruiter
  who created them. Ranking, results, explain, export, and feedback on a
  JD you don't own all return 403. The candidate/resume pool itself is
  shared org-wide by design (all recruiters at one org search the same
  uploaded resumes) — only JDs and everything derived from them are
  per-recruiter.
- **Encryption at rest** (`backend/crypto_utils.py`, Fernet/AES via the
  `cryptography` library): resume files on disk, and candidate email/phone
  in the database, are encrypted — not just masked in API responses.
  Key comes from `ENCRYPTION_KEY` in production; for local dev it's
  generated once and cached at `backend/instance/encryption.key`
  (gitignored). The parser needs a real file path, so an uploaded resume
  touches disk in plaintext only for the instant it takes to parse, then
  gets overwritten with the encrypted version before the request returns.
- **PII masking on list views** (Section 12.6): email/phone are masked in
  the ranked-results list and search results; shown in full only on the
  single-candidate explain view.
- **Right to deletion** (Section 12.6): `DELETE /api/resumes/{id}` removes
  a candidate's file, DB row, and all derived match results/feedback.

## Testing (Section 8)

```bash
cd backend
pytest tests/ -v
```

151 tests: pipeline unit tests (tokenizer, stopwords, lemmatizer, gazetteer
matcher, scoring formula, confidence bands), the ranking-quality metric
functions, a full end-to-end API integration test against real dataset
resumes, auth/access-control tests (register/login, rejected-without-token,
cross-recruiter 403s, encryption-at-rest, cascading delete), the
Section 8.3 edge cases specifically — corrupt `.docx`, a `.exe` renamed to
`.docx`, oversized/empty files, duplicate resumes, deterministic
tie-breaking, a deliberately mismatched JD producing `no_strong_matches`,
the internal-storage-filename leak described below, and a resume file
deleted from disk after upload — async processing and the fairness/
re-weighting suites described in their own sections below, and the ML
training tooling (taxonomy, labeling-agreement scoring, the frozen-
classifier loader, and the candidate-based split + regularized fit behind
the optional trained re-weighting upgrade).

## Model evaluation (Section 12.1-12.2)

```bash
python backend/scripts/evaluate_ranking.py
```

Computes Precision@5, Precision@10, NDCG@10, and MRR against a manually
labeled validation set. **No labels ship with this repo** — Section 12.1
requires them to be judged by a human and never used for tuning, so
fabricating them would defeat the point. To use it: copy
`docs/validation_labels_template.json` to `docs/validation_labels.json`
and fill in `relevant_candidates` per JD (30-40 resumes, at least 10 per
role category — see `docs/test_data_notes.md`). Until then, the script
reports that clearly instead of pretending to have a number.

## Fairness & bias testing (Section 12.5)

```bash
python backend/scripts/fairness_test.py
```

For 10 real resumes, scores a name-swapped variant (gender or
race/ethnicity association changed, everything else byte-identical)
against the same JD and checks the composite-score shift against a ±2.0
point tolerance. The race/ethnicity name pairs are drawn from Bertrand &
Mullainathan's 2004 field-experiment name lists (independently validated
via birth records and perception surveys), not guessed internally — see
`backend/nlp_pipeline/fairness.py`'s module docstring for the full
citation and rationale.

**Result on this dataset: 10/10 pairs passed, all with a measured delta
of 0.0.** Full writeup, including *why* it's exactly zero and what that
does and doesn't prove (short version: it rules out one specific, literal
failure mode for the current spaCy-fallback backend — it is not a
certification of being unbiased, and should be re-run once real SBERT is
active) — see
[`docs/fairness_check_report.md`](docs/fairness_check_report.md).

## Feedback loop & re-weighting (Section 5.4/12.3, FR-10)

Every JD gets a role **category**, inferred from its title (Business
Analyst, Full Stack Developer, Project Manager, Software Engineer, or
General — `services.py:infer_job_category`). Recruiter hire/reject
decisions accumulate per category; `POST /api/feedback/reweight` triggers
the re-weighting step:

1. **Propose.** Compare the average keyword-score and average
   semantic-score of hired vs. rejected candidates in that category.
   Whichever score type separates the two groups more gets nudged up by a
   fixed step (0.05), clamped to [0.2, 0.8], keyword+semantic always
   summing to 1.0. This is a documented heuristic, not real ML training —
   Section 5.4 explicitly scopes it that way ("without requiring a full
   production MLOps setup"). Refuses to propose anything below 6 total
   feedback samples, or with feedback in only one direction — not enough
   signal to mean anything.
2. **Gate.** This is the tech-debt register's "Critical" item ("no
   model/weight versioning... retraining could silently degrade ranking
   mid-demo") — resolved by never promoting silently. If
   `docs/validation_labels.json` (Section 12.1's hand-labeled ground
   truth) exists, both the current and proposed weights are evaluated
   against it; the proposal is only applied if Precision@5/NDCG@10 don't
   regress beyond tolerance (`nlp_pipeline.evaluation.should_promote_weights`,
   already built in Phase 2-3). If no validation set exists yet — the
   real situation for this repo, since no one has hand-labeled resumes —
   the proposal is computed and logged but **never applied**. Ranking
   behavior for that category stays exactly as it was.
3. **Log.** Every attempt — promoted, rejected by the regression check,
   no-op because the signal was too weak, or blocked for lack of a
   validation set — is written to the `ScoringWeights` table and visible
   via `GET /api/feedback/weights`. Full audit trail, nothing silent.

This whole feature is additive: with zero `ScoringWeights` rows (the
default, out of the box), `get_active_weights()` returns the documented
0.4/0.6 blend, so ranking behavior is unchanged until someone explicitly
triggers a re-weighting that a regression check actually approves.

**Known scope reduction:** Section 5.4 envisions "a scheduled job" running
this periodically. This implementation exposes it as an explicit trigger
(API endpoint) instead of adding Celery Beat — with no labeled validation
set yet, an automatic timer would just accumulate `proposed_no_validation_set`
log rows on a schedule, which isn't worth the added infrastructure. The
interesting design (heuristic + regression-gated promote/rollback) is
identical either way; wiring a Celery Beat schedule around the same
`run_reweighting_for_category()` call is a small addition once labels exist.

**Optional trained upgrade:** the heuristic above can be swapped for a
genuinely trained 2-feature logistic regression once there's enough
feedback volume — see "ML training & validation" below.

## ML training & validation (AI/ML Model Training & Validation Master Plan)

The one component in this system that's genuinely supposed to be a
**trained supervised model** — a resume category classifier (Business
Analyst / Business Systems Analyst / Project Manager / Java Developer /
Full Stack Developer / Other-General) — plus an honest accounting of why
nothing else here is fine-tuned. Full workflow: `docs/ml_training/README.md`.

- **Taxonomy fixed first** (`backend/ml/taxonomy.py`) — six categories,
  each with a one-line rule, before a single resume gets labeled.
- **Labeling tooling, no fabricated labels.** `scripts/build_labeling_worksheet.py`
  builds a per-resume worksheet from parsed **body text**, never the
  filename; `scripts/check_labeling_agreement.py` scores two independent
  labelers' passes (percent agreement + Cohen's kappa) so disagreements get
  resolved, not silently averaged away. No labels ship with this repo —
  that step needs a human, the same honesty policy as the Precision@k
  validation set.
- **Training** (`scripts/train_classifier.py`), once `docs/category_labels.json`
  exists: stratified 5-fold CV, TF-IDF + Logistic Regression vs. TF-IDF +
  Linear SVM compared head-to-head with a logged hyperparameter grid search
  (`class_weight="balanced"` for both — no synthetic oversampling on a
  ~231-row dataset), an honest out-of-fold confusion matrix, and a frozen,
  versioned artifact + metadata saved to `backend/ml/artifacts/`.
- **Wired in, inert until trained.** `backend/ml/classify.py` loads that
  artifact if it exists; `Candidate.predicted_category` is `null` until it
  does. Exactly the same transparency pattern as the SBERT-vs-fallback
  semantic backend below — report what's actually active, never guess.
- **SBERT stays pretrained, deliberately.** 231 resumes is far too little
  to fine-tune a sentence embedding model without overfitting to this
  exact dataset's vocabulary — reasoning is in the master plan's Section 3
  and in `docs/ml_training/README.md`. The legitimate calibration step
  instead: `scripts/calibrate_thresholds.py` sweeps the confidence-band
  score cutoffs (currently 80/55) against `docs/validation_labels.json`.
- **Optional trained re-weighting upgrade** (Section 4) — a genuinely
  fitted 2-feature logistic regression (`propose_weights_trained`) as an
  alternative to the heuristic nudge above, exposed at
  `POST /api/feedback/reweight-trained`. Gated on **35+** real
  hired+rejected examples (well above the heuristic's 6), splits feedback
  by candidate identity (not by row) before fitting, and is promoted
  through the identical Section 12.3 regression-gated check as the
  heuristic — a trained model doesn't get to skip that safety net. Stays
  inert (`insufficient_feedback`) until real feedback volume exists; the
  heuristic remains the default.
- **Checklist:** `docs/ml_training/zero_error_margin_checklist.md` tracks
  every item in the master plan's Section 8 — what's built as tooling
  versus what's still pending a human actually labeling data.

## Semantic matching backend (SBERT vs. fallback)

The production design targets **Sentence-BERT** (`all-MiniLM-L6-v2`, via
`sentence-transformers`) for the semantic half of the hybrid matching score.
That model downloads from huggingface.co **the first time it's used** —
**internet access is required for that one-time download**, after which it
is cached locally and runs fully offline.

If `sentence-transformers` isn't installed, or the model can't be
downloaded (no internet access), the pipeline **automatically falls back**
to a TF-IDF-weighted spaCy word-vector similarity (`en_core_web_md`) — a
legitimate, documented classical-NLP technique, but weaker than true
sentence embeddings. If even that isn't available, it degrades further to
keyword-only scoring, and is explicit about it in the confidence output
rather than silently pretending to be the full hybrid model.

Check which backend is active:

```bash
cd backend
python -m nlp_pipeline.matching_engine --selftest
```

To get real SBERT: `pip install sentence-transformers` on a machine with
normal internet access — no code changes needed, it's auto-detected.

## Known environment note (Python 3.13)

`requirements.txt` uses version floors (e.g. `numpy>=1.26`) rather than
exact pins. Exact pins such as `numpy==1.26.4` have no prebuilt wheel for
Python 3.13 and fail to build from source without a C compiler installed.
Version floors let `pip` resolve whatever wheel matches each teammate's
Python version (3.11 through 3.13 all confirmed working). The Docker image
pins Python 3.11 to avoid this entirely.

## Assumptions

- The organizer-provided dataset (`datasets/resumes/`, 229 `.docx` files —
  the SRS text says "228"; the delivered dataset has one more) is used
  as-is, unmodified.
- English-language resumes only, per SRS Section 1.5 constraints.
- The skills gazetteer (`backend/nlp_pipeline/skills_gazetteer.py`) is a
  curated starter list (~180 terms) tuned against this dataset; it is
  expected to be expanded as more of the dataset is reviewed (see
  `notebooks/01_dataset_exploration.ipynb` for a skill-frequency breakdown
  that highlights gaps).
- Resume "experience years" is a heuristic (widest year-range span found in
  the text), not a guarantee — documented as a known limitation.
- Where a resume identifies the candidate only as `CandidateNNN` (the
  dataset's own anonymization convention), that ID is used as the display
  name rather than attempting to guess a real name.

## Async processing (Section 4.1/7.1 Phase 5, NFR-01/NFR-02)

Resume uploads go through Celery/Redis once a batch is large enough to be
worth queuing (`ASYNC_UPLOAD_THRESHOLD`, default 10 files) — small batches,
and any batch where the broker turns out to be unreachable, process inline
instead. That inline fallback is a deliberate feature, not a stopgap: the
project documentation's Section 13 tech-debt register calls it out by name
as the fix for *"no graceful degraded mode if Redis/Celery fails
mid-demo."* A dead queue degrades the upload feature, not the whole app.

Every uploaded file gets an `UploadJob` row and a `job_id` in the response,
whether it was processed inline or queued — poll
`GET /api/resumes/jobs/{job_id}/status` for `queued` → `processing` →
`created`/`duplicate`/`error`. The frontend's upload wizard does exactly
this: one combined upload request, then polling per file, so its
per-file progress indicators reflect the real async pipeline instead of
being faked by issuing one HTTP request per file.

### Running it locally

`docker-compose up` starts a real `redis:7-alpine` broker and a
`worker` service automatically. Outside Docker (e.g. this project's actual
dev machine, Windows without WSL/Docker installed), there's no native
Redis — for local dev/testing, `fakeredis` (a real Redis-protocol server
in pure Python, not a mock) stands in:

```bash
cd backend
# terminal 1: a real Redis-protocol socket, no Docker/WSL needed
python -c "from fakeredis import TcpFakeServer; TcpFakeServer(('127.0.0.1', 6379), server_type='redis').serve_forever()"

# terminal 2: a Celery worker (--pool=solo is a Windows-only requirement --
# the default prefork pool needs os.fork(), which Windows doesn't have;
# drop it on Linux/Docker for real worker concurrency)
celery -A celery_app.celery_app worker --loglevel=info --pool=solo

# terminal 3: the Flask app, as usual
python app.py
```

Upload 10+ files and watch terminal 2 — you'll see the worker pick up and
process each one. `docker-compose.yml` uses the real Redis image; this is
a dev-only substitute, documented as such in `requirements-dev.txt`.

## Load testing (Section 8.2/12.7, NFR-01/NFR-02)

```bash
python backend/scripts/load_test.py --base-url http://localhost:5000
```

Runs against a *live* backend over real HTTP — not a direct function-call
benchmark — and reports what Section 12.7 explicitly asks for: p50/p95
per-resume latency, total wall-clock time for the batch, and any
failures, instead of an unverifiable "tested with 500+ resumes" claim.

**Honesty note:** the organizer dataset has 229 resumes, not 500+. The
script uploads all of them and says so in its own output — it does not
round up. A genuine 500+ data point needs synthetic filler resumes added
to `datasets/resumes/`, clearly labeled as synthetic in the report if you
do that, so the reported numbers stay defensible.

For the run to exercise the real async pipeline rather than its
synchronous fallback, start Redis + a Celery worker first (see "Async
processing" above) — the script's own output tells you which path it took
(`X came back 'queued'` vs `fell back to synchronous`).

### Real results (this machine, single `--pool=solo` worker, fakeredis broker)

```
Phase 1 -- bulk upload: 229 resumes, upload REQUEST itself took 4.3s
  (all 229 came back "queued" -- async genuinely engaged, not the sync fallback)
Phase 2 -- all jobs resolved after 470.4s total wall-clock
  final status: 214 created, 15 duplicate, 0 errors
  per-resume latency (upload-start -> resolved): p50=238.2s  p95=445.8s  max=470.4s
Phase 3 -- ranking: 229 candidates against 1 JD in 259.1s (1.13s/candidate, batch-derived)
```

Read this honestly, not just as a pass/fail: the 4.3s upload response vs.
470s to fully resolve is exactly what async is *for* — the API stays
responsive immediately, while a single background worker chews through
the real NLP work. The 15 duplicates are real too, not a test artifact —
a subset of this dataset was already uploaded earlier under a different
recruiter account, and the shared candidate pool correctly caught them by
content hash rather than double-counting. The p50/p95 spread (238s vs
446s) is queue-depth latency from having exactly one worker process 229
files sequentially — `docker-compose.yml`'s worker runs
`--concurrency=4`, which would cut that spread roughly proportionally;
report both numbers if you re-run this against Docker rather than quoting
just the more flattering one. The 259s/229-candidate ranking pass
(1.13s/candidate) technically clears the literal "5s per resume" NFR-01
target on a batch-derived basis, but a real production deployment doing
this at 500+ scale would want either true SBERT (batch-encodes far faster
than this spaCy TF-IDF-vector fallback, one JD embedding reused across
all candidates instead of two full spaCy passes per candidate) or
parallelized per-candidate scoring — flagged honestly here rather than
implemented speculatively, since the dataset available doesn't force the
issue yet.

## Frontend (Section 4.5)

React + Tailwind, dark slate/charcoal base with a single accent color, no
default-template look. Three views (`frontend/src/App.jsx` switches
between them, no router needed for this size of app):

- **Upload & Rank** — drag-and-drop resume upload with genuine per-file
  progress (each file is its own request against the synchronous backend,
  not a faked progress bar around one batch call), JD input, rank trigger.
- **Results** — ranked candidate cards with a score gauge, matched-skill
  pills, shortlist badge, search/filter bar (keyword, min. experience, min.
  score — filters the already-fetched ranked list client-side), Hire/Reject
  buttons wired to the feedback endpoint, Excel/PDF export links, and the
  **explainability drawer** (`ExplainabilityDrawer.jsx`) — the signature
  feature: composite score with the keyword/semantic breakdown and formula,
  matched/missing requirement pills, and unmasked contact/education/
  certification detail (Section 12.6: masked in the list view, shown in
  full only here). It deliberately shows what the pipeline actually
  computes — skill-level matched/missing evidence — rather than fabricating
  the phrase-by-phrase evidence pairs in Section 9.3's illustrative example,
  which the current matching engine doesn't produce.
- **Analytics** — stat cards, score distribution, hiring funnel (from
  captured recruiter feedback), most in-demand skills.

Verified in a real browser against the live backend, not just read: full
upload → rank → results → explain → search/filter → feedback → export →
analytics flow, plus the duplicate-upload and no-strong-matches states.
That testing caught a real cross-platform bug — see below.

## Status / not yet built

See [`docs/AI_Resume_Ranker_Project_Documentation.docx`](docs/AI_Resume_Ranker_Project_Documentation.docx)
Section 7.1 for the full phased plan.

- **Done:** Phase 1 (repo scaffolding), Phase 2-3 (Flask API over the NLP
  pipeline — resumes, JDs, ranking, explainability, search, feedback
  capture, export, analytics — with SQLite/Postgres persistence), Phase 4
  (the React frontend), Phase 5 auth/security (JWT auth, bcrypt,
  per-recruiter access control, encryption at rest), Phase 5
  async/hardening (Celery/Redis with a synchronous fallback, the load-test
  script, real measured numbers), fairness/bias testing (Section 12.5 —
  see the dedicated section above), and the feedback-loop re-weighting
  with its Section 12.3 regression-gated promote/rollback safety net (see
  "Feedback loop & re-weighting" above), plus the Section 8.3 edge-case
  handling and the Precision@k/NDCG/MRR evaluation harness (Section 12.2,
  pending real labels) that span all of the above.
- **Not yet built:** nothing from the documentation's Section 7.1 phased
  plan remains unbuilt. What's genuinely still open: a ground-truth hand-labeled
  validation set (Section 12.1 — designed for domain recruiters to manually label
  relevance) and an optional automated Celery Beat schedule for the re-weighting
  trigger (a straightforward addition once labeled ground truth exists — see the
  scope note in that section).
- **Bugs found and fixed during real testing** (not caught by unit tests
  alone — worth citing in the report as evidence of genuine end-to-end
  testing, not just isolated unit tests):
  1. *(live browser testing)* On Windows, when a corrupt resume failed to
     parse, python-docx could still hold the file handle open, so the
     cleanup `unlink()` in `services.py` threw `PermissionError` and
     turned what should have been a clean per-file `"error"` status into
     an unhandled 500 for the whole upload request. Regression test:
     `test_edge_cases.py::test_corrupt_docx_through_upload_api_returns_400_not_500`.
  2. *(live browser testing)* Resumes stored on disk get a UUID-based
     filename (avoids collisions); `parser.py` derives
     `ParsedResume.filename` from whatever path it's given, so without
     correction, `extractor.py`'s name-extraction fallback chain would
     display that internal UUID as the candidate's name for any resume
     without a recognizable name/ID in the text. Fixed in `services.py`
     (and `tasks.py`'s async path) by restoring the original uploaded
     filename right after parsing. Regression test:
     `test_edge_cases.py::TestUploadFilenameIdentity`.
  3. *(introduced and caught within Phase 5 itself)* Adding per-file
     `UploadJob` DB rows for async tracking meant 2-3 SQLite commits per
     uploaded file instead of 1. Combined with this repo living under a
     OneDrive-synced folder (which intercepts file writes), a 15-file test
     that normally took ~30s took 52 minutes in one run. Fixed with
     `PRAGMA journal_mode=WAL` (`app.py`) — a standard, well-justified
     SQLite optimization for write-heavy workloads regardless of the exact
     cause. Also added `pytest-timeout` (`pytest.ini`, 120s/test) as a
     safety net so a genuine hang fails loudly instead of burning an hour
     silently.
  4. `DELETE /api/resumes/{id}` deleted the `Candidate` row but left
     `UploadJob.candidate_id` pointing at nothing. Fixed by nulling that
     reference (the upload job itself survives as an audit trail — Section
     12.6's deletion principle is about candidate data, not the fact that
     an upload happened).
