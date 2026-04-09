"""
Tests for the context_message_limit feature on LlmModel.

Covers:
- trim_history_for_context: no-op when history is within limit, tail-slice when
  over limit, and safe boundary adjustment when a naive slice would begin with an
  orphaned ToolResultMessage or an incomplete AssistantMessage+tool-call block.
- run_agent: when called with a long synthetic history, the first LLM payload
  contains only the trimmed subset (plus system prompt + new user message).
- LlmModel.clean(): rejects values outside [1, 1024].
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from agent.models import LlmModel
from agent.run import run_agent
from agent.schemas import (
    AssistantMessage,
    ToolCallFunction,
    ToolResultMessage,
    UserMessage,
)
from agent.utils import trim_history_for_context

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        email="ctx_limit@example.com",
        password="testpass",
    )


@pytest.fixture
def llm_model(test_user):
    return LlmModel.objects.create(
        user=test_user,
        model_key="system_free",
        context_message_limit=25,
    )


def _make_user_msg(text: str = "hello") -> UserMessage:
    return UserMessage(content=text)


def _make_assistant_msg(text: str = "ok") -> AssistantMessage:
    return AssistantMessage(content=text)


def _make_tool_pair(tool_name: str = "do_thing") -> tuple[AssistantMessage, ToolResultMessage]:
    """Return a matched (AssistantMessage with tool_call, ToolResultMessage) pair."""
    tc_id = f"tc_{tool_name}"
    assistant = AssistantMessage(
        content=None,
        tool_calls=[ToolCallFunction(id=tc_id, name=tool_name, arguments=json.dumps({}))],
    )
    result = ToolResultMessage(tool_call_id=tc_id, name=tool_name, content="done")
    return assistant, result


# ---------------------------------------------------------------------------
# Capturing scripted LLM callable (records messages from each call)
# ---------------------------------------------------------------------------

class CapturingScriptedLlm:
    """
    Scripted LLM that records the ``messages`` list from every invocation.
    Returns a plain-text response on the first call (triggering loop exit).
    """

    from channels.tests.scripted_llm import FakeChoice, FakeMessage, FakeResponse, FakeUsage

    def __init__(self) -> None:
        self.calls: list[list[dict[str, Any]]] = []
        self._done = False

    def __call__(self, llm_model: Any, messages: Any, **kwargs: Any) -> Any:
        self.calls.append(list(messages))
        from channels.tests.scripted_llm import (
            FakeChoice,
            FakeMessage,
            FakeResponse,
            FakeUsage,
        )
        return FakeResponse(
            choices=[FakeChoice(message=FakeMessage(content="Done.", tool_calls=[]))],
            usage=FakeUsage(prompt_tokens=5, completion_tokens=5),
        )


# ---------------------------------------------------------------------------
# trim_history_for_context unit tests
# ---------------------------------------------------------------------------

class TestTrimHistoryForContext:
    def test_no_trim_when_within_limit(self):
        history = [_make_user_msg(), _make_assistant_msg()]
        assert trim_history_for_context(history, limit=10) == history

    def test_no_trim_when_exactly_at_limit(self):
        history = [_make_user_msg() for _ in range(5)]
        assert trim_history_for_context(history, limit=5) == history

    def test_plain_trim_to_limit(self):
        history = [_make_user_msg(f"msg {i}") for i in range(10)]
        result = trim_history_for_context(history, limit=4)
        assert len(result) == 4
        assert result == history[-4:]

    def test_trim_drops_orphaned_tool_result_at_start(self):
        """After slicing, if the first message is a ToolResultMessage, it's dropped."""
        assistant, tool_result = _make_tool_pair("search")
        history = [
            _make_user_msg("q1"),
            assistant,
            tool_result,
            _make_user_msg("q2"),
            _make_assistant_msg("a2"),
        ]
        # limit=3 → naive tail is [tool_result, user("q2"), assistant("a2")]
        # tool_result at index 0 is invalid; it should be dropped
        result = trim_history_for_context(history, limit=3)
        assert not any(isinstance(m, ToolResultMessage) for m in result[:1]), (
            "Leading ToolResultMessage should be dropped"
        )
        for msg in result:
            assert not isinstance(msg, ToolResultMessage) or result.index(msg) > 0

    def test_trim_drops_incomplete_tool_call_block_at_start(self):
        """
        If after slicing the first message is an AssistantMessage with tool_calls
        but the matching ToolResultMessage(s) are outside the window, that
        AssistantMessage should be dropped too.
        """
        assistant, tool_result = _make_tool_pair("query")
        history = [
            _make_user_msg("q1"),
            # assistant with tool_call starts here; tool_result follows
            assistant,
            tool_result,
            _make_user_msg("q2"),
            _make_assistant_msg("a2"),
        ]
        # limit=2 → naive tail is [user("q2"), assistant("a2")] — already valid, no drop needed
        result = trim_history_for_context(history, limit=2)
        assert len(result) == 2

        # Now test a case where the tool_result is cut off:
        # Build a history where the assistant+tool_result pair is split by the limit.
        # limit=1 starting from assistant (no tool_result in window)
        history2 = [_make_user_msg("q0"), assistant, tool_result]
        # limit=2 → tail is [assistant, tool_result] — complete pair, should be fine
        result2 = trim_history_for_context(history2, limit=2)
        assert len(result2) == 2

        # limit=1 → tail is [tool_result] — orphaned, should drop to []
        result3 = trim_history_for_context(history2, limit=1)
        assert result3 == []

    def test_empty_history_returns_empty(self):
        assert trim_history_for_context([], limit=10) == []

    def test_limit_zero_or_one_edge(self):
        history = [_make_user_msg("a"), _make_user_msg("b"), _make_user_msg("c")]
        result = trim_history_for_context(history, limit=1)
        assert len(result) == 1
        assert result[0].content == "c"


