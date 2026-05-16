"""A2A Protocol placeholder for PhyAgentOS integration.

Phase 2 will implement actual Agent-to-Agent communication with the
PhyAgentOS-main project. For Phase 0.5 this file is interface
specification only — Protocol methods have no body.

Reference target: ``C:/Users/10420/Desktop/bos 0506/PhyAgentOS-main/PhyAgentOS/``.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol


class A2AClient(Protocol):
    """Minimal A2A client surface BOS Agent will require in Phase 2."""

    async def send_command(self, cmd: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a command to the embodied agent."""

    async def query_state(self) -> dict[str, Any]:
        """Read the latest known embodied-agent state snapshot."""

    async def subscribe_events(
        self,
        callback: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Register a callback for asynchronous events from the agent."""
