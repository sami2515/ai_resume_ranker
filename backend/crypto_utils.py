"""
Encryption at rest (project documentation Section 3.4/12.6, NFR-04)
------------------------------------------------------------------------
Symmetric encryption (Fernet -- AES-128-CBC + HMAC, from the `cryptography`
library) for two things:
  1. Extracted PII fields (candidate email/phone) stored in the database.
  2. Original resume files stored on disk.

Key management: ENCRYPTION_KEY env var in production/Docker (set once,
never committed). For local dev, a key is generated on first run and
cached at backend/instance/encryption.key -- gitignored, machine-local,
same pattern as the SQLite dev database. Losing this key makes existing
encrypted data unreadable, same as losing any encryption key; that's
expected for a competition dev environment, not a production guarantee.
"""

from __future__ import annotations
import os
from pathlib import Path
from functools import lru_cache

from cryptography.fernet import Fernet

import config


@lru_cache(maxsize=16)
def _fernet_for(key_material: bytes) -> Fernet:
    # Cached by the actual key bytes (not zero-arg global caching), so tests
    # that point config.INSTANCE_DIR at different tmp_paths each get their
    # own correctly-isolated Fernet instance instead of all sharing whichever
    # key happened to load first in the process.
    return Fernet(key_material)


def _get_fernet() -> Fernet:
    env_key = os.environ.get("ENCRYPTION_KEY")
    if env_key:
        return _fernet_for(env_key.encode())

    # Looked up dynamically (see auth.py's _get_secret for why) so tests get
    # an isolated key under tmp_path instead of writing into the real
    # backend/instance dir.
    config.INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    key_file = config.INSTANCE_DIR / "encryption.key"
    if key_file.exists():
        key = key_file.read_bytes()
    else:
        key = Fernet.generate_key()
        key_file.write_bytes(key)
    return _fernet_for(key)


def encrypt_text(plaintext: str | None) -> str | None:
    if not plaintext:
        return plaintext
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_text(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return ciphertext
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except Exception:  # noqa: BLE001 -- legacy unencrypted data, or wrong key
        return ciphertext


def encrypt_bytes(data: bytes) -> bytes:
    return _get_fernet().encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    return _get_fernet().decrypt(data)
