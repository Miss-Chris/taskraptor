from __future__ import annotations

from .schemas import TaskContextEntry

_SYSTEM_PROMPT = """\
You are TaskRaptor's task agent.

You convert natural language into operations on the user's task list.

Rules:
- Only communicate through the respond_to_user tool.
- Be direct. No greetings, no sign-offs.
- Prefer search_tasks before updating or deleting when the user names a task by description.
- Prefer complete_task over update_task when the user asks to finish a task.
- Use list_tasks for "what do I have", "show my tasks", or when search results are ambiguous.
- After finishing the required actions, call respond_to_user exactly once unless the response must be split.

Current date/time ({timezone}): {current_time}

Open tasks:
{open_tasks}
"""


def build_system_prompt(
    *,
    timezone: str,
    current_time: str,
    open_tasks: list[TaskContextEntry],
) -> str:
    return _SYSTEM_PROMPT.format(
        timezone=timezone,
        current_time=current_time,
        open_tasks=_format_open_tasks(open_tasks),
    )


def _format_open_tasks(tasks: list[TaskContextEntry]) -> str:
    if not tasks:
        return "(none)"

    lines: list[str] = []
    for task in tasks:
        due = f", due {task.due_at}" if task.due_at else ""
        lines.append(f"- [{task.id}] {task.description} ({task.status}{due})")
    return "\n".join(lines)

