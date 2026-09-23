from apps.catalog.models import Product
from apps.orders.models import Order, OrderItem
from rest_framework import serializers


class OrderItemSerializer(serializers.ModelSerializer):
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_sku", "product_name", "quantity", "unit_price"]
        read_only_fields = ["id", "unit_price"]


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True))
    quantity = serializers.IntegerField(min_value=1)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["id", "status", "total_amount", "items", "created_at", "updated_at"]
        read_only_fields = fields


class OrderCreateSerializer(serializers.Serializer):
    items = OrderItemInputSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("An order needs at least one item.")
        return value

    def create(self, validated_data):
        from apps.orders.services import place_order

        request = self.context["request"]
        items = [
            {"product_id": item["product_id"].id, "quantity": item["quantity"]}
            for item in validated_data["items"]
        ]
        return place_order(customer=request.user, items=items)

    def to_representation(self, instance):
        return OrderSerializer(instance, context=self.context).data
