"""
Unit tests for the core agent loop (apps/agent/agent.py).
No DB access. Uses FakeLLMClient and in-memory ToolContext.
"""
import pytest

from apps.agent.agent import run_agent
from apps.agent.schemas import AgentRequest
from tests.agent.conftest import make_in_memory_tool_context
from tests.agent.fakes import (
    FakeLLMClient,
    FakeMessage,
    RaisingLLMClient,
    end_turn_block,
    respond_block,
    tool_use_block,
)


def _make_request(**kwargs) -> AgentRequest:
    defaults = dict(
        api_key="test-key",
        user_id=1,
        user_timezone="UTC",
        message="test message",
    )
    defaults.update(kwargs)
    return AgentRequest(**defaults)


def test_single_respond_to_user_returns_completed():
    """Model calls respond_to_user once, then end_turn → completed."""
    client = FakeLLMClient(
        responses=[
            FakeMessage(content=[respond_block("Done!", id="r1")]),
            FakeMessage(content=[end_turn_block()]),
        ]
    )
    result = run_agent(_make_request(), make_in_memory_tool_context(), llm_client=client)

    assert result.stopped_reason == "completed"
    user_msgs = [a for a in result.actions if a.type == "user_message"]
    assert len(user_msgs) == 1
    assert user_msgs[0].user_message == "Done!"


def test_tool_call_then_respond_produces_ordered_actions():
    """Model calls add_todo then respond_to_user → both actions in index order."""
    client = FakeLLMClient(
        responses=[
            FakeMessage(content=[
                tool_use_block("add_todo", {"title": "Buy milk"}, id="t1"),
            ]),
            FakeMessage(content=[
                respond_block("Added it!", id="r1"),
            ]),
            FakeMessage(content=[end_turn_block()]),
        ]
    )
    result = run_agent(_make_request(), make_in_memory_tool_context(), llm_client=client)

    assert result.stopped_reason == "completed"
    assert len(result.actions) == 2
    assert result.actions[0].type == "tool_call"
    assert result.actions[0].tool_call.tool_name == "add_todo"
    assert result.actions[0].index == 0
    assert result.actions[1].type == "user_message"
    assert result.actions[1].user_message == "Added it!"
    assert result.actions[1].index == 1


def test_max_iterations_stops_loop():
    """Model keeps calling tools without responding → max_iterations."""
    # Always return a tool_use that is never respond_to_user
    client = FakeLLMClient(
        responses=[
            FakeMessage(content=[tool_use_block("list_todos", {}, id=f"t{i}")])
            for i in range(20)
        ]
    )
    req = _make_request(max_iterations=3)
    result = run_agent(req, make_in_memory_tool_context(), llm_client=client)

    assert result.stopped_reason == "max_iterations"
    assert client.call_count == 3


def test_max_respond_calls_stops_loop():
    """Model calls respond_to_user 3 times → max_respond_calls."""
    client = FakeLLMClient(
        responses=[
            FakeMessage(content=[respond_block("Msg 1", id="r1")]),
            FakeMessage(content=[respond_block("Msg 2", id="r2")]),
            FakeMessage(content=[respond_block("Msg 3", id="r3")]),
        ]
    )
    req = _make_request(max_respond_calls=3)
    result = run_agent(req, make_in_memory_tool_context(), llm_client=client)

    assert result.stopped_reason == "max_respond_calls"
    user_msgs = [a for a in result.actions if a.type == "user_message"]
    assert len(user_msgs) == 3


def test_llm_error_returns_error_response():
    """LLM raises → stopped_reason=error, error field populated."""
    result = run_agent(_make_request(), make_in_memory_tool_context(), llm_client=RaisingLLMClient())

    assert result.stopped_reason == "error"
    assert "LLM unavailable" in result.error


def test_unknown_tool_returns_error_output():
    """Model calls a tool not in ToolContext → tool_output["ok"] == False."""
    client = FakeLLMClient(
        responses=[
            FakeMessage(content=[tool_use_block("nonexistent_tool", {}, id="t1")]),
            FakeMessage(content=[respond_block("ok", id="r1")]),
            FakeMessage(content=[end_turn_block()]),
        ]
    )
    result = run_agent(_make_request(), make_in_memory_tool_context(), llm_client=client)

    tool_actions = [a for a in result.actions if a.type == "tool_call"]
    assert len(tool_actions) == 1
    assert tool_actions[0].tool_call.tool_output["ok"] is False
    assert "Unknown tool" in tool_actions[0].tool_call.tool_output["error"]


def test_tool_call_summary_is_populated():
    """Tool call actions have a non-empty summary."""
    client = FakeLLMClient(
        responses=[
            FakeMessage(content=[tool_use_block("add_todo", {"title": "Walk dog"}, id="t1")]),
            FakeMessage(content=[respond_block("Done", id="r1")]),
            FakeMessage(content=[end_turn_block()]),
        ]
    )
    result = run_agent(_make_request(), make_in_memory_tool_context(), llm_client=client)

    tool_actions = [a for a in result.actions if a.type == "tool_call"]
    assert tool_actions[0].tool_call.summary != ""


def test_action_indexes_are_sequential():
    """Action indexes always start at 0 and increment by 1."""
    client = FakeLLMClient(
        responses=[
            FakeMessage(content=[
                tool_use_block("add_todo", {"title": "A"}, id="t1"),
                tool_use_block("add_todo", {"title": "B"}, id="t2"),
            ]),
            FakeMessage(content=[respond_block("Done", id="r1")]),
            FakeMessage(content=[end_turn_block()]),
        ]
    )
    result = run_agent(_make_request(), make_in_memory_tool_context(), llm_client=client)

    for expected_idx, action in enumerate(result.actions):
        assert action.index == expected_idx


def test_tool_results_are_compacted_before_follow_up_llm_call():
    client = FakeLLMClient(
        responses=[
            FakeMessage(content=[tool_use_block("list_todos", {}, id="t1")]),
            FakeMessage(content=[respond_block("Done", id="r1")]),
            FakeMessage(content=[end_turn_block()]),
        ]
    )
    result = run_agent(_make_request(), make_in_memory_tool_context(), llm_client=client)

    assert result.stopped_reason == "completed"
    second_call_messages = client.calls[1]["messages"]
    tool_result_payload = second_call_messages[-1]["content"][0]["content"]
    assert "created_at" not in tool_result_payload
    assert "updated_at" not in tool_result_payload
    assert "\"count\"" in tool_result_payload
