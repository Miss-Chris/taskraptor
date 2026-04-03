import pytest

from apps.agent2.tools import complete_task, create_task, delete_task, list_tasks, search_tasks, update_task
from apps.tasks.models import Task


@pytest.mark.django_db
def test_create_task_creates_db_row(user):
    result = create_task(user.pk, description="Buy milk")

    assert result["ok"] is True
    assert Task.objects.filter(user=user, description="Buy milk").exists()


@pytest.mark.django_db
def test_list_tasks_filters_by_status(user):
    Task.objects.create(user=user, description="Open task", status=Task.Status.PENDING)
    Task.objects.create(user=user, description="Done task", status=Task.Status.DONE)

    result = list_tasks(user.pk, status=Task.Status.PENDING)

    assert result["ok"] is True
    descriptions = [task["description"] for task in result["data"]]
    assert descriptions == ["Open task"]


@pytest.mark.django_db
def test_search_tasks_matches_only_owner(user, other_user):
    Task.objects.create(user=user, description="Call dentist")
    Task.objects.create(user=other_user, description="Call dentist")

    result = search_tasks(user.pk, "dentist", status=None)

    assert result["ok"] is True
    assert result["count"] == 1


@pytest.mark.django_db
def test_complete_task_marks_task_done(user):
    task = Task.objects.create(user=user, description="Write report")

    result = complete_task(user.pk, task.id)

    assert result["ok"] is True
    task.refresh_from_db()
    assert task.status == Task.Status.DONE


@pytest.mark.django_db
def test_update_and_delete_task(user):
    task = Task.objects.create(user=user, description="Draft note")

    updated = update_task(user.pk, task.id, description="Draft weekly note")
    deleted = delete_task(user.pk, task.id)

    assert updated["ok"] is True
    assert updated["data"]["description"] == "Draft weekly note"
    assert deleted["ok"] is True
    assert not Task.objects.filter(id=task.id).exists()

