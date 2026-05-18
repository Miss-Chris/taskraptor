"""
Live acceptance tests for the channel workflow orchestrator.

These tests call the real Anthropic API and are excluded from the default
pytest run. To run them:

    pytest -m live_api

They require TEST_ANTHROPIC_API_KEY to be set in the environment or .env.

Set WORKFLOW_AUDIT=1 to print every NewMessage and ToolCallRecord per turn
(use with ``pytest -s`` to see output on the terminal).
"""
from __future__ import annotations

from datetime import UTC, datetime
import json
import os

import pytest

from agent.models import AgentRun, AgentRunStatus, MessageLog
from agent.schemas import AgentResult
from channels.workflow import handle_system_message, handle_user_incoming
from tasks.models import DueType, Task
from tasks.reminders import build_task_reminder_prompt
from tasks.services import create_task


def _audit_turn(turn_idx: int, user_text: str, result: AgentResult) -> None:
    """Pretty-print agent output for manual audits (WORKFLOW_AUDIT=1)."""
    print(f"\n{'=' * 72}")
    print(f"TURN {turn_idx}  user: {user_text!r}")
    print(f"  response_text: {result.response_text!r}")
    print(f"  iterations: {result.iterations}  error: {result.error!r}")
    print("  --- new_messages (ordered) ---")
    for i, msg in enumerate(result.new_messages):
        line = f"    [{i}] actor={msg.actor!r}"
        if msg.tool_name:
            line += f" tool_name={msg.tool_name!r}"
        if msg.tool_call_id:
            line += f" tool_call_id={msg.tool_call_id!r}"
        if msg.content:
            preview = msg.content if len(msg.content) < 500 else msg.content[:500] + "…"
            line += f"\n        content: {preview!r}"
        if msg.arguments:
            line += f"\n        arguments: {json.dumps(msg.arguments, ensure_ascii=False)}"
        print(line)
    print("  --- tool_calls (execute_tool records) ---")
    for i, tc in enumerate(result.tool_calls):
        res_preview = tc.result if len(tc.result) < 400 else tc.result[:400] + "…"
        print(
            f"    [{i}] {tc.tool_name!r} id={tc.tool_call_id!r}\n"
            f"        args: {json.dumps(tc.arguments, ensure_ascii=False)}\n"
            f"        result: {res_preview!r}"
        )
    print(f"{'=' * 72}\n")


@pytest.mark.live_api
@pytest.mark.django_db
def test_workflow_interprets_tomorrow_in_user_timezone(
    monkeypatch,
    test_user,
    test_llm_model,
    test_conversation,
):
    """
    Workflow prompt should give the model enough local-time context for relative dates.

    The frozen instant is 2026-04-10 06:30 UTC, which is still 2026-04-09 in
    America/Los_Angeles. "Tomorrow" should therefore become 2026-04-10 local.
    """
    test_user.timezone = "America/Los_Angeles"
    test_user.save(update_fields=["timezone"])
    frozen_now = datetime(2026, 4, 10, 6, 30, tzinfo=UTC)
    monkeypatch.setattr("channels.workflow.timezone.now", lambda: frozen_now)

    user_text = "Create a task called 'Submit LA permit' due tomorrow with no specific time."
    result = handle_user_incoming(test_conversation, user_text)

    if os.environ.get("WORKFLOW_AUDIT") == "1":
        _audit_turn(1, user_text, result)

    assert result.error is None
    create_calls = [
        msg
        for msg in result.new_messages
        if msg.actor == "tool_call" and msg.tool_name == "create_task"
    ]
    assert create_calls, "Expected a create_task tool call"

    task = Task.objects.get(user=test_user, name__icontains="LA permit")
    assert task.due_type == DueType.DATE
    assert task.due_at == datetime(2026, 4, 11, 6, 59, 59, 999999, tzinfo=UTC)


