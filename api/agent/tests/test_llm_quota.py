from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.llm import call_llm
from agent.models import LlmModel, SYSTEM_FREE_MODEL_KEY


@pytest.mark.django_db
def test_system_model_provider_requests_do_not_mutate_cached_quota_used(
    settings,
    monkeypatch,
    test_user,
):
    settings.DEEPSEEK_API_KEY = "server-key"
    model = LlmModel.objects.create(
        user=test_user,
        model_key=SYSTEM_FREE_MODEL_KEY,
        quota=10,
        quota_used=3,
        is_active=True,
    )

    def fake_completion(**kwargs):
        assert kwargs["api_key"] == "server-key"
        return SimpleNamespace(usage=SimpleNamespace(total_tokens=250))

    monkeypatch.setattr("agent.llm.completion", fake_completion)

    call_llm(model, [{"role": "user", "content": "hello"}])

    model.refresh_from_db()
    assert model.quota_used == 3
