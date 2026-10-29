# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY . .

RUN chmod +x init.sh && \
    addgroup --system taskraptor && \
    adduser --system --ingroup taskraptor taskraptor && \
    chown -R taskraptor:taskraptor /app

ENV HOME=/app
EXPOSE 8000

USER taskraptor

CMD ["sh", "-c", "./init.sh && exec uv run gunicorn --bind 0.0.0.0:8000 --workers 1 --timeout 120 --access-logfile - --error-logfile - --capture-output taskraptor.wsgi:application"]
