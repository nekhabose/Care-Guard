# CareGuard API — FastAPI + Celery share this image.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (better layer caching). pyproject is the manifest.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# App source
COPY . .

# Run as a non-root user (defense in depth).
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Entrypoint runs `alembic upgrade head` then starts the server. The worker
# overrides the command in docker-compose. Shell form so ${PORT} (set by Railway
# and other PaaS) expands; falls back to 8000 locally / in docker-compose.
COPY --chown=appuser:appuser docker-entrypoint.sh /app/docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
