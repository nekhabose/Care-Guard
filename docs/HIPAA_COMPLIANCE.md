# CareGuard — HIPAA Compliance

CareGuard handles electronic Protected Health Information (ePHI): patient names,
phone numbers, clinical conditions, and recorded/transcribed voice check-ins.
This document records the safeguards implemented in code, the operational
requirements that must be met before production, and the residual gaps.

> **Status:** Technical safeguards implemented. **Not production-ready** until the
> BAAs are signed and the operational checklist below is complete.

---

## 1. Requirements → Controls

### Technical Safeguards (§164.312)

| Requirement | Control | Where |
|---|---|---|
| Encryption at rest | Fernet (AES-128-CBC + HMAC) on all `_enc` PHI columns and call transcripts, via `EncryptedString`/`EncryptedText`. Key rotation supported (`MultiFernet`). KMS-wrapped keys supported. | `security/crypto.py`, `security/sqlalchemy_types.py`, `models/db/patient.py`, `models/db/session.py` |
| Encryption in transit | HTTPS redirect + HSTS in production; TLS required to the DB; FHIR/Twilio/LLM calls over TLS. | `main.py`, `api/middleware/security_headers.py`, `database.py` |
| Access control — authentication | Short-lived JWTs with enforced `exp`. | `security/auth.py`, `api/deps.py` |
| Access control — authorization (RBAC) | `Role` ladder (viewer/nurse/care_lead/admin); reads open to any role, mutations (resolve escalation, place calls) restricted to care_lead/admin. | `security/auth.py`, `api/deps.py`, `api/routes/dashboard.py` |
| Audit controls | `HIPAAAuditMiddleware` logs every PHI-path request (method, path, status, user, client IP, duration) in a `finally` block so access is recorded even on error. **Never logs PHI bodies.** | `api/middleware/audit.py` |
| Integrity — webhook authenticity | `X-Twilio-Signature` validation on all Twilio callbacks (`/twiml`, `/status`, `/recording`). | `api/deps.py::verify_twilio_signature` |
| Transmission security — no PHI to non-BAA services | Escalation payloads carry UUIDs only; production refuses non-BAA notification providers and DeepSeek LLM. | `services/notification.py`, `config.py::_enforce_production` |

### Data lifecycle & Privacy Rule

| Requirement | Control | Where |
|---|---|---|
| Minimum necessary | Alerts use UUIDs, not identifiers; logs use `patient_id` UUIDs only. | `services/notification.py`, all services |
| Recordings encrypted + retained | Recordings copied to KMS-encrypted S3 (SSE-KMS), purged after `RECORDING_RETENTION_DAYS` by a daily Celery sweep + an S3 lifecycle rule. Disabled by default. | `services/recording.py`, `tasks/retention.py` |
| Secrets management | Secrets resolvable from AWS Secrets Manager via `secretsmanager:<id>` references; FHIR private key loadable from a secret, not just disk. Pre-commit secret scanning (gitleaks). | `security/secrets.py`, `fhir/client.py`, `.pre-commit-config.yaml` |
| Right of access (§164.524) | `GET /dashboard/patients/{id}/export` returns the patient's full designated record set (decrypted), restricted to care_lead/admin. | `services/patient_rights.py`, `api/routes/dashboard.py` |
| Right to opt out of outreach | `PATCH /dashboard/patients/{id}/contact-preferences` sets `call_opt_out`; both the scheduled (`tasks/outreach`) and on-demand (`CallTriggerService`) call paths honor it. | `models/db/patient.py`, `services/patient_rights.py`, `services/call_trigger.py`, `tasks/outreach.py` |
| Right to erasure | `DELETE /dashboard/patients/{id}/transcripts` hard-deletes conversation turns and S3 recordings (admin only). | `services/patient_rights.py`, `repositories/session.py`, `services/recording.py` |
| De-identification (§164.514(b) Safe Harbor) | `GET /dashboard/analytics/dataset` returns analytics rows with all 18 identifiers removed: keyed HMAC pseudonyms, age bands (90+ capped), year-only dates. | `services/deidentify.py`, `api/routes/dashboard.py` |
| WebSocket handshake auth | The Twilio media-stream socket is bound to its session by a short-lived signed token minted in the (signature-validated) TwiML and verified on connect. | `security/auth.py::create_stream_token`/`verify_stream_token`, `api/routes/twilio_voice.py` |

