import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """Adds created/updated timestamps. Base for every domain model."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDPrimaryKeyModel(models.Model):
    """UUID primary key so IDs are safe to expose across service boundaries
    (Kafka payloads, the notification_service, public API responses) without
    leaking sequential-integer volume information.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class BaseModel(UUIDPrimaryKeyModel, TimeStampedModel):
    class Meta:
        abstract = True
