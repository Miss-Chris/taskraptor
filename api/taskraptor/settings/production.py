from decouple import Csv

from .env import config
from .local import *  # noqa: F401, F403

SECRET_KEY = config("SECRET_KEY")
DEBUG = False

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1,api",
    cast=Csv(),
)

_csrf_trusted_origins = config("CSRF_TRUSTED_ORIGINS", default="")
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in _csrf_trusted_origins.split(",")
    if origin.strip()
]

SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=False, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=False, cast=bool)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
    cast=bool,
)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=False, cast=bool)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("PGDATABASE"),
        "USER": config("PGUSER"),
        "PASSWORD": config("PGPASSWORD"),
        "HOST": config("PGHOST"),
        "PORT": config("PGPORT", default="5432"),
        "OPTIONS": {
            "sslmode": config("PGSSLMODE", default="require"),
        },
    }
}

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=CELERY_BROKER_URL)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "stream": "ext://sys.stdout",
        },
        "console_error": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console_error"],
            "level": "WARNING",
            "propagate": False,
        },
        "taskraptor": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "gunicorn.access": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "gunicorn.error": {
            "handlers": ["console_error"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
