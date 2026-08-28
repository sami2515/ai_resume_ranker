"""
Upload validation (project documentation Section 8.3)
----------------------------------------------------------
Rejects malicious/mis-typed uploads (e.g. a .exe renamed to .docx) BEFORE
they ever reach the resume parser, by checking real file-signature magic
bytes against the claimed extension -- not just trusting the filename.

.docx files are zip archives (magic bytes b'PK\\x03\\x04'); .pdf files start
with b'%PDF'. Anything else with those extensions is not a real docx/pdf,
whatever its name claims.
"""

from __future__ import annotations
import hashlib

ALLOWED_EXTENSIONS = {".docx", ".pdf"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per resume -- generous vs. the 24-90 KB dataset range

_MAGIC_BYTES = {
    ".docx": (b"PK\x03\x04",),
    ".pdf": (b"%PDF",),
}


class UploadValidationError(Exception):
    """Raised for a rejected upload. Message is safe to show the user."""


def validate_upload(filename: str, content: bytes) -> None:
    if not filename or "." not in filename:
        raise UploadValidationError(f"'{filename}' has no file extension.")

    ext = "." + filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"Unsupported file type '{ext}' for '{filename}'. Only .docx and .pdf are accepted."
        )

    if len(content) == 0:
        raise UploadValidationError(f"'{filename}' is empty.")

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise UploadValidationError(
            f"'{filename}' is {len(content) / 1024 / 1024:.1f} MB, over the {MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f} MB limit."
        )

    signatures = _MAGIC_BYTES[ext]
    if not any(content.startswith(sig) for sig in signatures):
        raise UploadValidationError(
            f"'{filename}' claims to be a {ext} file but its content doesn't match "
            f"that format. It may be corrupted, or a disguised/renamed file."
        )


def file_hash(content: bytes) -> str:
    """SHA-256 of the raw file bytes, used for duplicate-resume detection (Section 8.3)."""
    return hashlib.sha256(content).hexdigest()
