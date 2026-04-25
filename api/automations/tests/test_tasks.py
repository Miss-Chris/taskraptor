from __future__ import annotations

import datetime
from uuid import UUID

import pytest
from django.utils import timezone

from automations.models import Automation
from automations.services import run_automation_on_active_channels
from automations.tasks import (
    dispatch_due_automations,
    run_automation,
    run_automation_immediately,
)
from channels.models import Channel, ChannelType, Conversation


@pytest.mark.django_db
def test_dispatch_due_automations_enqueues_only_due_rows(monkeypatch, test_user):
    test_user.timezone = "UTC"
    test_user.save(update_fields=["timezone"])
    now = datetime.datetime(2026, 4, 5, 15, 0, tzinfo=datetime.UTC)
    queued_ids: list[str] = []

    due = Automation.objects.create(
        user=test_user,
        prompt="Run now",
        schedule_time=datetime.time(14, 0),
    )
    Automation.objects.create(
        user=test_user,
        prompt="Too early",
        schedule_time=datetime.time(16, 0),
    )
    Automation.objects.create(
        user=test_user,
        prompt="Already ran",
        schedule_time=datetime.time(13, 0),
        last_run_at=now - datetime.timedelta(hours=1),
    )
    Automation.objects.create(
        user=test_user,
        prompt="Inactive",
        schedule_time=datetime.time(13, 0),
        is_active=False,
    )

    monkeypatch.setattr("automations.tasks.timezone.now", lambda: now)
    monkeypatch.setattr(run_automation, "delay", queued_ids.append)

    queued = dispatch_due_automations()

    assert queued == 1
    assert queued_ids == [str(due.pk)]


@pytest.mark.django_db
def test_run_automation_executes_and_marks_last_run_at(monkeypatch, test_user):
    automation = Automation.objects.create(
        user=test_user,
        prompt="Run automation",
        schedule_time=datetime.time(9, 0),
    )
    now = datetime.datetime(2026, 4, 5, 15, 0, tzinfo=datetime.UTC)
    calls: list[tuple[UUID, str]] = []

    monkeypatch.setattr("automations.tasks.timezone.now", lambda: now)
    monkeypatch.setattr(
        "automations.services.handle_system_message",
        lambda channel, prompt: calls.append((channel.pk, prompt)),
    )

    ran = run_automation(automation.pk)

    automation.refresh_from_db()
    assert ran is True
    web = Channel.objects.get(user=test_user, type=ChannelType.WEB)
    assert calls == [(web.pk, "Run automation")]
    assert automation.last_run_at == now


@pytest.mark.django_db
def test_run_automation_skips_when_already_run_today_in_user_timezone(
    monkeypatch,
    test_user,
):
    test_user.timezone = "America/New_York"
    test_user.save(update_fields=["timezone"])
    now = datetime.datetime(2026, 4, 5, 15, 0, tzinfo=datetime.UTC)
    automation = Automation.objects.create(
        user=test_user,
        prompt="Already handled",
        schedule_time=datetime.time(9, 0),
        last_run_at=datetime.datetime(2026, 4, 5, 13, 30, tzinfo=datetime.UTC),
    )
    called = False

    monkeypatch.setattr("automations.tasks.timezone.now", lambda: now)

    def _unexpected_call(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("automations.services.handle_system_message", _unexpected_call)

    ran = run_automation(automation.pk)

    assert ran is False
    assert called is False


@pytest.mark.django_db
def test_automation_runs_at_user_local_wall_clock_time(monkeypatch, test_user):
    test_user.timezone = "America/Los_Angeles"
    test_user.save(update_fields=["timezone"])
    automation = Automation.objects.create(
        user=test_user,
        prompt="Local 9am",
        schedule_time=datetime.time(9, 0),
    )
    now = datetime.datetime(2026, 4, 5, 16, 0, tzinfo=datetime.UTC)

    monkeypatch.setattr("automations.tasks.timezone.now", lambda: now)
    monkeypatch.setattr("automations.services.handle_system_message", lambda *_: None)

    assert run_automation(automation.pk) is True


@pytest.mark.django_db
def test_automation_dst_fall_back_does_not_double_run_same_local_day(
    monkeypatch,
    test_user,
):
    test_user.timezone = "America/New_York"
    test_user.save(update_fields=["timezone"])
    automation = Automation.objects.create(
        user=test_user,
        prompt="DST",
        schedule_time=datetime.time(1, 30),
        last_run_at=datetime.datetime(2026, 11, 1, 5, 35, tzinfo=datetime.UTC),
    )
    second_130 = datetime.datetime(2026, 11, 1, 6, 35, tzinfo=datetime.UTC)
    called = False

    monkeypatch.setattr("automations.tasks.timezone.now", lambda: second_130)

    def _unexpected_call(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("automations.services.handle_system_message", _unexpected_call)

    assert run_automation(automation.pk) is False
    assert called is False


@pytest.mark.django_db
def test_run_automation_fans_out_to_active_channels_and_creates_default_web(
    monkeypatch,
    test_user,
):
    telegram = Channel.objects.create(
        user=test_user,
        name="Telegram",
        type=ChannelType.TELEGRAM,
        external_id="123",
    )
    archived = Channel.objects.create(
        user=test_user,
        name="Old Telegram",
        type=ChannelType.TELEGRAM,
        external_id="456",
        archived_at=timezone.now(),
    )
    dummy = Channel.objects.create(
        user=test_user,
        name="Dummy",
        type=ChannelType.DUMMY,
    )
    dummy_conversation = Conversation.objects.create(channel=dummy)
    automation = Automation.objects.create(
        user=test_user,
        prompt="Fan out",
        schedule_time=datetime.time(9, 0),
    )
    calls: list[tuple[UUID, str]] = []

    monkeypatch.setattr(
        "automations.services.handle_system_message",
        lambda channel, prompt: calls.append((channel.pk, prompt)),
    )

    count = run_automation_on_active_channels(automation)

    web = Channel.objects.get(user=test_user, type=ChannelType.WEB)
    assert count == 3
    assert calls == [
        (telegram.pk, "Fan out"),
        (dummy.pk, "Fan out"),
        (web.pk, "Fan out"),
    ]
    assert archived.pk not in {channel_id for channel_id, _ in calls}
    assert Conversation.objects.filter(channel=web).exists()
    assert Conversation.objects.filter(pk=dummy_conversation.pk).exists()


@pytest.mark.django_db
def test_run_automation_immediately_bypasses_due_and_active_checks(
    monkeypatch,
    test_user,
):
    now = datetime.datetime(2026, 4, 5, 15, 0, tzinfo=datetime.UTC)
    automation = Automation.objects.create(
        user=test_user,
        prompt="Force run",
        schedule_time=datetime.time(23, 59),
        is_active=False,
    )
    calls: list[tuple[UUID, str]] = []

    monkeypatch.setattr("automations.tasks.timezone.now", lambda: now)
    monkeypatch.setattr(
        "automations.services.handle_system_message",
        lambda channel, prompt: calls.append((channel.pk, prompt)),
    )

    ran = run_automation_immediately(automation.pk)

    automation.refresh_from_db()
    web = Channel.objects.get(user=test_user, type=ChannelType.WEB)
    assert ran is True
    assert calls == [(web.pk, "Force run")]
    assert automation.last_run_at == now


@pytest.mark.django_db
def test_run_automation_immediately_returns_false_for_missing_automation():
    assert (
        run_automation_immediately(UUID("00000000-0000-0000-0000-000000000000"))
        is False
    )
