from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from ninja import Router, Status

from accounts.bearer import AuthBearer
from accounts.http import AuthedHttpRequest
from accounts.schemas import ErrorOut
from agent.models import (
    AgentRun,
    AgentRunStatus,
    LlmModel,
    MessageLog,
    SUPPORTED_MODEL_KEYS,
    SYSTEM_FREE_MODEL_KEY,
    get_or_create_system_model,
)
from agent.quota import (
    current_month_system_request_count,
    effective_quota,
    is_system_quota_available,
    quota_remaining,
)
from agent.usage_schemas import (
    SupportedModelOptionOut,
    UsageLlmModelOut,
    UsageModelCreateIn,
    UsageModelUpdateIn,
    UsageSummaryOut,
    UsageSystemQuotaOut,
    UsageTotalsOut,
)

router = Router(tags=["usage"], auth=AuthBearer())

RECENT_USAGE_DAYS = 30


def _provider_for_model_key(model_key: str) -> str:
    if model_key == SYSTEM_FREE_MODEL_KEY:
        return SYSTEM_FREE_MODEL_KEY
    return model_key.split("/", 1)[0]


def _display_name_for_model_key(model_key: str) -> str:
    if model_key == SYSTEM_FREE_MODEL_KEY:
        return "System model"
    provider, _, name = model_key.partition("/")
    return f"{provider.title()} {name}".replace("-", " ")


