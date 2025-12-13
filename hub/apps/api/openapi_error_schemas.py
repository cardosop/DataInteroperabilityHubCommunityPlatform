"""
OpenAPI Error Response Schemas

Comprehensive error response schemas for OpenAPI specification.
All error responses follow the standard error envelope format.
"""

from drf_spectacular.utils import inline_serializer
from rest_framework import serializers


# Standard Error Response Schema
def get_error_response_schema(
    status_code: int = 400,
    description: str = "Error response",
    error_code: str = "ERROR",
) -> dict:
    """
    Get standard error response schema.

    Args:
        status_code: HTTP status code
        description: Error description
        error_code: Error code example

    Returns:
        OpenAPI response schema
    """
    return inline_serializer(
        name=f"Error{status_code}",
        fields={
            "error": inline_serializer(
                name="ErrorObject",
                fields={
                    "code": serializers.CharField(
                        help_text="Machine-readable error code",
                        example=error_code,
                    ),
                    "message": serializers.CharField(
                        help_text="Human-readable error message",
                        example="An error occurred",
                    ),
                    "http_status": serializers.IntegerField(
                        help_text="HTTP status code",
                        example=status_code,
                    ),
                    "request_id": serializers.CharField(
                        help_text="Unique request identifier",
                        example="550e8400-e29b-41d4-a716-446655440000",
                    ),
                    "timestamp": serializers.DateTimeField(
                        help_text="ISO 8601 timestamp",
                        example="2025-01-15T10:30:00Z",
                    ),
                    "details": serializers.DictField(
                        help_text="Additional error details",
                        required=False,
                        allow_null=True,
                    ),
                },
            ),
        },
    )


# Common Error Response Schemas
ERROR_400_VALIDATION = get_error_response_schema(
    status_code=400,
    description="Validation error - invalid request data",
    error_code="VALIDATION_ERROR",
)

ERROR_400_VALIDATION_FAILED = get_error_response_schema(
    status_code=400,
    description="Contract validation failed",
    error_code="VALIDATION_FAILED",
)

ERROR_401_UNAUTHORIZED = get_error_response_schema(
    status_code=401,
    description="Authentication required - missing or invalid token",
    error_code="AUTH_UNAUTHORIZED",
)

ERROR_403_FORBIDDEN = get_error_response_schema(
    status_code=403,
    description="Insufficient permissions",
    error_code="AUTH_FORBIDDEN",
)

ERROR_404_NOT_FOUND = get_error_response_schema(
    status_code=404,
    description="Resource not found",
    error_code="NOT_FOUND",
)

ERROR_409_CONFLICT = get_error_response_schema(
    status_code=409,
    description="Resource conflict",
    error_code="CONFLICT_ERROR",
)

ERROR_429_RATE_LIMIT = get_error_response_schema(
    status_code=429,
    description="Rate limit exceeded",
    error_code="RATE_LIMIT_EXCEEDED",
)

ERROR_500_INTERNAL = get_error_response_schema(
    status_code=500,
    description="Internal server error",
    error_code="INTERNAL_ERROR",
)

ERROR_502_BAD_GATEWAY = get_error_response_schema(
    status_code=502,
    description="Service unavailable",
    error_code="SERVICE_UNAVAILABLE",
)

ERROR_503_SERVICE_UNAVAILABLE = get_error_response_schema(
    status_code=503,
    description="Service temporarily unavailable",
    error_code="SERVICE_UNAVAILABLE",
)


# Standard Error Responses Dictionary
STANDARD_ERROR_RESPONSES = {
    400: ERROR_400_VALIDATION,
    401: ERROR_401_UNAUTHORIZED,
    403: ERROR_403_FORBIDDEN,
    404: ERROR_404_NOT_FOUND,
    409: ERROR_409_CONFLICT,
    429: ERROR_429_RATE_LIMIT,
    500: ERROR_500_INTERNAL,
    502: ERROR_502_BAD_GATEWAY,
    503: ERROR_503_SERVICE_UNAVAILABLE,
}


def get_standard_error_responses(
    include_status_codes: list[int] = None,
) -> dict:
    """
    Get standard error responses for OpenAPI spec.

    Args:
        include_status_codes: List of status codes to include (default: all)

    Returns:
        Dictionary mapping status codes to error response schemas
    """
    if include_status_codes is None:
        include_status_codes = list(STANDARD_ERROR_RESPONSES.keys())

    return {
        status_code: STANDARD_ERROR_RESPONSES[status_code]
        for status_code in include_status_codes
        if status_code in STANDARD_ERROR_RESPONSES
    }
