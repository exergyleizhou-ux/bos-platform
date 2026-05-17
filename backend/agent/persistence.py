"""BOS Agent - LangGraph checkpointer factory.

Plan v2 decision D3:
    Phase A  -> InMemorySaver (single process, no cross-session state)
    Phase B+ -> Redis / Postgres (set STATE_BACKEND env)

Node code MUST go through ``get_checkpointer()`` so future backend swaps
do not touch the graph at all.
"""

from __future__ import annotations

import os
from typing import Any


def get_checkpointer() -> Any:
    """Return a LangGraph BaseCheckpointSaver instance.

    Phase A: InMemorySaver. Phase B+ extends the dispatch below without
    changing the graph wiring.
    """
    backend = os.environ.get("STATE_BACKEND", "memory").lower()

    if backend == "memory":
        from langgraph.checkpoint.memory import InMemorySaver
        return InMemorySaver()

    if backend == "redis":
        raise NotImplementedError(
            "STATE_BACKEND=redis is reserved for Phase B+. Extend"
            " agent/persistence.py with a RedisSaver branch when ready."
        )

    if backend == "postgres":
        raise NotImplementedError(
            "STATE_BACKEND=postgres is reserved for Phase B+. Extend"
            " agent/persistence.py with a PostgresSaver branch when ready."
        )

    raise ValueError(
        f"Unknown STATE_BACKEND={backend!r}. Supported: memory."
        f" Reserved for Phase B+: redis, postgres."
    )
