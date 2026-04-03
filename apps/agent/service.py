from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.tasks.models import Task

from .models import AgentRun, ChatMessage, ToolCall, UserProfile
from .runtime import estimate_initial_tokens, run_agent
from .schemas import AgentRequest, AgentTokenEstimate, ConversationEntry, TaskContextEntry
from .tools import build_task_tools

MAX_CONVERSATION_HISTORY = 8
MAX_OPEN_TASK_CONTEXT = 10


def handle_message(
    user_id: int,
    text: str,
    channel: str,
    *,
    trigger_type: str = AgentRun.TriggerType.USER,
) -> list[str]:
    request = _build_agent_request(user_id=user_id, text=text, channel=channel)
    tools = build_task_tools(user_id)

    with transaction.atomic():
        agent_run = AgentRun.objects.create(
            user_id=user_id,
            trigger_message=text,
            trigger_type=trigger_type,
            stopped_reason="",
            model_used=request.model,
        )
        ChatMessage.objects.create(
            user_id=user_id,
            agent_run=agent_run,
            role=ChatMessage.Role.USER,
            content=text,
            channel=channel,
        )

        result = run_agent(request, tools)

        AgentRun.objects.filter(id=agent_run.id).update(
            stopped_reason=result.stopped_reason,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            completed_at=timezone.now(),
        )

        user_messages: list[str] = []
        for action in result.actions:
            if action.type == "tool_call" and action.tool_call:
                ToolCall.objects.create(
                    user_id=user_id,
                    agent_run=agent_run,
                    index=action.index,
                    tool_name=action.tool_call.tool_name,
                    tool_input=action.tool_call.tool_input,
                    tool_output=action.tool_call.tool_output,
                    summary=action.tool_call.summary,
                )
            elif action.type == "user_message" and action.user_message is not None:
                ChatMessage.objects.create(
                    user_id=user_id,
                    agent_run=agent_run,
                    role=ChatMessage.Role.ASSISTANT,
                    content=action.user_message,
                    index=action.index,
                    channel=channel,
                )
                user_messages.append(action.user_message)

    return user_messages


def estimate_message_tokens(
    user_id: int,
    text: str,
    channel: str,
) -> AgentTokenEstimate:
    request = _build_agent_request(user_id=user_id, text=text, channel=channel)
    tools = build_task_tools(user_id)
    return estimate_initial_tokens(request, tools)


def _resolve_api_key(profile: UserProfile | None) -> str:
    if profile:
        api_key = profile.preferences.get("anthropic_api_key")
        if isinstance(api_key, str) and api_key.strip():
            return api_key.strip()
    return settings.ANTHROPIC_API_KEY


def _build_agent_request(user_id: int, text: str, channel: str) -> AgentRequest:
    profile = UserProfile.objects.filter(user_id=user_id).first()
    user_timezone = profile.timezone if profile else "UTC"
    api_key = _resolve_api_key(profile)

    recent_messages = list(
        ChatMessage.objects.filter(user_id=user_id, channel=channel)
        .order_by("-created_at")[:MAX_CONVERSATION_HISTORY]
    )
    conversation_history = [
        ConversationEntry(role=message.role, content=message.content)
        for message in reversed(recent_messages)
    ]

    open_tasks = [
        TaskContextEntry(
            id=task.id,
            description=task.description,
            status=task.status,
            due_at=task.due_at.isoformat() if task.due_at else None,
        )
        for task in Task.objects.filter(user_id=user_id, status=Task.Status.PENDING)
        .order_by("due_at", "-created_at")[:MAX_OPEN_TASK_CONTEXT]
    ]

    return AgentRequest(
        api_key=api_key,
        user_id=user_id,
        user_timezone=user_timezone,
        message=text,
        conversation_history=conversation_history,
        open_tasks=open_tasks,
    )
