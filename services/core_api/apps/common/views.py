from apps.common.cache import get_redis_client
from django.db import connection
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """Liveness/readiness probe for Kubernetes and load balancers. Checks the
    two hard dependencies (DB, cache) that every request needs.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        checks = {"database": self._check_database(), "cache": self._check_cache()}
        healthy = all(checks.values())
        status_code = 200 if healthy else 503
        return Response(
            {
                "status": "ok" if healthy else "degraded",
                "timestamp": timezone.now().isoformat(),
                "checks": checks,
            },
            status=status_code,
        )

    @staticmethod
    def _check_database() -> bool:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _check_cache() -> bool:
        try:
            get_redis_client().ping()
            return True
        except Exception:  # noqa: BLE001
            return False
