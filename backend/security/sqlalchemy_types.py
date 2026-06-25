"""
SQLAlchemy column types that transparently encrypt PHI at rest.

Bind an ``EncryptedString``/``EncryptedText`` to any ``_enc`` column and the ORM
attribute holds plaintext in memory while the database only ever sees ciphertext.
Encryption happens on write (bind param) and decryption on read (result value),
so repositories, services, and schemas need no changes.
"""
from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.types import TypeDecorator

from security.crypto import get_encryptor


class EncryptedString(TypeDecorator):
    """``VARCHAR`` whose value is Fernet-encrypted in the database."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return get_encryptor().encrypt(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        return get_encryptor().decrypt(value)


class EncryptedText(EncryptedString):
    """``TEXT`` variant for long PHI free-text (e.g. call transcripts)."""

    impl = Text
    cache_ok = True
