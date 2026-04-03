import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def postgres_database_config(
    *,
    default_name: str,
    default_user: str,
    default_password: str,
    default_host: str,
    default_port: str,
) -> dict[str, str]:
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme not in {"postgres", "postgresql"}:
            raise ValueError("DATABASE_URL must use postgres:// or postgresql://")
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")) or default_name,
            "USER": unquote(parsed.username or default_user),
            "PASSWORD": unquote(parsed.password or default_password),
            "HOST": parsed.hostname or default_host,
            "PORT": str(parsed.port or default_port),
        }

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", default_name),
        "USER": os.environ.get("PGUSER", default_user),
        "PASSWORD": os.environ.get("PGPASSWORD", default_password),
        "HOST": os.environ.get("PGHOST", default_host),
        "PORT": os.environ.get("PGPORT", default_port),
    }

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ninja",
    "apps.accounts",
    "apps.tasks",
    "apps.channels",
    "apps.agent",
    "apps.agent2",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "taskraptor.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "taskraptor.wsgi.application"

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Vite builds into frontend/dist/; collectstatic picks it up from here.
STATICFILES_DIRS = [BASE_DIR / "frontend" / "dist"]
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Ninja API CSRF — disabled in local.py, enforced in production.py
NINJA_CSRF = True

# Sessions
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# CSRF — JS must be able to read this cookie to include it in mutation headers.
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

# Celery
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULER = "celery.beat:PersistentScheduler"
CELERY_BEAT_SCHEDULE = {
    "worker-heartbeat-log-every-5-minutes": {
        "task": "apps.tasks.tasks.log_worker_heartbeat",
        "schedule": crontab(minute="*/5"),
    },
    "dispatch-due-schedules": {
        "task": "apps.agent.tasks.dispatch_due_schedules",
        "schedule": crontab(minute="*"),
    },
}

# Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_BASE_URL = os.environ.get("TELEGRAM_WEBHOOK_BASE_URL", "")

# Anthropic
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
