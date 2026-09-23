"""Thin, lazily-initialised Kafka producer wrapper.

core_api is a *producer only* - it publishes domain events (order placed,
stock adjusted) and never blocks a request/response cycle waiting on a
consumer. notification_service (a separate FastAPI process) is the consumer
that turns these events into WebSocket pushes / persisted notifications.
This decouples the two services: core_api works even if Kafka or the
notification service is temporarily down, it just stops publishing events.
"""

import json
import logging
from functools import lru_cache

from django.conf import settings

logger = logging.getLogger("apps.common.kafka")


@lru_cache(maxsize=1)
def _get_producer():
    if not settings.KAFKA_PRODUCER_ENABLED:
        return None
    from kafka import KafkaProducer
    from kafka.errors import NoBrokersAvailable

    try:
        return KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            retries=3,
            linger_ms=20,
        )
    except NoBrokersAvailable:
        logger.warning("kafka_unavailable", extra={"brokers": settings.KAFKA_BOOTSTRAP_SERVERS})
        return None


def publish_event(topic: str, event_type: str, payload: dict, key: str | None = None) -> None:
    """Publish a JSON event. Failures are logged and swallowed - event
    publishing is best-effort and must never fail the request that
    triggered it (e.g. placing an order should succeed even if Kafka is
    momentarily unreachable).
    """
    producer = _get_producer()
    if producer is None:
        logger.debug("kafka_publish_skipped", extra={"topic": topic, "event_type": event_type})
        return

    envelope = {"event_type": event_type, "data": payload}
    try:
        producer.send(topic, key=key, value=envelope)
        producer.flush(timeout=5)
    except Exception:  # noqa: BLE001 - best-effort publish, never raise into caller
        logger.exception("kafka_publish_failed", extra={"topic": topic, "event_type": event_type})
