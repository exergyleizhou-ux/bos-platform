"""render_node - format final markdown report + chart hints.

Pure-Python; no HTTP, no LLM (Phase A keeps rendering deterministic so
unit tests don't depend on an LLM provider). Phase D can swap in an
LLM-driven render pass.

Phase B B4 v2: extended with a causal block that renders the five
``state.causal`` results (identify / estimate / refute / mediation /
sensitivity) plus a `````mermaid`` fenced DAG diagram
(Plan v2 §3.4 + §3.6). The Mermaid emitter mirrors the B6 frontend
``dagToMermaidSource`` byte-for-byte: 6 node shapes (treatment
rectangle / outcome circle / mediator hexagon / covariate rounded /
instrument asymmetric / latent parallelogram) and 2 edge styles
(``direct`` solid arrow / ``confounding`` dashed arrow).

CI rendering convention is locked to ``[low, high]`` (square
brackets, comma + space) per Plan v2 §3.4 via ``format_ci``. The
helper is exposed for re-use by future Phase G renderers and gated
by ``test_render_conventions`` in B4 v2 Step 4.
"""

from __future__ import annotations

from typing import Any

from agent.state import BOSState


# ════════════════════════════════════════════════════════════════════
# Plan v2 §3.4 helpers
# ════════════════════════════════════════════════════════════════════


def format_ci(low: float, high: float, *, decimals: int = 3) -> str:
    """``[low, high]`` — Phase B markdown convention (Plan v2 §3.4).

    Exposed module-top so future Phase G renderers (and the
    ``test_render_conventions`` gate) can import it. Every caller
    that prints a CI MUST go through this helper; the gate test
    fails on a grep of stray ``(low, high)`` parentheses-CI
    patterns.
    """
    return f"[{low:.{decimals}f}, {high:.{decimals}f}]"


def _format_ci(ci: tuple[float, float] | None) -> str:
    if ci is None:
        return ""
    lo, hi = ci
    return f" (95% CI {format_ci(lo, hi)})"


# ════════════════════════════════════════════════════════════════════
# Mermaid DAG emitter (Plan v2 §3.6, mirrors B6 frontend)
# ════════════════════════════════════════════════════════════════════


_NODE_SHAPE: dict[str, str] = {
    "treatment": "{n}[{n}]",       # rectangle
    "outcome": "{n}(({n}))",       # circle
    "mediator": "{n}{{{{{n}}}}}",  # hexagon (Mermaid {{ }} needs escaping)
    "covariate": "{n}({n})",       # rounded
    "instrument": "{n}>{n}]",      # asymmetric
    "latent": "{n}[/{n}/]",        # parallelogram
}


def render_dag_as_mermaid(dag: Any) -> str:
    """Render a ``DagSpec`` (or a dict-shaped equivalent) as a
    `````mermaid graph LR`` block.

    Byte-identical to ``frontend/src/components/bos/CausalMermaidPanel.
    tsx``'s ``dagToMermaidSource`` so the agent's markdown output is
    rendered without surprises by the V2 frontend panel.

    ``dag`` accepts either a Pydantic ``DagSpec`` instance (with
    ``.nodes`` / ``.edges`` attributes) or a plain dict / TypedDict
    with the same shape. Defensive against an unknown ``node_kind``
    by falling back to a plain rectangle (B6 panel does the same).
    """
    nodes = getattr(dag, "nodes", None) or (
        dag.get("nodes") if isinstance(dag, dict) else None
    )
    edges = getattr(dag, "edges", None) or (
        dag.get("edges") if isinstance(dag, dict) else None
    )
    if not nodes:
        return "```mermaid\ngraph LR\n```"

    lines: list[str] = ["```mermaid", "graph LR"]
    for node in nodes:
        name = getattr(node, "name", None) or node["name"]
        kind = getattr(node, "node_kind", None) or node["node_kind"]
        shape_fmt = _NODE_SHAPE.get(kind, "{n}[{n}]")
        lines.append("  " + shape_fmt.format(n=name))
    for edge in edges or []:
        src = getattr(edge, "src", None) or edge["src"]
        dst = getattr(edge, "dst", None) or edge["dst"]
        kind = (
            getattr(edge, "edge_kind", None)
            or (edge.get("edge_kind") if isinstance(edge, dict) else None)
            or "direct"
        )
        arrow = "-.->" if kind == "confounding" else "-->"
        lines.append(f"  {src} {arrow} {dst}")
    lines.append("```")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════
