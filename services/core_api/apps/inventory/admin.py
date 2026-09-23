from apps.inventory.models import StockItem
from django.contrib import admin


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ["product", "quantity", "reserved_quantity", "available_quantity"]
    search_fields = ["product__sku", "product__name"]
