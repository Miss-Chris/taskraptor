# Agent2

## Overview

`agent` is the task agent workflow for TaskRaptor.

It replaces the older `apps.agent` todo-specific path with a workflow built on the main `Task` domain model in [`apps/tasks/models.py`](/Users/anirudh/work/taskraptor/apps/tasks/models.py). The goal is to keep the dashboard, API, Telegram bot, and agent operating on the same source of truth.

At a high level, `agent` does four things:

1. Builds a compact view of the user's current state.
2. Sends that state plus the incoming message to Claude as a tool-calling prompt.
3. Executes task tools against the real database.
4. Persists the run and sends the resulting reply back through the triggering channel.

## Main Components

### Runtime

[`apps/agent/runtime.py`](/Users/anirudh/work/taskraptor/apps/agent/runtime.py) contains the core loop.

It:

- Builds the system prompt and initial message list.
- Registers the available task tools plus `respond_to_user`.
- Calls the LLM in a loop until it either stops, hits the respond limit, or hits the iteration limit.
- Executes tool calls locally and feeds compact tool results back into the next model turn.
- Tracks actual input and output token usage when the Anthropic API returns usage metadata.

### Prompt

[`apps/agent/prompts.py`](/Users/anirudh/work/taskraptor/apps/agent/prompts.py) defines the system prompt.

The prompt is intentionally narrow:

- The model is told it is TaskRaptor's task agent.
- It can only communicate through `respond_to_user`.
- It should prefer `search_tasks` before ambiguous edits.
- It should use `complete_task` for completion requests.
- It receives a short list of currently open tasks as context.

### Tools

[`apps/agent/tools.py`](/Users/anirudh/work/taskraptor/apps/agent/tools.py) defines the task-facing tools.

Current tools:

- `create_task`
- `list_tasks`
- `search_tasks`
- `update_task`
- `complete_task`
- `delete_task`

Each tool operates directly on `Task` rows and returns structured JSON-like results. The runtime also compacts tool outputs before sending them back to the model so later turns do not carry unnecessary payload.

### Service Layer

[`apps/agent/service.py`](/Users/anirudh/work/taskraptor/apps/agent/service.py) is the application boundary.

It:

- Loads the user's timezone and API key.
- Pulls recent conversation history for the active channel.
- Pulls a short list of open tasks for prompt context.
- Builds the `AgentRequest`.
- Persists the inbound user message before running the model.
- Persists the resulting `AgentRun`, `ToolCall`, and assistant messages.

This is the main entry point for synchronous agent execution inside the app.

### Transport Tasks

[`apps/agent/tasks.py`](/Users/anirudh/work/taskraptor/apps/agent/tasks.py) contains async entrypoints.

Current tasks:

- `run_agent_for_telegram_message(chat_id, text)`
- `run_agent_scheduled_prompt(user_id, text)`

These tasks call the service layer, then deliver any assistant messages back to Telegram when a linked channel exists.

## Request Flow

### Telegram message flow

1. Telegram sends a webhook to [`apps/channels/api.py`](/Users/anirudh/work/taskraptor/apps/channels/api.py).
2. `JOIN <code>` messages are handled by the channel-linking path.
3. Non-join messages from an already linked chat enqueue `run_agent_for_telegram_message`.
4. The task resolves the linked user and calls `agent.service.handle_message(...)`.
5. `handle_message(...)` builds context, runs the runtime, persists logs, and returns user-facing messages.
6. The Celery task sends those messages back to Telegram.

### Scheduled flow

1. Some scheduler path decides a user should receive a proactive prompt.
2. It enqueues `run_agent_scheduled_prompt(user_id, text)`.
3. The task runs `handle_message(...)` with `trigger_type="schedule"`.
4. The reply is sent to the user's latest linked Telegram channel if one exists.

## Context Model

`agent` currently uses two context sources:

- Recent `ChatMessage` rows for the current channel.
- A capped list of open `Task` rows.

This is deliberately simple. It gives the model enough context to act on recent conversation and active work without pulling the entire task database into the prompt.

## Token Usage

`agent` supports two token views:

- Actual token usage from normal runs, recorded from Anthropic response metadata.
- Preflight token estimation via [`estimate_initial_tokens()`](/Users/anirudh/work/taskraptor/apps/agent/runtime.py#L149) and [`estimate_message_tokens()`](/Users/anirudh/work/taskraptor/apps/agent/service.py#L79).

When an Anthropic key is available, the estimator uses the API's `count_tokens` endpoint for the initial prompt. Otherwise it falls back to a heuristic estimate.

## Why Agent2 Exists

The old agent path had a few structural problems:

- It used a separate `Todo` model instead of the main `Task` model.
- Transport, persistence, and runtime concerns were too tightly mixed.
- Scheduled and interactive paths were not clearly separated.

`agent` keeps the same general tool-calling model, but moves it onto the real product domain and cleaner boundaries.

## Current Limitations

`agent` is intentionally incremental and not fully “done”.

Known gaps:

- The prompt context is basic; there is no search/ranking layer beyond simple task queries.
- The proactive scheduling policy is not yet fully redesigned; `agent` only exposes the entrypoint for scheduled prompts.

## Intended Direction

The intended end state is:

- `agent` is the default task agent.
- Legacy `Todo`/`Schedule`-specific workflows are removed.
- Prompt context becomes more deliberate, likely with stronger search and summarisation of relevant tasks.
