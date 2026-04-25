from __future__ import annotations

from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist
from ninja import Router, Status

from accounts.bearer import AuthBearer
from accounts.http import AuthedHttpRequest
from accounts.schemas import ErrorOut
from automations.models import Automation
from automations.schemas import (
    AutomationCreateIn,
    AutomationListOut,
    AutomationOut,
    AutomationRunOut,
    AutomationUpdateIn,
)
from automations.tasks import run_automation_immediately

router = Router(tags=["automations"], auth=AuthBearer())


def _automation_queryset(user):
    return Automation.objects.filter(user=user).order_by("-created_at")


def _to_automation_out(automation: Automation) -> AutomationOut:
    return AutomationOut(
        id=automation.pk,
        prompt=automation.prompt,
        schedule_time=automation.schedule_time,
        is_active=automation.is_active,
        last_run_at=automation.last_run_at,
        created_at=automation.created_at,
        updated_at=automation.updated_at,
    )


def _clean_prompt(prompt: str) -> str:
    return prompt.strip()


@router.get(
    "/",
    response={200: AutomationListOut, 401: ErrorOut},
)
def list_automations(request: AuthedHttpRequest):
    automations = list(_automation_queryset(request.auth))
    return Status(
        200,
        AutomationListOut(
            automations=[_to_automation_out(automation) for automation in automations],
            count=len(automations),
        ),
    )


@router.post(
    "/",
    response={201: AutomationOut, 400: ErrorOut, 401: ErrorOut},
)
def create_automation(request: AuthedHttpRequest, payload: AutomationCreateIn):
    prompt = _clean_prompt(payload.prompt)
    if not prompt:
        return Status(400, {"detail": "Prompt cannot be blank."})

    automation = Automation.objects.create(
        user=request.auth,
        prompt=prompt,
        schedule_time=payload.schedule_time,
    )
    return Status(201, _to_automation_out(automation))


@router.get(
    "/{automation_id}",
    response={200: AutomationOut, 401: ErrorOut, 404: ErrorOut},
)
def get_automation(request: AuthedHttpRequest, automation_id: UUID):
    try:
        automation = _automation_queryset(request.auth).get(pk=automation_id)
    except ObjectDoesNotExist:
        return Status(404, {"detail": "Not found."})
    return Status(200, _to_automation_out(automation))


@router.post(
    "/{automation_id}/test",
    response={202: AutomationRunOut, 401: ErrorOut, 404: ErrorOut},
)
def test_automation(request: AuthedHttpRequest, automation_id: UUID):
    try:
        automation = _automation_queryset(request.auth).get(pk=automation_id)
    except ObjectDoesNotExist:
        return Status(404, {"detail": "Not found."})

    run_automation_immediately.delay(str(automation.pk))
    return Status(
        202,
        AutomationRunOut(
            automation_id=automation.pk,
            queued=True,
        ),
    )


@router.patch(
    "/{automation_id}",
    response={200: AutomationOut, 400: ErrorOut, 401: ErrorOut, 404: ErrorOut},
)
def update_automation(
    request: AuthedHttpRequest,
    automation_id: UUID,
    payload: AutomationUpdateIn,
):
    try:
        automation = _automation_queryset(request.auth).get(pk=automation_id)
    except ObjectDoesNotExist:
        return Status(404, {"detail": "Not found."})

    update_fields: list[str] = []
    if payload.prompt is not None:
        prompt = _clean_prompt(payload.prompt)
        if not prompt:
            return Status(400, {"detail": "Prompt cannot be blank."})
        automation.prompt = prompt
        update_fields.append("prompt")
    if payload.schedule_time is not None:
        automation.schedule_time = payload.schedule_time
        update_fields.append("schedule_time")
    if payload.is_active is not None:
        automation.is_active = payload.is_active
        update_fields.append("is_active")

    if update_fields:
        update_fields.append("updated_at")
        automation.save(update_fields=update_fields)
    return Status(200, _to_automation_out(automation))


@router.delete(
    "/{automation_id}",
    response={204: None, 401: ErrorOut, 404: ErrorOut},
)
def delete_automation(request: AuthedHttpRequest, automation_id: UUID):
    deleted, _ = Automation.objects.filter(
        pk=automation_id,
        user=request.auth,
    ).delete()
    if deleted == 0:
        return Status(404, {"detail": "Not found."})
    return Status(204, None)
