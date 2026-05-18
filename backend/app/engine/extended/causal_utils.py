"""Phase B causal-layer engine helpers.

Pure utility functions shared across the identify / estimate / refute /
mediation / sensitivity engines:

- DAG → DoWhy graph string (GML)
- DAG → NetworkX DiGraph (kept distinct from the schema-level acyclic
  validation, which uses NetworkX in ``app.schemas.causal_common``)
- Dataset frame builder from CausalData
- Per-stratum sample-size counter
- Cheap VanderWeele-Ding E-value computation for continuous outcomes
- Continuous-covariate detector (validates D9=α's DML pre-condition)

Reference: PHASE_B_PLAN.md §2.6 + §2.8.
"""

from __future__ import annotations

import hashlib
import math
from typing import Dict, List, Optional, Sequence

import networkx as nx
import numpy as np
import pandas as pd

from app.schemas.causal_common import CausalData, DagSpec


# ════════════════════════════════════════════════════════════════════
# DAG conversions
# ════════════════════════════════════════════════════════════════════


def dag_to_networkx(dag: DagSpec) -> nx.DiGraph:
    """Build a NetworkX DiGraph from a validated DagSpec.

    The schema-layer validator already ensured acyclicity; no further
    cycle check here. We attach ``node_kind`` and ``edge_kind`` as
    node/edge attributes so downstream engines can reason about
    roles without re-parsing the DagSpec.
    """
    g = nx.DiGraph()
    for node in dag.nodes:
        g.add_node(node.name, node_kind=node.node_kind)
    for edge in dag.edges:
        g.add_edge(edge.src, edge.dst, edge_kind=edge.edge_kind)
    return g


def dag_to_gml(dag: DagSpec) -> str:
    """Serialise a DagSpec to a GML graph string accepted by DoWhy's
    ``CausalModel(graph=...)`` constructor.

    GML keeps the format simple and DoWhy parses it via NetworkX.
    """
    lines = ["graph [", "  directed 1"]
    name_to_id: Dict[str, int] = {}
    for i, node in enumerate(dag.nodes):
        name_to_id[node.name] = i
        lines.append("  node [")
        lines.append(f"    id {i}")
        lines.append(f'    label "{node.name}"')
        lines.append("  ]")
    for edge in dag.edges:
        lines.append("  edge [")
        lines.append(f"    source {name_to_id[edge.src]}")
        lines.append(f"    target {name_to_id[edge.dst]}")
        lines.append("  ]")
    lines.append("]")
    return "\n".join(lines)


def has_only_trivial_edge(dag: DagSpec, treatment: str, outcome: str) -> bool:
    """True when the DAG only contains the direct treatment->outcome
    edge with no other edges or no other nodes (modulo isolated
    covariates), which corresponds to the ``strategy="trivial"`` case
    in the identify spec (PHASE_B_PLAN.md §2.1)."""
    if len(dag.edges) != 1:
        return False
    only = dag.edges[0]
    return only.src == treatment and only.dst == outcome


# ════════════════════════════════════════════════════════════════════
# Data envelope
# ════════════════════════════════════════════════════════════════════


def causal_data_to_dataframe(data: CausalData) -> pd.DataFrame:
    """Realise the CausalData envelope into a pandas DataFrame.

    Phase B MVP only supports ``inline``; ``batch_query_key`` raises a
    NotImplementedError so callers can decide whether to 422 or queue
    the request. Phase G ships the server-side backing store.
    """
    if data.inline is not None:
        if not data.inline:
            raise ValueError("CausalData.inline is an empty list.")
        return pd.DataFrame(data.inline)
    raise NotImplementedError(
        "CausalData.batch_query_key support is reserved for Phase G; "
        "Phase B MVP only accepts inline data."
    )


def compute_fingerprint(df: pd.DataFrame) -> str:
    """Compute a stable SHA-256 prefix for a dataframe's column set +
    row count. Mirrors the format the schema layer expects in
    ``CausalData.fingerprint``."""
    cols = ",".join(sorted(df.columns.astype(str)))
    payload = f"{cols}|n={len(df)}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]


