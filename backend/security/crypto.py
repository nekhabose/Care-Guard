"""
Application-layer PHI encryption (HIPAA Security Rule §164.312(a)(2)(iv)).

All PHI columns suffixed ``_enc`` and free-text transcripts are encrypted here
before they touch the database. Symmetric encryption uses Fernet (AES-128-CBC +
HMAC-SHA256). ``MultiFernet`` lets us rotate keys with zero downtime: the first
key encrypts, every key can decrypt.

Key material comes from a ``KeyProvider`` so the source is swappable:

    env   keys read directly from ``PHI_ENCRYPTION_KEY`` (comma-separated)
    kms   a KMS-wrapped data key, decrypted at startup via AWS KMS

In development with no key configured we derive a *deterministic, insecure* dev
key so tests and local runs work out of the box. Production refuses to boot
without a real key (see ``config._enforce_production``).
"""
from __future__ import annotations

import base64
import hashlib
import logging
from abc import ABC, abstractmethod
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from config import get_settings

logger = logging.getLogger(__name__)

# Stable key derived for local/dev use ONLY. Never selected in production.
_DEV_KEY_SEED = b"careguard-development-insecure-do-not-use-in-production"


def _derive_dev_key() -> str:
    digest = hashlib.sha256(_DEV_KEY_SEED).digest()
    return base64.urlsafe_b64encode(digest).decode()


class KeyProvider(ABC):
    """Source of Fernet keys. ``keys()[0]`` encrypts; all keys can decrypt."""

    @abstractmethod
    def keys(self) -> list[str]: ...


class EnvKeyProvider(KeyProvider):
    """Keys straight from ``PHI_ENCRYPTION_KEY`` (comma-separated, newest first)."""

    def keys(self) -> list[str]:
        settings = get_settings()
        raw = settings.phi_encryption_key.strip()
        if raw:
            return [k.strip() for k in raw.split(",") if k.strip()]
        if settings.is_production:
            raise RuntimeError("PHI_ENCRYPTION_KEY is unset in production")
        logger.warning("PHI_ENCRYPTION_KEY unset — using INSECURE derived dev key")
        return [_derive_dev_key()]


class KmsKeyProvider(KeyProvider):
    """Decrypts a KMS-wrapped data key into a Fernet key at startup.

    ``PHI_ENCRYPTION_KEY`` holds the base64 KMS CiphertextBlob; KMS returns the
    plaintext Fernet key, which never leaves memory.
    """

    def keys(self) -> list[str]:
        import boto3  # lazy — AWS SDK not needed for env provider

        settings = get_settings()
        kms = boto3.client("kms", region_name=settings.aws_region)
        keys: list[str] = []
        for wrapped in settings.phi_encryption_key.split(","):
            wrapped = wrapped.strip()
            if not wrapped:
                continue
            blob = base64.b64decode(wrapped)
            resp = kms.decrypt(CiphertextBlob=blob, KeyId=settings.phi_kms_key_id)
            keys.append(resp["Plaintext"].decode())
        if not keys:
            raise RuntimeError("KMS provider produced no keys")
        return keys


def _build_provider() -> KeyProvider:
    provider = get_settings().phi_key_provider.lower()
    if provider == "kms":
        return KmsKeyProvider()
    return EnvKeyProvider()


class PHIEncryptor:
    """Encrypt/decrypt PHI strings. Tolerates legacy plaintext on decrypt."""

    def __init__(self, provider: KeyProvider) -> None:
        fernets = [Fernet(k) for k in provider.keys()]
        self._fernet = MultiFernet(fernets)

    def encrypt(self, plaintext: str | None) -> str | None:
        if plaintext is None:
            return None
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str | None) -> str | None:
        if token is None:
            return None
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken:
            # Value predates encryption (migration window) — return as-is.
            logger.warning("PHI value not decryptable; treating as legacy plaintext")
            return token

    def rotate(self, token: str | None) -> str | None:
        """Re-encrypt a token under the primary key (for key-rotation jobs)."""
        if token is None:
            return None
        try:
            return self._fernet.rotate(token.encode()).decode()
        except InvalidToken:
            return self.encrypt(token)


@lru_cache
def get_encryptor() -> PHIEncryptor:
    return PHIEncryptor(_build_provider())
