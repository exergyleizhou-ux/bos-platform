"""BOS Agent - LLM provider factory.

Decision (Plan v2 confirmation):
    LLM_PROVIDER=anthropic              (default)
    LLM_MODEL_ROUTER=claude-sonnet-4-5  (hot path: intent classification)
    LLM_MODEL_RENDER=claude-sonnet-4-5  (report rendering)
    ANTHROPIC_API_KEY=<required>

This module MUST NOT import ``app.*`` (per Plan v2 paragraph 3.4).
A grep test in the smoke suite enforces the isolation rule.
"""

from __future__ import annotations

import os
from typing import Any, Literal


Role = Literal["router", "render"]


_DEFAULT_PROVIDER = "anthropic"
_DEFAULT_MODEL = "claude-sonnet-4-5"


def _read_role_model(role: Role) -> str:
    """Three-level fallback:

        LLM_MODEL_<ROLE>  ->  LLM_MODEL  ->  hardcoded default.
    """
    role_env = f"LLM_MODEL_{role.upper()}"
    return os.environ.get(role_env) or os.environ.get("LLM_MODEL") or _DEFAULT_MODEL


def get_chat_model(role: Role = "router") -> Any:
    """Return a LangChain chat model configured for the given role.

    The return type is intentionally ``Any`` so this module does not
    drag the heavy LangChain provider imports into every call site;
    each branch lazy-imports its own provider so missing optional
    providers do not break the default Anthropic path.
    """
    provider = os.environ.get("LLM_PROVIDER", _DEFAULT_PROVIDER).lower()
    model = _read_role_model(role)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable is required for"
                " LLM_PROVIDER=anthropic (the Phase A default)."
            )
        return ChatAnthropic(model=model, api_key=api_key, temperature=0.0)

    if provider == "openai":
        # Lazy import: langchain-openai is an optional dependency.
        from langchain_openai import ChatOpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is required for"
                " LLM_PROVIDER=openai."
            )
        return ChatOpenAI(model=model, api_key=api_key, temperature=0.0)

    if provider in ("qwen", "deepseek"):
        # OpenAI-compatible providers via their respective base URLs.
        from langchain_openai import ChatOpenAI

        api_env = f"{provider.upper()}_API_KEY"
        base_env = f"{provider.upper()}_BASE_URL"
        api_key = os.environ.get(api_env)
        base_url = os.environ.get(base_env)
        if not api_key or not base_url:
            raise RuntimeError(
                f"{api_env} and {base_env} environment variables are"
                f" required for LLM_PROVIDER={provider}."
            )
        return ChatOpenAI(
            model=model, api_key=api_key, base_url=base_url, temperature=0.0,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER={provider!r}. Supported:"
        f" anthropic | openai | qwen | deepseek."
    )
