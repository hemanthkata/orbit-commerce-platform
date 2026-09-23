import pytest
from app.kafka.consumer import event_consumer
from app.models.store import notification_store
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    """A TestClient whose lifespan doesn't touch a real Redis/Kafka - the
    unit tests below only exercise HTTP/WS routing and the in-process
    connection manager, not the external integrations (those are covered
    by the docker-compose based manual/integration test path)."""

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(notification_store, "connect", noop)
    monkeypatch.setattr(notification_store, "disconnect", noop)
    monkeypatch.setattr(event_consumer, "start", noop)
    monkeypatch.setattr(event_consumer, "stop", noop)

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