def count_per_stratum(
    df: pd.DataFrame,
    stratum_columns: Optional[Sequence[str]] = None,
) -> Dict[str, int]:
    """Return ``{stratum_label: n_rows}``.

    With ``stratum_columns=None`` (or empty), returns ``{'overall': n}``.
    Otherwise builds composite labels by joining values across columns
    with ``'|'``.
    """
    if not stratum_columns:
        return {"overall": len(df)}
    # Composite stratum label = col1=val1|col2=val2|...
    labels = df[list(stratum_columns)].astype(str).agg(
        lambda row: "|".join(f"{c}={row[c]}" for c in stratum_columns),
        axis=1,
    )
    counts = labels.value_counts().to_dict()
    return {str(k): int(v) for k, v in counts.items()}


# ════════════════════════════════════════════════════════════════════
# Covariate analysis
# ════════════════════════════════════════════════════════════════════


def split_covariates(
    df: pd.DataFrame,
    adjustment_set: Sequence[str],
    *,
    discrete_threshold: int = 10,
) -> tuple[List[str], List[str]]:
    """Partition adjustment_set into (continuous, discrete) covariates.

    Heuristic: a column is discrete when its number of distinct values
    is below ``discrete_threshold``. dtype is not consulted: the
    CausalData inline protocol declares ``Dict[str, float]``, so
    pandas always promotes columns to ``float64`` — the dtype check
    in earlier revisions was effectively dead code that misclassified
    int-coded categorical columns (e.g. species_code, feedstock_code).
    """
    continuous: List[str] = []
    discrete: List[str] = []
    for col in adjustment_set:
        if col not in df.columns:
            continue  # ignore columns not in the data; engine will surface
        n_unique = df[col].nunique(dropna=True)
        if n_unique < discrete_threshold:
            discrete.append(col)
        else:
            continuous.append(col)
    return continuous, discrete


def has_continuous_covariate(
    df: pd.DataFrame, adjustment_set: Sequence[str]
) -> bool:
    """D9=α DML pre-condition. True when at least one column in
    ``adjustment_set`` qualifies as continuous per ``split_covariates``."""
    cont, _ = split_covariates(df, adjustment_set)
    return len(cont) > 0


# ════════════════════════════════════════════════════════════════════
# E-value (VanderWeele-Ding 2017; cheap continuous-outcome variant)
# ════════════════════════════════════════════════════════════════════


def cheap_evalue(
    point_estimate: float,
    std_outcome: float,
    *,
    confidence_floor: float = 1.0,
) -> float:
    """Approximate E-value for a continuous-outcome ATE.

    Uses the Chinn (2000) RR-from-standardised-effect approximation:
    ``RR ≈ exp(0.91 * std_effect)`` where
    ``std_effect = |point_estimate| / std_outcome``. VanderWeele-Ding
    E-value is then ``RR + sqrt(RR * (RR - 1))``.

    Returns ``confidence_floor`` (default 1.0, the no-effect anchor)
    when std_outcome is 0 or non-finite — the cheap approximation is
    undefined in that limit and Phase B's evidence_level rule treats
    E-value=1.0 as "no robustness margin".

    Phase B uses this as a free side-effect of /estimate. For
    full-fidelity sensitivity analysis, callers invoke
    /api/v1/causal/sensitivity.
    """
    if std_outcome <= 0.0 or not math.isfinite(std_outcome):
        return confidence_floor
    if not math.isfinite(point_estimate):
        return confidence_floor
    std_effect = abs(point_estimate) / std_outcome
    rr = math.exp(0.91 * std_effect)
    if rr < 1.0:
        # By construction rr >= 1 (since std_effect >= 0); guard against
        # numerical underflow.
        return confidence_floor
    return rr + math.sqrt(rr * (rr - 1.0))


# ════════════════════════════════════════════════════════════════════
# Misc
# ════════════════════════════════════════════════════════════════════


def issue_timestamp_utc() -> "datetime":  # noqa: F821 — runtime import below
    """Single source of UTC 'now' for engine-issued handles."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
