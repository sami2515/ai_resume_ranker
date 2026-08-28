import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BACKEND_DIR.parent / "datasets" / "resumes"


@pytest.fixture()
def app(tmp_path):
    from config import Config

    class TestConfig(Config):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
        TESTING = True
        STORAGE_DIR = tmp_path / "storage"
        # High enough that no test here accidentally crosses it and pays for
        # a real (bounded but non-zero) broker-connection-attempt timeout.
        # tests/test_async.py exercises the async path directly with its own
        # low-threshold config + a fake in-process broker instead.
        ASYNC_UPLOAD_THRESHOLD = 10_000

    TestConfig.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    # auth.py / crypto_utils.py cache secrets in backend/instance/ by default
    # (INSTANCE_DIR from config.py); redirect those to the per-test tmp_path
    # too, so tests never touch the real dev instance dir and each test gets
    # its own fresh JWT secret / encryption key.
    import config as config_module
    config_module.INSTANCE_DIR = tmp_path / "instance"

    from app import create_app
    application = create_app(TestConfig)
    yield application


def _register_and_login(raw_client, email="recruiter@example.com", password="testpass123", full_name="Test Recruiter"):
    resp = raw_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    return body["token"], body["recruiter"]


@pytest.fixture()
def client(app):
    """Pre-authenticated test client -- every route except health/register/login
    requires a valid JWT, so tests default to already having one attached."""
    c = app.test_client()
    token, recruiter = _register_and_login(c)
    c.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    c.recruiter = recruiter  # stashed for tests that need the id/email
    return c


@pytest.fixture()
def anon_client(app):
    """No Authorization header -- for testing that protected routes reject
    unauthenticated requests."""
    return app.test_client()


@pytest.fixture()
def second_client(app):
    """A second, distinct authenticated recruiter -- for cross-account access
    control tests (Section 8.2 Security Testing)."""
    c = app.test_client()
    token, recruiter = _register_and_login(c, email="other-recruiter@example.com")
    c.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    c.recruiter = recruiter
    return c


@pytest.fixture()
def sample_resume_files(request):
    """Real .docx files from the organizer dataset, for realistic upload tests."""
    n = getattr(request, "param", 5)
    files = sorted(DATASET_DIR.glob("*.docx"))[:n]
    if not files:
        pytest.skip("Dataset not found at datasets/resumes -- run from repo checkout with dataset present.")
    return files
