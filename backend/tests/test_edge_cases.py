"""
Edge-case tests (project documentation Section 8.3) -- the specific failure
modes evaluators are most likely to probe live.
"""

import io
import os

import pytest

from upload_validation import validate_upload, UploadValidationError
from nlp_pipeline.matching_engine import rank_candidates, JobDescription
from nlp_pipeline.extractor import CandidateProfile


class TestUploadValidation:
    def test_rejects_unsupported_extension(self):
        try:
            validate_upload("resume.txt", b"some text")
            assert False, "expected UploadValidationError"
        except UploadValidationError as e:
            assert "Unsupported file type" in str(e)

    def test_rejects_no_extension(self):
        try:
            validate_upload("resume", b"content")
            assert False, "expected UploadValidationError"
        except UploadValidationError:
            pass

    def test_rejects_empty_file(self):
        try:
            validate_upload("resume.docx", b"")
            assert False, "expected UploadValidationError"
        except UploadValidationError as e:
            assert "empty" in str(e)

    def test_rejects_exe_renamed_to_docx(self):
        """Section 8.3: a .exe renamed to .docx must be rejected at validation,
        never passed to the parser."""
        exe_bytes = b"MZ\x90\x00\x03\x00\x00\x00" + os.urandom(100)  # real PE header magic
        try:
            validate_upload("resume.docx", exe_bytes)
            assert False, "expected UploadValidationError"
        except UploadValidationError as e:
            assert "doesn't match that format" in str(e)

    def test_rejects_oversized_file(self):
        from upload_validation import MAX_FILE_SIZE_BYTES
        oversized = b"PK\x03\x04" + b"0" * (MAX_FILE_SIZE_BYTES + 1)
        try:
            validate_upload("resume.docx", oversized)
            assert False, "expected UploadValidationError"
        except UploadValidationError as e:
            assert "MB" in str(e)

    def test_accepts_valid_docx_signature(self):
        # Doesn't need to be a *complete* valid docx -- just needs to pass the
        # signature check; parser.py handles deeper corruption separately.
        validate_upload("resume.docx", b"PK\x03\x04" + b"\x00" * 20)

    def test_accepts_valid_pdf_signature(self):
        validate_upload("resume.pdf", b"%PDF-1.4" + b"\x00" * 20)


