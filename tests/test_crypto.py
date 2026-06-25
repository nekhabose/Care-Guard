"""PHI encryption at rest — round-trip, ciphertext opacity, key rotation, legacy."""
from cryptography.fernet import Fernet

import security.crypto as C
from security.crypto import PHIEncryptor
from security.sqlalchemy_types import EncryptedString


class _StaticProvider(C.KeyProvider):
    def __init__(self, keys):
        self._keys = keys

    def keys(self):
        return self._keys


def test_roundtrip_and_opacity():
    enc = PHIEncryptor(_StaticProvider([Fernet.generate_key().decode()]))
    cipher = enc.encrypt("Jane Smith")
    assert cipher != "Jane Smith"          # stored value is opaque
    assert "Jane" not in cipher
    assert enc.decrypt(cipher) == "Jane Smith"


def test_none_passthrough():
    enc = PHIEncryptor(_StaticProvider([Fernet.generate_key().decode()]))
    assert enc.encrypt(None) is None
    assert enc.decrypt(None) is None


def test_legacy_plaintext_is_tolerated():
    # A value written before encryption existed must not crash on read.
    enc = PHIEncryptor(_StaticProvider([Fernet.generate_key().decode()]))
    assert enc.decrypt("legacy-plaintext-value") == "legacy-plaintext-value"


def test_key_rotation_decrypts_old_ciphertext():
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()
    old_enc = PHIEncryptor(_StaticProvider([old]))
    cipher = old_enc.encrypt("+15551234567")

    # New primary key first, old key retained for decryption.
    rotated_enc = PHIEncryptor(_StaticProvider([new, old]))
    assert rotated_enc.decrypt(cipher) == "+15551234567"


def test_encrypted_column_type_binds_ciphertext():
    # Uses the process-wide encryptor (dev key in tests) — deterministic enough
    # to verify the column stores ciphertext and reads back plaintext.
    col = EncryptedString()
    bound = col.process_bind_param("+15550001111", dialect=None)
    assert bound != "+15550001111"
    assert col.process_result_value(bound, dialect=None) == "+15550001111"
