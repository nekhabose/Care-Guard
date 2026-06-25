# Database migrations (Alembic)

Alembic **owns the schema**. The app no longer creates tables at startup
(`Base.metadata.create_all` was removed from `main.py`'s lifespan), so you must
run migrations before the app can serve traffic.

Run from the `backend/` directory (env.py reads `DATABASE_URL` from your app
settings):

```bash
# Apply all pending migrations (required before starting the app)
alembic upgrade head

# Inspect / roll back
alembic current
alembic history
alembic downgrade -1

# Author a new migration from model changes
alembic revision --autogenerate -m "describe change"
```

## Migrations

- **`0001_initial_schema`** — baseline of all current tables. Creates each table
  only if absent, so it's safe against a database that the old `create_all` path
  already populated.
- **`0002_call_opt_out`** — adds `patients.call_opt_out`. Idempotent (checks for
  the column first).

## Existing databases (built by the old `create_all`)

Just run `alembic upgrade head`. The baseline no-ops the tables that already
exist and `0002` adds the new `call_opt_out` column — **no `alembic stamp`
needed**, thanks to the idempotent guards. (Verified against PostgreSQL for both
a fresh DB and a pre-existing `create_all` DB.)

## Fresh databases

`alembic upgrade head` builds the full schema from scratch.