# Causal block (Plan v2 §3.4 causal-block template)
# ════════════════════════════════════════════════════════════════════


def _render_causal_block(causal: dict[str, Any]) -> list[str]:
    """Emit the causal-block markdown lines.

    Five sub-blocks corresponding to the five ``causal.*`` endpoints,
    plus the Mermaid DAG. Each sub-block prints only when its
    corresponding ``*_result`` is non-None on the slice.

    Errors (identify / estimate failures from §3.3) and warnings
    (refute / mediation / sensitivity failures) surface inline as
    bullet sections.
    """
    lines: list[str] = ["", "### Causal analysis"]

    treatment = causal.get("treatment")
    outcome = causal.get("outcome")
    if treatment and outcome:
        lines.append(f"- **Treatment**: `{treatment}`    "
                     f"**Outcome**: `{outcome}`")

    identify = causal.get("identify_result")
    if identify is not None:
        adj = ", ".join(getattr(identify, "adjustment_set", []) or []) or "—"
        lines.append(
            f"- **Identification**: strategy=`{identify.strategy}` "
            f"on adjustment set [{adj}]"
        )

    estimate = causal.get("estimate_result")
    if estimate is not None:
        ate = estimate.point_estimate
        ci_lo, ci_hi = estimate.ci_lower, estimate.ci_upper
        lines.append(
            f"- **ATE**: {ate:.3f}    **95% CI**: {format_ci(ci_lo, ci_hi)}"
        )
        if estimate.e_value_cheap is not None:
            lines.append(
                f"- **E-value (cheap)**: {estimate.e_value_cheap:.2f}"
            )

    refute = causal.get("refute_result")
    if refute is not None:
        results = getattr(refute, "refute_results", None) or []
        n_passed = sum(1 for r in results if r.passed)
        n_total = len(results)
        lines.append(
            f"- **Refutation**: {n_passed}/{n_total} robust    "
            f"**Overall robust**: {refute.overall_robust}"
        )

    mediation = causal.get("mediation_result")
    if mediation is not None:
        pm = mediation.proportion_mediated
        d = mediation.decomposition
        lines.append(
            f"- **Mediation**: proportion mediated = {pm:.3f}    "
            f"(direct={d.direct_effect:.3f}, "
            f"indirect={d.indirect_effect:.3f}, "
            f"total={d.total_effect:.3f})"
        )

    sensitivity = causal.get("sensitivity_result")
    if sensitivity is not None:
        if sensitivity.method == "evalue" and sensitivity.evalue_detail:
            ev = sensitivity.evalue_detail
            lines.append(
                f"- **Sensitivity** ({sensitivity.method}, "
                f"src=`{ev.source}`): "
                f"E-value point={ev.e_value_point:.2f}, "
                f"lower-CI={ev.e_value_lower_ci:.2f}"
            )
        elif sensitivity.method == "linear" and sensitivity.linear_detail:
            ln = sensitivity.linear_detail
            lines.append(
                f"- **Sensitivity** ({sensitivity.method}): "
                f"RV={ln.robustness_value:.3f}, "
                f"RV_α={ln.robustness_value_alpha:.3f}, "
                f"partial R²(Y, D)={ln.partial_r2_yd:.3f}"
            )
        lines.append(
            f"- **Overall robust** (paper Γ-bound ≥ 1.5): "
            f"{sensitivity.overall_robust}"
        )

    errors = causal.get("errors") or []
    if errors:
        lines.append("- **Causal errors**:")
        for err in errors:
            lines.append(f"  - {err}")

    warnings_list = causal.get("warnings") or []
    if warnings_list:
        lines.append("- **Causal warnings**:")
        for w in warnings_list:
            lines.append(f"  - {w}")

    # Mermaid DAG (Plan v2 §3.6) renders last so the prose summary
    # sits above the diagram in the chat surface.
    dag = causal.get("dag")
    if dag is not None:
        lines.append("")
        lines.append(render_dag_as_mermaid(dag))

    return lines


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

    # Phase B B4 v2 causal block. Renders any non-None ``state.causal``
    # subkeys plus a Mermaid DAG; surfaces ``state.causal.errors`` and
    # ``state.causal.warnings`` inline.
    causal = state.get("causal")
    if causal:
        lines.extend(_render_causal_block(dict(causal)))

    if len(lines) == 1:
        lines.append("- _(no computed fields on state — nothing to render)_")

    return {"report": "\n".join(lines)}
