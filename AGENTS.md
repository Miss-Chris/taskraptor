# AGENTS.md

## Project Overview

TaskRaptor is a Django API plus Vite/React frontend repository:

- `api/` contains the Django 5.1 application and Python project metadata.
- `frontend/` contains the Vite/React app and TypeScript project metadata.
- Root `README.md` is empty, so this file is the main agent-facing orientation doc for now.

## Repo Layout

- `api/manage.py`: Django entrypoint.
- `api/taskraptor/`: project package, API wiring, and settings modules.
- `api/taskraptor/settings/local.py`: local development settings.
- `api/taskraptor/settings/test.py`: pytest settings module.
- `api/accounts/`, `api/agent/`, `api/automations/`, `api/channels/`, `api/tasks/`: Django apps.
- `api/*/tests/`: app-level test suites.
- `api/pyproject.toml`: dependency and pytest config.
- `api/uv.lock`: locked Python dependencies for `uv`.
- `frontend/src/`: React app source.
- `frontend/package.json`: frontend scripts and dependencies.

## Environment And Tooling

- Python: `>=3.12`
- Package manager: `uv`
- Web framework: Django
- API layer: Django Ninja
- Test runner: `pytest`

Use commands from `api/` unless there is a reason to operate from the repo root.

## Common Commands

From `api/`:

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
uv run pytest
uv run pytest -m live_api
```

From `frontend/`:

```bash
npm run typecheck
npm run lint
npm run build
```

Notes:

- Default test runs exclude `live_api` tests.
- `DJANGO_SETTINGS_MODULE` for pytest is already configured as `taskraptor.settings.test`.
- A local `.env` exists under `api/`; treat it as developer-specific and do not commit secrets.

## Agent Debug Introspection

When debugging why an agent conversation did not behave as expected, prefer the
redacted debug surfaces instead of querying tables ad hoc. They are scoped to a
single user/conversation and intentionally hide API keys and session tokens while
including message/tool contents needed for diagnosis.

### Browser UI

While logged into the frontend as the affected user, open:

```text
/debug
```

This page lists that user's conversations and shows the selected conversation's
visible chat messages, `AgentRun` rows, low-level `MessageLog` tool calls/results,
related tasks, task audit logs, active automations, and redacted LLM config.

### API Endpoints

Authenticated requests use the same bearer token as the rest of the app:

```bash
curl -H "Authorization: Bearer $TASKRAPTOR_TOKEN" \
  http://localhost:8000/api/debug/summary

curl -H "Authorization: Bearer $TASKRAPTOR_TOKEN" \
  http://localhost:8000/api/debug/conversations

curl -H "Authorization: Bearer $TASKRAPTOR_TOKEN" \
  http://localhost:8000/api/debug/conversations/<conversation_id>
```

Optional query parameters for the conversation endpoint:

- `run_id=<agent_run_uuid>`: limit low-level run/log output to one run.
- `limit=<n>`: cap returned runs/messages/log rows.

### LLM-Friendly Snapshot Command

From `api/`, generate a redacted Markdown snapshot for another LLM or agent to
inspect:

```bash
uv run python manage.py dump_agent_debug \
  --user-email user@example.com \
  --conversation-id <conversation_uuid>
```

Useful variants:

```bash
uv run python manage.py dump_agent_debug \
  --user-email user@example.com \
  --conversation-id <conversation_uuid> \
  --run-id <agent_run_uuid> \
  --format json \
  --output /tmp/taskraptor-debug.json
```

The command enforces user scoping: the conversation and optional run must belong
to the supplied user email. Do not bypass this by dumping raw session tokens,
API keys, or unrelated users' rows into prompts.

## Working Conventions

- Keep backend and frontend changes scoped to the area requested by the task.
- Prefer adding or updating tests in the corresponding app under `api/*/tests/` when changing backend behavior.
- Avoid editing generated environment artifacts such as `api/.venv/` or `api/.pytest_cache/`.
- Preserve existing app boundaries: auth in `accounts`, agent logic in `agent`, channel runtime/services in `channels`, task domain models in `tasks`, scheduled automations in `automations`.
- If a task needs new setup docs for humans, update `README.md` in addition to this file.

## Gaps To Notice

- There are no root-level task runners or monorepo scripts yet.
- Repo documentation is still minimal, so verify assumptions from the code before making broad structural changes.
