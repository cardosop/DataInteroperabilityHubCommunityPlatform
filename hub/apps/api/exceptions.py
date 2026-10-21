"""
Custom exception handler for REST API

Provides standardized error response format across all API endpoints.
"""

import contextlib
import re
import uuid

import structlog
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = structlog.get_logger(__name__)


# Error code mappings
ERROR_CODE_MAP = {
    status.HTTP_400_BAD_REQUEST: "VALIDATION_ERROR",
    status.HTTP_401_UNAUTHORIZED: "AUTH_UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "AUTH_FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT_ERROR",
    status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMIT_EXCEEDED",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_ERROR",
    status.HTTP_502_BAD_GATEWAY: "SERVICE_UNAVAILABLE",
    status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
}


# Django/DRF's GENERIC field-error codes — carry no machine-readable
# meaning, so nested-code extraction skips them (the HTTP-status mapping
# remains the fallback, unchanged from the historical contract). Domain
# codes (DATABRICKS_HOST_NOT_ALLOWED, DATA_RESIDENCY_MISMATCH, ...) are
# NOT in this set and pass through to the envelope.
_GENERIC_FIELD_CODES = frozenset(
    {
        # DRF field codes
        "invalid",
        "required",
        "blank",
        "null",
        "empty",
        "min_value",
        "max_value",
        "min_length",
        "max_length",
        "max_string_length",
        "max_digits",
        "max_decimal_places",
        "max_whole_digits",
        "unique",
        "does_not_exist",
        "incorrect_type",
        "invalid_choice",
        "overflow",
        "not_a_list",
        "not_a_dict",
        "no_name",
        # Django validator codes
        "invalid_email",
        "invalid_image",
        "invalid_time",
        "invalid_date",
        "invalid_datetime",
        "invalid_url",
        "invalid_extension",
        "file_too_large",
        "too_short",
        "too_long",
    }
)


# W1.16 — dict-form domain codes travel in the ErrorDetail STRING
# (services raise ValidationError({"field": ["SOME_DOMAIN_CODE"]}) and DRF
# tags them code='invalid'); recognize the uppercase-snake shape so the
# domain code reaches the envelope instead of collapsing to
# VALIDATION_ERROR.  Human-readable messages ("This field is required")
# never match this shape.
_DOMAIN_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{3,}\Z")


def _first_domain_code(detail) -> str | None:
    """Walk a DRF ValidationError detail tree; return the first nested
    code that is NOT one of Django/DRF's generic field-error codes."""
    if isinstance(detail, dict):
        for value in detail.values():
            found = _first_domain_code(value)
            if found:
                return found
    elif isinstance(detail, (list, tuple)):
        for item in detail:
            code = getattr(item, "code", None)
            if code and str(code) not in _GENERIC_FIELD_CODES:
                return str(code)
            # ErrorDetail is a str subclass (no .string attribute) —
            # the domain code is the string itself.
            raw = str(item) if isinstance(item, str) else None
            if (
                raw
                and _DOMAIN_CODE_RE.match(raw)
                and raw not in _GENERIC_FIELD_CODES
            ):
                return raw
            if isinstance(item, (dict, list, tuple)):
                found = _first_domain_code(item)
                if found:
                    return found
    return None


def get_error_code(exc, http_status):
    """
    Get error code from exception or HTTP status.

    Args:
        exc: Exception instance
        http_status: HTTP status code

    Returns:
        Error code string
    """
    # Check if exception has a code attribute
    if hasattr(exc, "code") and exc.code:
        return exc.code

    # Dict-form ValidationErrors carry the DOMAIN code on the nested field
    # errors (Django does not propagate top-level codes into dict-form
    # errors) — surface the first one so e.g. DATABRICKS_HOST_NOT_ALLOWED
    # reaches the envelope instead of collapsing to VALIDATION_ERROR.
    if hasattr(exc, "detail"):
        nested_code = _first_domain_code(exc.detail)
        if nested_code:
            return nested_code

    # Map HTTP status to error code
    return ERROR_CODE_MAP.get(http_status, "UNKNOWN_ERROR")


