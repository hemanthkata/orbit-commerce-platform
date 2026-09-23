from apps.orders.views import OrderViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register("", OrderViewSet, basename="order")

urlpatterns = router.urls
