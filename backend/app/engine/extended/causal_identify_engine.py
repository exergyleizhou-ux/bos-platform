"""Phase B — /api/v1/causal/identify engine.

Wraps DoWhy's ``CausalModel.identify_effect`` and renders its verdict
into the typed ``CausalIdentifyResponse`` defined in
``app.schemas.causal.identify``.

Identification strategy is reported as one of the six Literals from the
schema (backdoor / frontdoor / iv / mediation / trivial /
unidentifiable). The endpoint never throws on unidentifiable graphs —
``proceed_when_unidentifiable=True`` is the default-on path for the
operator who *wants* the unidentifiable verdict (it carries evidence-
level=planned and is itself an audit signal).

Reference: PHASE_B_PLAN.md §2.1 + §2.8.
"""

from __future__ import annotations

import warnings
from datetime import datetime, timezone
from typing import List, Tuple

from app.engine.extended.causal_utils import (
    dag_to_gml,
    has_only_trivial_edge,
)
from app.schemas.causal.identify import (
    CausalIdentifyRequest,
    CausalIdentifyResponse,
)
from app.schemas.causal_common import (
    CAUSAL_ENGINE_VERSION,
    Assumption,
    DagSpec,
    EvidenceLevel,
    IdentifiedEstimandHandle,
    IdentifyStrategy,
)


# ════════════════════════════════════════════════════════════════════
# Strategy resolution
# ════════════════════════════════════════════════════════════════════


def _classify_strategy(
    estimand_obj,
    dag: DagSpec,
    treatment: str,
    outcome: str,
) -> Tuple[IdentifyStrategy, List[str], str]:
    """Inspect a DoWhy ``IdentifiedEstimand`` and return
    (strategy_literal, adjustment_set, estimand_expression).

    DoWhy returns multiple estimand_type slots
    (``backdoor`` / ``frontdoor`` / ``iv``). We prefer them in that
    order — back-door is most common, then front-door, then IV. When
    all three are missing the verdict is unidentifiable unless the
    DAG is the trivial T→O case.
    """
    # Trivial: only one edge in the DAG, from T to O.
    if has_only_trivial_edge(dag, treatment, outcome):
        return ("trivial", [], "E[Y|T]")

    # Mediation: the DAG contains at least one node with role 'mediator'
    # that sits on a treatment->outcome path. Note: this overrides the
    # backdoor verdict when the DAG was constructed primarily for
    # mediation analysis. We surface it so /mediation has a clear
    # entry point.
    mediator_names = [
        n.name for n in dag.nodes if n.node_kind == "mediator"
    ]
    if mediator_names:
        # Only label as mediation when at least one mediator lies on a
        # T->...->O directed path (sanity check).
        from app.engine.extended.causal_utils import dag_to_networkx
        g = dag_to_networkx(dag)
        try:
            paths = list(
                __import__("networkx").all_simple_paths(g, treatment, outcome)
            )
        except Exception:
            paths = []
        on_path_mediators = {
            m for path in paths for m in path if m in mediator_names
        }
        if on_path_mediators:
            # Adjustment set under sequential ignorability is the union of
            # other (non-mediator) covariates on or off the path.
            covariates = [
                n.name for n in dag.nodes if n.node_kind == "covariate"
            ]
            return (
                "mediation",
                covariates,
                f"E[Y(t)] - E[Y(t')] decomposed via {sorted(on_path_mediators)}",
            )

    # Read DoWhy's identify_effect output. The estimand object exposes
    # backdoor / frontdoor / iv variants via either attributes or
    # ``get_backdoor_variables()`` style methods depending on version.
    def _vars_or_empty(method_name: str) -> List[str]:
        fn = getattr(estimand_obj, method_name, None)
        if fn is None:
            return []
        try:
            v = fn()
        except Exception:
            return []
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x) for x in v]
        if isinstance(v, set):
            return sorted(str(x) for x in v)
        return [str(v)]

    backdoor_vars = _vars_or_empty("get_backdoor_variables")
    frontdoor_vars = _vars_or_empty("get_frontdoor_variables")
    iv_vars = _vars_or_empty("get_instrumental_variables")

    estimand_expr = str(getattr(estimand_obj, "estimand_type", "unknown"))

    if backdoor_vars:
        return ("backdoor", backdoor_vars, f"E[Y|do(T)] backdoor on {backdoor_vars}")
    if frontdoor_vars:
        return (
            "frontdoor",
            frontdoor_vars,
            f"E[Y|do(T)] frontdoor on {frontdoor_vars}",
        )
    if iv_vars:
        return ("iv", iv_vars, f"E[Y|do(T)] IV via {iv_vars}")

    return ("unidentifiable", [], "no identification under standard assumptions")


