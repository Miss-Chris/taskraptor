from __future__ import annotations

from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist
from ninja import Router, Status

from accounts.bearer import AuthBearer
from accounts.schemas import ErrorOut
from agent.debug import (
    conversation_debug_bundle,
    list_debug_conversations,
    user_debug_summary,
)
from agent.debug_schemas import (
    DebugConversationBundleOut,
    DebugConversationsOut,
    DebugSummaryOut,
)

router = Router(tags=["debug"], auth=AuthBearer())


@router.get("/summary", response={200: DebugSummaryOut, 401: ErrorOut})
def debug_summary(request):
    return Status(200, DebugSummaryOut.model_validate(user_debug_summary(request.auth)))


@router.get("/conversations", response={200: DebugConversationsOut, 401: ErrorOut})
def debug_conversations(request, limit: int = 50):
    safe_limit = max(1, min(limit, 200))
    conversations = list_debug_conversations(request.auth, limit=safe_limit)
    return Status(
        200,
        DebugConversationsOut(
            conversations=conversations,
            count=len(conversations),
        ),
    )


@router.get(
    "/conversations/{conversation_id}",
    response={200: DebugConversationBundleOut, 401: ErrorOut, 404: ErrorOut},
)
def debug_conversation(request, conversation_id: UUID, run_id: UUID | None = None, limit: int = 500):
    try:
        bundle = conversation_debug_bundle(
            request.auth,
            conversation_id,
            run_id=run_id,
            limit=max(1, min(limit, 1000)),
        )
    except ObjectDoesNotExist:
        return Status(404, {"detail": "Not found."})
    return Status(200, DebugConversationBundleOut.model_validate(bundle))
