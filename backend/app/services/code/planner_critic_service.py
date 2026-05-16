"""
Optional planner/critic abstraction for BOS Code runtime.

This service preserves the current heuristic control-plane behavior while
creating a clean seam for future LLM-native planner/critic decisions.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import get_settings
from app.services.code.providers import OpenAICodexProvider, ProviderRequest

settings = get_settings()


class CodePlannerCriticService:
    def __init__(self) -> None:
        self.provider = OpenAICodexProvider(enabled=settings.BOS_CODE_ENABLE_LLM_PLANNER)

    async def derive_heartbeat_packet(
        self,
        *,
        workspace_id: int,
        heuristic_packet: dict[str, Any],
    ) -> dict[str, Any]:
        packet = dict(heuristic_packet)
        packet["decision_source"] = "heuristic"

        if not settings.BOS_CODE_ENABLE_LLM_PLANNER:
            return packet

        prompt = (
            "You are the BOS Code planner/critic layer. "
            "Return a compact JSON object with keys "
            "`planner_recommendation`, `planner_steps`, `critic_notes`, `critic_checks`, `risk_level`, "
            "`loop_budget`, `convergence_signal`, and `difficulty_signals` "
            "based on the current heartbeat packet. Keep the same intent unless you have strong reason to improve it. "
            "Use `loop_budget` values `short`, `standard`, `deep`, or `exit`. "
            "Use `convergence_signal` values like `ready_to_exit`, `continue_until_next_gate`, `needs_more_evidence`, or `idle`.\n\n"
            f"Current packet:\n{json.dumps(heuristic_packet, ensure_ascii=False)}"
        )

        try:
            response = await self.provider.run(
                ProviderRequest(
                    session_id=workspace_id,
                    prompt=prompt,
                    model=settings.BOS_CODE_DEFAULT_MODEL,
                    provider=settings.BOS_CODE_DEFAULT_PROVIDER,
                    permission_mode="read-only",
                    tool_names=[],
                )
            )
        except Exception:
            packet["decision_source"] = "heuristic_fallback"
            return packet

        parsed = self._extract_json_object(response.output_text)
        if not parsed:
            packet["decision_source"] = "heuristic_fallback"
            return packet

        for key in (
            "planner_recommendation",
            "planner_steps",
            "critic_notes",
            "critic_checks",
            "risk_level",
            "loop_budget",
            "convergence_signal",
            "difficulty_signals",
        ):
            value = parsed.get(key)
            if value:
                packet[key] = value
        packet["decision_source"] = "llm"
        return packet

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any] | None:
        if not text:
            return None
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
