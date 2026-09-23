"""Redis-backed notification history, keyed by recipient.

A recipient is either a customer id (order events belong to the customer
that placed the order) or the literal string "ops" (inventory events such as
low-stock alerts are broadcast to whichever staff are watching the ops feed,
not to a single customer). Kept as a capped Redis list rather than a
database table - notification history here is a rolling, short-retention
convenience feed, not a system of record (core_api's Postgres database is).
"""

import json
from typing import Any

import redis.asyncio as redis
from app.core.config import get_settings

_MAX_HISTORY_PER_RECIPIENT = 100


class NotificationStore:
    def __init__(self):
        self._settings = get_settings()
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        self._redis = redis.from_url(self._settings.redis_url, decode_responses=True)

    async def disconnect(self) -> None:
        if self._redis is not None:
            await self._redis.close()

    async def ping(self) -> bool:
        if self._redis is None:
            return False
        try:
            return await self._redis.ping()
        except Exception:  # noqa: BLE001
            return False

    def _key(self, recipient: str) -> str:
        return f"notifications:{recipient}"

    async def append(self, recipient: str, notification: dict[str, Any]) -> None:
        key = self._key(recipient)
        await self._redis.lpush(key, json.dumps(notification, default=str))
        await self._redis.ltrim(key, 0, _MAX_HISTORY_PER_RECIPIENT - 1)
        await self._redis.expire(key, self._settings.notification_ttl_seconds)

    async def list_recent(self, recipient: str, limit: int = 20) -> list[dict[str, Any]]:
        raw = await self._redis.lrange(self._key(recipient), 0, limit - 1)
        return [json.loads(item) for item in raw]


notification_store = NotificationStore()
