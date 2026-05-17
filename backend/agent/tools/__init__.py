"""BOS Agent - async HTTP tools that call BOS Core.

Every tool here uses a shared ``httpx.AsyncClient`` so nodes can fan
out parallel Core calls via ``asyncio.gather`` (Plan v2 D4).
"""

from agent.tools.client import (
    close_client,
    get_client,
    set_client,
    CORE_URL,
    ToolError,
)
from agent.tools.ser import ser_compute
from agent.tools.sfi import sfi_check
from agent.tools.relay import relay_simulate
from agent.tools.mc import mc_propagate
from agent.tools.twin import twin_run

__all__ = [
    "close_client",
    "get_client",
    "set_client",
    "CORE_URL",
    "ToolError",
    "ser_compute",
    "sfi_check",
    "relay_simulate",
    "mc_propagate",
    "twin_run",
]
