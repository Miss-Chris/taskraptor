"""
ScriptedLlm -- a deterministic drop-in replacement for call_llm in tests.

Usage
-----
Build a sequence of responses (one per agent-loop iteration) using the
convenience builders, then pass the ScriptedLlm instance as ``llm_callable``
to ``handle_user_incoming`` or ``run_agent``:

    from channels.tests.scripted_llm import ScriptedLlm, tool_call_response

    scripted = ScriptedLlm([
        tool_call_response("create_task", {"name": "Buy milk"}),
        tool_call_response("respond_to_user", {"message": "Task created!"}),
    ])
    result = handle_user_incoming(conversation, "Add a task", llm_callable=scripted)
    scripted.assert_exhausted()   # optional: verify all scripted turns were consumed

ScriptedLlm accepts the same positional/keyword arguments as call_llm
(llm_model, messages, **kwargs) and ignores them -- the scripted responses
are independent of the actual messages sent.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Minimal response shape -- only the attributes run_agent() actually reads
# ---------------------------------------------------------------------------

@dataclass
class FakeFunction:
    name: str
    arguments: str  # JSON string, matching litellm


@dataclass
class FakeToolCall:
    function: FakeFunction
    id: str = field(default_factory=lambda: f"fake_tc_{uuid.uuid4().hex[:8]}")


@dataclass
class FakeMessage:
    content: str | None
    tool_calls: list[FakeToolCall] = field(default_factory=list)


@dataclass
class FakeUsage:
    prompt_tokens: int = 10
    completion_tokens: int = 10


@dataclass
class FakeChoice:
    message: FakeMessage


@dataclass
class FakeResponse:
    choices: list[FakeChoice]
    usage: FakeUsage = field(default_factory=FakeUsage)


# ---------------------------------------------------------------------------
# Convenience builders
# ---------------------------------------------------------------------------

def tool_call_response(
    tool_name: str,
    arguments: dict[str, Any],
    content: str | None = None,
    *,
    tool_call_id: str | None = None,
) -> FakeResponse:
    """Return a FakeResponse that makes the agent call one tool."""
    tc_id = tool_call_id or f"fake_tc_{uuid.uuid4().hex[:8]}"
    return FakeResponse(
        choices=[
            FakeChoice(
                message=FakeMessage(
                    content=content,
                    tool_calls=[
                        FakeToolCall(
                            id=tc_id,
                            function=FakeFunction(
                                name=tool_name,
                                arguments=json.dumps(arguments, default=str),
                            ),
                        )
                    ],
                )
            )
        ]
    )


def text_response(content: str) -> FakeResponse:
    """Return a FakeResponse with plain text content and no tool calls."""
    return FakeResponse(
        choices=[FakeChoice(message=FakeMessage(content=content, tool_calls=[]))]
    )


# ---------------------------------------------------------------------------
# ScriptedLlm
# ---------------------------------------------------------------------------

class ScriptedLlm:
    """
    Callable replacement for call_llm backed by a pre-defined response list.

    Each call to the instance consumes the next FakeResponse in the queue.
    Raises ``ScriptExhausted`` if the agent makes more calls than scripted,
    so runaway loops are immediately visible in test output.
    """

    class ScriptExhausted(Exception):
        """Raised when the agent calls llm_callable more times than scripted."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    def __call__(self, llm_model: Any, messages: Any, **kwargs: Any) -> FakeResponse:
        self._call_count += 1
        if not self._responses:
            raise ScriptedLlm.ScriptExhausted(
                f"ScriptedLlm ran out of scripted responses after {self._call_count - 1} call(s). "
                "Add more responses to the script or investigate why the agent loop isn't terminating."
            )
        return self._responses.pop(0)

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def remaining(self) -> int:
        return len(self._responses)

    def assert_exhausted(self) -> None:
        """Assert that every scripted response was consumed."""
        if self._responses:
            raise AssertionError(
                f"ScriptedLlm has {len(self._responses)} unused response(s). "
                "The agent terminated earlier than expected."
            )
