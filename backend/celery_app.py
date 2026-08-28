"""
Celery integration (project documentation Section 3.4/4.1, NFR-01/NFR-02)
--------------------------------------------------------------------------
Standard Flask 3.x + Celery 5.x pattern: tasks run inside the Flask app's
context (so they can use db.session, the encryption key, etc. exactly like
a request would), via a custom Task base class.

Run a worker from backend/:
    celery -A celery_app.celery_app worker --loglevel=info --pool=solo

(--pool=solo is a Windows-specific requirement; Celery's default prefork
pool needs os.fork(), which Windows doesn't have. Linux/Docker can drop
--pool=solo and get real worker concurrency -- see docker-compose.yml.)
"""

from __future__ import annotations
from celery import Celery, Task


def make_celery(flask_app) -> Celery:
    class FlaskContextTask(Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(flask_app.import_name, task_cls=FlaskContextTask)
    celery_app.conf.update(
        broker_url=flask_app.config["CELERY_BROKER_URL"],
        result_backend=flask_app.config["CELERY_RESULT_BACKEND"],
        task_always_eager=flask_app.config["CELERY_TASK_ALWAYS_EAGER"],
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
    )
    celery_app.set_default()
    flask_app.extensions["celery"] = celery_app
    return celery_app


# Module-level app + celery instance so `celery -A celery_app.celery_app
# worker` works from the CLI without needing a running Flask request.
# Uses create_core_app() (config + db, no blueprints) rather than the full
# create_app() -- a blueprint enqueuing a task would otherwise import this
# module, which would import create_app(), which imports that same
# blueprint mid-initialization. Tasks only need db/config, not routes.
from app import create_core_app  # noqa: E402

flask_app = create_core_app()
celery_app = make_celery(flask_app)

from tasks import register_tasks  # noqa: E402

process_resume_upload_task = register_tasks(celery_app)
