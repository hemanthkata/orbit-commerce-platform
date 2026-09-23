import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger("app.ws")


class ConnectionManager:
    """Tracks live WebSocket connections per recipient (customer id, or
    "ops" for the staff inventory feed) using FastAPI's native WebSocket
    support directly - no external broker needed for fan-out within a
    single process, since each recipient's sockets are held in memory here.
    A multi-instance deployment would additionally subscribe each instance
    to a Redis pub/sub channel per recipient; noted in docs/architecture.md
    as the next step if this service is horizontally scaled.
    """

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, recipient: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[recipient].add(websocket)

    async def disconnect(self, recipient: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[recipient].discard(websocket)
            if not self._connections[recipient]:
                self._connections.pop(recipient, None)

    async def broadcast(self, recipient: str, message: dict) -> None:
        sockets = list(self._connections.get(recipient, ()))
        for socket in sockets:
            try:
                await socket.send_json(message)
            except Exception:  # noqa: BLE001
                logger.warning("ws_send_failed", extra={"recipient": recipient})
                await self.disconnect(recipient, socket)


connection_manager = ConnectionManager()
