from apps.common.models import BaseModel
from django.db import models


class StockItem(BaseModel):
    """One row per product. ``quantity`` is total on-hand stock;
    ``reserved_quantity`` is stock allocated to unpaid/unfulfilled orders.
    Kept as two separate counters (rather than decrementing quantity
    directly on order placement) so a cancelled/expired order can release
    its reservation without needing to know the "original" quantity.
    """

    product = models.OneToOneField(
        "catalog.Product", on_delete=models.CASCADE, related_name="stock_item"
    )
    quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    reorder_threshold = models.PositiveIntegerField(default=10)

    class Meta:
        indexes = [models.Index(fields=["product"])]

    def __str__(self):
        return f"{self.product.sku}: {self.available_quantity} available"

    @property
    def available_quantity(self) -> int:
        return max(self.quantity - self.reserved_quantity, 0)

    @property
    def is_below_reorder_threshold(self) -> bool:
        return self.available_quantity <= self.reorder_threshold
