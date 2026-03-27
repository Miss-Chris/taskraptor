#!/usr/bin/env sh
set -eu

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-taskraptor.settings.production}"

exec uv run celery -A taskraptor beat \
  --loglevel="${CELERY_LOG_LEVEL:-info}" \
  --schedule="${CELERY_BEAT_SCHEDULE_FILE:-/tmp/celerybeat-schedule}"
