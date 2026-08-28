"""
Flask application entrypoint (project documentation Section 4.1/4.4)
----------------------------------------------------------------------
Phase 2-3: registers the full Section 4.4 API surface (resumes, jobs,
ranking, explainability, search, feedback, export, analytics) on top of
the nlp_pipeline package, backed by SQLite/Postgres persistence.

Split into create_core_app() (config + db, no routes) and create_app()
(the above, plus blueprints) so celery_app.py can build a Flask app for
task-execution context without importing the API blueprints -- which
would otherwise create a circular import (a blueprint enqueuing a task
-> celery_app -> create_app -> that same blueprint, mid-import).
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from extensions import db


def create_core_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    CORS(app)

    Path(app.config["STORAGE_DIR"]).mkdir(parents=True, exist_ok=True)
    db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    is_sqlite = db_uri.startswith("sqlite:///")
    if is_sqlite:
        Path(db_uri.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        if is_sqlite:
            # WAL mode instead of SQLite's default rollback-journal mode:
            # each commit no longer needs a full fsync of the whole file,
            # just an append to the WAL -- a large, well-known win for
            # write-heavy workloads. The async upload-job tracking (Section
            # 4.1 Phase 5) commits several times per file (queued ->
            # processing -> resolved), so this isn't optional polish --
            # without it, uploading a batch of real resumes was measured
            # taking several times longer than the equivalent NLP parsing
            # work itself, most likely because this repo lives under a
            # OneDrive-synced folder that intercepts every file write. WAL
            # mode's fewer/smaller writes meaningfully sidesteps that
            # regardless of the exact cause.
            from sqlalchemy import event

            @event.listens_for(db.engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, _connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

        import models  # noqa: F401 -- registers models on db.metadata before create_all
        db.create_all()

        if is_sqlite:
            # db.create_all() only creates missing TABLES, not missing
            # COLUMNS on tables that already existed from a previous run --
            # there's no Alembic in this project, so a lightweight
            # best-effort ADD COLUMN keeps an existing local dev database
            # (e.g. from before ml.classify's predicted_category column was
            # added) working without a manual reset.
            from sqlalchemy import inspect, text

            inspector = inspect(db.engine)
            if "candidate" in inspector.get_table_names():
                existing_columns = {c["name"] for c in inspector.get_columns("candidate")}
                if "predicted_category" not in existing_columns:
                    db.session.execute(text("ALTER TABLE candidate ADD COLUMN predicted_category VARCHAR(64)"))
                    db.session.commit()

    return app


def create_app(config_object: type = Config) -> Flask:
    app = create_core_app(config_object)

    from api import ALL_BLUEPRINTS
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    @app.get("/api/health")
    def health():
        from nlp_pipeline import semantic_backend_name
        return jsonify(status="ok", semantic_backend=semantic_backend_name())

    @app.errorhandler(413)
    def too_large(_e):
        return jsonify(error="Upload too large."), 413

    @app.errorhandler(Exception)
    def unhandled_error(e):
        # Section 8.3: the app must fail gracefully, never crash uncaught --
        # but real HTTP errors (404 on an unmatched route, 405, etc.) should
        # keep their own status code, not get flattened into a 500.
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return jsonify(error=e.description), e.code
        app.logger.exception("Unhandled error")
        return jsonify(error="Internal error. Please try again."), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
