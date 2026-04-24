from __future__ import annotations

from collections.abc import Iterable

from accounts.models import User
from automations.models import Automation
from channels.models import Channel
from channels.services import get_conversation
from channels.web import get_or_create_default_web_channel
from channels.workflow import handle_system_message


def active_automation_channels(user: User) -> Iterable[Channel]:
    """Return channels that should receive user-level automation runs."""
    get_or_create_default_web_channel(user)
    return (
        Channel.objects.filter(user=user, archived_at__isnull=True)
        .order_by("created_at", "id")
        .select_related("user")
    )


def run_automation_on_active_channels(automation: Automation) -> int:
    """
    Execute an automation prompt once per active channel.

    The channel workflow resolves the channel's default conversation: the latest
    updated conversation, or a newly created conversation when none exists.
    """
    count = 0
    for channel in active_automation_channels(automation.user):
        get_conversation(channel.pk)
        handle_system_message(channel, automation.prompt)
        count += 1
    return count
