"""router_node - classify operator intent into BOSState["intent"].

Phase A heuristic: cheap LLM call when ANTHROPIC_API_KEY is set,
otherwise a deterministic keyword classifier so the graph keeps
working in unit tests without an API key.
"""

from __future__ import annotations

import os
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.state import BOSState, Intent


_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    # Phase B B4 v2 causal intents come FIRST: a message that
    # mentions both a causal action ("what is the ATE") AND a Phase
    # A surface variable ("of SER on D'") should be classified as
    # causal, not as the variable-naming intent. The four causal
    # intents are ordered specific → generic so a "mediation"
    # mention is not swallowed by the generic ``causal`` keyword
    # under causal.ate.
    "causal.full": (
        "explain in depth", "full causal", "深度因果", "all causal",
    ),
    "causal.mediation": (
        "mediation", "中介", "proportion mediated", "direct effect",
        "indirect effect", "ade", "acme", "nde", "nie",
    ),
    "causal.sensitivity": (
        "sensitivity", "敏感性", "e-value", "evalue", "robustness",
        "unmeasured", "gamma bound", "γ-bound",
    ),
    "causal.ate": (
        "因果", "causal", "cause", "ate", "why did", "为什么",
        "intervention", "do-operator",
    ),
    # Phase A intents.
    "ser": ("ser", "efficiency", "yield", "conversion", "出米率"),
    "sfi": ("sfi", "envelope", "safety", "danger", "operating", "flight"),
    "relay": ("relay", "m1", "m2", "m3", "stages", "stage", "pipeline"),
    "cyber_lab": ("compare", "what-if", "scenario", "experiment", "vs", "对比"),
    "render": ("report", "summary", "render", "format", "markdown"),
    "smalltalk": ("hello", "hi", "thanks", "thank you"),
}

_SYSTEM_PROMPT = """You are the BOS Agent intent classifier.

Given an operator message, output exactly ONE of these intent codes:
  ser, sfi, relay, cyber_lab, render, smalltalk, noop,
  causal.ate, causal.mediation, causal.sensitivity, causal.full

Definitions:
  ser                  — compute the System Efficiency Ratio for a batch
  sfi                  — check signal/flight integrity (operating envelope)
  relay                — simulate the M1->M2->M3 three-stage relay
  cyber_lab            — compare scenarios / run a what-if experiment
  render               — format prior results into a markdown report
  smalltalk            — greeting or chitchat
  noop                 — none of the above
  causal.ate           — the operator wants WHY did a result happen,
                         a treatment's average effect, or do-intervention
                         reasoning. Example: "why did SER drop on this
                         feedstock?", "what is the ATE of Signal-API?"
  causal.mediation     — operator wants WHICH PATHWAY mediated the
                         effect, ACME/ADE/NDE/NIE decomposition, or
                         proportion mediated. Example: "how much of
                         the SER lift came from D' vs G'?"
  causal.sensitivity   — operator wants ROBUSTNESS bounds: E-value,
                         gamma-bound, unmeasured-confounder. Example:
                         "how robust is this estimate to a hidden
                         confounder?"
  causal.full          — operator wants the full causal report
                         (identify + estimate + refute + mediation +
                         sensitivity in one shot). Example: "explain
                         this causally in depth."

Reply with the single intent code only. No prose.
"""


def _matches_keyword(message: str, keyword: str) -> bool:
    """Match a keyword against a message.

    Phase B B4 v2 behaviour fix: ASCII keywords use word-boundary
    regex (avoids ``"user"`` → ser, ``"confounders"`` → nde
    substring collisions). Non-ASCII keywords (Chinese 因果 / 中介
    / 敏感性) keep substring semantics because ``\\b`` does not
    apply to CJK characters in Python's ``re`` module.
    """
    if keyword.isascii():
        pattern = rf"\b{re.escape(keyword)}\b"
        return bool(re.search(pattern, message, re.IGNORECASE))
    return keyword in message


def _keyword_intent(text: str) -> Intent:
    """Fallback keyword routing when the LLM path is unavailable.

    Phase A behaviour upgrade (B4 v2 incidental fix): substring
    match (``w in t``) replaced with ``_matches_keyword`` which
    uses word-boundary regex for ASCII keywords. This is a
    strict-improvement: fewer false positives ("user" no longer
    matches ser, "confounders" no longer matches nde), no new
    misses.
    """
    for intent, words in _KEYWORDS.items():
        for w in words:
            if _matches_keyword(text, w):
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
            # Accept first known token. The causal.* compound names
            # come BEFORE the bare `causal.ate` substring so a
            # mediation/sensitivity/full mention doesn't get
            # mis-matched as the generic ATE intent.
            for candidate in (
                "causal.mediation", "causal.sensitivity",
                "causal.full", "causal.ate",
                "ser", "sfi", "relay", "cyber_lab",
                "render", "smalltalk", "noop",
            ):
                if candidate in raw:
                    return {"intent": candidate}
        except Exception:
            # LLM failed - fall through to keyword classifier.
            pass

    return {"intent": keyword_hit}
