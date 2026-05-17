import httpx
import pytest

pytestmark = pytest.mark.skip(
    reason="legacy-deferred per Phase 0.5/D5 - Code Cockpit subsystem deferred"
)

from app.services.code.providers import (
    CodeProviderError,
    OpenAICodexProvider,
    ProviderRequest,
    list_available_provider_profiles,
    list_team_chat_models,
    resolve_provider_profile,
    settings,
)


@pytest.mark.asyncio
async def test_openai_provider_returns_stub_when_disabled():
    provider = OpenAICodexProvider(enabled=False)

    response = await provider.run(
        ProviderRequest(
            session_id=42,
            prompt="Summarize the workspace posture.",
            model="gpt-5.5",
            provider="openai",
            permission_mode="read-only",
        )
    )

    assert response.blocked_reason == "provider_unavailable"
    assert response.usage == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    assert "workspace posture" in response.output_text


def test_extract_output_text_prefers_direct_output_text():
    body = {"output_text": "Direct output"}
    assert OpenAICodexProvider._extract_output_text(body) == "Direct output"


def test_extract_output_text_falls_back_to_message_content():
    body = {
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "Hello"},
                    {"type": "output_text", "text": "World"},
                ],
            }
        ]
    }
    assert OpenAICodexProvider._extract_output_text(body) == "Hello\nWorld"


def test_provider_classifies_trust_required_errors():
    provider = OpenAICodexProvider(enabled=True)
    response = httpx.Response(
        403,
        request=httpx.Request("POST", "https://example.com/responses"),
        json={"error": {"code": "trust_required", "message": "Workspace trust is required before continuing."}},
    )

    error = provider._build_error(response)

    assert error.blocked_reason == "trust_required"
    assert "trust gate" in error.user_message.lower() or "trust" in error.user_message.lower()


def test_provider_classifies_prompt_misdelivery_from_error_message():
    provider = OpenAICodexProvider(enabled=True)
    response = httpx.Response(
        400,
        request=httpx.Request("POST", "https://example.com/responses"),
        json={"error": {"code": "bad_request", "message": "Prompt was delivered to the wrong shell target."}},
    )

    error = provider._build_error(response)

    assert error.blocked_reason == "prompt_misdelivery"
    assert "wrong runtime surface" in error.user_message.lower() or "prompt" in error.user_message.lower()


@pytest.mark.asyncio
async def test_provider_retries_transient_gateway_error(monkeypatch):
    provider = OpenAICodexProvider(enabled=True)
    attempts = {"count": 0}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            attempts["count"] += 1
            if attempts["count"] == 1:
                return httpx.Response(502, request=httpx.Request("POST", url), text="bad gateway")
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"output_text": "Recovered", "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}},
            )

    monkeypatch.setattr("app.services.code.providers.httpx.AsyncClient", lambda timeout=60.0: FakeAsyncClient())

    response = await provider.run(
        ProviderRequest(
            session_id=7,
            prompt="Say ok",
            model="gpt-5.5",
            provider="openai",
            permission_mode="read-only",
        )
    )

    assert attempts["count"] == 2
    assert response.output_text == "Recovered"


@pytest.mark.asyncio
async def test_provider_surfaces_model_cooldown_without_retry_storm(monkeypatch):
    provider = OpenAICodexProvider(enabled=True)
    attempts = {"count": 0}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            attempts["count"] += 1
            return httpx.Response(
                429,
                request=httpx.Request("POST", url),
                json={
                    "error": {
                        "code": "model_cooldown",
                        "message": "All credentials for model gpt-5.4 are cooling down",
                        "reset_seconds": 3600,
                        "reset_time": "1h0m0s",
                    }
                },
            )

    monkeypatch.setattr("app.services.code.providers.httpx.AsyncClient", lambda timeout=60.0: FakeAsyncClient())

    with pytest.raises(CodeProviderError) as exc:
        await provider.run(
            ProviderRequest(
                session_id=8,
                prompt="Say ok",
                model="gpt-5.4",
                provider="openai",
                permission_mode="read-only",
            )
        )

    assert attempts["count"] == 1
    assert "model cooldown" in str(exc.value).lower()


def test_provider_profiles_include_public_and_team_aliases(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "default-key")
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", "https://default.example/v1")
    monkeypatch.setattr(settings, "OPENAI_PUBLIC_API_KEY", "public-key")
    monkeypatch.setattr(settings, "OPENAI_PUBLIC_BASE_URL", "https://public.example/v1")
    monkeypatch.setattr(settings, "OPENAI_TEAM_API_KEY", "team-key")
    monkeypatch.setattr(settings, "OPENAI_TEAM_BASE_URL", "https://team.example/v1")

    profiles = {profile.name: profile for profile in list_available_provider_profiles()}

    assert {"openai", "openai-public", "openai-team"}.issubset(profiles)
    assert profiles["openai-team"].base_url == "https://team.example/v1"
    assert profiles["openai-public"].api_key == "public-key"


def test_resolve_provider_profile_rejects_unconfigured_alias(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_TEAM_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_TEAM_BASE_URL", "")

    with pytest.raises(CodeProviderError) as exc:
        resolve_provider_profile("openai-team")

    assert "not configured" in exc.value.user_message.lower()


@pytest.mark.asyncio
async def test_provider_run_uses_selected_alias_credentials(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "default-key")
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", "https://default.example/v1")
    monkeypatch.setattr(settings, "OPENAI_TEAM_API_KEY", "team-key")
    monkeypatch.setattr(settings, "OPENAI_TEAM_BASE_URL", "https://team.example/v1")

    captured: dict[str, object] = {}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"output_text": "Team pool ok", "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}},
            )

    monkeypatch.setattr("app.services.code.providers.httpx.AsyncClient", lambda timeout=60.0: FakeAsyncClient())

    provider = OpenAICodexProvider(enabled=True)
    response = await provider.run(
        ProviderRequest(
            session_id=77,
            prompt="Use the team pool",
            model="gpt-5.4",
            provider="openai-team",
            permission_mode="workspace-write",
        )
    )

    assert response.output_text == "Team pool ok"
    assert captured["url"] == "https://team.example/v1/responses"
    assert captured["headers"]["Authorization"] == "Bearer team-key"


@pytest.mark.asyncio
async def test_list_team_chat_models_filters_and_sorts_models(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_TEAM_API_KEY", "team-key")
    monkeypatch.setattr(settings, "OPENAI_TEAM_BASE_URL", "https://team.example/v1")

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            return httpx.Response(
                200,
                request=httpx.Request("GET", url),
                json={
                    "data": [
                        {"id": "gpt-image-2"},
                        {"id": "gpt-5.4"},
                        {"id": "gpt-5.5"},
                        {"id": "gpt-5.2"},
                    ]
                },
            )

    monkeypatch.setattr("app.services.code.providers.httpx.AsyncClient", lambda timeout=30.0: FakeAsyncClient())

    models = await list_team_chat_models()

    assert models == ["gpt-5.5", "gpt-5.4"]
