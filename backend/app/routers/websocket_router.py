"""
BOS Pipeline v9.0 �� WebSocket Router

Real-time data streaming via WebSocket for:
  - Live digital twin state updates
  - Batch processing progress
  - Alert notifications
  - Dashboard real-time metrics

Feature-flagged: requires FF_ENABLE_WEBSOCKET.
"""

import asyncio
import json
import time
from typing import Dict, Set

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from app.config import get_settings
from app.deps import decode_access_token

router = APIRouter()
settings = get_settings()


class ConnectionManager:
    """Manages active WebSocket connections per tenant."""

    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}  # tenant_id �� set of connections

    async def connect(self, websocket: WebSocket, tenant_id: int):
        await websocket.accept()
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = set()
        self.active_connections[tenant_id].add(websocket)

    def disconnect(self, websocket: WebSocket, tenant_id: int):
        if tenant_id in self.active_connections:
            self.active_connections[tenant_id].discard(websocket)
            if not self.active_connections[tenant_id]:
                del self.active_connections[tenant_id]

    async def broadcast_to_tenant(self, tenant_id: int, message: dict):
        """Broadcast a message to all connections in a tenant."""
        connections = self.active_connections.get(tenant_id, set())
        dead: Set[WebSocket] = set()

        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)

        for ws in dead:
            connections.discard(ws)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send a message to a specific connection."""
        try:
            await websocket.send_json(message)
        except Exception:
            pass

    @property
    def connection_count(self) -> int:
        return sum(len(conns) for conns in self.active_connections.values())


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    WebSocket connection endpoint.
    Requires a valid JWT access token as a query parameter.
    """
    if not settings.FF_ENABLE_WEBSOCKET:
        await websocket.close(code=4003, reason="WebSocket feature is disabled")
        return

    # Authenticate
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
        tenant_id = int(payload["tenant_id"])
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    # Connect
    await manager.connect(websocket, tenant_id)

    # Send welcome
    await manager.send_personal(websocket, {
        "type": "connected",
        "user_id": user_id,
        "tenant_id": tenant_id,
        "timestamp": time.time(),
        "active_connections": manager.connection_count,
    })

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await manager.send_personal(websocket, {
                    "type": "error",
                    "detail": "Invalid JSON",
                })
                continue

            msg_type = message.get("type", "")

            if msg_type == "ping":
                await manager.send_personal(websocket, {
                    "type": "pong",
                    "timestamp": time.time(),
                })

            elif msg_type == "subscribe":
                # Client subscribes to a channel (e.g., "twin:123", "batch:456")
                channel = message.get("channel", "")
                await manager.send_personal(websocket, {
                    "type": "subscribed",
                    "channel": channel,
                })

            elif msg_type == "broadcast":
                # Only for testing; in production, broadcasts come from server-side events
                await manager.broadcast_to_tenant(tenant_id, {
                    "type": "broadcast",
                    "from_user": user_id,
                    "data": message.get("data"),
                    "timestamp": time.time(),
                })

            else:
                await manager.send_personal(websocket, {
                    "type": "echo",
                    "original": message,
                    "timestamp": time.time(),
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket, tenant_id)
    except Exception:
        manager.disconnect(websocket, tenant_id)


@router.get("/ws/stats")
async def websocket_stats():
    """Get WebSocket connection statistics."""
    return {
        "total_connections": manager.connection_count,
        "tenants_connected": len(manager.active_connections),
        "connections_by_tenant": {
            tid: len(conns) for tid, conns in manager.active_connections.items()
        },
    }
