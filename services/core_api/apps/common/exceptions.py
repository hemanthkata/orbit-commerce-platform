import logging

from rest_framework.views import exception_handler

logger = logging.getLogger("apps.common")


class DomainError(Exception):
    """Base class for business-rule violations raised from service code
    (as opposed to Django/DRF framework exceptions)."""

    default_message = "A domain error occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class InsufficientStockError(DomainError):
    default_message = "Not enough stock available to fulfil this order."


def api_exception_handler(exc, context):
    """Wraps DRF's default handler so every error response - framework or
    domain - has the same envelope: {"error": {"detail": ..., "code": ...}}.
    Keeps API error shapes predictable for API consumers and Sentry noise low
    by logging with the correlation id set by RequestLoggingMiddleware.
    """
    if isinstance(exc, DomainError):
        from rest_framework import status
        from rest_framework.response import Response

        logger.warning("domain_error", extra={"detail": exc.message})
        return Response(
            {"error": {"detail": exc.message, "code": exc.__class__.__name__}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = exception_handler(exc, context)
    if response is not None:
        response.data = {
            "error": {
                "detail": response.data,
                "code": exc.__class__.__name__,
            }
        }
    return response
