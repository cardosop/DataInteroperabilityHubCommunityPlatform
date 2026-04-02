"""
Standardized Filtering

Provides consistent filtering across all API endpoints.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

import structlog
from django.db.models import Q, QuerySet
from rest_framework.exceptions import ValidationError
from rest_framework.filters import BaseFilterBackend
from rest_framework.request import Request

logger = structlog.get_logger(__name__)


class StandardFilterBackend(BaseFilterBackend):
    """
    Standard filter backend for consistent filtering across endpoints.

    Supports:
    - Exact match: ?field=value
    - Case-insensitive: ?field__iexact=value
    - Contains: ?field__contains=value
    - In: ?field__in=value1,value2
    - Range: ?field__gte=value&field__lte=value
    - Null: ?field__isnull=true
    """

    def filter_queryset(self, request: Request, queryset: QuerySet, view) -> QuerySet:
        """
        Filter queryset based on query parameters.

        Args:
            request: DRF request object
            queryset: Django queryset
            view: View instance

        Returns:
            Filtered queryset
        """
        filter_params = parse_filter_params(request)

        if not filter_params:
            return queryset

        # Get allowed filter fields from view; normalise to List[str] | None
        raw_fields = getattr(view, "filter_fields", None)
        if raw_fields and isinstance(raw_fields, (list, set, tuple, frozenset)):
            allowed_fields: Optional[List[str]] = list(raw_fields)
        else:
            allowed_fields = None

        # When a whitelist is set, silently drop params whose base field is not
        # in the list rather than raising a 400 — unknown client-side params
        # (e.g. from URL bookmarks or older frontends) should not break requests.
        if allowed_fields is not None:
            filter_params = {
                k: v
                for k, v in filter_params.items()
                if k.split("__")[0] in allowed_fields
            }
            if not filter_params:
                return queryset

        # Apply filters
        queryset = apply_filters(queryset, filter_params, allowed_fields)

        return queryset


def parse_filter_params(request) -> Dict[str, Any]:
    """
    Parse filter parameters from request query params.

    Args:
        request: DRF request object or Django WSGIRequest

    Returns:
        Dictionary of filter parameters
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

    filter_params = {}

    for key, value in query_params.items():
        # Skip pagination and sorting parameters
        if key in ["page", "page_size", "cursor", "ordering", "order_by", "sort", "sort_by"]:
            continue

        # Skip special parameters
        if key.startswith("_"):
            continue

        filter_params[key] = value

    return filter_params


def validate_filter_params(
    filter_params: Dict[str, Any],
    allowed_fields: Optional[List[str]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate filter parameters.

    Args:
        filter_params: Dictionary of filter parameters
        allowed_fields: List of allowed field names (None = all allowed)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not filter_params:
        return True, None

    # Check if all fields are allowed
    if allowed_fields is not None:
        for field in filter_params.keys():
            # Extract base field name (before __)
            base_field = field.split("__")[0]
            if base_field not in allowed_fields:
                return False, f"Filter field '{base_field}' is not allowed"

    # Validate filter operators
    valid_operators = {
        "exact",
        "iexact",
        "contains",
        "icontains",
        "startswith",
        "istartswith",
        "endswith",
        "iendswith",
        "in",
        "gt",
        "gte",
        "lt",
        "lte",
        "isnull",
        "isnotnull",
        "range",
        "date",
        "year",
        "month",
        "day",
    }

    for field in filter_params.keys():
        if "__" in field:
            parts = field.split("__")
            if len(parts) > 1:
                operator = parts[-1]
                if operator not in valid_operators and operator not in ["in", "range"]:
                    # Allow custom operators for JSONB fields
                    if not operator.startswith("jsonb_"):
                        logger.warning(
                            "unknown_filter_operator",
                            field=field,
                            operator=operator,
                        )

    return True, None


def apply_filters(
    queryset: QuerySet,
    filter_params: Dict[str, Any],
    allowed_fields: Optional[List[str]] = None,
) -> QuerySet:
    """
    Apply filters to queryset.

    Args:
        queryset: Django queryset
        filter_params: Dictionary of filter parameters
        allowed_fields: List of allowed field names (None = all allowed)

    Returns:
        Filtered queryset
    """
    if not filter_params:
        return queryset

    # Validate filters
    is_valid, error = validate_filter_params(filter_params, allowed_fields)
    if not is_valid:
        raise ValidationError(error)

    # Build Q objects for filters
    q_objects = Q()

    for field, value in filter_params.items():
        # Skip empty values
        if value is None or value == "":
            continue

        # Handle special operators
        if "__in" in field:
            # Handle comma-separated values
            if isinstance(value, str):
                value = [v.strip() for v in value.split(",") if v.strip()]
            if value:
                q_objects &= Q(**{field: value})
        elif "__isnull" in field or "__isnotnull" in field:
            # Handle boolean strings
            if isinstance(value, str):
                value = value.lower() in ["true", "1", "yes"]
            q_objects &= Q(**{field: value})
        elif "__range" in field:
            # Handle range (comma-separated)
            if isinstance(value, str):
                parts = value.split(",")
                if len(parts) == 2:
                    try:
                        range_values = [float(parts[0]), float(parts[1])]
                        q_objects &= Q(**{field: range_values})
                    except ValueError:
                        logger.warning("invalid_range_value", field=field, value=value)
        else:
            # Standard filter
            try:
                q_objects &= Q(**{field: value})
            except Exception as e:
                logger.warning(
                    "filter_application_failed",
                    field=field,
                    value=value,
                    error=str(e),
                )

    # Apply filters
    if q_objects:
        queryset = queryset.filter(q_objects)

    return queryset
