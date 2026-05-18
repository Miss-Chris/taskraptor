from __future__ import annotations

import pytest

from agent.llm import MissingApiKeyError
from agent.models import LlmModel
from agent.run import MODEL_CONFIGURATION_HELP_MESSAGE, run_agent


@pytest.mark.django_db
def test_run_agent_missing_api_key_returns_actionable_configuration_message(test_user):
    model = LlmModel.objects.create(
        user=test_user,
        model_key="deepseek/deepseek-chat",
        api_key="",
    )

    def missing_key_llm(*args, **kwargs):
        raise MissingApiKeyError("DeepSeek API key is missing on this LlmModel.")

    result = run_agent(
        user_id=test_user.pk,
        llm_model=model,
        history=[],
        new_message="hello",
        llm_callable=missing_key_llm,
    )

    assert result.response_text == MODEL_CONFIGURATION_HELP_MESSAGE
    assert result.new_messages[-1].content == MODEL_CONFIGURATION_HELP_MESSAGE
    assert result.error == "DeepSeek API key is missing on this LlmModel."