@pytest.mark.live_api
@pytest.mark.django_db
def test_multi_turn_workflow(test_user, test_llm_model, test_conversation):
    """
    End-to-end acceptance test exercising handle_user_incoming across four turns:

      1. "Add a task to buy milk"
      2. "I need to call my cousin"
      3. "On second thoughts I already have milk, let's change that to buy cookies"
      4. "What are my tasks?"

    Because the agent is non-deterministic we keep assertions loose -- we verify
    structural correctness (runs created, messages persisted, tasks in DB) and
    basic semantic plausibility (edit call issued, final response mentions tasks).
    """
    turns = [
        "Add a task to buy milk",
        "I need to call my cousin",
        "On second thoughts I already have milk, let's change that to buy cookies",
        "What are my tasks?",
    ]

    results = []
    for turn_text in turns:
        result = handle_user_incoming(test_conversation, turn_text)
        results.append(result)

        if os.environ.get("WORKFLOW_AUDIT") == "1":
            _audit_turn(len(results), turn_text, result)

        assert result.error is None, f"Turn {len(results)} returned an error: {result.error!r}"
        assert result.response_text, f"Turn {len(results)} returned an empty response"

        run = AgentRun.objects.filter(conversation=test_conversation).order_by("-created_at").first()
        assert run is not None
        assert run.status == AgentRunStatus.COMPLETED, f"AgentRun not completed after turn {len(results)}"

    log_count = MessageLog.objects.filter(conversation=test_conversation).count()
    assert log_count > len(turns), (
        f"Expected more than {len(turns)} MessageLog rows, got {log_count}"
    )

    all_tool_calls = [
        msg
        for result in results
        for msg in result.new_messages
        if msg.actor == "tool_call"
    ]
    tool_names = [tc.tool_name for tc in all_tool_calls]

    create_calls = [n for n in tool_names if n == "create_task"]
    assert len(create_calls) >= 2, (
        f"Expected at least 2 create_task calls (milk + cousin), got {create_calls}"
    )

    edit_calls = [n for n in tool_names if n == "edit_task"]
    assert len(edit_calls) >= 1, (
        "Expected at least 1 edit_task call (milk -> cookies)"
    )

    final_response = results[3].response_text.lower()
    assert "cookie" in final_response or "cousin" in final_response or "call" in final_response, (
        f"Turn 4 response doesn't seem to reference the user's tasks: {results[3].response_text!r}"
    )

    user_tasks = Task.objects.filter(user=test_user, deleted_at__isnull=True)
    assert user_tasks.exists(), "Expected at least one active Task in the DB for the user"

    agent_runs = AgentRun.objects.filter(conversation=test_conversation)
    assert agent_runs.count() == len(turns), (
        f"Expected {len(turns)} AgentRun rows, got {agent_runs.count()}"
    )
    assert all(r.status == AgentRunStatus.COMPLETED for r in agent_runs), (
        "All AgentRun rows should be completed"
    )


@pytest.mark.live_api
@pytest.mark.django_db
def test_task_reminder_delivery_not_rescheduled(
    test_user,
    test_llm_model,
    test_conversation,
):
    """
    A fired reminder should be delivered as a notification, not interpreted as
    a fresh instruction to schedule another reminder.
    """
    test_user.timezone = "America/Toronto"
    test_user.save(update_fields=["timezone"])
    task = create_task(user_id=test_user.pk, name="Park the car")

    result = handle_system_message(
        test_conversation.channel,
        build_task_reminder_prompt(task),
    )

    if os.environ.get("WORKFLOW_AUDIT") == "1":
        _audit_turn(1, build_task_reminder_prompt(task), result)

    assert result.error is None
    assert result.response_text
    assert "park" in result.response_text.lower()
    tool_names = [
        msg.tool_name
        for msg in result.new_messages
        if msg.actor == "tool_call"
    ]
    assert "set_task_reminder" not in tool_names
    task.refresh_from_db()
    assert task.remind_at is None
