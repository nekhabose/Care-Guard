#!/usr/bin/env bash
# Apply DB migrations before serving, then exec the given command (server/worker).
# Alembic owns the schema (no create_all); migrations are idempotent.
set -euo pipefail

# Only the web process should run migrations. Workers set RUN_MIGRATIONS=0 so two
# containers don't race the migration at the same time.
if [[ "${RUN_MIGRATIONS:-1}" == "1" ]]; then
  echo "[entrypoint] Running alembic upgrade head…"
  alembic upgrade head
fi

exec "$@"
