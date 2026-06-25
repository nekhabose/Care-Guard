"""
Secret resolution from AWS Secrets Manager (HIPAA §164.308 — access management).

Any setting whose value is ``secretsmanager:<secret-id>`` (optionally
``secretsmanager:<secret-id>#<json-key>``) is fetched at startup instead of being
read from an env file. Plain values pass through untouched, so local development
needs no AWS access.
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_PREFIX = "secretsmanager:"


def resolve_secret_ref(ref: str, region: str) -> str:
    """Resolve a ``secretsmanager:`` reference to its plaintext secret value."""
    if not ref.startswith(_PREFIX):
        return ref

    spec = ref[len(_PREFIX):]
    secret_id, _, json_key = spec.partition("#")

    import boto3  # lazy — only needed when a reference is actually used

    client = boto3.client("secretsmanager", region_name=region)
    resp = client.get_secret_value(SecretId=secret_id)
    secret = resp.get("SecretString", "")

    if json_key:
        secret = json.loads(secret)[json_key]
    logger.info("Resolved secret reference for secret_id=%s", secret_id)
    return secret
