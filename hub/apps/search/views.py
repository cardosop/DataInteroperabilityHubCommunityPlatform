"""
Search API Views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import models as db_models, transaction
from django.utils import timezone

from hub.apps.api.standards.pagination import StandardPageNumberPagination

from .models import SearchIndex, SearchAnalytics
from .search_engine import SearchEngine
from .services import SearchService
from .serializers import (
    SearchResponseSerializer,
    SearchSuggestionSerializer,
    SearchAnalyticsSerializer,
    SearchAnalyticsDashboardSerializer
)
from .indexing import SearchIndexer
from hub.apps.auth.permissions import HasRole

# Auditor permission - users with AUDITOR role
class IsAuditor(HasRole):
    def __init__(self):
        super().__init__('AUDITOR')


class SearchViewSet(viewsets.ViewSet):
    """
    Search API endpoints (DEPRECATED — Phase 54.1).

    Use /api/search/ (UnifiedSearchView) instead.
    This viewset returns Deprecation headers and will be removed after 30 days.
    """
    permission_classes = [IsAuthenticated]

    def finalize_response(self, request, response, *args, **kwargs):
        """Add deprecation headers to all responses (Phase 54.1)."""
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Deprecation"] = "true"
        response["Link"] = '</api/search/>; rel="successor-version"'
        return response

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

        query = request.query_params.get('q', '').strip()

        if not query:
            return Response(
                {"error": "q parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Phase 53: guard against arbitrarily long queries
        from django.conf import settings as _settings
        max_len = getattr(_settings, "MAX_SEARCH_QUERY_LENGTH", 512)
        if query and len(query) > max_len:
            return Response(
                {"error": "QUERY_TOO_LONG", "max_length": max_len},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get filters
        resource_type = request.query_params.get('type')
        classification = request.query_params.get('classification')
        owner_id = request.query_params.get('owner')
        tags_str = request.query_params.get('tags')
        max_tags = getattr(_settings, "MAX_SEARCH_TAGS", 50)
        tags = tags_str.split(',')[:max_tags] if tags_str else None
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

        # Check cache for search results (hash-based key to avoid
        # memcached-unsafe characters like spaces and colons).
        import hashlib
        from django.core.cache import cache
        cache_key_parts = [
            str(tenant.id),
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
            sort_order,
        ]
        raw_key = "|".join(cache_key_parts)
        key_hash = hashlib.md5(raw_key.encode()).hexdigest()
        cache_key = f"search_{key_hash}"
        cached_results = cache.get(cache_key)

        if cached_results is not None:
            results, total = cached_results
        else:
            # Perform search using SearchService (which publishes events)
            search_service = SearchService(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id) if request.user.is_authenticated else None
            )
            results, total = search_service.search(
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
                sort_order=sort_order,
                user_id=str(request.user.id) if request.user.is_authenticated else None
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

        # Track suggestion query (handle session gracefully for tests)
        try:
            SearchEngine.track_search(
                tenant_id=str(tenant.id),
                query=query,
                query_type="SUGGESTION",
                result_count=len(suggestions),
                user_id=str(request.user.id) if request.user.is_authenticated else None,
                session_id=request.session.session_key if hasattr(request, 'session') and hasattr(request.session, 'session_key') else None,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
        except Exception as e:
            # Log error but don't fail the request if tracking fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to track suggestion query: {e}", exc_info=True)

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

        try:
            SearchEngine.track_click(analytics_id, result_id, result_type)
            return Response({'status': 'click tracked'})
        except Exception as e:
            # Return 400 if analytics not found, 500 for other errors
            from hub.apps.search.models import SearchAnalytics
            try:
                SearchAnalytics.objects.get(id=analytics_id)
                # Analytics exists but track_click failed for another reason
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to track click: {e}", exc_info=True)
                return Response(
                    {'error': 'Failed to track click'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            except SearchAnalytics.DoesNotExist:
                return Response(
                    {'error': f'Analytics not found: {analytics_id}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

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

        # Rebuild index using SearchService (which publishes events)
        search_service = SearchService(
            tenant_id=tenant_id,
            user_id=str(request.user.id) if request.user.is_authenticated else None
        )
        result = search_service.rebuild_index(
            tenant_id=tenant_id,
            user_id=str(request.user.id) if request.user.is_authenticated else None
        )

        return Response({
            'status': 'index rebuild started',
            'resource_count': result.get('resource_count', 0),
            'duration_ms': result.get('duration_ms', 0),
            'success': result.get('success', True),
            'resource_types': result.get('resource_types', [])
        })


# ---------------------------------------------------------------------------
# Phase 18.3 — /api/search/ unified full-text search
# ---------------------------------------------------------------------------

class UnifiedSearchView(APIView):
    """
    GET /api/search/?q=<term>&types=assets,contracts

    Queries Asset and Contract models directly via their PostgreSQL
    search_vector fields (Phase 18.2).  Results are ranked by ts_rank and
    scoped to the authenticated user's tenant.

    Query parameters
    ----------------
    q      : search term (required)
    types  : comma-separated subset of ``assets``, ``contracts``
             (default: both)
    page   : page number (StandardPageNumberPagination, page_size=50)

    Response schema (per item)
    --------------------------
    {
        "type":  "asset" | "contract",
        "id":    "<uuid>",
        "name":  "<string>",
        "rank":  <float>
    }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from hub.apps.assets.models import Asset
        from hub.apps.contracts.models import Contract
        from hub.apps.tenants.models import Tenant

        # ── resolve tenant ──────────────────────────────────────────────
        tenant = getattr(request.user, "tenant", None)
        if tenant is None:
            tenant_id = getattr(request.user, "tenant_id", None)
            if tenant_id:
                try:
                    tenant = Tenant.objects.get(id=tenant_id)
                except Tenant.DoesNotExist:
                    pass
        if tenant is None:
            return Response(
                {"error": "User must belong to a tenant"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        q = request.query_params.get("q", "").strip()

        if not q:
            return Response(
                {"error": "q parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Phase 53: guard against arbitrarily long queries
        from django.conf import settings as _settings
        max_len = getattr(_settings, "MAX_SEARCH_QUERY_LENGTH", 512)
        if q and len(q) > max_len:
            return Response(
                {"error": "QUERY_TOO_LONG", "max_length": max_len},
                status=status.HTTP_400_BAD_REQUEST,
            )

        types_raw = request.query_params.get("types", "assets,contracts")
        requested_types = {
            t.strip().lower() for t in types_raw.split(",") if t.strip()
        }

        search_query = SearchQuery(q, search_type="websearch")

        results = []

        # ── assets ───────────────────────────────────────────────────────
        if "assets" in requested_types:
            asset_qs = (
                Asset.objects.filter(
                    tenant=tenant,
                    search_vector__isnull=False,
                )
                .filter(search_vector=search_query)
                .annotate(
                    rank=SearchRank(
                        db_models.F("search_vector"), search_query
                    )
                )
                .order_by("-rank")
                .values("id", "name", "rank")
            )
            for row in asset_qs:
                results.append(
                    {
                        "type": "asset",
                        "id": str(row["id"]),
                        "name": row["name"],
                        "rank": float(row["rank"]),
                    }
                )

        # ── contracts ────────────────────────────────────────────────────
        if "contracts" in requested_types:
            # Contracts don't have a `name` field; use original_spec_type
            # as the display label.
            contract_qs = (
                Contract.objects.filter(
                    tenant=tenant,
                    search_vector__isnull=False,
                )
                .filter(search_vector=search_query)
                .annotate(
                    rank=SearchRank(
                        db_models.F("search_vector"), search_query
                    )
                )
                .order_by("-rank")
                .values("id", "original_spec_type", "rank")
            )
            for row in contract_qs:
                results.append(
                    {
                        "type": "contract",
                        "id": str(row["id"]),
                        "name": row["original_spec_type"],
                        "rank": float(row["rank"]),
                    }
                )

        # ── sort merged results by rank desc ─────────────────────────────
        results.sort(key=lambda r: r["rank"], reverse=True)

        # ── analytics tracking (Phase 54.2) ──────────────────────────────
        try:
            SearchEngine.track_search(
                tenant_id=str(tenant.id),
                query=q,
                query_type="SEARCH",
                filters={"types": list(requested_types)},
                result_count=len(results),
                user_id=str(request.user.id) if request.user.is_authenticated else None,
                session_id=getattr(getattr(request, "session", None), "session_key", None),
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT"),
            )
        except Exception:
            pass  # analytics must not break search

        # ── paginate ─────────────────────────────────────────────────────
        paginator = StandardPageNumberPagination()
        page = paginator.paginate_queryset(results, request)
        if page is not None:
            return paginator.get_paginated_response(page)
        return Response(results)

