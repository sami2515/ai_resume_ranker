"""
predicted_category wiring tests (ML Training Master Plan Section 2):
the field must appear honestly (null, not guessed) with no trained model
present, and an existing pre-upgrade SQLite database must gain the column
without a manual reset -- db.create_all() alone won't add a column to a
table that already existed (app.py's lightweight ALTER TABLE guard).
"""
import io
import sqlite3

import pytest


def test_predicted_category_is_present_and_null_without_a_trained_model(client, sample_resume_files):
    f = sample_resume_files[0]
    resp = client.post(
        "/api/resumes/upload",
        data={"resumes": (io.BytesIO(f.read_bytes()), f.name)},
        content_type="multipart/form-data",
    )
    candidate = resp.get_json()["results"][0]["candidate"]
    assert "predicted_category" in candidate
    # No repo-shipped artifact exists (Section 2.2's labeling can't be
    # faked) -- honest null, never a guessed category.
    assert candidate["predicted_category"] is None


class TestSQLiteLightweightMigration:
    def test_add_column_guard_upgrades_an_existing_database(self, tmp_path):
        """Simulates a database created before predicted_category existed:
        a candidate table with every column except it. create_core_app must
        add the missing column via its best-effort ALTER TABLE guard rather
        than erroring (db.create_all() only creates missing TABLES)."""
        db_path = tmp_path / "old_shape.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE candidate (
                id INTEGER PRIMARY KEY,
                resume_filename VARCHAR(255) NOT NULL,
                stored_path VARCHAR(500) NOT NULL,
                file_hash VARCHAR(64) NOT NULL,
                full_name VARCHAR(255),
                email_encrypted TEXT,
                phone_encrypted TEXT,
                skills JSON,
                education JSON,
                certifications JSON,
                experience_years FLOAT,
                raw_text TEXT,
                created_at DATETIME
            )
        """)
        conn.commit()
        conn.close()

        columns_before = _column_names(db_path, "candidate")
        assert "predicted_category" not in columns_before

        from config import Config
        import config as config_module

        class OldShapeConfig(Config):
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path.as_posix()}"
            TESTING = True
            STORAGE_DIR = tmp_path / "storage"

        OldShapeConfig.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        config_module.INSTANCE_DIR = tmp_path / "instance"

        from app import create_core_app
        create_core_app(OldShapeConfig)  # must not raise

        columns_after = _column_names(db_path, "candidate")
        assert "predicted_category" in columns_after


def _column_names(db_path, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {row[1] for row in rows}
    finally:
        conn.close()
