"""render_node - format final markdown report + chart hints.

Pure-Python; no HTTP, no LLM (Phase A keeps rendering deterministic so
unit tests don't depend on an LLM provider). Phase D can swap in an
LLM-driven render pass.
"""

from __future__ import annotations

from typing import Any

from agent.state import BOSState


def _format_ci(ci: tuple[float, float] | None) -> str:
    if ci is None:
        return ""
    lo, hi = ci
    return f" (95% CI [{lo:.3f}, {hi:.3f}])"


async def render_node(state: BOSState) -> dict[str, Any]:
    """Render a markdown summary from the SER / SFI / relay outputs."""
    lines: list[str] = ["## BOS Agent run summary"]

    if state.get("intent"):
        lines.append(f"- **Intent**: `{state['intent']}`")
    if state.get("species_code"):
        lines.append(f"- **Species**: `{state['species_code']}`")

    if state.get("ser") is not None:
        ci = state.get("ser_ci")
        lines.append(
            f"- **SER**: {state['ser']:.4f}{_format_ci(ci)}"
        )
    if state.get("sfi_pass") is not None:
        ok = "PASS" if state["sfi_pass"] else "FAIL"
        zone = state.get("sfi_zone") or "?"
        lines.append(f"- **SFI**: {ok} (zone: `{zone}`)")

    sim = state.get("simulation_result")
    if isinstance(sim, dict) and "final_ser" in sim:
        health = sim.get("relay_health") or {}
        status = health.get("overall_status", "?")
        lines.append(
            f"- **Relay**: final_ser={sim['final_ser']:.4f}, status={status}"
        )

    cyber = state.get("cyber_experiment")
    if isinstance(cyber, dict) and cyber:
        if "baseline_ser" in cyber:
            lines.append(f"- **Cyber lab baseline SER**: {cyber['baseline_ser']:.4f}")
        if "mc_target_mean" in cyber and "mc_ci" in cyber:
            lo, hi = cyber["mc_ci"]
            lines.append(
                f"- **Cyber lab MC mean**: {cyber['mc_target_mean']:.4f}"
                f" (95% CI [{lo:.3f}, {hi:.3f}])"
            )

    if state.get("evidence_level"):
        lines.append(f"- **Evidence level**: `{state['evidence_level']}`")

    tool_calls = state.get("tool_calls") or []
    if tool_calls:
        ok = sum(1 for r in tool_calls if r.get("status") == "ok")
        err = len(tool_calls) - ok
        lines.append(f"- **Core calls**: {ok} ok / {err} error")

    if len(lines) == 1:
        lines.append("- _(no computed fields on state — nothing to render)_")

    return {"report": "\n".join(lines)}
