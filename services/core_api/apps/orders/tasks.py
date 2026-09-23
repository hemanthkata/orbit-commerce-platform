import logging
from datetime import timedelta

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.db.models import Count, Sum
from django.utils import timezone

logger = logging.getLogger("apps.orders.tasks")


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_order_confirmation_email(self, order_id: str):
    """Simulated email send. In production this would call an ESP (SES,
    SendGrid, ...); kept as a logged no-op here so the project runs without
    external credentials, while still demonstrating the async-task pattern:
    the HTTP request that places an order returns immediately and this runs
    out-of-band on a Celery worker."""
    from apps.orders.models import Order

    try:
        order = Order.objects.select_related("customer").get(id=order_id)
    except Order.DoesNotExist:
        logger.warning("order_confirmation_skipped_missing_order", extra={"order_id": order_id})
        return

    logger.info(
        "order_confirmation_sent",
        extra={"order_id": order_id, "customer_email": order.customer.email},
    )


@shared_task
def broadcast_order_update(order_id: str):
    """Pushes the current order status to any WebSocket client subscribed to
    this customer's order-updates group (see apps.orders.consumers).
    Run as a Celery task, not inline in the request/signal, so a slow or
    unavailable channel layer never adds latency to the order API call.
    """
    from apps.orders.models import Order
    from apps.orders.services import _order_event_payload

    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(
        f"orders_{order.customer_id}",
        {"type": "order.update", "order": _order_event_payload(order)},
    )


@shared_task
def generate_daily_sales_report():
    """Celery Beat periodic task (see config.settings + django-celery-beat
    schedule created by the `seed_beat_schedule` management command):
    aggregates yesterday's paid orders into a summary log line. A stand-in
    for a real reporting pipeline (e.g. writing to a warehouse table or
    pushing to Slack)."""
    from apps.orders.models import Order

    since = timezone.now() - timedelta(days=1)
    paid_orders = Order.objects.filter(status=Order.Status.PAID, updated_at__gte=since)
    totals = paid_orders.aggregate(order_count=Count("id"), revenue=Sum("total_amount"))

    logger.info(
        "daily_sales_report",
        extra={
            "since": since.isoformat(),
            "order_count": totals["order_count"],
            "revenue": str(totals["revenue"] or 0),
        },
    )
    return totals
