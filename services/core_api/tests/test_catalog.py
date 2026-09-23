import pytest
from django.urls import reverse
from tests.factories import ProductFactory

pytestmark = pytest.mark.django_db


def test_list_products_exposes_available_quantity(auth_client):
    ProductFactory(stock=7)

    response = auth_client.get(reverse("product-list"))

    assert response.status_code == 200
    assert response.data["results"][0]["available_quantity"] == 7


def test_customer_cannot_create_product(auth_client):
    from tests.factories import CategoryFactory

    category = CategoryFactory()
    response = auth_client.post(
        reverse("product-list"),
        {
            "sku": "SKU-1",
            "name": "Widget",
            "price": "9.99",
            "category_id": str(category.id),
        },
    )

    assert response.status_code == 403


def test_staff_can_create_product(staff_client):
    from tests.factories import CategoryFactory

    category = CategoryFactory()
    response = staff_client.post(
        reverse("product-list"),
        {
            "sku": "SKU-2",
            "name": "Widget",
            "price": "9.99",
            "category_id": str(category.id),
        },
    )

    assert response.status_code == 201


def test_price_filter(auth_client):
    ProductFactory(price="5.00")
    ProductFactory(price="50.00")

    response = auth_client.get(reverse("product-list"), {"min_price": "10"})

    assert response.status_code == 200
    prices = [item["price"] for item in response.data["results"]]
    assert "5.00" not in prices
