# TaskRaptor

Django + React task manager with a web dashboard and API.

## Local Dev

Requirements:

- Python 3.12+
- `uv`
- Node 20+
- `go-task`
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
task run
task frontend:dev
```

App: `http://localhost:5173`

API docs: `http://localhost:8000/api/docs`

## Deploying

This repo deploys to Railway with the included [Dockerfile](/Users/anirudh/work/taskraptor/Dockerfile).

One-time Railway setup:

1. Create a `web` service.
2. Add Railway Postgres and Railway Redis.
3. Set these `web` service variables:

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

4. Add the custom domain in Railway and create the DNS records Railway asks for.

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
- starts Gunicorn

## Testing

```bash
task test
```
