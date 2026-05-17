from __future__ import annotations

from typing import Any

from django.conf import settings
from django.utils import timezone
from litellm import completion

from agent.models import LlmModel, LlmProvider, SYSTEM_FREE_MODEL_KEY, SYSTEM_FREE_UNDERLYING_MODEL


class QuotaExceededError(Exception):
    """Raised when an LlmModel quota or expiry blocks a call."""


class InactiveLlmModelError(Exception):
    """Raised when the LlmModel is inactive."""


class MissingApiKeyError(Exception):
    """Raised when no API key is available for the request."""


def _litellm_model_id(llm_model: LlmModel) -> str:
    if llm_model.model_key == SYSTEM_FREE_MODEL_KEY:
        return SYSTEM_FREE_UNDERLYING_MODEL
    return llm_model.model_key


def _resolve_api_key(llm_model: LlmModel) -> str:
    if llm_model.model_key == SYSTEM_FREE_MODEL_KEY:
        key = (getattr(settings, "DEEPSEEK_API_KEY", None) or "").strip()
        if not key:
            raise MissingApiKeyError(
                "DEEPSEEK_API_KEY is not configured for system_free LLM calls.",
            )
        return key

    provider = llm_model.model_key.split("/")[0]

    if provider == LlmProvider.DEEPSEEK:
        key = (llm_model.api_key or "").strip()
        if not key:
            raise MissingApiKeyError("DeepSeek API key is missing on this LlmModel.")
        return key

    if provider == LlmProvider.ANTHROPIC:
        key = (llm_model.api_key or "").strip()
        if not key:
            raise MissingApiKeyError("Anthropic API key is missing on this LlmModel.")
        return key

    if provider == LlmProvider.OPENAI:
        key = (llm_model.api_key or "").strip()
        if not key:
            raise MissingApiKeyError("OpenAI API key is missing on this LlmModel.")
        return key

    key = (llm_model.api_key or "").strip()
    if not key:
        raise MissingApiKeyError(f"API key is missing for provider {provider!r}.")
    return key


def call_llm(llm_model: LlmModel, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
    """
    Call the LLM configured on ``llm_model`` via litellm.

    For ``system_free`` configs, enforces expiry before the call. Request quota
    is enforced at the AgentRun level so tool-heavy rounds still count once.

    Returns the litellm completion response object.
    """
    if not llm_model.is_active:
        raise InactiveLlmModelError(f"LlmModel id={llm_model.pk} is not active.")

    # Refresh availability-related fields from DB (short read, no lock during HTTP).
    llm_model.refresh_from_db(
        fields=["quota_expires_at", "is_active"],
    )
    if not llm_model.is_active:
        raise InactiveLlmModelError(f"LlmModel id={llm_model.pk} is not active.")
    if (
        llm_model.quota_expires_at is not None
        and timezone.now() > llm_model.quota_expires_at
    ):
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

    return response
