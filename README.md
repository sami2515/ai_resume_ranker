# AI Resume Ranker

**TechWiz 6 — Global AI-Based Tech Competition | AI and Machine Learning Mania**  
**Theme:** Smart Resume Ranker for Recruiters

AI Resume Ranker is an NLP/ML-based recruitment application that parses resumes, extracts structured candidate information, and ranks candidates against a Job Description (JD). The system combines keyword matching and semantic similarity and provides an explainability view for each ranked candidate.

Additional documentation:
- [`docs/AI_Resume_Ranker_Project_Documentation.docx`](docs/AI_Resume_Ranker_Project_Documentation.docx)
- [`docs/AI_Resume_Ranker_SRS_final.pdf`](docs/AI_Resume_Ranker_SRS_final.pdf)

## Team Information

- **Institute:** Aptech Learning - North Nazimabad
- **Saba Noor:** ML & NLP Lead
- **Muhmmad Sami:** Backend & API Lead
- **Ghanyan:** Frontend & UI Lead
- **Sami UR Rehman:** Data, Integration & Documentation Lead

## Google Colab Notebooks

### Dataset Exploration

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/sami2515/ai_resume_ranker/blob/main/notebooks/01_dataset_exploration.ipynb)

`notebooks/01_dataset_exploration.ipynb`

Covers dataset exploration, resume statistics, parsing success, resume-length distribution, and skill-frequency analysis.

### Resume Ranking Pipeline

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/sami2515/ai_resume_ranker/blob/main/notebooks/02_resume_ranking_pipeline.ipynb)

`notebooks/02_resume_ranking_pipeline.ipynb`

Covers resume parsing, candidate profile extraction, Job Description parsing, keyword matching, semantic matching, ranking, and explainability.

The notebooks include their required package and NLP-resource setup steps.

For local Jupyter Notebook:

```bash
cd notebooks
jupyter notebook 01_dataset_exploration.ipynb
```

The same approach can be used for `02_resume_ranking_pipeline.ipynb`.

## Repository Structure

```text
AI-Resume-Ranker/
│
├── README.md
├── ReadMe.docx
├── docker-compose.yml
│
├── backend/
│   ├── app.py
│   ├── auth.py
│   ├── crypto_utils.py
│   ├── nlp_pipeline/
│   ├── scripts/
│   └── tests/
│
├── frontend/
│   ├── src/
│   └── package.json
│
├── notebooks/
│   ├── 01_dataset_exploration.ipynb
│   └── 02_resume_ranking_pipeline.ipynb
│
├── datasets/
│   ├── resumes/
│   └── test_jds/
│
├── docs/
│
└── demo/
```

## Quick Start

### Docker

From the project root:

```bash
docker-compose up --build
```

Application endpoints:

```text
Frontend:
http://localhost:5173

Backend health check:
http://localhost:5000/api/health
```

### Manual Local Setup

Requirements:

- Python 3.11–3.13
- Node.js 18+
- npm
- Git

Backend:

```bash
cd backend
python -m venv .venv
```

Windows Git Bash:

