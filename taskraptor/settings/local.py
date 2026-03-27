import os

from .base import *  # noqa: F401, F403

DEBUG = True
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-local-dev-secret-key")
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": postgres_database_config(
        default_name="taskraptor",
        default_user="",
        default_password="",
        default_host="localhost",
        default_port="5432",
    )
}

CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

NINJA_CSRF = False
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

# Remove CSRF middleware entirely in dev — Vite serves the HTML so Django never
# gets to seed the CSRF cookie before the first POST. Production keeps it.
MIDDLEWARE = [m for m in MIDDLEWARE if m != "django.middleware.csrf.CsrfViewMiddleware"]
