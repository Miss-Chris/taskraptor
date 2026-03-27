FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=taskraptor.settings.production \
    PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b /usr/local/bin
ENV PATH="/root/.local/bin:${PATH}"

COPY pyproject.toml uv.lock manage.py Taskfile.yml ./
COPY taskraptor/ ./taskraptor/
COPY apps/ ./apps/

RUN uv sync --frozen --no-dev

COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
COPY docker/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && SECRET_KEY=build-time-secret \
       REDIS_URL=redis://localhost:6379/0 \
       PGDATABASE=taskraptor \
       PGUSER=postgres \
       PGPASSWORD=postgres \
       PGHOST=localhost \
       PGPORT=5432 \
       uv run python manage.py collectstatic --no-input

EXPOSE 8000

CMD ["/entrypoint.sh"]
