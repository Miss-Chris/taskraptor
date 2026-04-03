from celery import shared_task
from django.utils import timezone


@shared_task
def run_scheduled_agent(schedule_id: str) -> None:
    from .models import Schedule
    from .service import handle_message

    try:
        schedule = Schedule.objects.select_related("user").get(id=schedule_id)
    except Schedule.DoesNotExist:
        return

    if not schedule.is_active:
        return

    handle_message(
        user_id=schedule.user_id,
        text=schedule.instruction,
        channel="schedule",
    )

    if not schedule.is_recurring:
        schedule.is_active = False
        schedule.save(update_fields=["is_active"])


@shared_task
def dispatch_due_schedules() -> None:
    from .models import Schedule

    now = timezone.now()
    due = Schedule.objects.filter(is_active=True, next_run_at__lte=now)
    for schedule in due:
        run_scheduled_agent.delay(str(schedule.id))
