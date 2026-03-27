# TaskRaptor

Personal task manager with a Telegram bot interface and React web dashboard. Capture tasks via natural language in Telegram; manage them in the browser.

## Stack

| Layer | Choice |
|---|---|
| Backend | Django 5.1, Python 3.12 |
| API | Django Ninja (REST + OpenAPI) |
| Frontend | React 18 + Vite + Tailwind CSS |
| Auth | Session cookies + CSRF |
| Database | Postgres (tsvector, JSONB) |
| Queue | Celery + Redis + Celery Beat |
| Bot | Telegram webhook (M2) |
| Agent | Claude via Anthropic SDK (M3) |
| Deploy | Railway / Render |

## Project structure

```
taskraptor/
├── taskraptor/           # Django project
│   ├── settings/
│   │   ├── base.py       # Shared config
│   │   ├── local.py      # Dev overrides (reads .env)
│   │   └── production.py # Prod overrides (reads env vars)
│   ├── celery.py
│   └── urls.py           # API routers + SPA catch-all
├── apps/
│   ├── accounts/         # Custom User model (email auth), login/logout API
│   ├── tasks/            # Task model, full CRUD API
│   ├── channels/         # TelegramChannel stub (M2)
│   └── agent/            # Agent runner stub (M2)
├── frontend/             # React SPA
│   ├── src/
│   │   ├── api/          # Typed fetch wrappers (client, auth, tasks)
│   │   ├── pages/        # LoginPage, TasksPage
│   │   └── components/   # TaskItem, CreateTaskForm
│   └── vite.config.ts    # Dev proxy → :8000; prod base = /static/
└── tests/
    └── e2e/              # Real Postgres, zero mocks
```

## Getting started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node 20+
- [Task](https://taskfile.dev) (`brew install go-task`)
- Postgres running locally
- Redis running locally

### Setup

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd taskraptor

# 2. Copy env file and adjust if needed
cp .env.example .env

# 3. Create the database
psql postgres -c "CREATE DATABASE taskraptor;"

# 4. Install dependencies and migrate
task install
task migrate

# 5. Create an admin user
task createsuperuser
```

### Development

Run Django and Vite in separate terminals:

```bash
task run           # Django on http://localhost:8000
task frontend:dev  # Vite on http://localhost:5173
```

Open **http://localhost:5173** — Vite proxies all `/api/*` requests to Django. Session cookies and CSRF work transparently through the proxy.

## API

Auto-generated docs at **http://localhost:8000/api/docs** (Swagger UI).

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Start session |
| `POST` | `/api/auth/logout` | End session |
| `GET` | `/api/auth/me` | Current user |
| `GET` | `/api/tasks/` | List tasks |
| `POST` | `/api/tasks/` | Create task |
| `PATCH` | `/api/tasks/{id}` | Update task |
| `DELETE` | `/api/tasks/{id}` | Delete task |

## Environment variables

Loaded from `.env` in development (via `python-dotenv`). Copy `.env.example` to get started.

| Variable | Description | Default |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | Settings module to use | `taskraptor.settings.local` |
| `SECRET_KEY` | Django secret key | insecure dev key |
| `PGDATABASE` | Postgres database name | `taskraptor` |
| `PGUSER` | Postgres user | _(OS auth)_ |
| `PGPASSWORD` | Postgres password | _(OS auth)_ |
| `PGHOST` | Postgres host | `localhost` |
| `PGPORT` | Postgres port | `5432` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |

## Production

Build the frontend first — Django's `spa_view` reads `frontend/dist/index.html` directly, and whitenoise serves the assets at `/static/`.

```bash
task frontend:build
python manage.py collectstatic --no-input
```

Three processes to run (e.g. as separate Railway / Render services):

```bash
gunicorn taskraptor.wsgi          # web
celery -A taskraptor worker       # worker
celery -A taskraptor beat         # beat
```

## Testing

```bash
task test
```

Tests use a real Postgres database — no mocks. pytest-django creates and tears down `test_taskraptor` automatically. The E2E suite in `tests/e2e/test_task_flow.py` covers the full lifecycle: create user → login → create task → mark done → assert DB state → delete → logout.

## Milestones

| Milestone | Status | Description |
|---|---|---|
| M1 | ✅ Done | Auth + task CRUD + React dashboard + E2E harness |
| M2 | Planned | Telegram webhook, JOIN flow, agent via Celery |
| M3 | Planned | Full-text search (tsvector), tags, agent context |
| M4 | Planned | Celery Beat reminders pushed to Telegram |
| M5 | Planned | Read-only Google Calendar / iCal integration |
