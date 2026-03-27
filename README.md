# TaskRaptor

Django + React task manager with a web dashboard and API.

## Local Dev

Requirements:

- Python 3.12+
- `uv`
- Node 20+
- `go-task`
- `overmind` (`brew install overmind`)
- local Postgres
- local Redis

Setup:

```bash
cp .env.example .env
psql postgres -c "CREATE DATABASE taskraptor;"
task install
task migrate
task createsuperuser
```

Run:

```bash
task dev
```

This uses [Procfile.dev](/Users/anirudh/work/taskraptor/Procfile.dev) with Overmind to run Django, Celery worker, Celery beat, and Vite together in one terminal.

Or run services separately:

```bash
task run
task worker
task beat
task frontend:dev
```

App: `http://localhost:5173`

API docs: `http://localhost:8000/api/docs`

## Deploying

This repo deploys to Railway with the included [Dockerfile](/Users/anirudh/work/taskraptor/Dockerfile).

One-time Railway setup:

1. Create `web`, `worker`, and `beat` services from this repo.
2. Add Railway Postgres and Railway Redis.
3. Set these variables on each service:

```bash
DJANGO_SETTINGS_MODULE=taskraptor.settings.production
SECRET_KEY=<strong-random-secret>
ALLOWED_HOSTS=dashboard.taskraptor.app,.up.railway.app
CSRF_TRUSTED_ORIGINS=https://dashboard.taskraptor.app,https://*.up.railway.app
PGDATABASE=...
PGUSER=...
PGPASSWORD=...
PGHOST=...
PGPORT=...
REDIS_URL=...
```

4. Use these start commands:

```bash
web: /entrypoint.sh
worker: task worker
beat: task beat
```

5. Add the custom domain to the `web` service and create the DNS records Railway asks for.

Deploy a new version:

```bash
git push origin main
railway up -s web -d
```

Healthcheck:

```bash
curl https://dashboard.taskraptor.app/healthz
```

What the deploy does:

- builds the frontend with `npm run build`
- runs `collectstatic` during image build
- runs `python manage.py migrate --noinput` on container start
- starts Gunicorn on `web`
- starts a Celery worker on `worker`
- starts Celery Beat on `beat`

Scheduled task verification:

- every 5 minutes, Beat enqueues `apps.tasks.tasks.log_worker_heartbeat`
- the `worker` service logs `Celery heartbeat test message` at `INFO`
- verify production by checking the `worker` service logs, not `web` or `beat`

## Testing

```bash
task test
```
