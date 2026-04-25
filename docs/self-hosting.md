# Self-Hosting TaskRaptor

This guide runs TaskRaptor with Docker Compose, Caddy, Redis, and an external PostgreSQL database. The production compose file does not start Postgres; use a managed database such as RDS, or run Postgres separately on the same EC2 instance.

## Architecture

- Caddy is the only public container and listens on port `80`.
- Caddy proxies `/api/*` to the Django API container.
- Caddy serves React assets built into its Docker image.
- Redis is private to the Docker network, requires a password, and backs Celery.
- Django migrations run in a one-shot `init` container before the API, worker, and beat start.
- Celery worker processes chat, Telegram, and automation jobs.
- Celery beat dispatches due automations every minute.

## Prerequisites

- Docker and Docker Compose.
- A PostgreSQL database reachable from the Docker host.

For EC2, open inbound port `80` to the instance. If using RDS, allow the EC2 security group to connect to the RDS security group on port `5432`.

## Database Options

### RDS or Managed PostgreSQL

Create a PostgreSQL database and user for TaskRaptor. Use `PGSSLMODE=require` unless your provider documents a different setting.

Example env values:

```dotenv
PGHOST=taskraptor.xxxxxxxxxxxx.us-east-1.rds.amazonaws.com
PGPORT=5432
PGDATABASE=taskraptor
PGUSER=taskraptor
PGPASSWORD=replace-me
PGSSLMODE=require
```

### Local PostgreSQL on EC2

Install and manage Postgres outside Docker, create the database/user, and allow local Docker bridge connections. Use `PGSSLMODE=disable` unless you configure TLS locally.

Example env values:

```dotenv
PGHOST=172.17.0.1
PGPORT=5432
PGDATABASE=taskraptor
PGUSER=taskraptor
PGPASSWORD=replace-me
PGSSLMODE=disable
```

Depending on your Docker and Postgres configuration, `PGHOST` may be the host private IP instead of `172.17.0.1`.

## Setup

Create the environment file:

```bash
cp env.example env.txt
python -c "import secrets; print(secrets.token_urlsafe(50))"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Paste one generated value into `SECRET_KEY` and the other into `REDIS_PASSWORD`,
then fill in the Postgres settings. At minimum, set:

```dotenv
SECRET_KEY=
REDIS_PASSWORD=
PGHOST=
PGPORT=5432
PGDATABASE=taskraptor
PGUSER=taskraptor
PGPASSWORD=
PGSSLMODE=require
```

The backend dependencies are installed inside the API image with `uv sync --frozen --no-dev`.
The frontend is built inside the Caddy image with `npm ci && npm run build`, so the
EC2 host does not need Python packages, Node packages, or prebuilt `frontend/dist`
files outside Docker.

Start the stack:

```bash
docker compose up -d --build
```

Inspect logs:

```bash
docker compose logs -f api worker beat caddy
```

If migrations need to be run manually after a deploy:

```bash
docker compose run --rm init
```

## Upgrades

Pull the new code, rebuild images, then restart containers:

```bash
git pull
docker compose up -d --build
```

The `init` container runs migrations before the app services start. Do not run
`docker compose down` before building; if a new image build fails, the previous
running containers keep serving the last successful version.

## HTTPS and Domains

The default `config/Caddyfile` serves HTTP on port `80`:

```caddyfile
:80 {
    handle /api/* {
        reverse_proxy api:8000 {
            header_up X-Forwarded-Proto {scheme}
        }
    }

    handle {
        root * /srv/frontend
        try_files {path} /index.html
        file_server
    }
}
```

For a real domain with automatic HTTPS, point DNS at the server and replace `:80` with the domain:

```caddyfile
taskraptor.example.com {
    handle /api/* {
        reverse_proxy api:8000 {
            header_up X-Forwarded-Proto {scheme}
        }
    }

    handle {
        root * /srv/frontend
        try_files {path} /index.html
        file_server
    }
}
```

Then update `env.txt`:

```dotenv
ALLOWED_HOSTS=taskraptor.example.com,api
CSRF_TRUSTED_ORIGINS=https://taskraptor.example.com
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=true
SECURE_HSTS_PRELOAD=false
```

Expose ports `80` and `443` in `docker-compose.yml` if you enable HTTPS:

```yaml
ports:
  - "80:80"
  - "443:443"
```

## Telegram Webhooks

If you use Telegram, set these in `env.txt`:

```dotenv
TELEGRAM_BOT_NAME=your_bot_name
TELEGRAM_BOT_TOKEN=replace-me
TELEGRAM_WEBHOOK_BASE_URL=https://taskraptor.example.com
TELEGRAM_WEBHOOK_SECRET=replace-me
```

Generate `TELEGRAM_WEBHOOK_SECRET` with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

TaskRaptor registers that value with Telegram as `secret_token` and rejects
webhook requests whose `X-Telegram-Bot-Api-Secret-Token` header does not match.

After the stack is running, reset the webhook from the API container:

```bash
docker compose exec api uv run python manage.py reset_telegram_webhook
```

The HTTP `/api/telegram/reset-webhook` route is staff-only and is intended for
authenticated operator use, not public setup.

## Registration and System Model Quota

Public registration is enabled by default:

```dotenv
ALLOW_PUBLIC_REGISTRATION=true
```

For private instances, set it to `false` after creating the accounts you need.

New users receive a `system_free` model backed by `DEEPSEEK_API_KEY`. Control the
request quota assigned to newly created users with:

```dotenv
SYSTEM_FREE_MONTHLY_REQUEST_QUOTA=50
```

Set the quota to `0` if you want accounts to exist but not use the hosted
system model. Users can still add their own supported provider keys from the app.

## Redis

Compose requires `REDIS_PASSWORD` and starts Redis with `--requirepass`. Django
derives the default Celery broker/result URLs from that password:

```text
redis://:<REDIS_PASSWORD>@redis:6379/0
```

Only set `CELERY_BROKER_URL` or `CELERY_RESULT_BACKEND` if you are using an
external Redis or another Celery backend.

## Backups

TaskRaptor state lives in PostgreSQL. Back up the external database with your provider's snapshots or `pg_dump`.

Example:

```bash
PGSSLMODE=require pg_dump \
  --host "$PGHOST" \
  --port "$PGPORT" \
  --username "$PGUSER" \
  --dbname "$PGDATABASE" \
  --format custom \
  --file taskraptor.dump
```

Redis is used as a queue/result backend; it does not need to be backed up for normal recovery.

## Troubleshooting

Check container status:

```bash
docker compose ps
```

Check app logs:

```bash
docker compose logs -f api worker beat
```

Check Caddy routing:

```bash
curl http://localhost/api/openapi.json
```

If the frontend returns a blank or missing page, rebuild the Caddy image and
inspect the built assets inside the container:

```bash
docker compose build caddy
docker compose run --rm --entrypoint ls caddy /srv/frontend
```
