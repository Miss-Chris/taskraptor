from __future__ import annotations

import functools

from django.conf import settings
from django.utils import timezone

from .agent import run_agent
from .models import AgentRun, ChatMessage, ToolCall, UserProfile
from .schemas import AgentRequest, ConversationEntry, ToolCallEntry, ToolContext
from .tools import (
    add_todo,
    create_schedule,
    delete_schedule,
    delete_todo,
    list_schedules,
    list_todos,
    search_todos,
    update_todo,
)

MAX_CONVERSATION_HISTORY = 8
MAX_TOOL_CALL_HISTORY = 5


def handle_message(user_id: int, text: str, channel: str) -> list[str]:
    """Entry point for any transport layer. Returns user-facing message strings."""

    # 1. Fetch timezone from profile (default UTC if missing)
    try:
        profile = UserProfile.objects.get(user_id=user_id)
        user_timezone = profile.timezone
    except UserProfile.DoesNotExist:
        user_timezone = "UTC"

    # 2. Fetch recent conversation history for this user+channel.
    recent_messages = list(
        ChatMessage.objects.filter(user_id=user_id, channel=channel).order_by("-created_at")[:MAX_CONVERSATION_HISTORY]
    )
    conversation_history = [
        ConversationEntry(role=m.role, content=m.content)
        for m in reversed(recent_messages)
    ]

    # 3. Fetch recent tool call summaries for the system prompt.
    recent_tool_calls = list(
        ToolCall.objects.filter(user_id=user_id).order_by("-created_at")[:MAX_TOOL_CALL_HISTORY]
    )
    tool_call_history = [
        ToolCallEntry(
            index=tc.index,
            tool_name=tc.tool_name,
            tool_input=tc.tool_input,
            tool_output=tc.tool_output,
            summary=tc.summary,
        )
        for tc in reversed(recent_tool_calls)
    ]

    # 4. Build ToolContext — all callables pre-scoped to this user
    ctx = ToolContext(
        add_todo=functools.partial(add_todo, user_id),
        list_todos=functools.partial(list_todos, user_id),
        update_todo=functools.partial(update_todo, user_id),
        delete_todo=functools.partial(delete_todo, user_id),
        search_todos=functools.partial(search_todos, user_id),
        create_schedule=functools.partial(create_schedule, user_id),
        list_schedules=functools.partial(list_schedules, user_id),
        delete_schedule=functools.partial(delete_schedule, user_id),
    )

    # 5. Build and run the agent
    req = AgentRequest(
        api_key=settings.ANTHROPIC_API_KEY,
        user_id=user_id,
        user_timezone=user_timezone,
        message=text,
        conversation_history=conversation_history,
        tool_call_history=tool_call_history,
    )
    result = run_agent(req, ctx)

    # 6. Persist AgentRun
    agent_run = AgentRun.objects.create(
        user_id=user_id,
        trigger_message=text,
        trigger_type=AgentRun.TriggerType.USER,
        stopped_reason=result.stopped_reason,
        model_used=req.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        completed_at=timezone.now(),
    )

    # 7. Persist ToolCalls and assistant ChatMessages; collect user-facing strings
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

    # 8. Persist the inbound user message
    ChatMessage.objects.create(
        user_id=user_id,
        agent_run=agent_run,
        role=ChatMessage.Role.USER,
        content=text,
        channel=channel,
    )

    return user_messages
