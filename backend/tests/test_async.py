"""
Async upload tests (project documentation Section 4.1/7.1 Phase 5, NFR-01/NFR-02).

Split by what each test actually proves:
  - TestProcessResumeUploadImpl: the task's actual work function is correct,
    independent of Celery/Redis entirely.
  - TestBrokerUnavailableFallback: with no broker reachable (the real,
    unmocked failure case -- nothing is running on the configured Redis
    port during a normal pytest run), a large batch still resolves
    correctly by falling back to synchronous processing. This is the
    graceful-degradation behavior from the tech-debt register, exercised
    for real, not mocked.
  - TestRealBrokerViaFakeredis: spins up an actual Redis-protocol server
    (fakeredis's TCP mode -- a real socket, not a mock) and proves the
    producer side genuinely publishes a task to it. Full worker consumption
    is verified separately via live manual testing (documented in the
    README), the same way every other phase's live-server behavior was
    verified in this project.
"""
from __future__ import annotations
import threading

import pytest


class TestProcessResumeUploadImpl:
    def test_creates_candidate_on_success(self, app, sample_resume_files):
        from tasks import _process_resume_upload_impl
        from models import UploadJob, Candidate

        f = sample_resume_files[0]
        with app.app_context():
            from extensions import db
            job = UploadJob(filename=f.name, recruiter_id=1, status="queued")
            db.session.add(job)
            db.session.commit()

            _process_resume_upload_impl(job.id, f.name, f.read_bytes(), str(app.config["STORAGE_DIR"]))

            db.session.refresh(job)
            assert job.status == "created"
            assert job.candidate_id is not None
            candidate = db.session.get(Candidate, job.candidate_id)
            assert candidate.resume_filename == f.name

    def test_marks_duplicate_without_reparsing(self, app, sample_resume_files):
        from tasks import _process_resume_upload_impl
        from models import UploadJob

        f = sample_resume_files[0]
        content = f.read_bytes()
        with app.app_context():
            from extensions import db
            job1 = UploadJob(filename=f.name, recruiter_id=1, status="queued")
            db.session.add(job1)
            db.session.commit()
            _process_resume_upload_impl(job1.id, f.name, content, str(app.config["STORAGE_DIR"]))

            job2 = UploadJob(filename=f.name, recruiter_id=1, status="queued")
            db.session.add(job2)
            db.session.commit()
            _process_resume_upload_impl(job2.id, f.name, content, str(app.config["STORAGE_DIR"]))

            db.session.refresh(job2)
            assert job2.status == "duplicate"
            assert job2.candidate_id == job1.candidate_id

    def test_marks_error_on_corrupt_file(self, app):
        from tasks import _process_resume_upload_impl
        from models import UploadJob
        import os

        with app.app_context():
            from extensions import db
            job = UploadJob(filename="corrupt.docx", recruiter_id=1, status="queued")
            db.session.add(job)
            db.session.commit()

            _process_resume_upload_impl(job.id, "corrupt.docx", b"PK\x03\x04" + os.urandom(100), str(app.config["STORAGE_DIR"]))

            db.session.refresh(job)
            assert job.status == "error"
            assert job.error


class TestBrokerUnavailableFallback:
    def test_large_batch_falls_back_to_sync_when_broker_unreachable(self, app, sample_resume_files):
        """Real (unmocked) failure case: nothing is listening on the
        configured Redis port during a normal test run, so _broker_available()
        genuinely returns False and every file in the 'batch' should still
        resolve to a final status inline, not sit at 'queued' forever."""
        from services import process_resume_upload_batch

        files = [(f.name, f.read_bytes()) for f in sample_resume_files[:2]]
        with app.app_context():
            results = process_resume_upload_batch(
                files, app.config["STORAGE_DIR"], recruiter_id=1, async_threshold=1  # forces the async branch to be considered
            )

        assert len(results) == 2
        for r in results:
            assert r["status"] in ("created", "duplicate")  # resolved, never stuck at "queued"


class TestRealBrokerViaFakeredis:
    """Proves an actual Celery producer can publish to a real Redis-protocol
    socket (fakeredis's TCP mode, not a mock) -- independent of this app's
    config-caching (config.REDIS_URL is resolved once at class-definition
    time, so re-pointing it via env var mid-test-suite isn't reliable; a
    fresh Celery app pointed straight at the fake broker sidesteps that)."""

    @pytest.fixture()
    def fake_redis_server(self):
        fakeredis = pytest.importorskip("fakeredis")
        server = fakeredis.TcpFakeServer(("127.0.0.1", 0), server_type="redis")
        port = server.socket.getsockname()[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield f"redis://127.0.0.1:{port}/0"
        server.shutdown()

    def test_task_publish_reaches_a_real_broker_socket(self, fake_redis_server):
        from celery import Celery

        probe = Celery("probe", broker=fake_redis_server, backend=fake_redis_server)

        @probe.task(name="probe.echo")
        def echo(x):
            return x

        result = echo.apply_async(args=["hello"])  # a real publish over the socket
        assert result.id is not None  # the broker accepted and assigned it a real task id

    def test_services_enqueue_path_when_broker_available(self, app, sample_resume_files, monkeypatch):
        """Unit-tests services.py's own branching: when _broker_available()
        says yes, a large batch is handed to _enqueue() and marked 'queued'
        rather than processed inline. The broker-reachability and actual
        Celery-wire-protocol behavior are proven separately above and by
        live manual testing (see README) -- this test is about MY code's
        decision logic, so it stubs the boundary rather than re-proving
        Celery itself works."""
        import services

        calls = []
        monkeypatch.setattr(services, "_broker_available", lambda: True)
        monkeypatch.setattr(services, "_enqueue", lambda *a: calls.append(a) or True)

        f = sample_resume_files[0]
        with app.app_context():
            results = services.process_resume_upload_batch(
                [(f.name, f.read_bytes())], app.config["STORAGE_DIR"], recruiter_id=1, async_threshold=1
            )

        assert results[0]["status"] == "queued"
        assert len(calls) == 1
