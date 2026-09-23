from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: str
    event_type: str
    data: dict[str, Any]
    received_at: datetime = Field(default_factory=datetime.utcnow)


class HealthOut(BaseModel):
    status: str
    kafka_connected: bool
    redis_connected: bool
