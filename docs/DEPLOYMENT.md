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
`BOOTSTRAP_ADMIN_PASSWORD` (defaults `admin@careguard.health` / `ChangeMe123!`).
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

## 4. Vercel (frontend) + Railway (backend)

The split-host path: the Vite SPA on Vercel, the FastAPI + Postgres on Railway.
The SPA calls the API cross-origin, so set `VITE_API_BASE_URL` (Vercel) and
`CORS_ALLOW_ORIGINS` (Railway) to point them at each other.

### A. Backend → Railway

1. **New Project → Deploy from GitHub repo** → pick this repo.
2. On the service: **Settings → Root Directory = `backend`** (monorepo). Railway
   reads `backend/railway.json` and builds `backend/Dockerfile`. The container
   runs `alembic upgrade head` on boot and binds Railway's `$PORT` automatically.
3. **Add a database:** *New → Database → PostgreSQL*. (Redis + a Celery worker
   service are optional — only the scheduled-outreach path needs them; on-demand
   "call now" works without them.)
4. **Variables** on the backend service:
   ```
   ENVIRONMENT=development            # demo/mock; see §2 to go production
   DATABASE_URL=${{Postgres.DATABASE_URL}}   # reference var; auto-normalized to asyncpg
   JWT_SECRET=<python -c "import secrets;print(secrets.token_hex(32))">
   BOOTSTRAP_ADMIN_EMAIL=admin@careguard.health
   BOOTSTRAP_ADMIN_PASSWORD=<a strong password>
   FHIR_PROVIDER=mock
   NOTIFICATION_PROVIDER=noop
   CORS_ALLOW_ORIGINS=https://<your-app>.vercel.app   # set after step B
   ```
5. **Settings → Networking → Generate Domain.** Note the URL, e.g.
   `https://careguard-backend.up.railway.app`. Check `…/health` returns `ok`.

### B. Frontend → Vercel

1. **Add New → Project** → import this repo. **Root Directory = `frontend`.**
   Vercel reads `frontend/vercel.json` (Vite build + SPA fallback).
2. **Environment Variable:** `VITE_API_BASE_URL = https://<your-backend>.up.railway.app`
   (the Railway domain from step A.5).
3. **Deploy.** Then copy the Vercel domain back into the backend's
   `CORS_ALLOW_ORIGINS` (step A.4) and redeploy the Railway service.
4. Open the Vercel URL → sign in with the bootstrap admin → **Patients → Onboard**
   to add a test patient with your own mobile and verify a call.

### CLI alternative

```bash
# Frontend
cd frontend && vercel login && vercel --prod      # set VITE_API_BASE_URL in the dashboard/env

# Backend
npm i -g @railway/cli && railway login
cd backend && railway init && railway up           # add Postgres + vars in the dashboard
```

> Real outreach calls still need Twilio creds (`TWILIO_ACCOUNT_SID/AUTH_TOKEN/
> PHONE_NUMBER`) on the Railway service; without them the call path returns a
> clear "Twilio is not configured" error instead of dialing.

---

## 5. Migrations

The schema is Alembic-owned. The backend container runs `alembic upgrade head`
on startup (the worker skips it via `RUN_MIGRATIONS=0` to avoid a race). To run
it by hand: `docker compose exec backend alembic upgrade head`.
