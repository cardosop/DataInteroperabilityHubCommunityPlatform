"""
Search API Views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from django.db import transaction
from django.utils import timezone

from .models import SearchIndex, SearchAnalytics
from .search_engine import SearchEngine
from .serializers import (
    SearchResponseSerializer,
    SearchSuggestionSerializer,
    SearchAnalyticsSerializer,
    SearchAnalyticsDashboardSerializer
)
from .indexing import SearchIndexer
from rest_framework.permissions import IsAuthenticated
from hub.apps.auth.permissions import HasRole

# Auditor permission - users with AUDITOR role
class IsAuditor(HasRole):
    def __init__(self):
        super().__init__('AUDITOR')


class SearchViewSet(viewsets.ViewSet):
    """
    Search API endpoints.

    Provides full-text search across contracts, assets, and datasets.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def search(self, request: Request) -> Response:
        """
        Perform full-text search.

        GET /api/v1/search/search?q={query}&type={type}&classification={classification}&...

        Query Parameters:
        - q: Search query string (required)
        - type: Resource type filter (CONTRACT, ASSET, DATASET)
        - classification: Classification filter
        - owner: Owner ID filter
        - tags: Tags filter (comma-separated)
        - domain: Domain filter
        - quality_status: Quality status filter
        - compliance_status: Compliance status filter
        - limit: Results per page (default: 20, max: 100)
        - offset: Pagination offset (default: 0)
        - sort_by: Sort field (relevance, created_at, indexed_at)
        - sort_order: Sort order (asc, desc)
        """
        # Get tenant from user (with caching)
        from django.core.cache import cache
        tenant = None

        if hasattr(request.user, 'tenant_id'):
            tenant_id = request.user.tenant_id
            cache_key = f"tenant:{tenant_id}"
            tenant = cache.get(cache_key)
            if tenant is None:
                from hub.apps.tenants.models import Tenant
                try:
                    tenant = Tenant.objects.get(id=tenant_id)
                    cache.set(cache_key, tenant, 300)  # Cache for 5 minutes
                except Tenant.DoesNotExist:
                    pass

        if not tenant and hasattr(request.user, 'tenant') and request.user.tenant:
            tenant = request.user.tenant

        if not tenant:
            return Response(
                {'error': 'User must belong to a tenant to perform searches'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get query
        query = request.query_params.get('q', '').strip()

        # Get filters
        resource_type = request.query_params.get('type')
        classification = request.query_params.get('classification')
        owner_id = request.query_params.get('owner')
        tags_str = request.query_params.get('tags')
        tags = tags_str.split(',') if tags_str else None
        domain = request.query_params.get('domain')
        quality_status = request.query_params.get('quality_status')
        compliance_status = request.query_params.get('compliance_status')

        # Get pagination
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))

        # Validate pagination parameters
        if limit < 1:
            return Response(
                {'error': 'limit must be greater than 0'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if limit > 100:
            limit = 100  # Cap at maximum
        if offset < 0:
            offset = 0  # Clamp negative offset to 0

        # Get sorting
        sort_by = request.query_params.get('sort_by', 'relevance')
        sort_order = request.query_params.get('sort_order', 'desc')

        # Check cache for search results (cache key based on query and filters)
        from django.core.cache import cache
        cache_key_parts = [
            f"search:{tenant.id}",
            query or "",
            resource_type or "",
            classification or "",
            owner_id or "",
            ",".join(sorted(tags)) if tags else "",
            domain or "",
            quality_status or "",
            compliance_status or "",
            str(limit),
            str(offset),
            sort_by,
            sort_order
        ]
        cache_key = ":".join(cache_key_parts)
        cached_results = cache.get(cache_key)

        if cached_results is not None:
            results, total = cached_results
        else:
            # Perform search
            results, total = SearchEngine.search(
                tenant_id=str(tenant.id),
                query=query,
                resource_type=resource_type,
                classification=classification,
                owner_id=owner_id,
                tags=tags,
                domain=domain,
                quality_status=quality_status,
                compliance_status=compliance_status,
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_order=sort_order
            )
            # Cache results for 5 minutes
            cache.set(cache_key, (results, total), 300)

        # Track search (async in production via job queue)
        # For now, we'll do it synchronously but log it for async processing
        try:
            analytics = SearchEngine.track_search(
                tenant_id=str(tenant.id),
                query=query,
                query_type="SEARCH",
                filters={
                    "type": resource_type,
                    "classification": classification,
                    "owner": owner_id,
                    "tags": tags,
                    "domain": domain,
                    "quality_status": quality_status,
                    "compliance_status": compliance_status,
                },
                result_count=total,
                user_id=str(request.user.id) if request.user.is_authenticated else None,
                session_id=request.session.session_key if hasattr(request, 'session') else None,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to track search: {e}", exc_info=True)
            analytics = None

        # Return response
        response_data = {
            "results": results,
            "total": total,
            "limit": limit,
            "offset": offset,
            "query": query,
        }

        # Include analytics ID if tracking succeeded
        if analytics:
            response_data["analytics_id"] = str(analytics.id)

        serializer = SearchResponseSerializer(response_data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def suggestions(self, request: Request) -> Response:
        """
        Get search suggestions (autocomplete).

        GET /api/v1/search/suggestions?q={partial_query}

        Query Parameters:
        - q: Partial query string (required, min 2 characters)
        - limit: Maximum number of suggestions (default: 10)
        """
        # Get tenant from user
        tenant = request.user.tenant if hasattr(request.user, 'tenant') and request.user.tenant else None
        if not tenant:
            return Response(
                {'error': 'User must belong to a tenant to get suggestions'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get query
        query = request.query_params.get('q', '').strip()

        if len(query) < 2:
            return Response(
                {'error': 'Query must be at least 2 characters'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get limit
        limit = int(request.query_params.get('limit', 10))

        # Get suggestions
        suggestions = SearchEngine.get_suggestions(
            tenant_id=str(tenant.id),
            query=query,
            limit=limit
        )

        # Track suggestion query
        SearchEngine.track_search(
            tenant_id=str(tenant.id),
            query=query,
            query_type="SUGGESTION",
            result_count=len(suggestions),
            user_id=str(request.user.id) if request.user.is_authenticated else None,
            session_id=request.session.session_key if hasattr(request, 'session') else None,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )

        serializer = SearchSuggestionSerializer(suggestions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def track_click(self, request: Request) -> Response:
        """
        Track a click on a search result.

        POST /api/v1/search/track_click

        Body:
        {
            "analytics_id": "uuid",
            "result_id": "uuid",
            "result_type": "CONTRACT|ASSET|DATASET"
        }
        """
        analytics_id = request.data.get('analytics_id')
        result_id = request.data.get('result_id')
        result_type = request.data.get('result_type')

        if not all([analytics_id, result_id, result_type]):
            return Response(
                {'error': 'analytics_id, result_id, and result_type are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        SearchEngine.track_click(analytics_id, result_id, result_type)

        return Response({'status': 'click tracked'})

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsAuditor])
    def analytics(self, request: Request) -> Response:
        """
        Get search analytics dashboard.

        GET /api/v1/search/analytics

        Query Parameters:
        - start_date: Start date (ISO format)
        - end_date: End date (ISO format)
        - limit: Number of results per category (default: 10)
        """
        # Get tenant from user
        tenant = request.user.tenant if hasattr(request.user, 'tenant') and request.user.tenant else None
        if not tenant:
            return Response(
                {'error': 'User must belong to a tenant to view analytics'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get date range
        from datetime import datetime, timedelta
        from django.utils.dateparse import parse_datetime

        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)

        start_date_str = request.query_params.get('start_date')
        if start_date_str:
            parsed = parse_datetime(start_date_str)
            if parsed:
                start_date = parsed

        end_date_str = request.query_params.get('end_date')
        if end_date_str:
            parsed = parse_datetime(end_date_str)
            if parsed:
                end_date = parsed

        # Get limit
        limit = int(request.query_params.get('limit', 10))

        # Get analytics
        analytics_queryset = SearchAnalytics.objects.filter(
            tenant=tenant,
            created_at__gte=start_date,
            created_at__lte=end_date
        )

        # Popular searches
        from django.db.models import Count
        popular_searches = analytics_queryset.filter(
            no_results=False
        ).values('query').annotate(
            count=Count('id')
        ).order_by('-count')[:limit]

        # Search trends (by day)
        search_trends = analytics_queryset.extra(
            select={'day': "DATE(created_at)"}
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day')

        # No-result queries
        no_result_queries = analytics_queryset.filter(
            no_results=True
        ).values('query').annotate(
            count=Count('id')
        ).order_by('-count')[:limit]

        # Click-through rate
        total_searches = analytics_queryset.count()
        total_clicks = analytics_queryset.exclude(clicked_result_id__isnull=True).count()
        click_through_rate = (total_clicks / total_searches * 100) if total_searches > 0 else 0.0

        # Format response
        response_data = {
            "popular_searches": list(popular_searches),
            "search_trends": list(search_trends),
            "no_result_queries": list(no_result_queries),
            "click_through_rate": round(click_through_rate, 2),
            "total_searches": total_searches,
            "total_clicks": total_clicks
        }

        serializer = SearchAnalyticsDashboardSerializer(response_data)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsAuditor])
    def rebuild_index(self, request: Request) -> Response:
        """
        Rebuild search index.

        POST /api/v1/search/rebuild_index

        Body (optional):
        {
            "tenant_id": "uuid"  # If not provided, rebuilds for all tenants
        }
        """
        tenant_id = request.data.get('tenant_id')

        # Rebuild index
        SearchIndexer.rebuild_index(tenant_id=tenant_id)

        return Response({'status': 'index rebuild started'})

