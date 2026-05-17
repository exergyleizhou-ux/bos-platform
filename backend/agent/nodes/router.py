"""router_node - classify operator intent into BOSState["intent"].

Phase A heuristic: cheap LLM call when ANTHROPIC_API_KEY is set,
otherwise a deterministic keyword classifier so the graph keeps
working in unit tests without an API key.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.state import BOSState, Intent


_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    "ser": ("ser", "efficiency", "yield", "conversion", "出米率", "ser"),
    "sfi": ("sfi", "envelope", "safety", "danger", "operating", "flight"),
    "relay": ("relay", "m1", "m2", "m3", "stages", "stage", "pipeline"),
    "cyber_lab": ("compare", "what-if", "scenario", "experiment", "vs ", "对比"),
    "render": ("report", "summary", "render", "format", "markdown"),
    "smalltalk": ("hello", "hi ", "thanks", "thank you"),
}

_SYSTEM_PROMPT = """You are the BOS Agent intent classifier.

Given an operator message, output exactly ONE of these intent codes:
  ser, sfi, relay, cyber_lab, render, smalltalk, noop

Definitions:
  ser        — compute the System Efficiency Ratio for a batch
  sfi        — check signal/flight integrity (operating envelope)
  relay      — simulate the M1->M2->M3 three-stage relay
  cyber_lab  — compare scenarios / run a what-if experiment
  render     — format prior results into a markdown report
  smalltalk  — greeting or chitchat
  noop       — none of the above

Reply with the single intent code only. No prose.
"""


def _keyword_intent(text: str) -> Intent:
    t = text.lower()
    for intent, words in _KEYWORDS.items():
        for w in words:
            if w in t:
                return intent
    return "noop"


def _last_user_text(state: BOSState) -> str:
    for msg in reversed(state.get("messages", []) or []):
        # LangChain BaseMessage has .content (str) and .type ("human"/...)
        if getattr(msg, "type", "") == "human":
            content = getattr(msg, "content", "")
            if isinstance(content, str):
                return content
    return ""


async def router_node(state: BOSState) -> dict[str, Any]:
    """Classify the latest user message into an intent."""
    text = _last_user_text(state)
    if not text:
        return {"intent": "noop"}

    # Cheap keyword path always runs as a fallback / sanity floor.
    keyword_hit = _keyword_intent(text)

    if os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("AGENT_ROUTER_USE_LLM", "1") != "0":
        from agent.llm import get_chat_model
        try:
            llm = get_chat_model("router")
            response = await llm.ainvoke([
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=text),
            ])
            raw = str(response.content).strip().lower()
            # Accept first known token.
            for candidate in ("ser", "sfi", "relay", "cyber_lab",
                              "render", "smalltalk", "noop"):
                if candidate in raw:
                    return {"intent": candidate}
        except Exception:
            # LLM failed - fall through to keyword classifier.
            pass

    return {"intent": keyword_hit}