```bash
source .venv/Scripts/activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install dependencies and NLP resources:

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_md
python -c "import nltk; nltk.download('stopwords'); nltk.download('wordnet'); nltk.download('punkt'); nltk.download('punkt_tab')"
python app.py
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

### Smoke Test

```bash
python backend/scripts/quick_test.py
```

This test uses sample resumes from `datasets/resumes/`, ranks them against a sample Senior Business Analyst JD, and displays the ranking with an explainability example.

## Main Features

### Resume Parsing

- Supports `.docx`, `.pdf`, and text-based resumes.
- Extracts relevant resume sections.
- Detects duplicate resumes using SHA-256 content hashing.
- Handles corrupt, empty, oversized, and incorrectly typed files.

### Candidate Information Extraction

The NLP pipeline extracts:

- Candidate name
- Email address
- Phone number
- Education
- Work experience
- Technical skills
- Soft skills

Email addresses and phone numbers are masked in list-based views.

### Hybrid Matching

The default ranking model combines:

- **40% keyword matching**
- **60% semantic similarity**

Candidates are ranked against the selected Job Description with Strong, Moderate, and Low confidence bands.

### Explainability

The explainability view provides:

- Composite score
- Keyword score
- Semantic score
- Matched skills
- Missing skills
- Candidate information
- Score breakdown

### Recruiter Feedback

Recruiters can record hire/reject decisions. The system supports category-level score re-weighting based on accumulated feedback and validation checks.

### Security and Privacy

The application includes:

- JWT authentication
- bcrypt password hashing
- Recruiter-level access control
- Encryption at rest
- PII masking
- Candidate data deletion

### Async Processing

Large resume batches can be processed through Celery and Redis.

The default upload threshold is:

```text
10 files
```

When the broker is unavailable, the application can fall back to synchronous processing.

Each uploaded file receives an `UploadJob` record and a `job_id`.

Processing states:

```text
queued
processing
created
duplicate
error
```

Docker Compose starts Redis and the Celery worker automatically:

```bash
docker-compose up --build
```

For Windows development without Docker or WSL, a `fakeredis` option is available:

```bash
cd backend
python -c "from fakeredis import TcpFakeServer; TcpFakeServer(('127.0.0.1', 6379), server_type='redis').serve_forever()"
celery -A celery_app.celery_app worker --loglevel=info --pool=solo
python app.py
```

## Load Testing

Run:

```bash
python backend/scripts/load_test.py --base-url http://localhost:5000
```

The test reports per-resume latency, p50/p95 latency, total processing time, and failures.

### Current Test Run

Using the available 229-resume dataset:

```text
Uploaded resumes: 229
Created: 214
Duplicates: 15
Errors: 0

Upload request time: 4.3 seconds
All jobs resolved: 470.4 seconds
p50 resolution latency: 238.2 seconds
p95 resolution latency: 445.8 seconds

Ranking:
229 candidates against 1 JD
Total time: 259.1 seconds
Average: 1.13 seconds per candidate
```

These figures depend on the machine, worker configuration, NLP backend, and runtime environment.

## Frontend

The frontend is built with React and Tailwind CSS.

### Upload & Rank

- Resume upload
- Job Description input
- Upload progress
- Ranking trigger

### Results

- Ranked candidate cards
- Score display
- Matched skills
- Search and filtering
- Hire / Reject actions
- Excel / PDF export

### Explainability

- Composite score
- Keyword score
- Semantic score
- Matched requirements
- Missing requirements
- Candidate details

### Analytics

- Candidate statistics
- Score distribution
- Hiring funnel
- Most in-demand skills

## Testing

Run the backend test suite:

```bash
cd backend
pytest tests/ -v
```

The current repository contains **151 automated tests** covering NLP processing, scoring, API integration, authentication, access control, encryption, file validation, duplicate handling, async processing, fairness testing, feedback/re-weighting, and ML utilities.

## Dataset

The organizer-provided dataset is located at:

```text
datasets/resumes/
```

The delivered dataset contains:

```text
229 .docx resumes
```

Sample Job Descriptions are available under:

```text
datasets/test_jds/
```

Where the dataset uses identifiers such as `CandidateNNN`, those identifiers are retained as the candidate display name.

## Project Assumptions

- The organizer-provided dataset is used as delivered.
- Resume and Job Description content is treated as English-language text.
- Resume experience is estimated using text-based date and tenure heuristics.
- The skills gazetteer is a curated starter taxonomy.
- Sentence-BERT is the primary semantic matching model.
- A classical NLP fallback is available when the primary semantic backend cannot be used.
- Feedback-based scoring changes require sufficient feedback and validation before promotion.
- Large upload batches can use Celery/Redis with a synchronous fallback.

## Environment Notes

The project supports Python 3.11–3.13. Docker uses Python 3.11 for a more predictable dependency environment.

## Demo

The project demonstration video is included with the final project submission.

Demo-related files are stored under:

```text
demo/
```

## Project Links

**GitHub Repository:**  
https://github.com/sami2515/ai_resume_ranker

**Google Colab — Dataset Exploration:**  
https://colab.research.google.com/github/sami2515/ai_resume_ranker/blob/main/notebooks/01_dataset_exploration.ipynb

**Google Colab — Resume Ranking Pipeline:**  
https://colab.research.google.com/github/sami2515/ai_resume_ranker/blob/main/notebooks/02_resume_ranking_pipeline.ipynb
