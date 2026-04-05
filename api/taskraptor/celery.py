import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "taskraptor.settings.local")

app = Celery("taskraptor")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
