"""
Pagination utilities for contract queries.

Implements cursor-based and offset-based pagination for optimal performance.
"""
from typing import Any, Dict, List, Optional, Tuple
from django.core.paginator import Paginator
from django.db.models import QuerySet
from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response


class ContractPageNumberPagination(PageNumberPagination):
    """
    Page number-based pagination for contracts.
    
    Uses offset-based pagination with configurable page size.
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        """Return paginated response with metadata."""
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page': self.page.number,
            'page_size': self.page.paginator.per_page,
            'total_pages': self.page.paginator.num_pages,
            'results': data
        })


class ContractCursorPagination(CursorPagination):
    """
    Cursor-based pagination for contracts.
    
    Uses cursor-based pagination for better performance with large datasets.
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100
    ordering = '-created_at'
    
    def get_paginated_response(self, data):
        """Return paginated response with metadata."""
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page_size': self.page_size,
            'results': data
        })


def paginate_queryset(
    queryset: QuerySet,
    page: int = 1,
    page_size: int = 50,
    max_page_size: int = 100
) -> Tuple[List[Any], Dict[str, Any]]:
    """
    Paginate a queryset using offset-based pagination.
    
    Args:
        queryset: Django queryset to paginate
        page: Page number (1-indexed)
        page_size: Number of items per page
        max_page_size: Maximum page size allowed
    
    Returns:
        Tuple of (items list, pagination metadata)
    """
    # Enforce max page size
    page_size = min(page_size, max_page_size)
    
    paginator = Paginator(queryset, page_size)
    
    try:
        page_obj = paginator.page(page)
    except Exception:
        # Invalid page number, return empty results
        return [], {
            'count': paginator.count,
            'page': page,
            'page_size': page_size,
            'total_pages': paginator.num_pages,
            'has_next': False,
            'has_previous': False
        }
    
    return list(page_obj.object_list), {
        'count': paginator.count,
        'page': page_obj.number,
        'page_size': page_size,
        'total_pages': paginator.num_pages,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None
    }


def optimize_queryset_for_pagination(queryset: QuerySet, ordering: Optional[str] = None) -> QuerySet:
    """
    Optimize queryset for pagination by adding appropriate ordering and select_related.
    
    Args:
        queryset: Django queryset to optimize
        ordering: Optional ordering field (default: '-created_at')
    
    Returns:
        Optimized queryset
    """
    # Add default ordering if not present
    if not queryset.query.order_by and ordering:
        queryset = queryset.order_by(ordering)
    elif not queryset.query.order_by:
        queryset = queryset.order_by('-created_at')
    
    # Use select_related for foreign keys to reduce queries
    if hasattr(queryset.model, 'tenant'):
        queryset = queryset.select_related('tenant')
    if hasattr(queryset.model, 'asset'):
        queryset = queryset.select_related('asset')
    if hasattr(queryset.model, 'created_by'):
        queryset = queryset.select_related('created_by')
    
    # Use only() to limit fields if needed (for very large JSONB fields)
    # queryset = queryset.only('id', 'status', 'created_at', ...)
    
    return queryset


def get_pagination_params(request) -> Dict[str, Any]:
    """
    Extract pagination parameters from request.
    
    Args:
        request: Django/DRF request object
    
    Returns:
        Dictionary with pagination parameters
    """
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 50))
    max_page_size = int(request.query_params.get('max_page_size', 100))
    
    # Validate and clamp values
    page = max(1, page)
    page_size = max(1, min(page_size, max_page_size))
    
    return {
        'page': page,
        'page_size': page_size,
        'max_page_size': max_page_size
    }

