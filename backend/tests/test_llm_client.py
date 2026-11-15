"""One OpenAI-compatible client is built at startup and shared."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request

from app.services import openai as openai_service
from app.services.agent import AgentConfigurationError, AgentSearchService
from app.services.openai import AiSummary, build_llm_client


def _config(api_key: str | None, api_url: str | None, model: str = "test-model"):
    return SimpleNamespace(api_key=api_key, api_url=api_url, model=model)


def test_no_client_without_credentials():
    with patch.object(openai_service, "OpenAIConfig", return_value=_config(None, None)):
        assert build_llm_client() is None


def test_client_built_from_credentials():
    config = _config("key", "http://llm.test/v1")

    with (
        patch.object(openai_service, "OpenAIConfig", return_value=config),
        patch.object(openai_service, "OpenAI") as client_class,
    ):
        client = build_llm_client()

    client_class.assert_called_once_with(base_url="http://llm.test/v1", api_key="key")
    assert client is client_class.return_value


def test_summary_uses_the_shared_client():
    shared = MagicMock()

    with patch.object(openai_service, "OpenAIConfig", return_value=_config("k", "u")):
        summary = AiSummary(shared)

    assert summary.client is shared


def test_summary_without_a_client_is_unconfigured():
    with pytest.raises(ValueError):
        AiSummary(None)


def _request(llm_client) -> Request:
    state = SimpleNamespace(
        llm_client=llm_client, duck_db=MagicMock(), lance_db=MagicMock()
    )

    return cast(Request, SimpleNamespace(app=SimpleNamespace(state=state)))


def test_agent_search_uses_the_shared_client():
    shared = MagicMock()

    with (
        patch("app.services.agent.ImagePersistData"),
        patch("app.services.agent.LocalitySpecies"),
        patch("app.services.agent.SpeciesPageResolver"),
    ):
        service = AgentSearchService(_request(shared))

    assert service.client is shared


def test_agent_search_without_a_client_is_unconfigured():
    with pytest.raises(AgentConfigurationError):
        AgentSearchService(_request(None))
