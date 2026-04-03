"""
Unit tests for the tool functions (apps/agent/tools.py).
Uses a real DB via pytest-django.
"""
import pytest

from apps.agent.models import Todo
from apps.agent.tools import (
    add_todo,
    delete_todo,
    list_todos,
    search_todos,
    update_todo,
)


@pytest.mark.django_db
def test_add_todo_creates_db_row(user):
    result = add_todo(user.pk, title="Buy milk", priority="high")

    assert result["ok"] is True
    assert Todo.objects.filter(user=user, title="Buy milk").exists()
    assert result["data"]["priority"] == "high"


@pytest.mark.django_db
def test_add_todo_with_due_date(user):
    result = add_todo(user.pk, title="Meeting", due_date="2026-04-01", due_time="09:00")

    assert result["ok"] is True
    todo = Todo.objects.get(id=result["data"]["id"])
    assert str(todo.due_date) == "2026-04-01"
    assert todo.due_time.strftime("%H:%M") == "09:00"


@pytest.mark.django_db
def test_list_todos_excludes_other_users(user, other_user):
    add_todo(user.pk, title="Mine")
    add_todo(other_user.pk, title="Theirs")

    result = list_todos(user.pk)

    assert result["ok"] is True
    titles = [t["title"] for t in result["data"]]
    assert "Mine" in titles
    assert "Theirs" not in titles


@pytest.mark.django_db
def test_list_todos_excludes_completed_by_default(user):
    r = add_todo(user.pk, title="Active")
    update_todo(user.pk, r["data"]["id"], is_completed=True)
    add_todo(user.pk, title="Still active")

    result = list_todos(user.pk)

    titles = [t["title"] for t in result["data"]]
    assert "Active" not in titles
    assert "Still active" in titles


@pytest.mark.django_db
def test_update_todo_only_affects_owner(user, other_user):
    r = add_todo(other_user.pk, title="Their todo")
    todo_id = r["data"]["id"]

    result = update_todo(user.pk, todo_id, title="Hijacked")

    assert result["ok"] is False
    # DB record unchanged
    assert Todo.objects.get(id=todo_id).title == "Their todo"


@pytest.mark.django_db
def test_update_todo_sets_completed_at(user):
    r = add_todo(user.pk, title="Task")
    todo_id = r["data"]["id"]

    result = update_todo(user.pk, todo_id, is_completed=True)

    assert result["ok"] is True
    todo = Todo.objects.get(id=todo_id)
    assert todo.is_completed is True
    assert todo.completed_at is not None


@pytest.mark.django_db
def test_delete_todo_returns_error_for_wrong_user(user, other_user):
    r = add_todo(other_user.pk, title="Other's todo")
    todo_id = r["data"]["id"]

    result = delete_todo(user.pk, todo_id)

    assert result["ok"] is False
    assert Todo.objects.filter(id=todo_id).exists()


@pytest.mark.django_db
def test_delete_todo_removes_row(user):
    r = add_todo(user.pk, title="Temporary")
    todo_id = r["data"]["id"]

    result = delete_todo(user.pk, todo_id)

    assert result["ok"] is True
    assert not Todo.objects.filter(id=todo_id).exists()


@pytest.mark.django_db
def test_search_todos_matches_title_and_notes(user):
    add_todo(user.pk, title="Call dental office")
    add_todo(user.pk, title="Groceries", notes="Don't forget dental floss")
    add_todo(user.pk, title="Walk dog")

    result = search_todos(user.pk, "dental")

    titles = [t["title"] for t in result["data"]]
    assert "Call dental office" in titles
    assert "Groceries" in titles
    assert "Walk dog" not in titles


@pytest.mark.django_db
def test_search_todos_case_insensitive(user):
    add_todo(user.pk, title="Buy MILK")

    result = search_todos(user.pk, "milk")

    assert result["count"] == 1
