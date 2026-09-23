"""Aggregates websocket routes from every domain app so config.asgi has a
single import. Keeps the routing fan-out itself owned by this app while the
actual consumers stay next to the domain they belong to (apps.orders)."""

from apps.orders.routing import websocket_urlpatterns as order_ws_urlpatterns

websocket_urlpatterns = [
    *order_ws_urlpatterns,
]