class TestCorruptFileHandling:
    def test_corrupt_docx_fails_gracefully_not_uncaught(self, tmp_path):
        """A .docx with the right magic bytes but broken internal structure
        must raise ResumeParseError (caught upstream), never an uncaught
        exception that would crash the API."""
        from nlp_pipeline.parser import parse_resume, ResumeParseError

        bad_file = tmp_path / "corrupt.docx"
        bad_file.write_bytes(b"PK\x03\x04" + os.urandom(200))  # zip-signature but invalid zip/docx

        try:
            parse_resume(bad_file)
            assert False, "expected ResumeParseError"
        except ResumeParseError as e:
            assert "corrupt" in str(e).lower() or "not a valid" in str(e).lower()

    def test_corrupt_docx_through_upload_api_returns_400_not_500(self, client):
        """Regression test: a corrupt .docx uploaded through the real API must
        surface as a per-file error in the response, not crash the request.
        (Found via live browser testing: on Windows, python-docx can still
        hold the file handle after raising, so the cleanup unlink() in
        services.py was throwing PermissionError and turning this into an
        unhandled 500 instead of the clean per-file "error" status.)"""
        corrupt_bytes = b"PK\x03\x04" + os.urandom(200)
        resp = client.post(
            "/api/resumes/upload",
            data={"resumes": (io.BytesIO(corrupt_bytes), "corrupt.docx")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["results"][0]["status"] == "error"
        assert body["summary"]["errors"] == 1


class TestUploadFilenameIdentity:
    @pytest.mark.parametrize("sample_resume_files", [30], indirect=True)
    def test_extracted_name_never_falls_back_to_internal_storage_uuid(self, client, sample_resume_files):
        """Regression test, found via live browser testing: resumes stored
        get a UUID-based filename on disk to avoid collisions. parser.py
        derives ParsedResume.filename from whatever path it's given, so
        without correction in services.py, extractor.py's name-fallback
        chain (dataset id -> first line -> spaCy PERSON -> filename stem)
        would display that internal UUID as the candidate's name instead of
        the uploaded file's own name."""
        import re
        uuid_hex_pattern = re.compile(r"^[0-9a-f]{32}$")

        resp = client.post(
            "/api/resumes/upload",
            data={"resumes": [(io.BytesIO(f.read_bytes()), f.name) for f in sample_resume_files]},
            content_type="multipart/form-data",
        )
        for r in resp.get_json()["results"]:
            candidate = r["candidate"]
            assert candidate["resume_filename"] not in (None, "")
            assert not uuid_hex_pattern.match(candidate["resume_filename"].rsplit(".", 1)[0])
            if candidate["full_name"]:
                assert not uuid_hex_pattern.match(candidate["full_name"])


class TestResumeFileUnavailable:
    def test_download_returns_clean_404_when_file_missing_on_disk(self, app, client, sample_resume_files):
        """FR-07 edge case: the original file was deleted or moved on the
        server after upload -- must be a clean 404, never an uncaught
        FileNotFoundError turning into a 500 / broken download link."""
        resp = client.post(
            "/api/resumes/upload",
            data={"resumes": (io.BytesIO(sample_resume_files[0].read_bytes()), sample_resume_files[0].name)},
            content_type="multipart/form-data",
        )
        candidate_id = resp.get_json()["results"][0]["candidate_id"]

        with app.app_context():
            from extensions import db
            from models import Candidate
            candidate = db.session.get(Candidate, candidate_id)
            os.remove(candidate.stored_path)

        dl_resp = client.get(f"/api/resumes/{candidate_id}/download")
        assert dl_resp.status_code == 404
        assert "no longer available" in dl_resp.get_json()["error"]


class TestDuplicateDetection:
    def test_same_file_hash_flagged_as_duplicate(self, client, sample_resume_files):
        f = sample_resume_files[0]
        content = f.read_bytes()

        resp1 = client.post(
            "/api/resumes/upload",
            data={"resumes": (io.BytesIO(content), f.name)},
            content_type="multipart/form-data",
        )
        assert resp1.status_code == 201
        assert resp1.get_json()["results"][0]["status"] == "created"

        resp2 = client.post(
            "/api/resumes/upload",
            data={"resumes": (io.BytesIO(content), f.name)},
            content_type="multipart/form-data",
        )
        assert resp2.status_code == 201
        body2 = resp2.get_json()
        assert body2["results"][0]["status"] == "duplicate"
        assert body2["summary"]["duplicates"] == 1
        # duplicate must resolve to the SAME candidate id, not a new one
        assert body2["results"][0]["candidate_id"] == resp1.get_json()["results"][0]["candidate_id"]


class TestTieBreaking:
    def test_identical_profiles_break_ties_deterministically_by_filename(self):
        jd = JobDescription(title="X", raw_text="Python developer needed", required_skills=["Python"], min_experience=0)
        # Two candidates with IDENTICAL text -> guaranteed identical keyword
        # and semantic scores -> the tie must resolve by filename, and must
        # be stable across repeated calls.
        profiles = [
            CandidateProfile(filename="zzz.docx", full_name=None, email=None, phone=None,
                              skills=["Python"], education=[], certifications=[], experience_years=1,
                              raw_text="Experienced Python developer with strong skills."),
            CandidateProfile(filename="aaa.docx", full_name=None, email=None, phone=None,
                              skills=["Python"], education=[], certifications=[], experience_years=1,
                              raw_text="Experienced Python developer with strong skills."),
        ]
        results1 = rank_candidates(profiles, jd)
        results2 = rank_candidates(list(reversed(profiles)), jd)

        assert results1[0].composite_score == results1[1].composite_score  # confirm it's a real tie
        assert [r.candidate_filename for r in results1] == ["aaa.docx", "zzz.docx"]
        assert [r.candidate_filename for r in results2] == ["aaa.docx", "zzz.docx"]


class TestNoStrongMatches:
    def test_mismatched_jd_flags_no_strong_matches(self, client, sample_resume_files):
        for f in sample_resume_files[:3]:
            client.post(
                "/api/resumes/upload",
                data={"resumes": (io.BytesIO(f.read_bytes()), f.name)},
                content_type="multipart/form-data",
            )

        jd_resp = client.post("/api/jobs", json={
            "title": "Marine Biologist",
            "text": "Seeking a Marine Biologist with SCUBA certification for coral reef "
                    "field research, species identification, and marine conservation policy.",
        })
        job_id = jd_resp.get_json()["id"]

        client.post(f"/api/jobs/{job_id}/rank")
        results = client.get(f"/api/jobs/{job_id}/results").get_json()

        assert results["no_strong_matches"] is True


class TestEmptyUpload:
    def test_upload_with_no_files_returns_400(self, client):
        resp = client.post("/api/resumes/upload", data={}, content_type="multipart/form-data")
        assert resp.status_code == 400
