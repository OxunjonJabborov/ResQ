"""Domain exceptions and their mapping onto DRF error responses."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


class DomainError(Exception):
    """Base class for business-rule violations raised by service modules.

    Services raise these instead of DRF exceptions so they stay usable from Celery
    tasks, admin actions and management commands.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "domain_error"

    def __init__(self, message: str, code: str | None = None, **extra):
        super().__init__(message)
        self.message = str(message)
        self.code = code or self.default_code
        self.extra = extra


class NotAllowed(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "not_allowed"


class NotFound(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "not_found"


class Conflict(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"


class TooManyRequests(DomainError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "too_many_requests"


class ServiceUnavailable(DomainError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "service_unavailable"


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        body = {"detail": exc.message, "code": exc.code, **exc.extra}
        return Response(body, status=exc.status_code)
    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, "error_dict") else {"detail": exc.messages}
        exc = DRFValidationError(detail=detail)
    return exception_handler(exc, context)
