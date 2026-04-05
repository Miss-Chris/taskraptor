from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db.models import F
from django.utils import timezone
from litellm import completion

from agent.models import LlmModel, LlmProvider


class QuotaExceededError(Exception):
    """Raised when an LlmModel quota or expiry blocks a call."""


class InactiveLlmModelError(Exception):
    """Raised when the LlmModel is inactive."""


class MissingApiKeyError(Exception):
    """Raised when no API key is available for the request."""


def _litellm_model_id(llm_model: LlmModel) -> str:
    return f"anthropic/{llm_model.model_name}"


def _resolve_api_key(llm_model: LlmModel) -> str:
    if llm_model.provider == LlmProvider.SYSTEM_FREE:
        key = (getattr(settings, "SERVER_API_KEY", None) or "").strip()
        if not key:
            raise MissingApiKeyError(
                "SERVER_API_KEY is not configured for system_free LLM calls.",
            )
        return key
    key = (llm_model.api_key or "").strip()
    if not key:
        raise MissingApiKeyError("Anthropic API key is missing on this LlmModel.")
    return key


def _total_tokens_from_response(response: Any) -> int:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 1
    total = getattr(usage, "total_tokens", None)
    if total is not None:
        return int(total)
    prompt = getattr(usage, "prompt_tokens", None) or 0
    completion_tokens = getattr(usage, "completion_tokens", None) or 0
    n = int(prompt) + int(completion_tokens)
    return n if n > 0 else 1


def call_llm(llm_model: LlmModel, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
    """
    Call the LLM configured on ``llm_model`` via litellm.

    For ``system_free`` configs, enforces quota/expiry before the call and
    increments ``quota_used`` by reported total tokens after a successful response.

    Returns the litellm completion response object.
    """
    if not llm_model.is_active:
        raise InactiveLlmModelError(f"LlmModel id={llm_model.pk} is not active.")

    # Refresh quota-related fields from DB (short read, no lock during HTTP).
    llm_model.refresh_from_db(
        fields=["quota", "quota_used", "quota_expires_at", "is_active"],
    )
    if llm_model.is_quota_exceeded:
        raise QuotaExceededError(
            f"LlmModel id={llm_model.pk} quota expired or exhausted.",
        )

    api_key = _resolve_api_key(llm_model)
    model = _litellm_model_id(llm_model)

    response = completion(
        model=model,
        messages=messages,
        api_key=api_key,
        **kwargs,
    )

    if llm_model.provider == LlmProvider.SYSTEM_FREE:
        delta = _total_tokens_from_response(response)
        LlmModel.objects.filter(pk=llm_model.pk).update(
            quota_used=F("quota_used") + delta,
            updated_at=timezone.now(),
        )

    return response
