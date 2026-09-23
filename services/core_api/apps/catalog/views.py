from apps.catalog.filters import ProductFilter
from apps.catalog.models import Category, Product
from apps.catalog.serializers import CategorySerializer, ProductSerializer
from apps.common.permissions import IsStaffOrReadOnly
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from rest_framework import viewsets


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsStaffOrReadOnly]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsStaffOrReadOnly]
    filterset_class = ProductFilter
    search_fields = ["name", "sku", "description"]
    ordering_fields = ["price", "created_at", "name"]

    def get_queryset(self):
        return (
            Product.objects.select_related("category", "stock_item").filter(is_active=True)
            if not self.request.user.is_staff
            else Product.objects.select_related("category", "stock_item").all()
        )

    @method_decorator(vary_on_headers("Authorization"))
    @method_decorator(cache_page(60))
    def list(self, request, *args, **kwargs):
        # Product listing is read-heavy and changes infrequently relative to
        # request volume, so it's a good candidate for a short Redis cache -
        # cuts DB load under the "high-throughput concurrent reads" case
        # called out in the job spec. Varying on Authorization keeps the
        # staff-vs-customer queryset difference from leaking across users.
        return super().list(request, *args, **kwargs)
