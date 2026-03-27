#!/usr/bin/env sh
set -eu

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-taskraptor.settings.production}"

case "${SERVICE_ROLE:-web}" in
  web)
    uv run python manage.py migrate --noinput
    exec uv run gunicorn taskraptor.wsgi:application --bind 0.0.0.0:${PORT:-8000}
    ;;
  worker)
    exec /start-worker.sh
    ;;
  beat)
    exec /start-beat.sh
    ;;
  *)
    echo "Unknown SERVICE_ROLE: ${SERVICE_ROLE}" >&2
    exit 1
    ;;
esac
