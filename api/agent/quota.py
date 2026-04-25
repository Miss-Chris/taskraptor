from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from agent.models import AgentRun, AgentRunStatus, LlmModel, SYSTEM_FREE_MODEL_KEY

COUNTED_SYSTEM_RUN_STATUSES = (
    AgentRunStatus.RUNNING,
    AgentRunStatus.COMPLETED,
    AgentRunStatus.FAILED,
)

QUOTA_EXCEEDED_MESSAGE = "You've used up your message quota. Please upgrade or wait for it to reset."


def current_month_bounds(now=None):
    local_now = timezone.localtime(now or timezone.now())
    month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        next_month_start = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month_start = month_start.replace(month=month_start.month + 1)
    return month_start, next_month_start


def current_month_system_request_count(
    user,
    *,
    model: LlmModel | None = None,
    now=None,
) -> int:
    month_start, next_month_start = current_month_bounds(now=now)
    qs = AgentRun.objects.filter(
        user=user,
        llm_model__model_key=SYSTEM_FREE_MODEL_KEY,
        status__in=COUNTED_SYSTEM_RUN_STATUSES,
        started_at__isnull=False,
        created_at__gte=month_start,
        created_at__lt=next_month_start,
    )
    if model is not None:
        qs = qs.filter(llm_model=model)
    return qs.count()


def effective_quota(model: LlmModel) -> int | None:
    if model.model_key != SYSTEM_FREE_MODEL_KEY:
        return model.quota
    if model.quota is not None:
        return model.quota
    return getattr(settings, "SYSTEM_FREE_MONTHLY_REQUEST_QUOTA", 50)


def quota_remaining(model: LlmModel, quota_used: int) -> int | None:
    quota = effective_quota(model)
    if quota is None:
        return None
    return max(quota - quota_used, 0)


def is_system_quota_available(model: LlmModel, quota_used: int) -> bool:
    if not model.is_active:
        return False
    if model.quota_expires_at is not None and timezone.now() > model.quota_expires_at:
        return False
    quota = effective_quota(model)
    if quota is not None and quota_used >= quota:
        return False
    return True


def is_system_quota_exceeded(model: LlmModel, user) -> bool:
    if model.model_key != SYSTEM_FREE_MODEL_KEY:
        return False
    quota_used = current_month_system_request_count(user, model=model)
    return not is_system_quota_available(model, quota_used)
