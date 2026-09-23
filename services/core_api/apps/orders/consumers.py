from channels.generic.websocket import AsyncJsonWebSocketConsumer


class OrderStatusConsumer(AsyncJsonWebSocketConsumer):
    """ws://.../ws/orders/ - pushes real-time order status updates to the
    authenticated customer. Each connection joins a per-user group
    (``orders_<user_id>``) so ``apps.orders.tasks.broadcast_order_update``
    can target exactly the customer who placed the order, regardless of
    which ASGI worker process holds that socket (the Redis channel layer
    handles routing across processes).
    """

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f"orders_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def order_update(self, event):
        """Handler name must match the ``type`` key ("order.update" ->
        "order_update") sent via group_send in apps.orders.tasks."""
        await self.send_json(event["order"])
