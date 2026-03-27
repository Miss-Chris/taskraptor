#!/usr/bin/env sh
set -eu

uv run python manage.py migrate --noinput
exec uv run gunicorn taskraptor.wsgi:application --bind 0.0.0.0:${PORT:-8000}
