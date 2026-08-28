"""
App configuration (project documentation Section 3.4/4.1)
------------------------------------------------------------
DATABASE_URL defaults to a local SQLite file for offline dev/demo safety
(the documented fallback -- Section 3.4: "PostgreSQL (SQLite fallback for
offline demo)"). docker-compose.yml overrides it to point at the postgres
service.
"""

from __future__ import annotations
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BACKEND_DIR / "instance"
STORAGE_DIR = BACKEND_DIR / "storage" / "resumes"

# Directories are created lazily in app.create_app(), based on the resolved
# config -- NOT here at import time. A subclass (e.g. tests/conftest.py's
# TestConfig) overriding STORAGE_DIR must control what actually gets
# created on disk; creating it unconditionally on import would leave stray
# real backend/instance and backend/storage dirs behind on every test run.


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{(INSTANCE_DIR / 'app.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB per request (Section 8.3: reject oversized/malicious uploads)

    STORAGE_DIR = STORAGE_DIR

    # Composite score threshold for auto-shortlisting (FR-04).
    SHORTLIST_THRESHOLD = 55.0

    # Async processing (Section 4.1/7.1 Phase 5, NFR-02). Batches at or above
    # this many files are queued through Celery/Redis instead of processed
    # inline -- small batches stay synchronous (project documentation
    # Section 13 tech-debt register's own prescribed resolution for "no
    # graceful degraded mode if Redis/Celery fails mid-demo": a synchronous
    # fallback path for small uploads). If the broker is unreachable at
    # request time, every batch falls back to synchronous regardless of size
    # -- a dead queue must never take the whole upload feature down with it.
    ASYNC_UPLOAD_THRESHOLD = 10

    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    # Tests set this True (Celery's standard testing pattern): tasks run
    # in-process, synchronously, with no broker/worker needed at all.
    CELERY_TASK_ALWAYS_EAGER = False
