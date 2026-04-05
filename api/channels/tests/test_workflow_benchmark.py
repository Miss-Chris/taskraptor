"""
Live multi-turn benchmark for the channel workflow (token and tool usage).

Server model: deepseek/deepseek-chat (DeepSeek v3 via DEEPSEEK_API_KEY)

Last run (2026-04-05, 20 turns):
  tasks_in_db_delta:       7  (create_task tool invocations: 8)
  tool_calls_total:        40
  input_tokens_total:      214,262
  output_tokens_total:     3,819
  tokens_total:            218,081
  total_wall_seconds:      132.1s
  avg_seconds_per_turn:    6.6s

Excluded from the default pytest run. To execute:

    cd api && uv run pytest -m benchmark -s

Requires TEST_DEEPSEEK_API_KEY (see channels.tests.conftest).

Optional: ``BENCHMARK_INTER_TURN_SLEEP`` (seconds, default ``3``) pauses between
user turns. Spacing turns helps stay under provider TPM limits (adjust if your
key allows faster runs).

Prints a summary line block with user turns, tasks created (DB delta), total
tool calls, input/output/total tokens aggregated across AgentRuns, and wall-clock
timing per turn -- useful for comparing prompt or context changes.
"""
from __future__ import annotations

import os
import time

import pytest

from channels.workflow import handle_user_incoming
from tasks.models import Task

# Fixed script of 20 user messages: mix of creates, lists, and edits so the
# agent exercises tools across a long conversation.
BENCHMARK_TURNS: list[str] = [
    "Add a task to buy milk",
    "Add a task to email the team about the launch",
    "Remind me to call my dentist",
    "What tasks do I have?",
    "Change the milk task to say buy oat milk instead",
    "Add a task: review the design doc by Friday",
    "List my open tasks",
    "Mark the dentist call task as completed",
    "Add a task to book flights",
    "What are my pending tasks?",
    "Delete or cancel the flights task — I will drive instead",
    "Add a task to water the plants",
    "Show everything on my task list",
    "Rename the design review task to 'Review design doc (high priority)'",
    "Add a task: send thank-you notes",
    "What should I focus on next from my tasks?",
    "Mark the oat milk task complete",
    "Add a task to schedule a team retro",
    "List tasks again briefly",
    "Thanks — summarize what is still open on my list",
]


@pytest.mark.live_api
@pytest.mark.benchmark
@pytest.mark.django_db
def test_workflow_benchmark_multi_turn(test_user, test_llm_model, test_conversation):
    tasks_before = Task.objects.filter(user=test_user, deleted_at__isnull=True).count()

    total_input_tokens = 0
    total_output_tokens = 0
    total_tool_calls = 0
    create_task_invocations = 0
    total_wall_seconds = 0.0
    turn_times: list[float] = []

    inter_turn_sleep = float(os.environ.get("BENCHMARK_INTER_TURN_SLEEP", "3"))

    for turn_idx, turn_text in enumerate(BENCHMARK_TURNS, start=1):
        if turn_idx > 1 and inter_turn_sleep > 0:
            time.sleep(inter_turn_sleep)

        print(f"  turn {turn_idx:>2}/{len(BENCHMARK_TURNS)}  {turn_text!r}", flush=True)

        t0 = time.perf_counter()
        result = handle_user_incoming(test_conversation, turn_text)
        elapsed = time.perf_counter() - t0

        turn_times.append(elapsed)
        total_wall_seconds += elapsed

        tools_this_turn = [tc.tool_name for tc in result.tool_calls]
        print(
            f"           {elapsed:.1f}s  |  tools={tools_this_turn}  "
            f"| in={result.input_tokens} out={result.output_tokens}  "
            f"| error={result.error!r}",
            flush=True,
        )

        assert result.error is None, (
            f"Turn {turn_idx} error: {result.error!r} (message={turn_text!r})"
        )
        assert result.response_text, f"Turn {turn_idx} empty response"

        total_input_tokens += result.input_tokens
        total_output_tokens += result.output_tokens
        total_tool_calls += len(result.tool_calls)
        create_task_invocations += sum(
            1 for tc in result.tool_calls if tc.tool_name == "create_task"
        )

    tasks_after = Task.objects.filter(user=test_user, deleted_at__isnull=True).count()
    tasks_created_net = tasks_after - tasks_before
    total_tokens = total_input_tokens + total_output_tokens
    avg_seconds_per_turn = total_wall_seconds / len(BENCHMARK_TURNS)

    # Visible with: pytest -m benchmark -s
    print(
        "\n"
        "========== WORKFLOW BENCHMARK ==========\n"
        f"  model:                   deepseek/deepseek-chat\n"
        f"  user_turns:              {len(BENCHMARK_TURNS)}\n"
        f"  tasks_in_db_delta:       {tasks_created_net}  "
        f"(create_task tool invocations: {create_task_invocations})\n"
        f"  tool_calls_total:        {total_tool_calls}\n"
        f"  input_tokens_total:      {total_input_tokens}\n"
        f"  output_tokens_total:     {total_output_tokens}\n"
        f"  tokens_total:            {total_tokens}\n"
        f"  total_wall_seconds:      {total_wall_seconds:.1f}s\n"
        f"  avg_seconds_per_turn:    {avg_seconds_per_turn:.1f}s\n"
        "========================================\n",
        flush=True,
    )

    assert len(BENCHMARK_TURNS) == 20
    assert total_tokens > 0, "Expected provider usage metadata for token totals"
