from apps.orders.consumers import OrderStatusConsumer
from django.urls import re_path

websocket_urlpatterns = [
    re_path(r"^ws/orders/$", OrderStatusConsumer.as_asgi()),
]
