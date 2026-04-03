import pytest

from apps.accounts.models import User
from apps.agent.models import UserProfile


@pytest.fixture
def user(db):
    u = User.objects.create_user(email="agent@example.com", password="hunter2!")
    UserProfile.objects.create(user=u, timezone="America/New_York")
    return u


@pytest.fixture
def other_user(db):
    return User.objects.create_user(email="other@example.com", password="hunter2!")


def make_in_memory_tool_context():
    """Return a ToolContext backed by an in-memory dict — no DB required."""
    from apps.agent.schemas import ToolContext

    store: dict[str, dict] = {}
    _id_counter = [0]

    def _next_id():
        _id_counter[0] += 1
        return str(_id_counter[0])

    def add_todo(title, notes="", priority="medium", tags=None, due_date=None, due_time=None, alarm_at=None):
        tid = _next_id()
        store[tid] = {"id": tid, "title": title, "notes": notes, "priority": priority,
                      "tags": tags or [], "is_completed": False, "due_date": due_date,
                      "due_time": due_time, "alarm_at": alarm_at}
        return {"ok": True, "data": store[tid]}

    def list_todos(include_completed=False, priority=None):
        items = [t for t in store.values() if include_completed or not t.get("is_completed")]
        if priority:
            items = [t for t in items if t.get("priority") == priority]
        return {"ok": True, "data": items, "count": len(items)}

    def update_todo(todo_id, **fields):
        if todo_id not in store:
            return {"ok": False, "error": f"Todo {todo_id} not found"}
        store[todo_id].update(fields)
        return {"ok": True, "data": store[todo_id]}

    def delete_todo(todo_id):
        if todo_id not in store:
            return {"ok": False, "error": f"Todo {todo_id} not found"}
        del store[todo_id]
        return {"ok": True, "data": {"id": todo_id}}

    def search_todos(query):
        q = query.lower()
        items = [t for t in store.values()
                 if q in t.get("title", "").lower() or q in t.get("notes", "").lower()]
        return {"ok": True, "data": items, "count": len(items)}

    def create_schedule(instruction, cron_expression="", is_recurring=True, next_run_at=None):
        sid = _next_id()
        sched = {"id": sid, "instruction": instruction, "cron_expression": cron_expression,
                 "is_recurring": is_recurring, "next_run_at": next_run_at}
        return {"ok": True, "data": sched}

    def list_schedules():
        return {"ok": True, "data": [], "count": 0}

    def delete_schedule(schedule_id):
        return {"ok": True, "data": {"id": schedule_id}}

    return ToolContext(
        add_todo=add_todo,
        list_todos=list_todos,
        update_todo=update_todo,
        delete_todo=delete_todo,
        search_todos=search_todos,
        create_schedule=create_schedule,
        list_schedules=list_schedules,
        delete_schedule=delete_schedule,
    )
