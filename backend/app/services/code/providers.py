"""
Provider adapters for BOS Code.
"""

import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol

import httpx

from app.config import get_settings

settings = get_settings()


class CodeProviderError(RuntimeError):
    """Structured provider failure."""

    def __init__(
        self,
        message: str,
        *,
        blocked_reason: str = "provider_error",
        user_message: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.blocked_reason = blocked_reason
        self.user_message = user_message or message
        self.retry_after_seconds = retry_after_seconds


@dataclass(slots=True)
class ProviderRequest:
    session_id: int
    prompt: str
    model: str
    provider: str
    permission_mode: str
    tool_names: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CodeProviderResponse:
    summary: str
    output_text: str
    usage: dict[str, int] = field(default_factory=dict)
    estimated_cost: float | None = None
    blocked_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    name: str
    label: str
    base_url: str
    api_key: str
    organization: str
    project: str
    default_model: str
    is_default: bool = False

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.base_url)


class ModelProvider(Protocol):
    async def run(self, request: ProviderRequest) -> CodeProviderResponse:
        """Run a coding turn against the configured model backend."""

    async def stream(self, request: ProviderRequest) -> AsyncIterator[str]:
        """Yield streaming output chunks for the configured backend."""


def _provider_headers(profile: ProviderProfile, *, session_id: int | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {profile.api_key}",
        "Content-Type": "application/json",
    }
    if session_id is not None:
        headers["X-Client-Request-Id"] = f"bos-code-session-{session_id}"
    if profile.organization:
        headers["OpenAI-Organization"] = profile.organization
    if profile.project:
        headers["OpenAI-Project"] = profile.project
    return headers


def _provider_profiles() -> list[ProviderProfile]:
    public_api_key = settings.OPENAI_PUBLIC_API_KEY or settings.OPENAI_API_KEY
    public_base_url = settings.OPENAI_PUBLIC_BASE_URL or settings.OPENAI_BASE_URL
    public_organization = settings.OPENAI_PUBLIC_ORGANIZATION or settings.OPENAI_ORGANIZATION
    public_project = settings.OPENAI_PUBLIC_PROJECT or settings.OPENAI_PROJECT

    return [
        ProviderProfile(
            name="openai",
            label="OpenAI Default",
            base_url=settings.OPENAI_BASE_URL,
            api_key=settings.OPENAI_API_KEY,
            organization=settings.OPENAI_ORGANIZATION,
            project=settings.OPENAI_PROJECT,
            default_model=settings.BOS_CODE_DEFAULT_MODEL,
            is_default=True,
        ),
        ProviderProfile(
            name="openai-public",
            label="OpenAI Public Pool",
            base_url=public_base_url,
            api_key=public_api_key,
            organization=public_organization,
            project=public_project,
            default_model=settings.BOS_CODE_DEFAULT_MODEL,
        ),
        ProviderProfile(
            name="openai-team",
            label="OpenAI Team Pool",
            base_url=settings.OPENAI_TEAM_BASE_URL,
            api_key=settings.OPENAI_TEAM_API_KEY,
            organization=settings.OPENAI_TEAM_ORGANIZATION,
            project=settings.OPENAI_TEAM_PROJECT,
            default_model=settings.BOS_CODE_DEFAULT_MODEL,
        ),
    ]


def list_available_provider_profiles() -> list[ProviderProfile]:
    seen_names: set[str] = set()
    enabled_profiles: list[ProviderProfile] = []
    for profile in _provider_profiles():
        if profile.name in seen_names or not profile.enabled:
            continue
        seen_names.add(profile.name)
        enabled_profiles.append(profile)
    return enabled_profiles


def resolve_provider_profile(provider_name: str | None) -> ProviderProfile:
    normalized = (provider_name or settings.BOS_CODE_DEFAULT_PROVIDER or "openai").strip().lower()
    for profile in _provider_profiles():
        if profile.name == normalized:
            if profile.enabled:
                return profile
            raise CodeProviderError(
                f"Provider '{normalized}' is not configured.",
                blocked_reason="provider_unavailable",
                user_message=f"Provider '{normalized}' is not configured in BOS yet.",
            )
    raise CodeProviderError(
        f"Unknown provider '{normalized}'.",
        blocked_reason="provider_error",
        user_message=f"Provider '{normalized}' is not supported by BOS Code.",
    )


def _team_model_sort_key(model_id: str) -> tuple[int, str]:
    if model_id == "gpt-5.5":
        return (0, model_id)
    if model_id == "gpt-5.4":
        return (1, model_id)
    if model_id.startswith("gpt-5."):
        return (2, model_id)
    return (9, model_id)


