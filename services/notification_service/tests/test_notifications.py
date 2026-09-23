from unittest.mock import AsyncMock

import pytest
from app.kafka.consumer import EventConsumer
from app.models.store import notification_store
from app.ws.manager import ConnectionManager


def test_list_notifications_returns_history(client, monkeypatch):
    async def list_recent(recipient, limit=20):
        assert recipient == "user-123"
        return [
            {"id": "n1", "event_type": "order.created", "data": {"order_id": "o1"}},
        ]

    monkeypatch.setattr(notification_store, "list_recent", list_recent)

    response = client.get("/notifications/user-123")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["event_type"] == "order.created"


@pytest.mark.asyncio
async def test_connection_manager_broadcasts_only_to_matching_recipient():
    manager = ConnectionManager()
    socket_a = AsyncMock()
    socket_b = AsyncMock()

    await manager.connect("user-123", socket_a)
    await manager.connect("user-456", socket_b)

    await manager.broadcast("user-123", {"event_type": "order.paid"})

    socket_a.send_json.assert_awaited_once_with({"event_type": "order.paid"})
    socket_b.send_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_connection_manager_drops_socket_on_send_failure():
    manager = ConnectionManager()
    broken_socket = AsyncMock()
    broken_socket.send_json.side_effect = RuntimeError("connection reset")

    await manager.connect("user-123", broken_socket)
    await manager.broadcast("user-123", {"event_type": "order.paid"})

    assert "user-123" not in manager._connections


def test_recipient_routing_for_order_vs_inventory_events():
    assert EventConsumer._recipient_for("order.created", {"customer_id": "abc"}) == "abc"
    assert EventConsumer._recipient_for("stock.reserved", {"sku": "SKU-1"}) == "ops"
