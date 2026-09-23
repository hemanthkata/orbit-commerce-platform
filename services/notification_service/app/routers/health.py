from app.kafka.consumer import event_consumer
from app.models.store import notification_store
from app.schemas.notification import HealthOut
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    redis_ok = await notification_store.ping()
    return HealthOut(
        status="ok" if redis_ok else "degraded",
        kafka_connected=event_consumer.connected,
        redis_connected=redis_ok,
    )
