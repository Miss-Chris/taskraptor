from decouple import config

SECRET_KEY = config("SECRET_KEY")

# DeepSeek API key for platform `system_free` LLM configs (per-user quota on `LlmModel`).
DEEPSEEK_API_KEY = config("DEEPSEEK_API_KEY", default="")
USER_SESSION_TTL_DAYS = config("USER_SESSION_TTL_DAYS", default=30, cast=int)

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "accounts",
    "tasks",
    "channels",
    "agent",
    "automations",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "taskraptor.urls"

WSGI_APPLICATION = "taskraptor.wsgi.application"
ASGI_APPLICATION = "taskraptor.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("PGDATABASE", default="taskraptor"),
        "USER": config("PGUSER", default=""),
        "PASSWORD": config("PGPASSWORD", default=""),
        "HOST": config("PGHOST", default="localhost"),
        "PORT": config("PGPORT", default="5432"),
        "TEST": {
            "NAME": config("PGDATABASE", default="taskraptor") + "_test",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

USE_TZ = True
