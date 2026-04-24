from taskraptor.settings.local import *  # noqa: F401, F403

# In-memory SQLite: no extra services, fast, good default for local/CI. JSON features
# differ from PostgreSQL (e.g. array containment); code paths that need PG can use
# a dedicated settings module or override DATABASES via env/CI to point at a real DB.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
