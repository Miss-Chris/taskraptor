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

Production uses one Docker image for all app services. Railway decides whether a service runs the Django app, Celery worker, or Celery Beat by setting `SERVICE_ROLE`:

- `web`: runs migrations, then starts Gunicorn
- `worker`: starts Celery worker
- `beat`: starts Celery Beat

Production worker defaults are intentionally conservative to keep Railway CPU and memory usage down:

- `CELERY_WORKER_POOL=solo`
- `CELERY_WORKER_CONCURRENCY=1`

Override those only if queue throughput actually requires more parallelism.

One-time Railway setup:

1. Create `web`, `worker`, and `beat` services from this repo.
2. Add Railway Postgres and Railway Redis.
3. Put the common Django settings in one place. Railway shared variables are the cleanest option:

```bash
SECRET_KEY=<strong-random-secret>
ALLOWED_HOSTS=dashboard.taskraptor.app,.up.railway.app
CSRF_TRUSTED_ORIGINS=https://dashboard.taskraptor.app,https://*.up.railway.app
DJANGO_SETTINGS_MODULE=taskraptor.settings.production
```

If you do not want to use Railway shared variables, keep those values on `web` and make `worker` / `beat` reference `web` instead:

```bash
SECRET_KEY=${{web.SECRET_KEY}}
ALLOWED_HOSTS=${{web.ALLOWED_HOSTS}}
CSRF_TRUSTED_ORIGINS=${{web.CSRF_TRUSTED_ORIGINS}}
DJANGO_SETTINGS_MODULE=${{web.DJANGO_SETTINGS_MODULE}}
```

4. On each service, add these service-specific variables:

```bash
web: SERVICE_ROLE=web
worker: SERVICE_ROLE=worker
beat: SERVICE_ROLE=beat
```

5. On each service, add reference variables so all three point at the same databases:

```bash
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
```

You can also reference the individual Postgres variables if you want them for debugging or another tool:

```bash
PGDATABASE=${{Postgres.PGDATABASE}}
PGUSER=${{Postgres.PGUSER}}
PGPASSWORD=${{Postgres.PGPASSWORD}}
PGHOST=${{Postgres.PGHOST}}
PGPORT=${{Postgres.PGPORT}}
```

Railway reference variable syntax:

- shared variable: `${{ shared.VARIABLE_KEY }}`
- another service: `${{SERVICE_NAME.VAR}}`
- same service: `${{ VARIABLE_NAME }}`

6. Leave the Railway start command empty for all three services so they use the image entrypoint:

```bash
/entrypoint.sh
```

7. Add the custom domain to the `web` service and create the DNS records Railway asks for.

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
