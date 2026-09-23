import pytest
from apps.common.exceptions import InsufficientStockError
from apps.inventory.models import StockItem
from apps.orders.models import Order
from apps.orders.services import cancel_order, mark_order_paid, place_order, reserve_stock
from django.urls import reverse
from tests.factories import ProductFactory

pytestmark = pytest.mark.django_db


def test_place_order_reserves_stock_and_computes_total(user):
    product = ProductFactory(price="10.00", stock=5)

    order = place_order(customer=user, items=[{"product_id": product.id, "quantity": 3}])

    stock = StockItem.objects.get(product=product)
    assert order.total_amount == 30
    assert order.status == Order.Status.PENDING
    assert stock.reserved_quantity == 3
    assert stock.available_quantity == 2


def test_place_order_raises_when_stock_insufficient(user):
    product = ProductFactory(price="10.00", stock=1)

    with pytest.raises(InsufficientStockError):
        place_order(customer=user, items=[{"product_id": product.id, "quantity": 5}])

    # the failed reservation must not have partially mutated stock
    stock = StockItem.objects.get(product=product)
    assert stock.reserved_quantity == 0


def test_cancel_order_releases_reserved_stock(user):
    product = ProductFactory(price="10.00", stock=5)
    order = place_order(customer=user, items=[{"product_id": product.id, "quantity": 2}])

    cancel_order(order)

    order.refresh_from_db()
    stock = StockItem.objects.get(product=product)
    assert order.status == Order.Status.CANCELLED
    assert stock.reserved_quantity == 0
    assert stock.available_quantity == 5


def test_mark_order_paid_commits_stock(user):
    product = ProductFactory(price="10.00", stock=5)
    order = place_order(customer=user, items=[{"product_id": product.id, "quantity": 2}])

    mark_order_paid(order)

    order.refresh_from_db()
    stock = StockItem.objects.get(product=product)
    assert order.status == Order.Status.PAID
    assert stock.quantity == 3
    assert stock.reserved_quantity == 0


def test_second_reservation_fails_once_stock_exhausted(user):
    product = ProductFactory(price="10.00", stock=2)

    reserve_stock(product.id, 2)

    with pytest.raises(InsufficientStockError):
        reserve_stock(product.id, 1)


def test_create_order_via_api(auth_client, user):
    product = ProductFactory(price="10.00", stock=5)

    response = auth_client.post(
        reverse("order-list"),
        {"items": [{"product_id": str(product.id), "quantity": 2}]},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["status"] == "pending"
    assert response.data["total_amount"] == "20.00"


def test_customer_cannot_see_others_orders(auth_client, user):
    other_product = ProductFactory(price="5.00", stock=5)
    from tests.factories import UserFactory

    other_user = UserFactory()
    place_order(customer=other_user, items=[{"product_id": other_product.id, "quantity": 1}])

    response = auth_client.get(reverse("order-list"))

    assert response.status_code == 200
    assert response.data["results"] == []
