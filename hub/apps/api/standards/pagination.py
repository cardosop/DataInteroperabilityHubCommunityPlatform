"""
Standardized Pagination

Provides cursor-based and page-based pagination for all API endpoints.
"""

import base64
import json
from typing import Any, Dict, List, Optional, Tuple

from django.core.paginator import InvalidPage, Paginator
from django.db.models import QuerySet
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response


class StandardCursorPagination(CursorPagination):
    """
    Standard cursor-based pagination for all API endpoints.

    Uses cursor-based pagination for better performance with large datasets.
    Recommended for most list endpoints.
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_at"
    cursor_query_param = "cursor"

    def get_paginated_response(self, data):
        """
        Return paginated response with standardized format.

        Returns:
            Response with count, results, next_cursor, previous_cursor
        """
        return Response(
            {
                "count": (
                    self.page.paginator.count
                    if hasattr(self, "page") and hasattr(self.page, "paginator")
                    else None
                ),
                "next_cursor": self.get_next_link(),
                "previous_cursor": self.get_previous_link(),
                "page_size": self.page_size,
                "results": data,
            }
        )

    def encode_cursor(self, position):
        """
        Encode cursor position.

        Args:
            position: Cursor position (tuple of values)

        Returns:
            Encoded cursor string
        """
        if not position:
            return None

        try:
            # Convert position to JSON and encode
            cursor_data = json.dumps(position)
            encoded = base64.b64encode(cursor_data.encode("utf-8")).decode("utf-8")
            return encoded
        except Exception:
            return None

    def decode_cursor(self, cursor):
        """
        Decode cursor position.

        Args:
            cursor: Encoded cursor string

        Returns:
            Decoded cursor position (tuple)
        """
        if not cursor:
            return None

        try:
            decoded = base64.b64decode(cursor.encode("utf-8")).decode("utf-8")
            position = json.loads(decoded)
            return tuple(position) if isinstance(position, list) else position
        except Exception:
            return None


class StandardPageNumberPagination(PageNumberPagination):
    """
    Standard page number-based pagination for API endpoints.

    Uses offset-based pagination. Use when cursor-based pagination is not suitable.
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        """
        Return paginated response with standardized format.

        Returns:
            Response with count, page, page_size, total_pages, next, previous, results
        """
        return Response(
            {
                "count": self.page.paginator.count,
                "page": self.page.number,
                "page_size": self.page.paginator.per_page,
                "total_pages": self.page.paginator.num_pages,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )


def get_pagination_params(request) -> Dict[str, Any]:
    """
    Extract and validate pagination parameters from request.

    Args:
        request: DRF request object or Django WSGIRequest

    Returns:
        Dictionary with pagination parameters
    """
    # Handle both DRF Request (has query_params) and Django WSGIRequest (has GET)
    if hasattr(request, "query_params"):
        # DRF Request
        query_params = request.query_params
    elif hasattr(request, "GET"):
        # Django WSGIRequest
        query_params = request.GET
    else:
        # Fallback
        query_params = {}

    # Get page number (for page-based pagination)
    try:
        page = int(query_params.get("page", 1))
        page = max(1, page)
    except (ValueError, TypeError):
        page = 1

    # Get page size
    try:
        page_size = int(query_params.get("page_size", 50))
        page_size = max(1, min(page_size, 100))  # Clamp between 1 and 100
    except (ValueError, TypeError):
        page_size = 50

    # Get cursor (for cursor-based pagination)
    cursor = query_params.get("cursor")

    return {
        "page": page,
        "page_size": page_size,
        "cursor": cursor,
    }


def validate_pagination_params(
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    cursor: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate pagination parameters.

    Args:
        page: Page number (for page-based pagination)
        page_size: Items per page
        cursor: Cursor string (for cursor-based pagination)

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Validate page
    if page is not None:
        if page < 1:
            return False, "Page number must be >= 1"

    # Validate page_size
    if page_size is not None:
        if page_size < 1:
            return False, "Page size must be >= 1"
        if page_size > 100:
            return False, "Page size must be <= 100"

    # Cannot use both page and cursor
    if page is not None and cursor is not None:
        return False, "Cannot use both page and cursor pagination"

    return True, None


def paginate_queryset_cursor(
    queryset: QuerySet,
    page_size: int = 50,
    cursor: Optional[str] = None,
    ordering: str = "-created_at",
) -> Tuple[QuerySet, Optional[str], Optional[str]]:
    """
    Paginate queryset using cursor-based pagination.

    Args:
        queryset: Django queryset
        page_size: Items per page
        cursor: Optional cursor string
        ordering: Ordering field (default: '-created_at')

    Returns:
        Tuple of (paginated_queryset, next_cursor, previous_cursor)
    """
    # Ensure ordering
    if not queryset.query.order_by:
        queryset = queryset.order_by(ordering)

    # Apply cursor if provided
    if cursor:
        # Decode cursor
        try:
            decoded = base64.b64decode(cursor.encode("utf-8")).decode("utf-8")
            position = json.loads(decoded)

            # Apply cursor filter
            if ordering.startswith("-"):
                field = ordering[1:]
                queryset = queryset.filter(**{f"{field}__lt": position[0]})
            else:
                field = ordering
                queryset = queryset.filter(**{f"{field}__gt": position[0]})
        except Exception:
            # Invalid cursor, return empty queryset
            return queryset.none(), None, None

    # Get page_size items
    items = list(queryset[: page_size + 1])

    # Check if there's a next page
    has_next = len(items) > page_size
    if has_next:
        items = items[:page_size]

    # Generate next cursor
    next_cursor = None
    if has_next and items:
        last_item = items[-1]
        if ordering.startswith("-"):
            field = ordering[1:]
        else:
            field = ordering

        if hasattr(last_item, field):
            position = [getattr(last_item, field)]
            next_cursor = base64.b64encode(json.dumps(position).encode("utf-8")).decode("utf-8")

    # Previous cursor is the current cursor (if provided)
    previous_cursor = cursor

    return (
        queryset.model.objects.filter(pk__in=[item.pk for item in items]),
        next_cursor,
        previous_cursor,
    )
