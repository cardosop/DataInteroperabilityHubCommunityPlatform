"""
Standardized Response Formats

Provides consistent response formatting across all API endpoints.
"""

import uuid
from typing import Any, Dict, List, Optional

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response


class StandardResponseFormatter:
    """
    Standardized response formatter for API endpoints.

    Ensures all responses follow a consistent format.
    """

    @staticmethod
    def format_success(
        data: Any,
        status_code: int = status.HTTP_200_OK,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
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
        items: List[Any],
        count: int,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        next_cursor: Optional[str] = None,
        previous_cursor: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
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
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> Response:
        """
        Format an error response.

        Args:
            error_code: Machine-readable error code
            message: Human-readable error message
            http_status: HTTP status code
            details: Optional error details
            request_id: Optional request ID

        Returns:
            Formatted error Response object
        """
        if not request_id:
            request_id = str(uuid.uuid4())

        error_data = {
            "error": {
                "code": error_code,
                "message": message,
                "http_status": http_status,
                "request_id": request_id,
                "timestamp": timezone.now().isoformat(),
            }
        }

        if details:
            error_data["error"]["details"] = details

        return Response(error_data, status=http_status)

    @staticmethod
    def format_created(
        data: Any,
        message: Optional[str] = None,
        location: Optional[str] = None,
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
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Response:
    """Convenience function for formatting success responses."""
    return StandardResponseFormatter.format_success(data, status_code, message, metadata)


def format_list_response(
    items: List[Any],
    count: int,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    next_cursor: Optional[str] = None,
    previous_cursor: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Response:
    """Convenience function for formatting list responses."""
    return StandardResponseFormatter.format_list(
        items, count, page, page_size, next_cursor, previous_cursor, metadata
    )


def format_error_response(
    error_code: str,
    message: str,
    http_status: int = status.HTTP_400_BAD_REQUEST,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Response:
    """Convenience function for formatting error responses."""
    return StandardResponseFormatter.format_error(
        error_code, message, http_status, details, request_id
    )
