# TaskRaptor

TaskRaptor is an open-source task and automation app with a Django/Django Ninja API and a Vite/React frontend.

## Self-hosting

TaskRaptor includes a Docker Compose setup modeled around a single public Caddy endpoint, a Django API container, Redis, Celery worker/beat containers, and an external PostgreSQL database.

See [`docs/self-hosting.md`](/Users/anirudh/work/taskraptor/docs/self-hosting.md) for the full setup guide.

## Local setup

From [`/Users/anirudh/work/taskraptor/api`](/Users/anirudh/work/taskraptor/api):

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

Celery assumes a local Redis server is available at `redis://127.0.0.1:6379/0` unless `CELERY_BROKER_URL` is set.

Run the worker with auto-reload:

```bash
uv run python manage.py runworker
```

Run beat:

```bash
uv run celery -A taskraptor beat --loglevel=info
```

Beat dispatches due automations every minute. Each automation runs once per local calendar day after its configured `schedule_time`, based on the owning user's timezone.