async def list_provider_models(provider_name: str) -> list[str]:
    profile = resolve_provider_profile(provider_name)
    headers = _provider_headers(profile)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{profile.base_url}/models", headers=headers)
        except httpx.HTTPError as exc:
            raise CodeProviderError(
                f"Provider model catalog request failed: {exc}",
                blocked_reason="provider_error",
                user_message="BOS could not read the provider model catalog right now.",
            ) from exc

    if not response.is_success:
        raise OpenAICodexProvider(enabled=True)._build_error(response)

    body = response.json() if response.content else {}
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        return []

    model_ids: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if isinstance(model_id, str) and model_id.strip():
            model_ids.append(model_id.strip())

    return sorted(set(model_ids), key=_team_model_sort_key)


async def list_team_chat_models() -> list[str]:
    allowed = {"gpt-5.5", "gpt-5.4"}
    return [model_id for model_id in await list_provider_models("openai-team") if model_id in allowed]


class OpenAICodexProvider:
    """
    BOS Code v1 default provider.

    This implementation is intentionally conservative: it preserves the
    provider boundary even when a real OpenAI client is not configured.
    """
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(self, *, enabled: bool | None = None) -> None:
        self.enabled = bool(list_available_provider_profiles()) if enabled is None else enabled
        self.max_retries = 2
        self.base_backoff_seconds = 1.0

    async def run(self, request: ProviderRequest) -> CodeProviderResponse:
        if not self.enabled:
            prompt_excerpt = request.prompt.strip().splitlines()[0][:120] if request.prompt.strip() else "empty prompt"
            placeholder_output = (
                "BOS Code provider boundary is active, but live OpenAI/Codex execution is currently "
                f"disabled. Latest prompt excerpt: {prompt_excerpt}"
            )
            return CodeProviderResponse(
                summary=placeholder_output,
                output_text=placeholder_output,
                usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                estimated_cost=0.0,
                blocked_reason="provider_unavailable",
            )

        profile = resolve_provider_profile(request.provider)
        headers = _provider_headers(profile, session_id=request.session_id)

        payload = {
            "model": request.model,
            "instructions": (
                "You are BOS Code v1, an embedded coding workspace inside BOS. "
                "Operate conservatively, favor repository-relative paths, and explain concrete code actions."
            ),
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": request.prompt,
                        }
                    ],
                }
            ],
            "reasoning": {"effort": settings.BOS_CODE_OPENAI_REASONING_EFFORT},
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await self._post_with_retry(
                client,
                url=f"{profile.base_url}/responses",
                headers=headers,
                payload=payload,
            )

        body = response.json()
        usage = body.get("usage") or {}
        output_text = self._extract_output_text(body)
        return CodeProviderResponse(
            summary=output_text or "Provider returned no text output.",
            output_text=output_text or "Provider returned no text output.",
            usage={
                "input_tokens": int(usage.get("input_tokens", 0) or 0),
                "output_tokens": int(usage.get("output_tokens", 0) or 0),
                "total_tokens": int(usage.get("total_tokens", 0) or 0),
            },
            estimated_cost=None,
            blocked_reason=None,
        )

    async def stream(self, request: ProviderRequest) -> AsyncIterator[str]:
        if not self.enabled:
            prompt_excerpt = request.prompt.strip().splitlines()[0][:120] if request.prompt.strip() else "empty prompt"
            yield (
                "BOS Code provider boundary is active, but live OpenAI/Codex execution is currently "
                f"disabled. Latest prompt excerpt: {prompt_excerpt}"
            )
            return

        profile = resolve_provider_profile(request.provider)
        headers = _provider_headers(profile, session_id=request.session_id)

        payload = {
            "model": request.model,
            "instructions": (
                "You are BOS Code v1, an embedded coding workspace inside BOS. "
                "Operate conservatively, favor repository-relative paths, and explain concrete code actions."
            ),
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": request.prompt,
                        }
                    ],
                }
            ],
            "reasoning": {"effort": settings.BOS_CODE_OPENAI_REASONING_EFFORT},
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{profile.base_url}/responses",
                headers=headers,
                json=payload,
            ) as response:
                if not response.is_success:
                    body = await response.aread()
                    fake_response = httpx.Response(
                        status_code=response.status_code,
                        headers=response.headers,
                        content=body,
                        request=response.request,
                    )
                    raise self._build_error(fake_response)

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = httpx.Response(200, content=data.encode("utf-8")).json()
                    except ValueError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    event_type = event.get("type")
                    if event_type == "response.output_text.delta":
                        delta = event.get("delta")
                        if isinstance(delta, str) and delta:
                            yield delta

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict,
    ) -> httpx.Response:
        last_error: CodeProviderError | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.post(url, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                last_error = CodeProviderError(
                    f"OpenAI Responses API request failed: {exc}",
                    blocked_reason="provider_error",
                    user_message="Provider request failed because the upstream model endpoint could not be reached.",
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.base_backoff_seconds * (2**attempt))
                    continue
                raise last_error from exc

            if response.is_success:
                return response

            retryable, delay_seconds = self._retry_plan(response=response, attempt=attempt)
            last_error = self._build_error(response)
            if retryable and attempt < self.max_retries:
                await asyncio.sleep(delay_seconds)
                continue
            raise last_error

        raise last_error or CodeProviderError("OpenAI Responses API request failed for an unknown reason.")

    def _retry_plan(self, *, response: httpx.Response, attempt: int) -> tuple[bool, float]:
        if response.status_code not in self.RETRYABLE_STATUS_CODES:
            return False, 0.0

        body = self._safe_json(response)
        error = body.get("error") if isinstance(body, dict) else {}
        error_code = error.get("code") if isinstance(error, dict) else None
        reset_seconds = error.get("reset_seconds") if isinstance(error, dict) else None

        if response.status_code == 429 and error_code == "model_cooldown":
            try:
                reset_seconds = int(reset_seconds)
            except (TypeError, ValueError):
                reset_seconds = None
            if reset_seconds is not None and reset_seconds > 30:
                return False, 0.0

        return True, self.base_backoff_seconds * (2**attempt)

    @staticmethod
    def _classify_blocked_reason(*, code: str | None, message: str | None) -> str:
        normalized_code = (code or "").strip().lower()
        normalized_message = (message or "").strip().lower()
        trust_markers = {"trust_required", "untrusted_workspace", "untrusted_repository"}
        if normalized_code in trust_markers:
            return "trust_required"
        if "trust" in normalized_message and any(
            marker in normalized_message for marker in ("workspace", "repository", "repo", "permission")
        ):
            return "trust_required"
        if "prompt" in normalized_message and any(
            marker in normalized_message for marker in ("shell", "misdelivery", "wrong target")
        ):
            return "prompt_misdelivery"
        return "provider_error"

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict:
        try:
            body = response.json()
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {}

    def _build_error(self, response: httpx.Response) -> CodeProviderError:
        body = self._safe_json(response)
        error = body.get("error") if isinstance(body, dict) else {}
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")
            if response.status_code == 429 and code == "model_cooldown":
                reset_time = error.get("reset_time")
                reset_seconds = error.get("reset_seconds")
                suffix_parts = []
                if reset_time:
                    suffix_parts.append(f"reset_time={reset_time}")
                if reset_seconds is not None:
                    suffix_parts.append(f"reset_seconds={reset_seconds}")
                suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
                retry_after_seconds = None
                try:
                    retry_after_seconds = int(reset_seconds) if reset_seconds is not None else None
                except (TypeError, ValueError):
                    retry_after_seconds = None
                user_message = "The model pool is cooling down right now."
                if reset_time:
                    user_message += f" Try again in about {reset_time}."
                return CodeProviderError(
                    f"OpenAI Responses API model cooldown for {message or 'requested model'}{suffix}",
                    blocked_reason="provider_cooldown",
                    user_message=user_message,
                    retry_after_seconds=retry_after_seconds,
                )
            if message:
                blocked_reason = self._classify_blocked_reason(code=code if isinstance(code, str) else None, message=message)
                return CodeProviderError(
                    f"OpenAI Responses API request failed: HTTP {response.status_code} {message}",
                    blocked_reason=blocked_reason,
                    user_message=(
                        "A trust gate must be cleared before the workspace can continue."
                        if blocked_reason == "trust_required"
                        else "The prompt may have landed in the wrong runtime surface."
                        if blocked_reason == "prompt_misdelivery"
                        else "Provider request failed because the upstream model service returned an error."
                    ),
                )
        text_excerpt = response.text[:300] if response.text else ""
        blocked_reason = self._classify_blocked_reason(code=None, message=text_excerpt)
        return CodeProviderError(
            f"OpenAI Responses API request failed: HTTP {response.status_code} {text_excerpt}".strip(),
            blocked_reason=blocked_reason,
            user_message=(
                "A trust gate must be cleared before the workspace can continue."
                if blocked_reason == "trust_required"
                else "The prompt may have landed in the wrong runtime surface."
                if blocked_reason == "prompt_misdelivery"
                else "Provider request failed because the upstream model service returned an unexpected response."
            ),
        )

    @staticmethod
    def _extract_output_text(body: dict) -> str:
        direct_output_text = body.get("output_text")
        if isinstance(direct_output_text, str) and direct_output_text.strip():
            return direct_output_text

        chunks: list[str] = []
        for output_item in body.get("output", []) or []:
            if not isinstance(output_item, dict):
                continue
            if output_item.get("type") != "message":
                continue
            for content_item in output_item.get("content", []) or []:
                if not isinstance(content_item, dict):
                    continue
                if content_item.get("type") in {"output_text", "text"}:
                    text = content_item.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
        return "\n".join(chunk for chunk in chunks if chunk).strip()
