from app.models.store import notification_store
from app.schemas.notification import NotificationOut
from fastapi import APIRouter, Query

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/{recipient_id}", response_model=list[NotificationOut])
async def list_notifications(
    recipient_id: str, limit: int = Query(default=20, ge=1, le=100)
) -> list[NotificationOut]:
    """Recent notification history for a recipient (a customer id, or
    "ops" for inventory alerts) - lets a client that just came online catch
    up before subscribing to the live WebSocket feed."""
    items = await notification_store.list_recent(recipient_id, limit=limit)
    return [NotificationOut(**item) for item in items]
