from apps.catalog.models import Category, Product
from rest_framework import serializers


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all(), write_only=True
    )
    available_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "sku",
            "name",
            "description",
            "price",
            "is_active",
            "category",
            "category_id",
            "available_quantity",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_available_quantity(self, obj) -> int:
        # ProductViewSet.get_queryset() uses select_related("stock_item") so
        # this is a single joined query, not an N+1 per row.
        stock = getattr(obj, "stock_item", None)
        return stock.available_quantity if stock else 0
