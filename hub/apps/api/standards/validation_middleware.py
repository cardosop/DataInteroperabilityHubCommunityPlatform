"""
API Validation Middleware

Validates API requests for consistency and standards compliance.
"""

import json
from collections.abc import Callable

import structlog
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework import status

from .error_codes import StandardErrorCodes
from .response_formats import format_error_response

logger = structlog.get_logger(__name__)


class APIValidationMiddleware(MiddlewareMixin):
    """
    Middleware to validate API requests for standards compliance.

    Validates:
    - Content-Type headers
    - Request body format (JSON)
    - Query parameter formats
    - Pagination parameters
    - Filtering parameters
    - Sorting parameters
    """

    def __init__(self, get_response: Callable):
        """Initialize middleware."""
        super().__init__(get_response)
        self.get_response = get_response

    def process_request(self, request: HttpRequest) -> HttpResponse | None:
        """
        Process and validate request.

        Args:
            request: Django HTTP request

        Returns:
            Error response if validation fails, None otherwise
        """
        # Only validate API requests
        if not request.path.startswith("/api/"):
            return None

        # W3C-spec endpoints accept non-JSON RDF/SPARQL bodies.
        # Phase 230.12 (REQ-SEM-LDN-001): LDN inbox accepts text/turtle,
        # application/ld+json, application/rdf+xml, application/n-triples.
        if "/api/v1/semantic/ldn/inbox/" in request.path or request.path.endswith(
            "/api/v1/semantic/ldn/inbox"
        ):
            return None

        # Validate Content-Type for POST/PUT/PATCH
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.META.get("CONTENT_TYPE", "")
            if "application/json" not in content_type and request.body:
                return self._error_response(
                    request,
                    StandardErrorCodes.INVALID_FORMAT,
                    "Content-Type must be application/json for POST/PUT/PATCH requests",
                    status.HTTP_400_BAD_REQUEST,
                )

        # Validate JSON body
        if request.method in ["POST", "PUT", "PATCH"] and request.body:
            try:
                json.loads(request.body)
            except json.JSONDecodeError as e:
                return self._error_response(
                    request,
                    StandardErrorCodes.INVALID_FORMAT,
                    f"Invalid JSON in request body: {e!s}",
                    status.HTTP_400_BAD_REQUEST,
                )

        # Validate query parameters
        validation_error = self._validate_query_params(request)
        if validation_error:
            return validation_error

        return None

    def _validate_query_params(self, request: HttpRequest) -> HttpResponse | None:
        """
        Validate query parameters.

        Args:
            request: Django HTTP request

        Returns:
            Error response if validation fails, None otherwise
        """
        # Validate pagination parameters
        page = request.GET.get("page")
        if page:
            try:
                page_num = int(page)
                if page_num < 1:
                    return self._error_response(
                        request,
                        StandardErrorCodes.VALIDATION_ERROR,
                        "Page number must be >= 1",
                        status.HTTP_400_BAD_REQUEST,
                    )
            except ValueError:
                return self._error_response(
                    request,
                    StandardErrorCodes.VALIDATION_ERROR,
                    "Page must be a valid integer",
                    status.HTTP_400_BAD_REQUEST,
                )

        page_size = request.GET.get("page_size")
        if page_size:
            try:
                page_size_num = int(page_size)
                if page_size_num < 1:
                    return self._error_response(
                        request,
                        StandardErrorCodes.VALIDATION_ERROR,
                        "Page size must be >= 1",
                        status.HTTP_400_BAD_REQUEST,
                    )
                if page_size_num > 100:
                    return self._error_response(
                        request,
                        StandardErrorCodes.VALIDATION_ERROR,
                        "Page size must be <= 100",
                        status.HTTP_400_BAD_REQUEST,
                    )
            except ValueError:
                return self._error_response(
                    request,
                    StandardErrorCodes.VALIDATION_ERROR,
                    "Page size must be a valid integer",
                    status.HTTP_400_BAD_REQUEST,
                )

        # Validate ordering parameters
        ordering = request.GET.get("ordering") or request.GET.get("order_by")
        if ordering:
            # Check for invalid characters
            if not all(c.isalnum() or c in ["-", "_", ",", "."] for c in ordering):
                return self._error_response(
                    request,
                    StandardErrorCodes.VALIDATION_ERROR,
                    "Invalid characters in ordering parameter",
                    status.HTTP_400_BAD_REQUEST,
                )

        return None

    def _error_response(
        self,
        request: HttpRequest,
        error_code: str,
        message: str,
        http_status: int,
    ) -> JsonResponse:
        """
        Create standardized error response.

        Args:
            request: The Django HTTP request (used to extract the
                traceable request_id set by RequestIDMiddleware).
            error_code: Error code
            message: Error message
            http_status: HTTP status code

        Returns:
            JSON error response
        """
        request_id = getattr(request, "request_id", None)
        error_data = format_error_response(
            error_code,
            message,
            http_status,
            request_id=request_id,
        )

        return JsonResponse(
            error_data.data,
            status=http_status,
        )
