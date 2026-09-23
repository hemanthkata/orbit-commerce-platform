from app.ws.manager import connection_manager
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/notifications/{recipient_id}")
async def notifications_socket(websocket: WebSocket, recipient_id: str):
    """Native FastAPI WebSocket endpoint - no Channels/Django dependency
    here, demonstrating framework-native real-time support alongside the
    Django Channels implementation in core_api's /ws/orders/."""
    await connection_manager.connect(recipient_id, websocket)
    try:
        while True:
            # Clients don't need to send anything; this just keeps the
            # connection open and detects disconnects promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(recipient_id, websocket)
