"""
Standardized Sorting

Provides consistent sorting across all API endpoints.
"""

from typing import Any, Dict, List, Optional, Tuple

import structlog
from django.db.models import QuerySet
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request

logger = structlog.get_logger(__name__)


class StandardOrderingBackend(OrderingFilter):
    """
    Standard ordering backend for consistent sorting across endpoints.

    Supports:
    - Single field: ?ordering=field_name
    - Multiple fields: ?ordering=field1,field2
    - Descending: ?ordering=-field_name
    - Ascending: ?ordering=field_name (default)
    """

    ordering_param = "ordering"
    ordering_fields = None  # Override in view
    ordering = ["-created_at"]  # Default ordering

    def filter_queryset(self, request: Request, queryset: QuerySet, view) -> QuerySet:
        """
        Apply ordering to queryset.

        Args:
            request: DRF request object
            queryset: Django queryset
            view: View instance

        Returns:
            Ordered queryset
        """
        ordering_params = parse_ordering_params(request)

        if not ordering_params:
            # Use default ordering; only accept list/tuple/str to guard against
            # Mock objects returned by `getattr` when view is a test double.
            raw_ordering = getattr(view, "ordering", None)
            if isinstance(raw_ordering, (list, tuple)) and raw_ordering:
                ordering = raw_ordering
            elif isinstance(raw_ordering, str) and raw_ordering:
                ordering = [raw_ordering]
            else:
                ordering = self.ordering
            if ordering:
                queryset = queryset.order_by(*ordering)
            return queryset

        # Get allowed ordering fields from view; guard against Mock/non-list values
        raw_ordering_fields = getattr(view, "ordering_fields", None)
        if isinstance(raw_ordering_fields, (list, set, tuple, frozenset)):
            ordering_fields: Optional[List[str]] = list(raw_ordering_fields)
        else:
            ordering_fields = self.ordering_fields

        # Validate ordering
        is_valid, error = validate_ordering_params(ordering_params, ordering_fields)
        if not is_valid:
            raise ValidationError(error)

        # Apply ordering
        queryset = apply_ordering(queryset, ordering_params)

        return queryset


def parse_ordering_params(request) -> List[str]:
    """
    Parse ordering parameters from request.

    Args:
        request: DRF request object or Django WSGIRequest

    Returns:
        List of ordering fields (e.g., ['-created_at', 'name'])
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

    ordering = (
        query_params.get("ordering") or query_params.get("order_by") or query_params.get("sort")
    )

    if not ordering:
        return []

    # Split comma-separated values
    ordering_fields = [field.strip() for field in ordering.split(",") if field.strip()]

    return ordering_fields


def validate_ordering_params(
    ordering_params: List[str],
    allowed_fields: Optional[List[str]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate ordering parameters.

    Args:
        ordering_params: List of ordering fields
        allowed_fields: List of allowed field names (None = all allowed)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not ordering_params:
        return True, None

    # Check if all fields are allowed
    if allowed_fields is not None:
        for field in ordering_params:
            # Remove leading - for descending
            base_field = field.lstrip("-")
            if base_field not in allowed_fields:
                return False, f"Ordering field '{base_field}' is not allowed"

    return True, None


def apply_ordering(queryset: QuerySet, ordering_params: List[str]) -> QuerySet:
    """
    Apply ordering to queryset.

    Args:
        queryset: Django queryset
        ordering_params: List of ordering fields

    Returns:
        Ordered queryset
    """
    if not ordering_params:
        return queryset

    # Apply ordering
    try:
        queryset = queryset.order_by(*ordering_params)
    except Exception as e:
        logger.warning(
            "ordering_application_failed",
            ordering=ordering_params,
            error=str(e),
        )
        # Fall back to default ordering
        queryset = queryset.order_by("-created_at")

    return queryset
