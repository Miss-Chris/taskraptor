# Self-Hosting TaskRaptor

This guide runs TaskRaptor with Docker Compose, Caddy, Redis, and an external PostgreSQL database. The production compose file does not start Postgres; use a managed database such as RDS, or run Postgres separately on the same EC2 instance.

## Architecture

- Caddy is the only public container and listens on port `80`.
- Caddy proxies `/api/*` to the Django API container.
- Caddy serves the built React app from `frontend/dist`.
- Redis is private to the Docker network and backs Celery.
- Django migrations run in a one-shot `init` container before the API, worker, and beat start.
- Celery worker processes chat, Telegram, and automation jobs.
- Celery beat dispatches due automations every minute.

## Prerequisites

- Docker and Docker Compose.
- Node.js and npm to build the frontend before deploy.
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

Build the frontend assets:

```bash
cd frontend
npm ci
npm run build
cd ..
```

Create the environment file:

```bash
cp env.example env.txt
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Paste the generated value into `SECRET_KEY`, then fill in the Postgres settings. At minimum, set:

```dotenv
SECRET_KEY=
PGHOST=
PGPORT=5432
PGDATABASE=taskraptor
PGUSER=taskraptor
PGPASSWORD=
PGSSLMODE=require
```

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

Pull the new code, rebuild frontend assets, then rebuild and restart containers:

```bash
git pull
cd frontend
npm ci
npm run build
cd ..
docker compose up -d --build
```

The `init` container runs migrations before the app services start.

## HTTPS and Domains

The default `config/Caddyfile` serves HTTP on port `80`:

```caddyfile
:80 {
    handle /api/* {
        reverse_proxy api:8000
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
        reverse_proxy api:8000
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
```

After the stack is running, reset the webhook:

```bash
docker compose exec api uv run python manage.py reset_telegram_webhook
```

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

If the frontend returns a blank or missing page, rebuild it and confirm `frontend/dist/index.html` exists:

```bash
cd frontend
npm ci
npm run build
cd ..
ls frontend/dist
```
