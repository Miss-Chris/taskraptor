#!/bin/bash
set -e

echo "========================================="
echo "TaskRaptor API Initialization"
echo "========================================="

echo "Running database migrations..."
uv run python manage.py migrate --noinput

echo "========================================="
echo "Initialization complete!"
echo "========================================="