def _to_model_out(model: LlmModel, *, system_quota_used: int) -> UsageLlmModelOut:
    quota_used = (
        system_quota_used
        if model.model_key == SYSTEM_FREE_MODEL_KEY
        else model.quota_used
    )
    is_available = (
        is_system_quota_available(model, quota_used)
        if model.model_key == SYSTEM_FREE_MODEL_KEY
        else not model.is_quota_exceeded
    )
    return UsageLlmModelOut(
        id=model.pk,
        model_key=model.model_key,
        provider=_provider_for_model_key(model.model_key),
        display_name=_display_name_for_model_key(model.model_key),
        has_api_key=bool((model.api_key or "").strip()),
        quota=effective_quota(model),
        quota_used=quota_used,
        quota_remaining=quota_remaining(model, quota_used),
        quota_expires_at=model.quota_expires_at,
        context_message_limit=model.context_message_limit,
        is_active=model.is_active,
        is_system=model.model_key == SYSTEM_FREE_MODEL_KEY,
        is_available=is_available,
        supports_image_input=model.supports_image_input,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_system_quota_out(model: LlmModel, *, quota_used: int) -> UsageSystemQuotaOut:
    return UsageSystemQuotaOut(
        model_id=model.pk,
        quota=effective_quota(model),
        quota_used=quota_used,
        quota_remaining=quota_remaining(model, quota_used),
        quota_expires_at=model.quota_expires_at,
        is_available=is_system_quota_available(model, quota_used),
        is_active=model.is_active,
    )


def _supported_model_options() -> list[SupportedModelOptionOut]:
    return [
        SupportedModelOptionOut(
            model_key=model_key,
            provider=_provider_for_model_key(model_key),
            display_name=_display_name_for_model_key(model_key),
            requires_api_key=True,
            supports_image_input=LlmModel(model_key=model_key).supports_image_input,
        )
        for model_key in sorted(SUPPORTED_MODEL_KEYS)
        if model_key != SYSTEM_FREE_MODEL_KEY
    ]


def _error_detail(exc: ValidationError) -> str:
    if hasattr(exc, "message_dict"):
        messages: list[str] = []
        for field, field_messages in exc.message_dict.items():
            messages.extend(f"{field}: {message}" for message in field_messages)
        return " ".join(messages)
    return " ".join(exc.messages)


def _usage_totals(user) -> UsageTotalsOut:
    recent_since = timezone.now() - timedelta(days=RECENT_USAGE_DAYS)
    token_totals = MessageLog.objects.filter(
        agent_run__user=user,
        agent_run__created_at__gte=recent_since,
    ).exclude(
        agent_run__llm_model__model_key=SYSTEM_FREE_MODEL_KEY,
    ).aggregate(
        input_tokens=Sum("input_tokens"),
        output_tokens=Sum("output_tokens"),
    )
    input_tokens = token_totals["input_tokens"] or 0
    output_tokens = token_totals["output_tokens"] or 0
    recent_runs = AgentRun.objects.filter(user=user, created_at__gte=recent_since)
    return UsageTotalsOut(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        recent_run_count=recent_runs.count(),
        failed_run_count=AgentRun.objects.filter(
            user=user,
            status=AgentRunStatus.FAILED,
        ).count(),
        recent_since=recent_since,
    )


def _ensure_system_model(user) -> LlmModel:
    active_non_system_exists = LlmModel.objects.filter(
        user=user,
        is_active=True,
    ).exclude(model_key=SYSTEM_FREE_MODEL_KEY).exists()
    system_model = get_or_create_system_model(user)
    if active_non_system_exists and system_model.is_active:
        system_model.is_active = False
        system_model.save(update_fields=["is_active", "updated_at"])
    return system_model


def _model_queryset(user):
    return LlmModel.objects.filter(user=user).order_by("-is_active", "model_key", "-created_at")


def _get_user_model(user, model_id: UUID) -> LlmModel:
    return LlmModel.objects.get(pk=model_id, user=user)


def _set_only_active_model(user, model: LlmModel) -> None:
    with transaction.atomic():
        LlmModel.objects.select_for_update().filter(user=user).update(is_active=False)
        LlmModel.objects.filter(pk=model.pk, user=user).update(
            is_active=True,
            updated_at=timezone.now(),
        )


def _validate_byo_model(model: LlmModel) -> str | None:
    if model.model_key == SYSTEM_FREE_MODEL_KEY:
        return "The system model cannot be managed through this endpoint."
    if not (model.api_key or "").strip():
        return "API key is required for BYO-key models."
    try:
        model.full_clean()
    except ValidationError as exc:
        return _error_detail(exc)
    return None


@router.get("/summary", response={200: UsageSummaryOut, 401: ErrorOut})
def usage_summary(request: AuthedHttpRequest):
    system_model = _ensure_system_model(request.auth)
    system_quota_used = current_month_system_request_count(
        request.auth,
        model=system_model,
    )
    models = list(_model_queryset(request.auth))
    return Status(
        200,
        UsageSummaryOut(
            system_model=_to_system_quota_out(
                system_model,
                quota_used=system_quota_used,
            ),
            totals=_usage_totals(request.auth),
            models=[
                _to_model_out(model, system_quota_used=system_quota_used)
                for model in models
            ],
            supported_models=_supported_model_options(),
        ),
    )


@router.post(
    "/models",
    response={201: UsageLlmModelOut, 400: ErrorOut, 401: ErrorOut},
)
def create_usage_model(request: AuthedHttpRequest, payload: UsageModelCreateIn):
    model = LlmModel(
        user=request.auth,
        model_key=payload.model_key.strip(),
        api_key=payload.api_key.strip(),
        context_message_limit=payload.context_message_limit,
        is_active=False,
    )
    error = _validate_byo_model(model)
    if error:
        return Status(400, {"detail": error})

    model.save()
    if payload.is_active:
        _set_only_active_model(request.auth, model)
        model.refresh_from_db()
    system_quota_used = current_month_system_request_count(request.auth)
    return Status(201, _to_model_out(model, system_quota_used=system_quota_used))


@router.patch(
    "/models/{model_id}",
    response={200: UsageLlmModelOut, 400: ErrorOut, 401: ErrorOut, 404: ErrorOut},
)
def update_usage_model(
    request: AuthedHttpRequest,
    model_id: UUID,
    payload: UsageModelUpdateIn,
):
    try:
        model = _get_user_model(request.auth, model_id)
    except ObjectDoesNotExist:
        return Status(404, {"detail": "Not found."})

    if model.model_key == SYSTEM_FREE_MODEL_KEY:
        return Status(400, {"detail": "The system model quota and key settings are read-only."})

    if payload.api_key is not None:
        model.api_key = payload.api_key.strip()
    if payload.context_message_limit is not None:
        model.context_message_limit = payload.context_message_limit

    original_is_active = model.is_active
    if payload.is_active is False and original_is_active:
        return Status(400, {"detail": "Activate another model before deactivating this one."})

    model.is_active = original_is_active
    error = _validate_byo_model(model)
    if error:
        return Status(400, {"detail": error})

    should_activate = payload.is_active is True
    if payload.is_active is False:
        model.is_active = False
    model.save(update_fields=["api_key", "context_message_limit", "is_active", "updated_at"])
    if should_activate:
        _set_only_active_model(request.auth, model)
    model.refresh_from_db()
    system_quota_used = current_month_system_request_count(request.auth)
    return Status(200, _to_model_out(model, system_quota_used=system_quota_used))


@router.post(
    "/models/{model_id}/activate",
    response={200: UsageLlmModelOut, 400: ErrorOut, 401: ErrorOut, 404: ErrorOut},
)
def activate_usage_model(request: AuthedHttpRequest, model_id: UUID):
    try:
        model = _get_user_model(request.auth, model_id)
    except ObjectDoesNotExist:
        return Status(404, {"detail": "Not found."})

    if model.model_key != SYSTEM_FREE_MODEL_KEY:
        error = _validate_byo_model(model)
        if error:
            return Status(400, {"detail": error})

    _set_only_active_model(request.auth, model)
    model.refresh_from_db()
    system_quota_used = current_month_system_request_count(request.auth)
    return Status(200, _to_model_out(model, system_quota_used=system_quota_used))


@router.delete(
    "/models/{model_id}",
    response={204: None, 400: ErrorOut, 401: ErrorOut, 404: ErrorOut},
)
def delete_usage_model(request: AuthedHttpRequest, model_id: UUID):
    try:
        model = _get_user_model(request.auth, model_id)
    except ObjectDoesNotExist:
        return Status(404, {"detail": "Not found."})

    if model.model_key == SYSTEM_FREE_MODEL_KEY:
        return Status(400, {"detail": "The system model cannot be deleted."})
    if model.is_active:
        return Status(400, {"detail": "Activate another model before deleting this one."})

    model.delete()
    return Status(204, None)
