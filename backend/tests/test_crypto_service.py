"""Phase 9 KEY-02 crypto_service round-trip + MultiFernet rotation regression gate.

crypto_service reads KEY_ENCRYPTION_SECRET via get_settings() (which is @lru_cache'd),
so every monkeypatch.setenv("KEY_ENCRYPTION_SECRET", ...) MUST be followed by
get_settings.cache_clear() before the service is exercised.
"""
from cryptography.fernet import Fernet


def test_encrypt_decrypt_roundtrip(monkeypatch):
    """A plaintext key encrypts (ciphertext != plaintext) and decrypts back round-trip."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", key)
    from config import get_settings
    get_settings.cache_clear()
    from services import crypto_service
    ct = crypto_service.encrypt_key("sk-or-v1-example")
    assert ct != "sk-or-v1-example"
    assert crypto_service.decrypt_key(ct) == "sk-or-v1-example"


def test_rotation_decrypts_old_and_reencrypts(monkeypatch):
    """A new master key decrypts a token encrypted under the old key, then re-encrypts it."""
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", old)
    from config import get_settings
    get_settings.cache_clear()
    from services import crypto_service
    token_old = crypto_service.encrypt_key("sk-or-v1-example")

    # rotate: new key first, old key still present for decrypt
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", f"{new},{old}")
    get_settings.cache_clear()
    rotated = crypto_service.rotate_token(token_old)

    # rotated token now decryptable with the NEW key alone
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", new)
    get_settings.cache_clear()
    assert crypto_service.decrypt_key(rotated) == "sk-or-v1-example"
