"""
Offline workflow tests using ScriptedLlm.

These run in every default pytest invocation (no live_api marker required)
and make no network calls. Tool execution, message persistence, AgentRun
bookkeeping, and channel delivery all run against the real test database.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone

from agent.models import AgentRun, AgentRunStatus, MessageLog
from channels.models import Conversation
from channels.runtime import DummyConversation
from channels.services import get_conversation
from channels.workflow import handle_system_message, handle_user_incoming
from tasks.models import Task

from channels.tests.scripted_llm import ScriptedLlm, text_response, tool_call_response


class CapturingTextLlm:
    def __init__(self, content: str = "Done.") -> None:
        self.content = content
        self.calls: list[list[dict[str, Any]]] = []

    def __call__(self, llm_model: Any, messages: Any, **kwargs: Any) -> Any:
        self.calls.append(list(messages))
        return text_response(self.content)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(conversation, message, *responses):
    """Run one turn with the given scripted responses and return (result, scripted)."""
    scripted = ScriptedLlm(list(responses))
    result = handle_user_incoming(conversation, message, llm_callable=scripted)
    scripted.assert_exhausted()
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_multi_turn_workflow_scripted(
    test_user,
    test_llm_model_offline,
    test_channel,
    test_conversation,
):
    """
    Four-turn offline replica of the live acceptance test:

      1. "Add a task to buy milk"          -> create_task + respond_to_user
      2. "I need to call my cousin"        -> create_task + respond_to_user
      3. "Change milk task to buy cookies" -> edit_task  + respond_to_user
      4. "What are my tasks?"              -> query_tasks + respond_to_user

    All tool calls execute against the real test DB. The only fake is
    the LLM response sequence.
    """
    conversation = test_conversation

    # -- Turn 1: create "buy milk" task ------------------------------------
    result1 = _run(
        conversation,
        "Add a task to buy milk",
        tool_call_response("create_task", {"name": "Buy milk"}),
        tool_call_response("respond_to_user", {"message": "I've added 'Buy milk' to your tasks."}),
    )
    assert result1.error is None
    assert result1.response_text == "I've added 'Buy milk' to your tasks."

    milk_task = Task.objects.filter(user=test_user, name="Buy milk").first()
    assert milk_task is not None, "Turn 1 should have created a 'Buy milk' task"

    # -- Turn 2: create "call cousin" task ---------------------------------
    result2 = _run(
        conversation,
        "I need to call my cousin",
        tool_call_response("create_task", {"name": "Call my cousin"}),
        tool_call_response("respond_to_user", {"message": "I've added 'Call my cousin' to your tasks."}),
    )
    assert result2.error is None
    assert result2.response_text == "I've added 'Call my cousin' to your tasks."

    cousin_task = Task.objects.filter(user=test_user, name="Call my cousin").first()
    assert cousin_task is not None, "Turn 2 should have created a 'Call my cousin' task"

    # -- Turn 3: edit milk -> cookies (task_id known from DB) --------------
    result3 = _run(
        conversation,
        "On second thoughts I already have milk, let's change that to buy cookies",
        tool_call_response("edit_task", {"task_id": milk_task.pk, "name": "Buy cookies"}),
        tool_call_response("respond_to_user", {"message": "Done! I've updated 'Buy milk' to 'Buy cookies'."}),
    )
    assert result3.error is None
    milk_task.refresh_from_db()
    assert milk_task.name == "Buy cookies", "edit_task should have renamed the milk task"

    # -- Turn 4: query tasks and respond -----------------------------------
    result4 = _run(
        conversation,
        "What are my tasks?",
        tool_call_response(
            "query_tasks",
            {},
        ),
        tool_call_response(
            "respond_to_user",
            {"message": "You have 2 tasks: 'Buy cookies' and 'Call my cousin'."},
        ),
    )
    assert result4.error is None
    assert result4.response_text == "You have 2 tasks: 'Buy cookies' and 'Call my cousin'."

    # -- Cross-turn structural assertions ----------------------------------

    agent_runs = AgentRun.objects.filter(conversation=conversation)
    assert agent_runs.count() == 4, f"Expected 4 AgentRun rows, got {agent_runs.count()}"
    assert all(r.status == AgentRunStatus.COMPLETED for r in agent_runs), (
        "All AgentRun rows should be COMPLETED"
    )

    log_count = MessageLog.objects.filter(conversation=conversation).count()
    assert log_count > 4, (
        f"Expected more MessageLog rows than turns (>4), got {log_count}"
    )

    active_tasks = Task.objects.filter(user=test_user, deleted_at__isnull=True)
    assert active_tasks.count() == 2, (
        f"Expected 2 active tasks (cookies + cousin), got {active_tasks.count()}"
    )

    sent = DummyConversation._sent.get(conversation.pk, [])
    assert len(sent) == 4, (
        f"Expected 4 outgoing messages via DummyConversation, got {len(sent)}"
    )
    assert sent[2] == "Done! I've updated 'Buy milk' to 'Buy cookies'."
    assert sent[3] == "You have 2 tasks: 'Buy cookies' and 'Call my cousin'."


@pytest.mark.django_db
def test_agent_run_marked_failed_on_script_exhausted(
    test_user,
    test_llm_model_offline,
    test_channel,
    test_conversation,
):
    """
    If the scripted LLM runs out of responses mid-loop, run_agent catches the
    exception and returns an AgentResult with error set. handle_user_incoming
    then marks the AgentRun as FAILED.
    """
    scripted = ScriptedLlm([
        tool_call_response("create_task", {"name": "Some task"}),
        # No respond_to_user scripted -- script exhausted on the next LLM call
    ])

    result = handle_user_incoming(test_conversation, "Add a task", llm_callable=scripted)

    assert result.error is not None
    assert "ScriptExhausted" in result.error or "ran out" in result.error

    run = AgentRun.objects.filter(conversation=test_conversation).order_by("-created_at").first()
    assert run is not None
    assert run.status == AgentRunStatus.FAILED


@pytest.mark.django_db
def test_workflow_delivers_plain_assistant_fallback(
    test_user,
    test_llm_model_offline,
    test_channel,
    test_conversation,
):
    """
    Some models complete a turn by returning plain assistant text after a tool
    call instead of calling respond_to_user. The workflow should still deliver
    that final assistant text to the channel.
    """
    DummyConversation._sent.clear()

    result = handle_user_incoming(
        test_conversation,
        "Add a task to buy milk",
        llm_callable=ScriptedLlm([
            tool_call_response("create_task", {"name": "Buy milk"}),
            text_response("Done! I've added Buy milk to your tasks."),
        ]),
    )

    assert result.error is None
    assert result.response_text == "Done! I've added Buy milk to your tasks."
    assert DummyConversation._sent.get(test_conversation.pk) == [
        "Done! I've added Buy milk to your tasks."
    ]


@pytest.mark.django_db
def test_handle_system_message_creates_conversation_and_runs_agent(
    test_user,
    test_llm_model_offline,
    test_channel,
):
    """
    System-initiated turn uses the latest-or-new conversation and runs the same
    agent loop as user messages.
    """
    DummyConversation._sent.clear()

    assert Conversation.objects.filter(channel=test_channel).count() == 0

    result = handle_system_message(
        test_channel,
        "List my top tasks",
        llm_callable=ScriptedLlm([
            tool_call_response("respond_to_user", {"message": "Here are your top tasks."}),
        ]),
    )

    assert result.error is None
    assert result.response_text == "Here are your top tasks."

    convos = Conversation.objects.filter(channel=test_channel)
    assert convos.count() == 1
    conversation = convos.first()
    assert conversation is not None

    run = AgentRun.objects.filter(conversation=conversation).order_by("-created_at").first()
    assert run is not None
    assert run.status == AgentRunStatus.COMPLETED

    sent = DummyConversation._sent.get(conversation.pk, [])
    assert sent == ["Here are your top tasks."]


@pytest.mark.django_db
def test_workflow_passes_user_prompt_instructions_into_system_message(
    test_user,
    test_llm_model_offline,
    test_channel,
    test_conversation,
):
    test_user.prompt_instructions = "Always include a short next-steps section."
    test_user.save(update_fields=["prompt_instructions"])
    test_llm_model_offline.context_message_limit = 2
    test_llm_model_offline.save(update_fields=["context_message_limit"])

    prior_run = AgentRun.objects.create(
        channel=test_channel,
        conversation=test_conversation,
        user=test_user,
        llm_model=test_llm_model_offline,
        status=AgentRunStatus.COMPLETED,
        started_at=timezone.now(),
        completed_at=timezone.now(),
    )
    MessageLog.objects.create(
        agent_run=prior_run,
        conversation=test_conversation,
        channel=test_channel,
        actor="user",
        content="first request",
    )
    MessageLog.objects.create(
        agent_run=prior_run,
        conversation=test_conversation,
        channel=test_channel,
        actor="assistant",
        content="first reply",
    )
    MessageLog.objects.create(
        agent_run=prior_run,
        conversation=test_conversation,
        channel=test_channel,
        actor="user",
        content="second request",
    )
    MessageLog.objects.create(
        agent_run=prior_run,
        conversation=test_conversation,
        channel=test_channel,
        actor="assistant",
        content="second reply",
    )

    scripted = CapturingTextLlm()

    result = handle_user_incoming(
        test_conversation,
        "latest request",
        llm_callable=scripted,
    )

    assert result.error is None
    assert scripted.calls, "Expected the LLM callable to be invoked"

    first_call_messages = scripted.calls[0]
    assert first_call_messages[0]["role"] == "system"
    assert "## User-Specific Standing Instructions" in first_call_messages[0]["content"]
    assert "Always include a short next-steps section." in first_call_messages[0]["content"]

    non_system_messages = first_call_messages[1:]
    assert len(non_system_messages) == 3
    assert non_system_messages[0]["role"] == "user"
    assert non_system_messages[0]["content"] == "second request"
    assert non_system_messages[1]["role"] == "assistant"
    assert non_system_messages[1]["content"] == "second reply"
    assert non_system_messages[2]["role"] == "user"
    assert non_system_messages[2]["content"] == "latest request"


@pytest.mark.django_db
def test_workflow_touches_dummy_conversation_recency(
    test_user,
    test_llm_model_offline,
    test_channel,
):
    older = Conversation.objects.create(channel=test_channel, title="Older")
    newer = Conversation.objects.create(channel=test_channel, title="Newer")
    Conversation.objects.filter(pk=older.pk).update(
        updated_at=timezone.now() - timedelta(days=1)
    )
    older.refresh_from_db()
    newer.refresh_from_db()
    assert older.updated_at < newer.updated_at

    result = _run(
        older,
        "Ping older conversation",
        tool_call_response("respond_to_user", {"message": "Done."}),
    )
    assert result.error is None

    latest = get_conversation(test_channel.pk)
    assert latest.conversation.pk == older.pk
