import logging
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.kafka.consumer import event_consumer
from app.models.store import notification_store
from app.routers import health, notifications, ws
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.main")

settings = get_settings()

if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await notification_store.connect()
    await event_consumer.start()
    logger.info("notification_service_started")
    yield
    await event_consumer.stop()
    await notification_store.disconnect()
    logger.info("notification_service_stopped")


app = FastAPI(
    title="Orbit Notification Service",
    description=(
        "Kafka-consuming, WebSocket-pushing microservice that turns core_api's "
        "order/inventory domain events into real-time notifications. See "
        "docs/architecture.md for how this fits into the wider platform."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(notifications.router)
app.include_router(ws.router)
