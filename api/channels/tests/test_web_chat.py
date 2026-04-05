from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from agent.models import AgentRun
from channels.services import get_conversation
from channels.models import Channel, ChannelType, Conversation, WebChatMessage, WebChatRole
from channels.tests.scripted_llm import ScriptedLlm, tool_call_response
from channels.web import (
    create_web_conversation,
    get_chat_history,
    get_or_create_default_web_channel,
    handle_web_user_message,
)


@pytest.mark.django_db
def test_get_or_create_default_web_channel_idempotent(test_user):
    c1 = get_or_create_default_web_channel(test_user)
    assert c1.type == ChannelType.WEB
    c2 = get_or_create_default_web_channel(test_user)
    assert c1.pk == c2.pk
    assert Channel.objects.filter(user=test_user, type=ChannelType.WEB).count() == 1


@pytest.mark.django_db
def test_handle_web_user_message_records_user_and_assistant_messages(
    test_user,
    test_llm_model_offline,
):
    channel = Channel.objects.create(
        user=test_user,
        name="Web",
        type=ChannelType.WEB,
    )
    conversation = Conversation.objects.create(channel=channel)

    scripted = ScriptedLlm(
        [
            tool_call_response("create_task", {"name": "Web chat task"}),
            tool_call_response("respond_to_user", {"message": "Done."}),
        ]
    )
    result = handle_web_user_message(
        conversation,
        "Add a task from web",
        llm_callable=scripted,
    )
    scripted.assert_exhausted()
    assert result.error is None
    assert result.response_text == "Done."

    msgs = list(WebChatMessage.objects.filter(conversation=conversation).order_by("pk"))
    assert len(msgs) == 2
    assert msgs[0].role == WebChatRole.USER
    assert msgs[0].content == "Add a task from web"
    assert msgs[0].agent_run_id is None

    assert msgs[1].role == WebChatRole.ASSISTANT
    assert msgs[1].content == "Done."
    assert msgs[1].agent_run_id is not None

    run = AgentRun.objects.get(pk=msgs[1].agent_run_id)
    assert run.conversation_id == conversation.pk


@pytest.mark.django_db
def test_get_chat_history_tail_and_pagination(test_user):
    channel = get_or_create_default_web_channel(test_user)
    conv = create_web_conversation(channel, title="Paginated")

    for i in range(5):
        WebChatMessage.objects.create(
            conversation=conv,
            role=WebChatRole.USER if i % 2 == 0 else WebChatRole.ASSISTANT,
            content=f"m{i}",
        )

    tail = list(get_chat_history(conv.pk, limit=3))
    assert [m.content for m in tail] == ["m2", "m3", "m4"]

    before_id = tail[0].pk
    older = list(get_chat_history(conv.pk, limit=2, before_id=before_id))
    assert [m.content for m in older] == ["m0", "m1"]


@pytest.mark.django_db
def test_web_message_activity_updates_conversation_recency(
    test_user,
    test_llm_model_offline,
):
    channel = Channel.objects.create(
        user=test_user,
        name="Web",
        type=ChannelType.WEB,
    )
    older = Conversation.objects.create(channel=channel, title="Older")
    newer = Conversation.objects.create(channel=channel, title="Newer")
    Conversation.objects.filter(pk=older.pk).update(
        updated_at=timezone.now() - timedelta(days=1)
    )
    older.refresh_from_db()
    newer.refresh_from_db()
    assert older.updated_at < newer.updated_at

    scripted = ScriptedLlm(
        [
            tool_call_response("respond_to_user", {"message": "Done."}),
        ]
    )
    result = handle_web_user_message(
        older,
        "Bump this conversation",
        llm_callable=scripted,
    )
    scripted.assert_exhausted()
    assert result.error is None

    latest = get_conversation(channel.pk)
    assert latest.conversation.pk == older.pk
