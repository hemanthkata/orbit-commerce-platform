from apps.common import idempotency
from apps.orders.models import Order
from apps.orders.serializers import OrderCreateSerializer, OrderSerializer
from apps.orders.services import cancel_order, mark_order_paid
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

_IDEMPOTENCY_SCOPE = "order-create"


class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Orders are created and read here, but never updated/deleted via a
    generic PUT/DELETE - state transitions (pay/cancel) go through explicit
    actions below so every transition can enforce its own business rules
    and emit the right domain event."""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Order.objects.prefetch_related("items__product").select_related("customer")
        if self.request.user.is_staff:
            return qs
        return qs.filter(customer=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        return OrderSerializer

    def create(self, request, *args, **kwargs):
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return self._create_order(request)

        outcome, payload = idempotency.begin(_IDEMPOTENCY_SCOPE, request.user.id, idempotency_key)
        if outcome == "in_progress":
            return Response(
                {
                    "error": {
                        "detail": "A request with this Idempotency-Key is still being processed.",
                        "code": "IdempotencyKeyInProgress",
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )
        if outcome == "replay":
            return Response(payload["body"], status=payload["status_code"])

        try:
            response = self._create_order(request)
        except Exception:
            idempotency.abandon(_IDEMPOTENCY_SCOPE, request.user.id, idempotency_key)
            raise

        idempotency.complete(
            _IDEMPOTENCY_SCOPE,
            request.user.id,
            idempotency_key,
            response.status_code,
            response.data,
        )
        return response

    def _create_order(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        order = self.get_object()
        order = mark_order_paid(order)
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        order = cancel_order(order)
        return Response(OrderSerializer(order).data)