# ---------------------------------------------------------------------------
# run_agent integration: history trimming via context_message_limit
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRunAgentContextLimit:
    def _build_plain_history(self, n: int):
        """Alternating user/assistant messages, no tool calls."""
        history = []
        for i in range(n):
            if i % 2 == 0:
                history.append(_make_user_msg(f"turn {i}"))
            else:
                history.append(_make_assistant_msg(f"reply {i}"))
        return history

    def test_history_is_capped_in_first_llm_call(self, llm_model):
        """run_agent should only pass context_message_limit history entries to LLM."""
        llm_model.context_message_limit = 5
        llm_model.save(update_fields=["context_message_limit"])

        history = self._build_plain_history(20)
        scripted = CapturingScriptedLlm()

        run_agent(
            user_id=llm_model.user_id,
            llm_model=llm_model,
            history=history,
            new_message="latest question",
            llm_callable=scripted,
        )

        assert scripted.calls, "LLM was never called"
        first_call_messages = scripted.calls[0]

        # System prompt (role=system) + up to 5 history + new user message
        history_messages = [m for m in first_call_messages if m["role"] != "system"]
        # Last message is the new user turn; rest is trimmed history
        history_in_payload = history_messages[:-1]
        assert len(history_in_payload) <= 5, (
            f"Expected at most 5 history messages in LLM payload, got {len(history_in_payload)}"
        )

    def test_short_history_not_trimmed(self, llm_model):
        """When history is shorter than the limit, all messages pass through unchanged."""
        llm_model.context_message_limit = 25
        llm_model.save(update_fields=["context_message_limit"])

        history = self._build_plain_history(4)
        scripted = CapturingScriptedLlm()

        run_agent(
            user_id=llm_model.user_id,
            llm_model=llm_model,
            history=history,
            new_message="go",
            llm_callable=scripted,
        )

        first_call_messages = scripted.calls[0]
        history_in_payload = [m for m in first_call_messages if m["role"] != "system"][:-1]
        assert len(history_in_payload) == 4

    def test_trim_does_not_send_orphaned_tool_result(self, llm_model):
        """
        When trimming would leave a ToolResultMessage at the front of the window,
        run_agent must drop it so the payload doesn't start with role='tool'.
        """
        llm_model.context_message_limit = 3
        llm_model.save(update_fields=["context_message_limit"])

        assistant, tool_result = _make_tool_pair("lookup")
        history = [
            _make_user_msg("q0"),
            assistant,
            tool_result,      # index 2
            _make_user_msg("q1"),   # index 3
            _make_assistant_msg("a1"),  # index 4
        ]
        # naive tail of 3 → [tool_result, user("q1"), assistant("a1")]
        # trim should strip the leading tool_result

        scripted = CapturingScriptedLlm()
        run_agent(
            user_id=llm_model.user_id,
            llm_model=llm_model,
            history=history,
            new_message="q2",
            llm_callable=scripted,
        )

        first_call_messages = scripted.calls[0]
        roles = [m["role"] for m in first_call_messages]
        # First role must be 'system'; after that, no 'tool' should appear before
        # an 'assistant' with tool_calls in the current window start.
        assert roles[0] == "system"
        # The new user message is last; drop system and last user
        inner_roles = roles[1:-1]
        if inner_roles:
            assert inner_roles[0] != "tool", (
                "Payload must not begin with a tool result after the system prompt"
            )


# ---------------------------------------------------------------------------
# LlmModel.clean() validation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestLlmModelClean:
    def test_valid_limit_passes(self, llm_model):
        llm_model.context_message_limit = 50
        llm_model.full_clean()  # should not raise

    def test_zero_is_rejected(self, llm_model):
        llm_model.context_message_limit = 0
        with pytest.raises(ValidationError, match="context_message_limit"):
            llm_model.full_clean()

    def test_above_max_is_rejected(self, llm_model):
        llm_model.context_message_limit = 1025
        with pytest.raises(ValidationError, match="context_message_limit"):
            llm_model.full_clean()

    def test_boundary_values_pass(self, llm_model):
        for value in (1, 1024):
            llm_model.context_message_limit = value
            llm_model.full_clean()  # should not raise
