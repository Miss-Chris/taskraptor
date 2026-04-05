from __future__ import annotations

import json

from agent.models import MessageActor, MessageLog
from agent.schemas import (
    AssistantMessage,
    HistoryMessage,
    ToolCallFunction,
    ToolResultMessage,
    UserMessage,
)


def history_from_message_logs(history: list[MessageLog]) -> list[HistoryMessage]:
    """
    Convert a list of MessageLog instances to typed HistoryMessage objects.

    This is the bridge between the Django persistence layer and the pure
    run_agent() interface. Pass the result directly as the `history` argument
    to run_agent().

    Tool call / tool result pairs are reconstructed so the LLM receives a
    valid conversation thread. Consecutive TOOL_CALL rows that share a turn
    are merged into a single AssistantMessage with multiple tool_calls.
    """
    messages: list[HistoryMessage] = []

    for log in history:
        if log.actor == MessageActor.USER:
            messages.append(UserMessage(content=log.content))

        elif log.actor == MessageActor.ASSISTANT:
            messages.append(AssistantMessage(content=log.content))

        elif log.actor == MessageActor.TOOL_CALL:
            tool_call = ToolCallFunction(
                id=log.tool_call_id,
                name=log.tool_name,
                arguments=json.dumps(log.metadata.get("arguments", {})),
            )
            # Merge into previous AssistantMessage if it already has tool_calls,
            # otherwise start a new one (carrying any assistant text from the first entry).
            if (
                messages
                and isinstance(messages[-1], AssistantMessage)
                and messages[-1].tool_calls
            ):
                messages[-1].tool_calls.append(tool_call)
            else:
                messages.append(
                    AssistantMessage(
                        content=log.content or None,
                        tool_calls=[tool_call],
                    )
                )

        elif log.actor == MessageActor.TOOL_RESULT:
            messages.append(
                ToolResultMessage(
                    tool_call_id=log.tool_call_id,
                    name=log.tool_name,
                    content=log.content,
                )
            )

    return messages


def _history_prefix_is_valid(history: list[HistoryMessage]) -> bool:
    """
    Return True when the first message in ``history`` is a safe starting point
    for an LLM API call — i.e. no orphaned tool results or incomplete
    assistant+tool-call blocks at the leading edge.

    Rules checked:
    - The first message must not be a ToolResultMessage (it would lack a
      preceding assistant message with a matching tool_call_id).
    - The first message must not be an AssistantMessage that carries tool_calls
      without the immediately following ToolResultMessages being present
      (an assistant message with tool_calls must always be followed by the
      matching tool result messages before any user or assistant message).
    """
    if not history:
        return True

    first = history[0]

    if isinstance(first, ToolResultMessage):
        return False

    if isinstance(first, AssistantMessage) and first.tool_calls:
        expected_ids = {tc.id for tc in first.tool_calls}
        seen_ids: set[str] = set()
        for msg in history[1:]:
            if isinstance(msg, ToolResultMessage):
                seen_ids.add(msg.tool_call_id)
            else:
                break
        if not expected_ids.issubset(seen_ids):
            return False

    return True


def trim_history_for_context(
    history: list[HistoryMessage],
    limit: int,
) -> list[HistoryMessage]:
    """
    Return at most ``limit`` HistoryMessage entries from the tail of ``history``,
    ensuring the resulting slice starts at a valid API boundary.

    After taking the last ``limit`` messages we drop entries from the front
    until ``_history_prefix_is_valid`` passes.  In the worst case (e.g. an
    extremely small limit) we may return an empty list; ``run_agent`` handles
    that gracefully by relying on the system prompt and new user message alone.
    """
    if len(history) <= limit:
        return history

    trimmed = list(history[-limit:])

    while trimmed and not _history_prefix_is_valid(trimmed):
        trimmed.pop(0)

    return trimmed
