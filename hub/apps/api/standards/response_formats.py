"""
Standardized Response Formats

Provides consistent response formatting across all API endpoints.
"""

from typing import Any

from rest_framework import status
from rest_framework.response import Response

from hub.apps.core.responses import api_error_response


class StandardResponseFormatter:
    """
    Standardized response formatter for API endpoints.

    Ensures all responses follow a consistent format.
    """

    @staticmethod
    def format_success(
        data: Any,
        status_code: int = status.HTTP_200_OK,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Response:
        """
        Format a successful response.

        Args:
            data: Response data (dict, list, or object)
            status_code: HTTP status code (default: 200)
            message: Optional success message
            metadata: Optional metadata to include

        Returns:
            Formatted Response object
        """
        response_data = {}

        # Add message if provided
        if message:
            response_data["message"] = message

        # Add metadata if provided
        if metadata:
            response_data["metadata"] = metadata

        # Add data
        if isinstance(data, dict):
            # Merge data into response if it's a dict
            response_data.update(data)
        else:
            # Otherwise, wrap in 'data' key
            response_data["data"] = data

        return Response(response_data, status=status_code)

    @staticmethod
    def format_list(
        items: list[Any],
        count: int,
        page: int | None = None,
        page_size: int | None = None,
        next_cursor: str | None = None,
        previous_cursor: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Response:
        """
        Format a paginated list response.

        Supports both cursor-based and page-based pagination.

        Args:
            items: List of items
            count: Total count of items
            page: Current page number (for page-based pagination)
            page_size: Items per page
            next_cursor: Next cursor (for cursor-based pagination)
            previous_cursor: Previous cursor (for cursor-based pagination)
            metadata: Optional metadata

        Returns:
            Formatted Response object
        """
        response_data = {
            "count": count,
            "results": items,
        }

        # Add pagination metadata
        if page is not None:
            response_data["page"] = page
        if page_size is not None:
            response_data["page_size"] = page_size

        # Add cursor-based pagination
        if next_cursor is not None:
            response_data["next_cursor"] = next_cursor
        if previous_cursor is not None:
            response_data["previous_cursor"] = previous_cursor

        # Add metadata
        if metadata:
            response_data["metadata"] = metadata

        return Response(response_data, status=status.HTTP_200_OK)

    @staticmethod
    def format_error(
        error_code: str,
        message: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> Response:
        """Format an error response.

        W12.5 — the ONE error envelope: this delegates to the canonical
        flat helper ``hub.apps.core.responses.api_error_response``
        (wire shape ``{"detail", "code", "details"}`` — the same shape
        the exception handler and the frontend consume). The pre-fix
        nested ``{"error": {...}}`` shape was a second, divergent
        envelope and is gone. ``request_id`` (when given) travels in
        the X-Request-ID response header, not the body.
        """
        response = api_error_response(
            message,
            status_code=http_status,
            code=error_code,
            details=details,
        )
        if request_id:
            response["X-Request-ID"] = request_id
        return response

    @staticmethod
    def format_created(
        data: Any,
        message: str | None = None,
        location: str | None = None,
    ) -> Response:
        """
        Format a 201 Created response.

        Args:
            data: Created resource data
            message: Optional success message
            location: Optional Location header value

        Returns:
            Formatted Response object
        """
        response_data = data if isinstance(data, dict) else {"data": data}

        if message:
            response_data["message"] = message

        response = Response(response_data, status=status.HTTP_201_CREATED)

        if location:
            response["Location"] = location

        return response

    @staticmethod
    def format_no_content() -> Response:
        """
        Format a 204 No Content response.

        Returns:
            Empty Response object
        """
        return Response(status=status.HTTP_204_NO_CONTENT)


# Convenience functions
def format_success_response(
    data: Any,
    status_code: int = status.HTTP_200_OK,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Response:
    """Convenience function for formatting success responses."""
    return StandardResponseFormatter.format_success(data, status_code, message, metadata)


def format_list_response(
    items: list[Any],
    count: int,
    page: int | None = None,
    page_size: int | None = None,
    next_cursor: str | None = None,
    previous_cursor: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Response:
    """Convenience function for formatting list responses."""
    return StandardResponseFormatter.format_list(
        items, count, page, page_size, next_cursor, previous_cursor, metadata
    )


def format_error_response(
    error_code: str,
    message: str,
    http_status: int = status.HTTP_400_BAD_REQUEST,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> Response:
    """Convenience function for formatting error responses.

    W12.5 — delegates to the canonical flat envelope
    (:func:`hub.apps.core.responses.api_error_response`).
    """
    return StandardResponseFormatter.format_error(
        error_code, message, http_status, details, request_id
    )