def get_error_message(exc, http_status):
    """
    Get user-friendly error message.

    Args:
        exc: Exception instance
        http_status: HTTP status code

    Returns:
        Error message string
    """
    # W1.16 / W10.3 (round-3 re-audit) — 5xx responses NEVER surface
    # exception text (SQL text, connection strings, internal stack
    # fragments). The redaction runs FIRST and unconditionally: the
    # pre-fix ordering checked ``.message`` and the detail-join BEFORE
    # the 5xx guard, so repo-defined service exceptions (environment
    # text by construction — warehouses/core-services/integrations
    # errors) leaked verbatim. Typed 4xx business errors keep their
    # messages — human-facing and safe by construction.
    if http_status >= 500:
        message = ""
    elif hasattr(exc, "message") and exc.message:
        # Check if exception has a message attribute
        message = exc.message
    elif hasattr(exc, "detail") and isinstance(exc.detail, (dict, list, tuple)):
        # DRF ValidationErrors: render the HUMAN field-error strings, joined.
        # ``str(exc)`` on these produces the Python repr
        # ``[ErrorDetail(string=..., code=...)]`` — internal representation
        # leaking into the user-facing envelope.
        parts: list[str] = []
        detail = exc.detail

        def collect(node) -> None:
            if isinstance(node, dict):
                for value in node.values():
                    collect(value)
            elif isinstance(node, (list, tuple)):
                for item in node:
                    if hasattr(item, "string"):
                        parts.append(str(item.string))
                    elif isinstance(item, (dict, list, tuple)):
                        collect(item)
                    else:
                        parts.append(str(item))
            else:
                parts.append(str(node))

        collect(detail)
        message = "; ".join(parts) if parts else str(exc)
    else:
        message = str(exc)

    # Remove stack traces and internal details
    if "Traceback" in message:
        message = message.split("Traceback", maxsplit=1)[0].strip()

    # Default messages for common status codes
    if not message or message == "None":
        default_messages = {
            status.HTTP_400_BAD_REQUEST: "Invalid request",
            status.HTTP_401_UNAUTHORIZED: "Authentication required",
            status.HTTP_403_FORBIDDEN: "Permission denied",
            status.HTTP_404_NOT_FOUND: "Resource not found",
            status.HTTP_409_CONFLICT: "Resource conflict",
            status.HTTP_429_TOO_MANY_REQUESTS: "Rate limit exceeded",
            status.HTTP_500_INTERNAL_SERVER_ERROR: "Internal server error",
        }
        message = default_messages.get(http_status, "An error occurred")

    return message


