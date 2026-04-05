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
