#!/usr/bin/env sh
set -eu

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-taskraptor.settings.production}"

exec uv run celery -A taskraptor worker \
  --loglevel="${CELERY_LOG_LEVEL:-info}" \
  --pool="${CELERY_WORKER_POOL:-solo}" \
  --concurrency="${CELERY_WORKER_CONCURRENCY:-1}" \
  --without-gossip \
  --without-mingle
