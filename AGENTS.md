# AGENTS.md

## Project Overview

TaskRaptor is currently a backend-first repository:

- `api/` contains the Django 5.1 application and Python project metadata.
- `frontend/` exists but has no committed app or tooling yet.
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

Notes:

- Default test runs exclude `live_api` tests.
- `DJANGO_SETTINGS_MODULE` for pytest is already configured as `taskraptor.settings.test`.
- A local `.env` exists under `api/`; treat it as developer-specific and do not commit secrets.

## Working Conventions

- Keep changes scoped to the Django backend unless the task explicitly involves bootstrapping the frontend.
- Prefer adding or updating tests in the corresponding app under `api/*/tests/` when changing backend behavior.
- Avoid editing generated environment artifacts such as `api/.venv/` or `api/.pytest_cache/`.
- Preserve existing app boundaries: auth in `accounts`, agent logic in `agent`, channel runtime/services in `channels`, task domain models in `tasks`, scheduled automations in `automations`.
- If a task needs new setup docs for humans, update `README.md` in addition to this file.

## Gaps To Notice

- There is no committed frontend implementation yet.
- There are no root-level task runners or monorepo scripts yet.
- Repo documentation is still minimal, so verify assumptions from the code before making broad structural changes.
