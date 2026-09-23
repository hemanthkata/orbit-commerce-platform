"""Stock reservation logic.

This is the one piece of the codebase where correctness under concurrency
matters more than anywhere else: two customers checking out the last unit of
the same product at the same moment must not both succeed. We handle that
with a pessimistic row lock (``select_for_update``) rather than an
optimistic-concurrency retry loop, because contention on hot SKUs is expected
to be common (flash sales, restocks) and a lock held for a few milliseconds
is cheaper than repeatedly retrying a failed compare-and-swap under load.
"""

from apps.common.exceptions import InsufficientStockError
from apps.common.kafka import publish_event
from apps.inventory.models import StockItem
from django.conf import settings
from django.db import transaction


@transaction.atomic
def reserve_stock(product_id, quantity: int) -> StockItem:
    """Locks the StockItem row for the duration of the transaction so
    concurrent requests for the same product serialize on this row instead
    of racing on a read-then-write of ``reserved_quantity``.
    """
    stock_item = StockItem.objects.select_for_update().get(product_id=product_id)

    if stock_item.available_quantity < quantity:
        raise InsufficientStockError(
            f"Only {stock_item.available_quantity} unit(s) left for "
            f"'{stock_item.product.name}'."
        )

    stock_item.reserved_quantity += quantity
    stock_item.save(update_fields=["reserved_quantity", "updated_at"])

    _publish_stock_event("stock.reserved", stock_item, quantity)
    return stock_item


@transaction.atomic
def release_stock(product_id, quantity: int) -> StockItem:
    """Called when an order is cancelled/expired before payment - returns
    the reserved units to the available pool."""
    stock_item = StockItem.objects.select_for_update().get(product_id=product_id)
    stock_item.reserved_quantity = max(stock_item.reserved_quantity - quantity, 0)
    stock_item.save(update_fields=["reserved_quantity", "updated_at"])

    _publish_stock_event("stock.released", stock_item, quantity)
    return stock_item


@transaction.atomic
def commit_stock(product_id, quantity: int) -> StockItem:
    """Called when an order is paid/fulfilled - converts a reservation into
    a permanent deduction from on-hand quantity."""
    stock_item = StockItem.objects.select_for_update().get(product_id=product_id)
    stock_item.quantity = max(stock_item.quantity - quantity, 0)
    stock_item.reserved_quantity = max(stock_item.reserved_quantity - quantity, 0)
    stock_item.save(update_fields=["quantity", "reserved_quantity", "updated_at"])

    _publish_stock_event("stock.committed", stock_item, quantity)
    return stock_item


def _publish_stock_event(event_type: str, stock_item: StockItem, quantity: int) -> None:
    publish_event(
        topic=settings.KAFKA_INVENTORY_EVENTS_TOPIC,
        event_type=event_type,
        key=str(stock_item.product_id),
        payload={
            "product_id": str(stock_item.product_id),
            "sku": stock_item.product.sku,
            "quantity_delta": quantity,
            "available_quantity": stock_item.available_quantity,
            "below_reorder_threshold": stock_item.is_below_reorder_threshold,
        },
    )
