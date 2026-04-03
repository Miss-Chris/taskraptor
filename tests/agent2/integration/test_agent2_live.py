"""
Integration tests against the real Anthropic API for agent2.
Skipped automatically if TEST_ANTHROPIC_API_KEY is not set.
"""
import os

import pytest

from apps.agent2.runtime import estimate_initial_tokens, run_agent
from apps.agent2.schemas import AgentRequest
from apps.agent2.tools import build_task_tools
from apps.tasks.models import Task

LIVE_API_KEY = os.environ.get("TEST_ANTHROPIC_API_KEY", "")
skip_without_key = pytest.mark.skipif(
    not LIVE_API_KEY, reason="TEST_ANTHROPIC_API_KEY not set"
)


def _make_request(user_id: int, message: str) -> AgentRequest:
    return AgentRequest(
        api_key=LIVE_API_KEY,
        user_id=user_id,
        user_timezone="America/Toronto",
        message=message,
    )


@skip_without_key
@pytest.mark.django_db
def test_agent2_live_run_reports_tokens_and_estimate_is_reasonable(user):
    Task.objects.create(user=user, description="Buy groceries")
    Task.objects.create(user=user, description="Call dentist")
    request = _make_request(user.pk, "What tasks do I have?")
    tools = build_task_tools(user.pk)

    estimate = estimate_initial_tokens(request, tools)
    result = run_agent(request, tools)

    assert estimate.method == "anthropic_count_tokens"
    assert estimate.initial_input_tokens > 0
    assert result.input_tokens > 0
    assert result.output_tokens > 0
    # Count endpoint and actual first-turn prompt usage should be in the same ballpark.
    assert abs(result.input_tokens - estimate.initial_input_tokens) < max(150, result.input_tokens * 0.35)
