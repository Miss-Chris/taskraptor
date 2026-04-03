from apps.agent2.runtime import run_agent
from apps.agent2.schemas import AgentRequest
from apps.agent2.tools import RegisteredTool
from tests.agent.fakes import FakeLLMClient, FakeMessage, end_turn_block, respond_block, tool_use_block


def _make_request(**kwargs) -> AgentRequest:
    defaults = {
        "api_key": "test-key",
        "user_id": 1,
        "user_timezone": "UTC",
        "message": "test message",
    }
    defaults.update(kwargs)
    return AgentRequest(**defaults)


def test_tool_call_then_respond_produces_ordered_actions():
    tools = [
        RegisteredTool(
            name="create_task",
            description="Create a task",
            input_schema={"type": "object", "properties": {"description": {"type": "string"}}},
            handler=lambda **kwargs: {
                "ok": True,
                "data": {
                    "id": 10,
                    "description": kwargs["description"],
                    "status": "pending",
                    "due_at": None,
                },
            },
        )
    ]
    client = FakeLLMClient(
        responses=[
            FakeMessage(content=[tool_use_block("create_task", {"description": "Buy milk"}, id="t1")]),
            FakeMessage(content=[respond_block("Added it.", id="r1")]),
            FakeMessage(content=[end_turn_block()]),
        ]
    )

    result = run_agent(_make_request(), tools, llm_client=client)

    assert result.stopped_reason == "completed"
    assert len(result.actions) == 2
    assert result.actions[0].type == "tool_call"
    assert result.actions[0].tool_call.tool_name == "create_task"
    assert result.actions[1].type == "user_message"
    assert result.actions[1].user_message == "Added it."


def test_tool_results_are_compacted_before_follow_up_llm_call():
    tools = [
        RegisteredTool(
            name="list_tasks",
            description="List tasks",
            input_schema={"type": "object", "properties": {}},
            handler=lambda **kwargs: {
                "ok": True,
                "count": 1,
                "data": [
                    {
                        "id": 1,
                        "description": "Task one",
                        "status": "pending",
                        "due_at": None,
                        "created_at": "2026-04-03T12:00:00+00:00",
                    }
                ],
            },
        )
    ]
    client = FakeLLMClient(
        responses=[
            FakeMessage(content=[tool_use_block("list_tasks", {}, id="t1")]),
            FakeMessage(content=[respond_block("Done.", id="r1")]),
            FakeMessage(content=[end_turn_block()]),
        ]
    )

    result = run_agent(_make_request(), tools, llm_client=client)

    assert result.stopped_reason == "completed"
    second_call_messages = client.calls[1]["messages"]
    tool_result_payload = second_call_messages[-1]["content"][0]["content"]
    assert "created_at" not in tool_result_payload
    assert '"count": 1' in tool_result_payload

