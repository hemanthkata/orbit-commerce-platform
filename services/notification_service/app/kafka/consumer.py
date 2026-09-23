import asyncio
import json
import logging
import uuid

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError
from app.core.config import get_settings
from app.models.store import notification_store
from app.ws.manager import connection_manager

logger = logging.getLogger("app.kafka.consumer")


class EventConsumer:
    """Consumes the order-events / inventory-events topics core_api
    publishes to (see apps.common.kafka on the Django side) and fans each
    message out to (a) Redis-backed history and (b) any connected WebSocket
    client for the right recipient.
    """

    def __init__(self):
        self._settings = get_settings()
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            *self._settings.kafka_topic_list,
            bootstrap_servers=self._settings.kafka_bootstrap_servers,
            group_id=self._settings.kafka_consumer_group,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            await self._consumer.start()
            self._connected = True
        except KafkaConnectionError:
            logger.warning("kafka_unreachable_at_startup", extra={"retrying": True})
            self._connected = False
            return

        try:
            async for message in self._consumer:
                await self._handle_message(message.value)
        finally:
            await self._consumer.stop()
            self._connected = False

    async def _handle_message(self, raw: bytes) -> None:
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("dropped_unparseable_message")
            return

        event_type = envelope.get("event_type", "unknown")
        data = envelope.get("data", {})
        recipient = self._recipient_for(event_type, data)

        notification = {"id": str(uuid.uuid4()), "event_type": event_type, "data": data}
        await notification_store.append(recipient, notification)
        await connection_manager.broadcast(recipient, notification)

    @staticmethod
    def _recipient_for(event_type: str, data: dict) -> str:
        if event_type.startswith("order.") and data.get("customer_id"):
            return data["customer_id"]
        return "ops"

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        if self._consumer:
            await self._consumer.stop()


event_consumer = EventConsumer()
