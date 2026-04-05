"""
Live acceptance tests for the agent loop.

These tests call the real Anthropic API and are excluded from the default
pytest run. To run them:

    pytest -m live_api

They require TEST_ANTHROPIC_API_KEY to be set in the environment or .env.
"""
from __future__ import annotations

import pytest

from agent.run import run_agent
from agent.schemas import (
    AssistantMessage,
    HistoryMessage,
    NewMessage,
    ToolResultMessage,
    UserMessage,
)


def _new_messages_to_history(new_messages: list[NewMessage]) -> list[HistoryMessage]:
    """
    Convert NewMessage records (as returned by AgentResult) back into typed
    HistoryMessage objects, simulating the DB round-trip without hitting the DB.

    The ordering emitted by run_agent is:
      user → (tool_call ... tool_result ...)* → assistant
    """
    history: list[HistoryMessage] = []
    for msg in new_messages:
        if msg.actor == "user":
            history.append(UserMessage(content=msg.content or ""))

        elif msg.actor == "tool_call":
            from agent.schemas import ToolCallFunction
            import json

            tool_call = ToolCallFunction(
                id=msg.tool_call_id or "",
                name=msg.tool_name or "",
                arguments=json.dumps(msg.arguments or {}),
            )
            if (
                history
                and isinstance(history[-1], AssistantMessage)
                and history[-1].tool_calls
            ):
                history[-1].tool_calls.append(tool_call)
            else:
                history.append(
                    AssistantMessage(
                        content=msg.content or None,
                        tool_calls=[tool_call],
                    )
                )

        elif msg.actor == "tool_result":
            history.append(
                ToolResultMessage(
                    tool_call_id=msg.tool_call_id or "",
                    name=msg.tool_name or "",
                    content=msg.content or "",
                )
            )

        elif msg.actor == "assistant":
            history.append(AssistantMessage(content=msg.content))

    return history


@pytest.mark.live_api
@pytest.mark.django_db
def test_simple_response(test_user, test_llm_model):
    """Agent should respond to a plain greeting with non-empty text."""
    result = run_agent(
        user_id=test_user.pk,
        llm_model=test_llm_model,
        history=[],
        new_message="Say hello",
    )

    assert result.response_text, "Expected a non-empty response"
    assert result.iterations >= 1
    assert result.error is None
    actors = {m.actor for m in result.new_messages}
    assert "assistant" in actors


@pytest.mark.live_api
@pytest.mark.django_db
def test_create_task(test_user, test_llm_model):
    """Agent should call create_task when asked to create a task."""
    result = run_agent(
        user_id=test_user.pk,
        llm_model=test_llm_model,
        history=[],
        new_message="Create a task called 'Buy milk'",
    )

    assert result.error is None
    tool_calls = [m for m in result.new_messages if m.actor == "tool_call"]
    create_calls = [tc for tc in tool_calls if tc.tool_name == "create_task"]
    assert create_calls, "Expected at least one create_task tool call"

    name_arg = create_calls[0].arguments or {}
    assert "Buy milk" in (name_arg.get("name") or "")

    assert result.response_text, "Expected a non-empty final response"


@pytest.mark.live_api
@pytest.mark.django_db
def test_multi_turn_history(test_user, test_llm_model):
    """Agent should maintain context across turns via typed history."""
    first = run_agent(
        user_id=test_user.pk,
        llm_model=test_llm_model,
        history=[],
        new_message="Create a task called 'Walk the dog'",
    )
    assert first.error is None

    history = _new_messages_to_history(first.new_messages)

    second = run_agent(
        user_id=test_user.pk,
        llm_model=test_llm_model,
        history=history,
        new_message="What was the last task I asked you to create?",
    )

    assert second.error is None
    assert second.response_text, "Expected a non-empty follow-up response"
    assert "dog" in second.response_text.lower() or "walk" in second.response_text.lower(), (
        f"Expected the response to reference the earlier task. Got: {second.response_text!r}"
    )
