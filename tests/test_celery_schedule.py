from django.conf import settings

from taskraptor.celery import app


def test_heartbeat_task_registered_in_beat_schedule():
    beat_entry = settings.CELERY_BEAT_SCHEDULE["worker-heartbeat-log-every-5-minutes"]

    assert beat_entry["task"] == "apps.tasks.tasks.log_worker_heartbeat"


def test_heartbeat_task_discovered_by_celery():
    app.loader.import_default_modules()

    assert "apps.tasks.tasks.log_worker_heartbeat" in app.tasks