def get_error_details(exc, response):
    """
    Extract error details from exception.

    Args:
        exc: Exception instance
        response: DRF response object

    Returns:
        Tuple of (details_dict, original_data_dict) for field-level access
    """
    details = {}
    original_data = {}

    # W1.16 / W10.3 (round-3 re-audit): a raised 5xx's exception text
    # never reaches ``details`` either — only 4xx field errors are
    # client-meaningful (the pre-fix ``str(exc.detail)`` path leaked
    # string details at 5xx).
    if response is not None and getattr(response, "status_code", 0) >= 500:
        return None, {}

    # Check if exception has detail attribute
    if hasattr(exc, "detail"):
        if isinstance(exc.detail, dict):
            details = exc.detail
            original_data = exc.detail.copy()
        elif isinstance(exc.detail, list):
            details = {"errors": exc.detail}
            original_data = {"errors": exc.detail}
        else:
            details = {"message": str(exc.detail)}
            original_data = {"message": str(exc.detail)}

    # Check response data for validation errors
    elif response and hasattr(response, "data"):
        if isinstance(response.data, dict):
            # Preserve original data for field-level access
            original_data = response.data.copy()

            # DRF validation errors
            if "non_field_errors" in response.data:
                details["non_field_errors"] = response.data["non_field_errors"]

            # Field-specific errors
            field_errors = []
            for field, errors in response.data.items():
                if field != "non_field_errors":
                    if isinstance(errors, list):
                        for error in errors:
                            field_errors.append(
                                {"field": field, "message": str(error), "code": "VALIDATION_ERROR"}
                            )
                    else:
                        field_errors.append(
                            {"field": field, "message": str(errors), "code": "VALIDATION_ERROR"}
                        )

            if field_errors:
                details["field_errors"] = field_errors
        elif isinstance(response.data, list):
            details = {"errors": response.data}
            original_data = {"errors": response.data}

    return details if details else None, original_data


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns standardized error format.

    Returns error responses in the format:
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable message",
            "http_status": 400,
            "request_id": "uuid",
            "timestamp": "2025-01-15T10:30:00Z",
            "details": {}
        }
    }
    """
    # DRF 3.16's built-in exception_handler does NOT handle
    # django.core.exceptions.ValidationError — it falls through,
    # returns None, and we default to 500.  Wrap it into a DRF
    # ValidationError so the framework produces a proper 400 with
    # field-level error detail (e.g. duplicate-constraint failures).
    # Use as_serializer_error (NOT message_dict/messages) so nested
    # field-error CODES survive — message_dict strips them and every
    # dict-form domain code (DATABRICKS_HOST_NOT_ALLOWED, ...) collapsed
    # to VALIDATION_ERROR in the envelope (task 0.15).
    if isinstance(exc, DjangoValidationError):
        from rest_framework.serializers import as_serializer_error

        exc = DRFValidationError(detail=as_serializer_error(exc))

    response = exception_handler(exc, context)
    request = context.get("request")

    # Generate request ID if not present
    request_id = getattr(request, "id", None) if request else None
    if not request_id:
        request_id = str(uuid.uuid4())
        if request:
            request.id = request_id

    # Get HTTP status code
    if response is not None:
        http_status = response.status_code
        # Capture original response data BEFORE we modify it (for field-level access)
        original_response_data = (
            response.data.copy()
            if hasattr(response, "data") and isinstance(response.data, dict)
            else {}
        )
    else:
        # Unhandled exception, default to 500
        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        response = Response(status=http_status)
        original_response_data = {}

    # Build standardized error response
    error_code = get_error_code(exc, http_status)
    error_message = get_error_message(exc, http_status)
    error_details, original_data = get_error_details(exc, response)

    custom_response_data = {
        "error": {
            "code": error_code,
            "message": error_message,
            "http_status": http_status,
            "request_id": request_id,
            "timestamp": timezone.now().isoformat(),
        }
    }

    # Add details if available
    if error_details:
        custom_response_data["error"]["details"] = error_details

        # For rate limit errors, ensure retry_after is in details.
        # Phase 260.2.E S-9 contract: 429 responses MUST include
        # ``details.retry_after`` (seconds) so the client can back off.
        if http_status == status.HTTP_429_TOO_MANY_REQUESTS:
            if isinstance(error_details, dict) and "retry_after" not in error_details:
                # DRF >=3.15 stores ``wait`` on Throttled instances.
                wait = getattr(exc, "wait", None)
                if wait is not None:
                    with contextlib.suppress(TypeError, ValueError):
                        custom_response_data["error"]["details"]["retry_after"] = int(wait)
                else:
                    # Fallback: parse the wait seconds from the detail
                    # message (e.g. "…available in 60 seconds.").
                    import re

                    msg = str(exc.detail) if hasattr(exc, "detail") else ""
                    m = re.search(r"(\d+)", msg)
                    if m:
                        custom_response_data["error"]["details"]["retry_after"] = int(m.group(1))

    # For validation errors (400), also preserve field-level access for backward compatibility
    # This allows tests to access response.data['email'] while still providing standardized format
    if http_status == status.HTTP_400_BAD_REQUEST:
        # Use captured original response data (before our handler modified it) - this has the actual field errors
        source_data = original_response_data if original_response_data else original_data
        if source_data:
            # Preserve original field-level errors at top level
            for field_name, field_value in source_data.items():
                if field_name not in ["error"]:  # Don't overwrite our error structure
                    # Extract message from ErrorDetail if needed
                    if hasattr(field_value, "string"):
                        custom_response_data[field_name] = field_value.string
                    elif isinstance(field_value, list) and len(field_value) > 0:
                        # Handle list of errors - take first error message
                        if hasattr(field_value[0], "string"):
                            custom_response_data[field_name] = field_value[0].string
                        else:
                            custom_response_data[field_name] = str(field_value[0])
                    else:
                        custom_response_data[field_name] = str(field_value)

            # Also handle non_field_errors - extract field names from error messages
            if "non_field_errors" in source_data:
                non_field_errors = source_data["non_field_errors"]
                if isinstance(non_field_errors, list):
                    for error in non_field_errors:
                        error_str = str(error) if not hasattr(error, "string") else error.string
                        # Try to extract field name from error message (e.g., "File size (X) exceeds limit")
                        if "size" in error_str.lower() and "size" not in custom_response_data:
                            custom_response_data["size"] = error_str
                        elif "file" in error_str.lower() and "file" not in custom_response_data:
                            custom_response_data["file"] = error_str

    # Log error using enhanced error logger
    from hub.apps.core.error_handling.error_logging import ErrorLogger
    from hub.apps.core.error_handling.error_tracking import get_error_tracker

    error_logger = ErrorLogger()
    error_tracker = get_error_tracker()

    # Get tenant and user IDs from request
    tenant_id = None
    user_id = None
    if request:
        if hasattr(request, "tenant_id"):
            tenant_id = str(request.tenant_id)
        if hasattr(request, "user") and request.user.is_authenticated:
            user_id = str(request.user.id)

    # Classify severity: 4xx responses are expected client behaviour
    # (auth failures, not-found, rate-limiting, validation rejections).
    # Only 5xx responses indicate an actual server fault worth an
    # ERROR-level alert.  This keeps the log signal clean so real
    # faults aren't buried under routine HTTP error noise.
    log_level = "warning" if http_status < 500 else "error"

    # Log error
    error_logger.log_error(
        error=exc,
        error_code=error_code,
        message=error_message,
        http_status=http_status,
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        additional_context={
            "path": request.path if request else None,
            "method": request.method if request else None,
        },
        level=log_level,
    )

    # Track error in Sentry
    error_tracker.track_error(
        error=exc,
        error_code=error_code,
        message=error_message,
        http_status=http_status,
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        context={
            "path": request.path if request else None,
            "method": request.method if request else None,
        },
        level=log_level,
    )

    # Set user context for Sentry
    if user_id:
        error_tracker.set_user(user_id)
    if tenant_id:
        error_tracker.set_tenant(tenant_id)

    response.data = custom_response_data
    return response
