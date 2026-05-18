from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from channels.models import Channel, ChannelType
from tasks.models import TaskStatus
from tasks.reminders import build_task_reminder_prompt, run_task_reminder_on_active_channels
from tasks.services import create_task
from tasks.tasks import dispatch_due_task_reminders, run_task_reminder

User = get_user_model()


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        email="task_reminders@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
def test_dispatch_due_task_reminders_enqueues_only_due_active_rows(monkeypatch, test_user):
    test_user.timezone = "UTC"
    test_user.save(update_fields=["timezone"])
    now = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    due = create_task(
        user_id=test_user.pk,
        name="Due",
        remind_at=timezone.now() + timedelta(days=1),
    )
    due.remind_at = now - timedelta(minutes=1)
    due.save(update_fields=["remind_at"])
    create_task(user_id=test_user.pk, name="Future", remind_at=timezone.now() + timedelta(days=1))
    fired = create_task(user_id=test_user.pk, name="Fired", remind_at=timezone.now() + timedelta(days=1))
    fired.remind_at = now - timedelta(minutes=1)
    fired.reminded_at = now - timedelta(seconds=30)
    fired.save(update_fields=["remind_at", "reminded_at"])
    completed = create_task(user_id=test_user.pk, name="Done", remind_at=timezone.now() + timedelta(days=1))
    completed.remind_at = now - timedelta(minutes=1)
    completed.status = TaskStatus.COMPLETED
    completed.save(update_fields=["remind_at", "status"])
    queued_ids: list[str] = []

    monkeypatch.setattr("tasks.tasks.timezone.now", lambda: now)
    monkeypatch.setattr(run_task_reminder, "delay", queued_ids.append)

    assert dispatch_due_task_reminders() == 1
    assert queued_ids == [str(due.pk)]


@pytest.mark.django_db
def test_run_task_reminder_executes_once_and_marks_reminded_at(monkeypatch, test_user):
    test_user.timezone = "UTC"
    test_user.save(update_fields=["timezone"])
    now = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    task = create_task(user_id=test_user.pk, name="Call mom", remind_at=timezone.now() + timedelta(days=1))
    task.remind_at = now - timedelta(minutes=1)
    task.save(update_fields=["remind_at"])
    calls: list[tuple[UUID, str]] = []

    monkeypatch.setattr("tasks.tasks.timezone.now", lambda: now)
    monkeypatch.setattr(
        "tasks.reminders.handle_system_message",
        lambda channel, prompt: calls.append((channel.pk, prompt)),
    )

    assert run_task_reminder(task.pk) is True
    assert run_task_reminder(task.pk) is False
    task.refresh_from_db()
    web = Channel.objects.get(user=test_user, type=ChannelType.WEB)
    assert calls == [(web.pk, build_task_reminder_prompt(task))]
    assert task.reminded_at == now


@pytest.mark.django_db
def test_run_task_reminder_skips_when_user_timezone_missing(monkeypatch, test_user):
    now = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    task = create_task(user_id=test_user.pk, name="No timezone", remind_at=timezone.now() + timedelta(days=1))
    task.remind_at = now - timedelta(minutes=1)
    task.save(update_fields=["remind_at"])
    called = False

    monkeypatch.setattr("tasks.tasks.timezone.now", lambda: now)

    def _unexpected_call(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("tasks.reminders.handle_system_message", _unexpected_call)

    assert run_task_reminder(task.pk) is False
    assert called is False


@pytest.mark.django_db
def test_run_task_reminder_fans_out_to_active_channels(monkeypatch, test_user):
    telegram = Channel.objects.create(
        user=test_user,
        name="Telegram",
        type=ChannelType.TELEGRAM,
        external_id="123",
    )
    archived = Channel.objects.create(
        user=test_user,
        name="Old",
        type=ChannelType.DUMMY,
    )
    archived.archived_at = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    archived.save(update_fields=["archived_at"])
    task = create_task(user_id=test_user.pk, name="Fan out")
    calls: list[tuple[UUID, str]] = []

    monkeypatch.setattr(
        "tasks.reminders.handle_system_message",
        lambda channel, prompt: calls.append((channel.pk, prompt)),
    )

    assert run_task_reminder_on_active_channels(task) == 2
    web = Channel.objects.get(user=test_user, type=ChannelType.WEB)
    assert calls == [
        (telegram.pk, build_task_reminder_prompt(task)),
        (web.pk, build_task_reminder_prompt(task)),
    ]
