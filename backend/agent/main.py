"""BOS Agent process entry: ``python -m agent.main``.

Defaults to port 8001 (Plan v2 paragraph 3.4). Override via the
``--port`` CLI argument or the ``AGENT_PORT`` environment variable.

The agent connects to BOS Core via ``BOS_CORE_URL``
(default ``http://localhost:8000/api/v1``).
"""

from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch the BOS Agent service")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("AGENT_PORT", "8001")),
        help="HTTP port (default 8001 or $AGENT_PORT)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("AGENT_HOST", "127.0.0.1"),
        help="HTTP host (default 127.0.0.1 or $AGENT_HOST)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn auto-reload (dev only)",
    )
    args = parser.parse_args(argv)

    # Lazy import so --help doesn't pull uvicorn etc.
    import uvicorn

    uvicorn.run(
        "agent.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=os.environ.get("AGENT_LOG_LEVEL", "info"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