### Administrative & Physical (§164.308 / §164.310)

These are **operational**, not code. See the checklist in §3.

---

## 2. Configuration (production)

Set in the environment (or via `secretsmanager:` references):

```
ENVIRONMENT=production
JWT_SECRET=<32+ byte random>                 # not the default
PHI_KEY_PROVIDER=kms                          # or env with a real PHI_ENCRYPTION_KEY
PHI_KMS_KEY_ID=<kms-key-arn>
PHI_ENCRYPTION_KEY=<fernet key | KMS-wrapped key>
NOTIFICATION_PROVIDER=sns                     # or twilio_sms — BAA-covered only
LLM_PROVIDER=claude                           # DeepSeek has no BAA
TWILIO_VALIDATE_SIGNATURES=true
TWILIO_AUTH_TOKEN=<token>
DB_REQUIRE_SSL=true
RECORDINGS_ENABLED=true                       # only if recordings are needed
RECORDINGS_S3_BUCKET=<bucket>
KMS_KEY_ID=<kms-key-arn>
```

`config._enforce_production` **fails the app at startup** if any of these are
insecure (default JWT secret, non-BAA notifier, missing PHI key, missing Twilio
token, recordings enabled without a bucket/KMS key).

### Key generation & rotation

```bash
# New PHI key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Rotate by prepending the new key: `PHI_ENCRYPTION_KEY=<new>,<old>`. New writes use
the new key; old ciphertext still decrypts. Run a re-encryption job, then drop the
old key.

---

## 3. Operational checklist (before real patient data)

- [ ] **Sign BAAs**: AWS, Twilio, Anthropic. (DeepSeek and ntfy.sh/Telegram have **no** BAA — never use for PHI.)
- [ ] Rotate any credentials that have ever been on a developer machine.
- [ ] Provision the KMS key and PHI encryption key; set `PHI_KEY_PROVIDER=kms`.
- [ ] Ship `hipaa.audit` logs to an immutable, access-controlled store retained **≥ 6 years**.
- [ ] Configure the S3 recordings bucket: block public access, SSE-KMS default, lifecycle rule (`tasks.retention.ensure_recording_lifecycle`).
- [ ] Conduct & document a **security risk assessment** (§164.308(a)(1)).
- [ ] Write & adopt policies: incident response / breach notification (60-day rule), access management, data retention & disposal, workforce training.
- [ ] Designate a Security Officer; establish periodic audit-log review and access recertification.
- [ ] Enable `pre-commit` (`pre-commit install`) in every contributor's clone.

---

## 4. Residual gaps / future work

Implemented since the first hardening pass: **patient right of access (export), call
opt-out, transcript/recording erasure, a Safe Harbor de-identification dataset, and
WebSocket handshake authorization** (see §1).

Remaining:

- **Right to amendment** (§164.526) and **accounting of disclosures** (§164.528) are not yet exposed as endpoints.
- **Erasure scope**: erasure removes transcripts and recordings; demographic/discharge records are retained for the clinical/legal record. A full account-closure flow (with legal-hold checks) is future work.
- **DB migration**: handled — the schema is now Alembic-owned (`backend/alembic/`, baseline `0001_initial_schema` + `0002_call_opt_out`). Run `alembic upgrade head`; `create_all` has been removed.
- **De-identification** covers analytics rows; a full research-grade export pipeline (expert determination, k-anonymity checks) is out of scope.
- Audit-log shipping/retention is infrastructure, not code — must be wired in deployment.
