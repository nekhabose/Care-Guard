from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Notification transports that can be covered by a signed BAA. Anything else
# (ntfy.sh, Telegram, noop) is forbidden in production — see _enforce_production.
BAA_NOTIFICATION_PROVIDERS = frozenset({"twilio_sms", "sns"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "CareGuard"
    app_version: str = "0.1.0"
    environment: str = "development"
    base_url: str = "https://api.careguard.health"
    domain: str = "api.careguard.health"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/careguard"
    # Require TLS on the DB connection. Defaults on in production (set in
    # database.py); asyncpg negotiates SSL when this is true.
    db_require_ssl: bool | None = None

    # AWS
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket: str = "careguard-discharge-docs"
    sns_escalation_topic_arn: str = ""

    # PHI encryption at rest (Phase 1).
    #   provider: 'env' (Fernet keys in PHI_ENCRYPTION_KEY) | 'kms' (KMS-wrapped key)
    # PHI_ENCRYPTION_KEY is a comma-separated list of urlsafe-base64 Fernet keys;
    # the first encrypts, all decrypt (supports zero-downtime key rotation).
    # Generate one: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    phi_key_provider: str = "env"
    phi_encryption_key: str = ""
    phi_kms_key_id: str = ""

    # Call recordings (Phase 4) — KMS-encrypted S3 storage + retention.
    recordings_enabled: bool = False
    recordings_s3_bucket: str = ""
    kms_key_id: str = ""
    recording_retention_days: int = 90

    # Twilio webhook signature validation (Phase 2). When true, inbound Twilio
    # callbacks must carry a valid X-Twilio-Signature. Auto-skips when no auth
    # token is configured (local/mock dev); always required in production.
    twilio_validate_signatures: bool = True

    # Notifications — care-team escalation alerts.
    # provider: 'ntfy' (free, no key) | 'telegram' | 'twilio_sms' | 'sns' | 'noop'
    notification_provider: str = "ntfy"
    # ntfy.sh — free push notifications. Pick a private, hard-to-guess topic and
    # subscribe to it in the ntfy mobile app or at https://ntfy.sh/<topic>.
    ntfy_base_url: str = "https://ntfy.sh"
    ntfy_topic: str = ""
    # Telegram bot — create a bot via @BotFather, then resolve the chat id.
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # Twilio SMS — reuses the Twilio creds below; set the care-team destination.
    escalation_sms_to: str = ""

    # LLM provider selector — 'claude' | 'deepseek'
    llm_provider: str = "claude"
    # Voice turns must be short — cap generation so replies are fast to produce
    # and quick to speak. Raise only if you switch to a text/chat channel.
    llm_max_tokens: int = 200

    # Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens: int = 500  # kept for backward compat; use llm_max_tokens

    # DeepSeek (OpenAI-compatible API)
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Epic FHIR
    # provider: 'mock' (built-in sample patients, no keys) | 'epic' (live OAuth)
    fhir_provider: str = "mock"
    epic_fhir_base_url: str = ""
    epic_client_id: str = ""
    epic_private_key_path: str = ""
    # PEM key material directly (preferred for production via a
    # ``secretsmanager:<id>`` reference). Takes precedence over the file path.
    epic_private_key: str = ""

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    # Initial admin bootstrap — on first startup with an empty users table, an
    # admin account is created from these so the login portal is usable after a
    # fresh deploy. No-ops once any user exists. Leave the password blank to skip.
    bootstrap_admin_email: str = "admin@careguard.local"
    bootstrap_admin_name: str = "CareGuard Admin"
    bootstrap_admin_password: str = ""

    # Celery — Redis broker + result backend (free, runs locally via `redis-server`).
    # Broker on db 0, results on db 1 so they never collide.
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _resolve_secret_refs(self) -> "Settings":
        """Resolve any setting whose value is a ``secretsmanager:<id>`` reference.

        Lets production inject secrets from AWS Secrets Manager instead of env
        files. No-op for plain values, so local dev needs no AWS access.
        """
        from security.secrets import resolve_secret_ref  # lazy: avoids boto3 at import

        for field in self.model_fields:
            value = getattr(self, field)
            if isinstance(value, str) and value.startswith("secretsmanager:"):
                object.__setattr__(self, field, resolve_secret_ref(value, self.aws_region))
        return self

    @model_validator(mode="after")
    def _enforce_production(self) -> "Settings":
        """Fail closed: refuse to boot with insecure settings in production."""
        if not self.is_production:
            return self

        problems: list[str] = []
        if self.jwt_secret in ("", "change-me-in-production",
                               "change-me-to-a-strong-random-secret-in-production"):
            problems.append("JWT_SECRET must be a strong random value in production")
        if self.notification_provider.lower() not in BAA_NOTIFICATION_PROVIDERS:
            problems.append(
                f"NOTIFICATION_PROVIDER={self.notification_provider!r} has no BAA; "
                f"use one of {sorted(BAA_NOTIFICATION_PROVIDERS)} in production"
            )
        if self.llm_provider.lower() == "deepseek":
            problems.append("DeepSeek has no HIPAA BAA; do not use LLM_PROVIDER=deepseek in production")
        if self.phi_key_provider == "env" and not self.phi_encryption_key:
            problems.append("PHI_ENCRYPTION_KEY must be set in production (or use PHI_KEY_PROVIDER=kms)")
        if self.phi_key_provider == "kms" and not self.phi_kms_key_id:
            problems.append("PHI_KMS_KEY_ID must be set when PHI_KEY_PROVIDER=kms")
        if self.twilio_validate_signatures and not self.twilio_auth_token:
            problems.append("TWILIO_AUTH_TOKEN required to validate Twilio webhook signatures")
        if self.recordings_enabled and not (self.recordings_s3_bucket and self.kms_key_id):
            problems.append("RECORDINGS_S3_BUCKET and KMS_KEY_ID required when RECORDINGS_ENABLED=true")

        if problems:
            raise ValueError(
                "Insecure production configuration:\n  - " + "\n  - ".join(problems)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
