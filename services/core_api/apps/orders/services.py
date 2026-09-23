from decimal import Decimal

from apps.catalog.models import Product
from apps.common.exceptions import DomainError
from apps.common.kafka import publish_event
from apps.inventory.services import release_stock, reserve_stock
from apps.orders.models import Order, OrderItem
from django.conf import settings
from django.db import transaction


@transaction.atomic
def place_order(customer, items: list[dict]) -> Order:
    """items: [{"product_id": UUID, "quantity": int}, ...]

    Reserves stock for every line item (each reservation takes its own row
    lock via ``inventory.services.reserve_stock``), then creates the order
    atomically - if any line is out of stock the whole transaction rolls
    back and nothing is reserved.
    """
    order = Order.objects.create(customer=customer, status=Order.Status.PENDING)
    total = Decimal("0")

    for line in items:
        product = Product.objects.select_related("category").get(
            id=line["product_id"], is_active=True
        )
        quantity = line["quantity"]
        reserve_stock(product.id, quantity)

        OrderItem.objects.create(
            order=order, product=product, quantity=quantity, unit_price=product.price
        )
        total += product.price * quantity

    order.total_amount = total
    order.save(update_fields=["total_amount"])

    publish_event(
        topic=settings.KAFKA_ORDER_EVENTS_TOPIC,
        event_type="order.created",
        key=str(order.id),
        payload=_order_event_payload(order),
    )
    return order


@transaction.atomic
def mark_order_paid(order: Order) -> Order:
    from apps.inventory.services import commit_stock

    order.status = Order.Status.PAID
    order.save(update_fields=["status", "updated_at"])

    for item in order.items.select_related("product"):
        commit_stock(item.product_id, item.quantity)

    publish_event(
        topic=settings.KAFKA_ORDER_EVENTS_TOPIC,
        event_type="order.paid",
        key=str(order.id),
        payload=_order_event_payload(order),
    )
    return order


@transaction.atomic
def cancel_order(order: Order) -> Order:
    """Only a PENDING order can be cancelled through this path: it's the
    only state where "cancel" means "release the stock reservation and
    nothing else." Once `mark_order_paid` has run, `commit_stock` has
    already permanently deducted on-hand quantity - releasing a
    (now-zeroed) reservation on top of that would flip the order to
    CANCELLED while silently leaving inventory understated, with no refund
    or restock actually issued. A paid/shipped order needs a real refund
    workflow, which is out of scope here, so we fail loudly instead of
    corrupting stock.
    """
    if order.status != Order.Status.PENDING:
        raise DomainError(
            f"Cannot cancel an order in '{order.status}' status; only pending "
            "(unpaid) orders can be cancelled this way."
        )

    for item in order.items.all():
        release_stock(item.product_id, item.quantity)

    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])

    publish_event(
        topic=settings.KAFKA_ORDER_EVENTS_TOPIC,
        event_type="order.cancelled",
        key=str(order.id),
        payload=_order_event_payload(order),
    )
    return order


def _order_event_payload(order: Order) -> dict:
    return {
        "order_id": str(order.id),
        "customer_id": str(order.customer_id),
        "status": order.status,
        "total_amount": str(order.total_amount),
    }
