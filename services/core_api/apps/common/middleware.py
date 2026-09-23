import logging
import time
import uuid

logger = logging.getLogger("apps.common")


class RequestLoggingMiddleware:
    """Stamps every request with a correlation id (propagated to callers via
    the X-Request-ID header) and logs method/path/status/duration as
    structured JSON, so Filebeat -> Logstash -> Elasticsearch can pivot on it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        response["X-Request-ID"] = request.correlation_id
        logger.info(
            "request_handled",
            extra={
                "correlation_id": request.correlation_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
