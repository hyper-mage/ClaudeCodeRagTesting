"""App-layer encryption for BYOK keys via MultiFernet (Phase 9 D-02, D-04).

KEY_ENCRYPTION_SECRET is a comma-separated list of url-safe base64 Fernet keys,
NEW KEY FIRST. Encryption uses the first (primary) key; decryption tries each key
in order; rotation re-encrypts an existing token under the primary key.

D-04: the master key, plaintext, and ciphertext are NEVER logged, traced, or returned
beyond each function's declared value.
"""
import logging

from cryptography.fernet import Fernet, MultiFernet

from config import get_settings

logger = logging.getLogger(__name__)


def _multifernet() -> MultiFernet:
    """Build a MultiFernet from the configured key list (NEW KEY FIRST), read at call time.

    Fails with a clear, actionable error when KEY_ENCRYPTION_SECRET is empty/unset
    (its default) or all-whitespace, instead of the opaque
    "MultiFernet requires at least one Fernet instance" ValueError from cryptography.
    D-04: the error message NEVER includes the key value or any ciphertext.
    """
    keys = [k.strip() for k in get_settings().key_encryption_secret.split(",") if k.strip()]
    if not keys:
        raise RuntimeError(
            "KEY_ENCRYPTION_SECRET is not set — cannot encrypt/decrypt BYOK keys"
        )
    return MultiFernet([Fernet(k.encode()) for k in keys])


def encrypt_key(plaintext: str) -> str:
    """Encrypt a plaintext key under the primary (first) master key; returns a Fernet token."""
    return _multifernet().encrypt(plaintext.encode()).decode()


def decrypt_key(ciphertext: str) -> str:
    """Decrypt a Fernet token, trying each configured master key in order; returns plaintext."""
    return _multifernet().decrypt(ciphertext.encode()).decode()


def rotate_token(ciphertext: str) -> str:
    """Re-encrypt an existing token under the current primary key (lazy MultiFernet rotation)."""
    return _multifernet().rotate(ciphertext.encode()).decode()
