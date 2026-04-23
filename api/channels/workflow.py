from __future__ import annotations

import logging
from uuid import UUID
from typing import Callable

from django.utils import timezone

from agent.models import AgentRun, AgentRunStatus, LlmModel, MessageLog
from agent.prompts import build_system_prompt
from agent.run import run_agent
from agent.schemas import AgentResult
from agent.utils import history_from_message_logs
from channels.models import Channel, Conversation
from channels.services import get_conversation, touch_conversation

logger = logging.getLogger(__name__)


class NoActiveLlmModel(Exception):
    """Raised when no active LlmModel exists for the user."""


def _persist_messages(
    agent_run: AgentRun,
    conversation: Conversation,
    channel: Channel,
    result: AgentResult,
) -> None:
    """
    Write each NewMessage from AgentResult to MessageLog.

    Token counts from the run are attached to the final assistant message.
    """
    total_new = len(result.new_messages)
    for idx, msg in enumerate(result.new_messages):
        is_last_assistant = (
            msg.actor == "assistant" and idx == total_new - 1
        )
        MessageLog.objects.create(
            agent_run=agent_run,
            conversation=conversation,
            channel=channel,
            actor=msg.actor,
            content=msg.content or "",
            tool_call_id=msg.tool_call_id or "",
            tool_name=msg.tool_name or "",
            metadata={"arguments": msg.arguments} if msg.arguments else {},
            input_tokens=result.input_tokens if is_last_assistant else None,
            output_tokens=result.output_tokens if is_last_assistant else None,
        )


def handle_user_incoming(
    conversation: Conversation,
    message: str,
    llm_callable: Callable | None = None,
) -> AgentResult:
    """
    Orchestrate a single user turn for the given conversation.

    Loads the message history, runs the agent, persists all new messages,
    updates the AgentRun record, and delivers each respond_to_user reply
    through the channel runtime.

    Returns the AgentResult so callers can inspect the response or tool calls.
    """
    channel = conversation.channel
    user_id: UUID = channel.user_id

    history_logs = list(
        MessageLog.objects.filter(conversation=conversation).order_by("created_at")
    )
    history = history_from_message_logs(history_logs)

    llm_model = (
        LlmModel.objects.filter(user_id=user_id, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if llm_model is None:
        raise NoActiveLlmModel(f"No active LlmModel for user_id={user_id}")

    agent_run = AgentRun.objects.create(
        channel=channel,
        conversation=conversation,
        user_id=user_id,
        llm_model=llm_model,
        status=AgentRunStatus.RUNNING,
        started_at=timezone.now(),
    )

    try:
        system_prompt = build_system_prompt(channel.user.prompt_instructions)
        result = run_agent(
            user_id=user_id,
            llm_model=llm_model,
            history=history,
            new_message=message,
            system_prompt=system_prompt,
            llm_callable=llm_callable,
        )
    except Exception as exc:
        agent_run.status = AgentRunStatus.FAILED
        agent_run.error = str(exc)
        agent_run.completed_at = timezone.now()
        agent_run.save(update_fields=["status", "error", "completed_at"])
        raise

    try:
        _persist_messages(agent_run, conversation, channel, result)
    except Exception as exc:
        agent_run.status = AgentRunStatus.FAILED
        agent_run.error = f"Persistence error: {exc}"
        agent_run.completed_at = timezone.now()
        agent_run.save(update_fields=["status", "error", "completed_at"])
        raise

    touch_conversation(conversation.pk)

    status = AgentRunStatus.FAILED if result.error else AgentRunStatus.COMPLETED
    agent_run.status = status
    agent_run.error = result.error or ""
    agent_run.completed_at = timezone.now()
    agent_run.save(update_fields=["status", "error", "completed_at"])

    runtime_conv = get_conversation(channel.pk, conversation.pk)
    for msg in result.new_messages:
        if msg.actor == "tool_call" and msg.tool_name == "respond_to_user":
            text = (msg.arguments or {}).get("message", "")
            if text:
                runtime_conv.send_message(text, agent_run=agent_run)

    logger.info(
        "[workflow] handle_user_incoming conversation_id=%s agent_run_id=%s status=%s iterations=%s",
        conversation.pk,
        agent_run.pk,
        agent_run.status,
        result.iterations,
    )

    return result


def handle_system_message(
    channel: Channel,
    message: str,
    llm_callable: Callable | None = None,
) -> AgentResult:
    """
    Orchestrate a system-initiated turn (e.g. from a cron job or automation).

    Resolves the default or most-recently-updated conversation on the given
    channel, then delegates to handle_user_incoming. If no conversation exists,
    a new one is created automatically (matching services.get_conversation behaviour).

    The prompt is passed through the same agent loop as a user message so the
    model can respond with tools; scheduling is handled elsewhere.
    """
    conversation = (
        Conversation.objects.filter(channel=channel)
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if conversation is None:
        conversation = Conversation.objects.create(channel=channel)

    return handle_user_incoming(conversation, message, llm_callable=llm_callable)