def _strategy_to_assumptions(
    strategy: IdentifyStrategy, dag: DagSpec
) -> List[Assumption]:
    """Map a strategy to its load-bearing identification assumptions."""
    base: List[Assumption] = ["consistency", "positivity", "sutva"]
    if strategy == "backdoor":
        return base + ["no_unobserved_confounders"]
    if strategy == "frontdoor":
        return base + ["no_unobserved_confounders"]
    if strategy == "iv":
        return base
    if strategy == "mediation":
        return base + [
            "sequential_ignorability",
            "no_treatment_mediator_interaction",
        ]
    if strategy == "trivial":
        return base
    # unidentifiable
    return []


def _strategy_to_evidence_level(
    strategy: IdentifyStrategy, adjustment_set: List[str]
) -> EvidenceLevel:
    """Per Plan v2 §2.1: refute (B2b) tightens this further; here we
    only commit to the conservative initial assignment."""
    if strategy in ("backdoor", "frontdoor", "iv") and adjustment_set:
        return "validated"
    if strategy in ("trivial", "mediation"):
        return "supported"
    if strategy == "backdoor" and not adjustment_set:
        # Edge case: DoWhy returned backdoor with an empty adjustment
        # set (no confounders) — that's just unconditional E[Y|T].
        return "supported"
    return "planned"


# ════════════════════════════════════════════════════════════════════
# Public entrypoint
# ════════════════════════════════════════════════════════════════════


def run_identify(
    request: CausalIdentifyRequest,
) -> CausalIdentifyResponse:
    """Execute the identification phase.

    The DAG is fed to DoWhy via a GML graph string. We build an
    *empty* DataFrame with the DAG node names as columns so DoWhy's
    constructor accepts the graph — identification itself doesn't
    need data, only the structure.
    """
    # Build an empty-but-typed DataFrame so DoWhy is happy. Schemas
    # already guaranteed treatment, outcome ∈ DAG.nodes.
    import pandas as pd
    from dowhy import CausalModel

    columns = [n.name for n in request.dag.nodes]
    empty_df = pd.DataFrame({c: pd.Series(dtype="float64") for c in columns})

    gml = dag_to_gml(request.dag)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = CausalModel(
            data=empty_df,
            treatment=request.treatment,
            outcome=request.outcome,
            graph=gml,
        )
        try:
            estimand = model.identify_effect(
                proceed_when_unidentifiable=request.proceed_when_unidentifiable,
                method_name="default",
            )
        except Exception as exc:  # pragma: no cover - DoWhy edge cases
            # DoWhy raises on hard-unidentifiable graphs when the
            # proceed flag is False. Surface as unidentifiable per
            # Plan v2 spec (never 500 on identification).
            strategy: IdentifyStrategy = "unidentifiable"
            return _render_response(
                request=request,
                strategy=strategy,
                adjustment_set=[],
                estimand_expression=f"identification raised: {type(exc).__name__}",
            )

    strategy, adjustment_set, estimand_expression = _classify_strategy(
        estimand, request.dag, request.treatment, request.outcome
    )

    return _render_response(
        request=request,
        strategy=strategy,
        adjustment_set=adjustment_set,
        estimand_expression=estimand_expression,
    )


def _render_response(
    *,
    request: CausalIdentifyRequest,
    strategy: IdentifyStrategy,
    adjustment_set: List[str],
    estimand_expression: str,
) -> CausalIdentifyResponse:
    assumptions = _strategy_to_assumptions(strategy, request.dag)
    evidence_level = _strategy_to_evidence_level(strategy, adjustment_set)
    identified = strategy != "unidentifiable"

    handle = IdentifiedEstimandHandle(
        strategy=strategy,
        adjustment_set=adjustment_set,
        estimand_expression=estimand_expression,
        dataset_fingerprint=request.dataset_fingerprint,
        issued_at=datetime.now(timezone.utc),
    )

    return CausalIdentifyResponse(
        identified=identified,
        strategy=strategy,
        adjustment_set=adjustment_set,
        estimand_expression=estimand_expression,
        assumptions=assumptions,
        estimand_handle=handle,
        evidence_level=evidence_level,
        engine_version=CAUSAL_ENGINE_VERSION,
    )
