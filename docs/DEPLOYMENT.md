# CareGuard — Deployment

CareGuard ships as three runtime processes plus two backing stores:

| Component | Image | Notes |
|---|---|---|
| `db` | `postgres:16` | Schema owned by Alembic |
| `redis` | `redis:7` | Celery broker + result backend |
| `backend` | `backend/Dockerfile` | FastAPI (uvicorn). Runs `alembic upgrade head` on start |
| `worker` | `backend/Dockerfile` | Celery worker (same image, different command) |
| `frontend` | `frontend/Dockerfile` | Vite SPA built + served by nginx, reverse-proxying the API |

The frontend nginx proxies `/auth`, `/dashboard`, `/webhooks`, `/twilio`, `/health`
to `backend:8000`, so the browser sees **one origin** — no CORS, nothing
host-specific baked into the JS bundle.

---

## 1. Local / demo stack (Docker Compose)

```bash
cp .env.docker.example .env     # optional — defaults work out of the box
docker compose up --build
```

Open <http://localhost:8080> and sign in with `BOOTSTRAP_ADMIN_EMAIL` /
`BOOTSTRAP_ADMIN_PASSWORD` (defaults `admin@careguard.local` / `ChangeMe123!`).
Then **Seed demo patients** from the dashboard to populate the cohort from the
mock FHIR data.

What the defaults give you: `ENVIRONMENT=development`, `FHIR_PROVIDER=mock`,
`NOTIFICATION_PROVIDER=noop`, an **insecure derived PHI key**, and a weak JWT
secret. Fine for a demo; **not** for real PHI.

The first admin is seeded automatically on first boot (empty `users` table). It
no-ops once any user exists, so changing the password later sticks.

---

## 2. Production checklist

Production fails closed: `config._enforce_production` refuses to boot if any of
these are wrong (see also `docs/HIPAA_COMPLIANCE.md`).

- [ ] `ENVIRONMENT=production`
- [ ] `JWT_SECRET` — strong random value (`python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] `BOOTSTRAP_ADMIN_PASSWORD` — strong; rotate / disable the account after creating real users
- [ ] `PHI_ENCRYPTION_KEY` set (Fernet), or `PHI_KEY_PROVIDER=kms` + `PHI_KMS_KEY_ID`
- [ ] `NOTIFICATION_PROVIDER` is a BAA-covered transport (`sns` or `twilio_sms`)
- [ ] `LLM_PROVIDER=claude` (DeepSeek has no BAA)
- [ ] `TWILIO_AUTH_TOKEN` set (webhook signature validation)
- [ ] `DATABASE_URL` points at managed Postgres with TLS (`DB_REQUIRE_SSL` defaults on in prod)
- [ ] Signed **BAAs** in place: AWS, Twilio, Anthropic
- [ ] TLS terminated in front of the stack; `DOMAIN` / allowed hosts set
- [ ] `alembic upgrade head` has run (the backend entrypoint does this automatically)

Provide real secrets via your platform's secret store, or use the
`secretsmanager:<id>` reference syntax any setting supports (see `config.py`).

---

## 3. Deploying to a host

Any Docker host works. The image pair is platform-agnostic, so the same
artifacts run on:

- **A single VM** (EC2 / Droplet / Lightsail): `docker compose up -d` behind an
  nginx/Caddy TLS terminator or an ALB. Simplest path.
- **AWS ECS / Fargate**: push `backend` + `frontend` images to ECR; one service
  each (plus a worker service). Use RDS Postgres + ElastiCache Redis instead of
  the `db`/`redis` compose services. SQS can replace Redis as the Celery broker.
- **Fly.io / Render / Railway**: deploy `backend/Dockerfile` and
  `frontend/Dockerfile` as two services; attach managed Postgres + Redis and set
  the env vars from the checklist above.

### Building / pushing images manually

```bash
docker build -t <registry>/careguard-backend:latest ./backend
docker build -t <registry>/careguard-frontend:latest ./frontend
docker push <registry>/careguard-backend:latest
docker push <registry>/careguard-frontend:latest
```

When the frontend is NOT served from the same origin as the API (e.g. separate
domains), build it with `VITE_API_BASE_URL=https://api.your-host` so the SPA
calls the API directly — and set CORS `allow_origins` accordingly in `main.py`.

---

## 4. Migrations

The schema is Alembic-owned. The backend container runs `alembic upgrade head`
on startup (the worker skips it via `RUN_MIGRATIONS=0` to avoid a race). To run
it by hand: `docker compose exec backend alembic upgrade head`.
