from app.kafka.consumer import event_consumer
from app.models.store import notification_store


def test_health_reports_degraded_when_redis_down(client, monkeypatch):
    async def ping_false():
        return False

    monkeypatch.setattr(notification_store, "ping", ping_false)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["redis_connected"] is False


def test_health_ok_when_dependencies_up(client, monkeypatch):
    async def ping_true():
        return True

    monkeypatch.setattr(notification_store, "ping", ping_true)
    monkeypatch.setattr(event_consumer, "_connected", True)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "kafka_connected": True,
        "redis_connected": True,
    }
