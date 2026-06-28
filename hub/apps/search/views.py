"""
Search API Views
"""

import contextlib
from typing import Any, cast

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import models as db_models
from django.http import HttpRequest
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from hub.apps.api.standards.pagination import StandardPageNumberPagination
from hub.apps.auth.permissions import HasRole
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.observability.cross_tenant_metrics import cross_tenant_denied
from hub.apps.search.throttles import SearchUserThrottle
from hub.apps.tenants.request_tenant import get_request_tenant_id

from .models import SearchAnalytics
from .search_engine import SearchEngine
from .serializers import (
    SearchAnalyticsDashboardSerializer,
    SearchResponseSerializer,
    SearchSuggestionSerializer,
)
from .services import SearchService


# Auditor permission - users with AUDITOR role
class IsAuditor(HasRole):
    def __init__(self):
        super().__init__("AUDITOR")


class SearchViewSet(viewsets.ViewSet):
    """
    Search API endpoints (DEPRECATED — Phase 54.1).

    Use /api/search/ (UnifiedSearchView) instead.
    This viewset returns Deprecation headers and will be removed after 30 days.
    """

    # Phase 273.2 — rate-limit search/suggestions per tenant.
    throttle_classes = [SearchUserThrottle]
    permission_classes = [IsAuthenticated]

    def finalize_response(self, request, response, *args, **kwargs):
        """Phase 54.1 + 273.1.8 — RFC 8594 deprecation headers.

        The legacy ViewSet will be removed after a 90-day sunset window
        (2026-05-12 + 90 days = 2026-08-10). Clients MUST migrate to
        the canonical ``/api/search/`` (UnifiedSearchView).
        """
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Deprecation"] = "true"
        response["Sunset"] = "Mon, 10 Aug 2026 00:00:00 GMT"
        response["Link"] = '</api/search/>; rel="successor-version"'
        response["Deprecation-Date"] = "Mon, 12 May 2026 00:00:00 GMT"
        return response

    @action(detail=False, methods=["get"])
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

        if hasattr(request.user, "tenant_id"):
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

        if not tenant and hasattr(request.user, "tenant") and request.user.tenant:
            tenant = request.user.tenant

        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to perform searches"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        query = request.query_params.get("q", "").strip()

        # Phase 53: guard against arbitrarily long queries
        from django.conf import settings as _settings

        max_len = getattr(_settings, "MAX_SEARCH_QUERY_LENGTH", 512)
        if query and len(query) > max_len:
            return Response(
                {"error": "QUERY_TOO_LONG", "max_length": max_len},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get filters
        resource_type = request.query_params.get("type")
        classification = request.query_params.get("classification")
        owner_id = request.query_params.get("owner")
        tags_str = request.query_params.get("tags")
        max_tags = getattr(_settings, "MAX_SEARCH_TAGS", 50)
        tags = tags_str.split(",")[:max_tags] if tags_str else None
        domain = request.query_params.get("domain")
        quality_status = request.query_params.get("quality_status")
        compliance_status = request.query_params.get("compliance_status")

        # Get pagination
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))

        # Validate pagination parameters
        if limit < 1:
            return Response(
                {"error": "limit must be greater than 0"}, status=status.HTTP_400_BAD_REQUEST
            )
        limit = min(limit, 100)  # Cap at maximum
        offset = max(offset, 0)  # Clamp negative offset to 0

        # Get sorting
        sort_by = request.query_params.get("sort_by", "relevance")
        sort_order = request.query_params.get("sort_order", "desc")

        # Check cache for search results (hash-based key to avoid
        # memcached-unsafe characters like spaces and colons).
        import hashlib

        from django.core.cache import cache

        # Phase 230.11 — read the semantic flag here so it can
        # contribute to the cache key (different responses for
        # ?semantic=true vs the legacy path).
        _semantic_for_cache = request.query_params.get("semantic", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
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
            "sem=1" if _semantic_for_cache else "sem=0",
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
                user_id=str(request.user.id) if request.user.is_authenticated else None,
            )
            try:
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
                    user_id=str(request.user.id) if request.user.is_authenticated else None,
                )
            except ServiceValidationError as e:
                return Response(
                    {"error": e.message, "code": e.code},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Phase 230.11 (REQ-SEM-SEARCH-EXPAND-001) — when the
            # request opts into semantic expansion AND the tenant has
            # the per-tenant flag enabled, run the expansion module
            # for each bridge term, dedupe by (id, type), apply the
            # 0.5× rank multiplier, and tag expansion-only matches
            # with matched_via=ontology + bridge_term.  Both flags
            # required → defence-in-depth (a tenant cannot opt itself
            # in via the URL alone).
            semantic_param = request.query_params.get("semantic", "").strip().lower() in (
                "1",
                "true",
                "yes",
            )
            tenant_semantic_enabled = bool(
                getattr(tenant, "semantic_search_enabled", False),
            )
            if semantic_param and tenant_semantic_enabled:
                try:
                    from .semantic_query_expansion import expand_query_terms

                    bridges = expand_query_terms(
                        query=query,
                        tenant_id=str(tenant.id),
                    )
                except Exception as _e:
                    import logging as _l

                    _l.getLogger(__name__).warning(
                        "search_semantic_expansion_failed tenant=%s error=%s",
                        tenant.id,
                        _e,
                    )
                    bridges = []

                if bridges:
                    seen_keys = {(r.get("type"), str(r.get("id"))) for r in results}
                    for bridge in bridges:
                        try:
                            bridge_results, _bridge_total = search_service.search(
                                tenant_id=str(tenant.id),
                                query=bridge.label,
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
                                user_id=str(request.user.id)
                                if request.user.is_authenticated
                                else None,
                            )
                        except Exception as _e:
                            import logging as _l

                            _l.getLogger(__name__).warning(
                                "search_semantic_bridge_query_failed bridge=%r error=%s",
                                bridge.label,
                                _e,
                            )
                            continue
                        for row in bridge_results:
                            key = (row.get("type"), str(row.get("id")))
                            if key in seen_keys:
                                # Exact match wins — keep the higher
                                # original rank, never relabel.
                                continue
                            row["relevance_score"] = float(row.get("relevance_score", 0.0)) * 0.5
                            row["matched_via"] = "ontology"
                            row["bridge_term"] = bridge.label
                            row["bridge_relation"] = bridge.relation
                            results.append(row)
                            seen_keys.add(key)
                    # Re-sort merged list — exact + expansion together —
                    # by relevance descending so the bridge multiplier
                    # bumps expansion matches below exact ones.
                    results.sort(
                        key=lambda r: float(r.get("relevance_score", 0.0)),
                        reverse=True,
                    )
                    total = len(results)

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
                session_id=request.session.session_key if hasattr(request, "session") else None,
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT"),
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

    @action(detail=False, methods=["get"])
    def suggestions(self, request: Request) -> Response:
        """
        Get search suggestions (autocomplete).

        GET /api/v1/search/suggestions?q={partial_query}

        Query Parameters:
        - q: Partial query string (required, min 2 characters)
        - limit: Maximum number of suggestions (default: 10)
        """
        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to get suggestions"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get query
        query = request.query_params.get("q", "").strip()

        if len(query) < 2:
            return Response(
                {"error": "Query must be at least 2 characters"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Get limit
        limit = int(request.query_params.get("limit", 10))

        # Get suggestions
        suggestions = SearchEngine.get_suggestions(
            tenant_id=str(tenant.id), query=query, limit=limit
        )

        # Track suggestion query (handle session gracefully for tests)
        try:
            SearchEngine.track_search(
                tenant_id=str(tenant.id),
                query=query,
                query_type="SUGGESTION",
                result_count=len(suggestions),
                user_id=str(request.user.id) if request.user.is_authenticated else None,
                session_id=request.session.session_key
                if hasattr(request, "session") and hasattr(request.session, "session_key")
                else None,
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT"),
            )
        except Exception as e:
            # Log error but don't fail the request if tracking fails
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to track suggestion query: {e}", exc_info=True)

        serializer = SearchSuggestionSerializer(suggestions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
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
        request_data = cast("dict[str, Any]", request.data)
        analytics_id_raw = request_data.get("analytics_id")
        result_id_raw = request_data.get("result_id")
        result_type_raw = request_data.get("result_type")

        if not all([analytics_id_raw, result_id_raw, result_type_raw]):
            return Response(
                {"error": "analytics_id, result_id, and result_type are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        analytics_id = str(analytics_id_raw)
        result_id = str(result_id_raw)
        result_type = str(result_type_raw)

        try:
            SearchEngine.track_click(analytics_id, result_id, result_type)
            return Response({"status": "click tracked"})
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
                    {"error": "Failed to track click"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            except SearchAnalytics.DoesNotExist:
                return Response(
                    {"error": f"Analytics not found: {analytics_id}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated, IsAuditor])
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
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to view analytics"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get date range
        from datetime import timedelta

        from django.utils.dateparse import parse_datetime

        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)

        start_date_str = request.query_params.get("start_date")
        if start_date_str:
            parsed = parse_datetime(start_date_str)
            if parsed:
                start_date = parsed

        end_date_str = request.query_params.get("end_date")
        if end_date_str:
            parsed = parse_datetime(end_date_str)
            if parsed:
                end_date = parsed

        # Get limit
        limit = int(request.query_params.get("limit", 10))

        # Get analytics
        analytics_queryset = SearchAnalytics.objects.filter(
            tenant=tenant, created_at__gte=start_date, created_at__lte=end_date
        )

        # Popular searches
        from django.db.models import Count

        popular_searches = (
            analytics_queryset.filter(no_results=False)
            .values("query")
            .annotate(count=Count("id"))
            .order_by("-count")[:limit]
        )

        # Search trends (by day)
        search_trends = (
            analytics_queryset.extra(select={"day": "DATE(created_at)"})
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        # No-result queries
        no_result_queries = (
            analytics_queryset.filter(no_results=True)
            .values("query")
            .annotate(count=Count("id"))
            .order_by("-count")[:limit]
        )

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
            "total_clicks": total_clicks,
        }

        serializer = SearchAnalyticsDashboardSerializer(response_data)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, IsAuditor])
    def rebuild_index(self, request: Request) -> Response:
        """
        Rebuild search index.

        POST /api/v1/search/rebuild_index

        Body (optional):
        {
            "tenant_id": "uuid"  # Deprecated: server derives tenant from request context
        }
        """
        request_data = cast("dict[str, Any]", request.data)
        tenant_id = get_request_tenant_id(cast("HttpRequest", request))
        body_tenant_id = request_data.get("tenant_id")
        if body_tenant_id is not None and str(body_tenant_id).strip():
            if str(body_tenant_id) != str(tenant_id):
                cross_tenant_denied(
                    endpoint="search.rebuild_index",
                    reason="body_tenant_mismatch",
                    request=cast("HttpRequest", request),
                    requested_tenant_id=body_tenant_id,
                    actual_tenant_id=tenant_id,
                )
                return Response(
                    {
                        "code": "CROSS_TENANT_FORBIDDEN",
                        "detail": "tenant_id must not be set in request body",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        if not tenant_id:
            return Response(
                {"error": "tenant_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Rebuild index using SearchService (which publishes events)
        search_service = SearchService(
            tenant_id=tenant_id,
            user_id=str(request.user.id) if request.user.is_authenticated else None,
        )
        result = search_service.rebuild_index(
            tenant_id=tenant_id,
            user_id=str(request.user.id) if request.user.is_authenticated else None,
        )

        return Response(
            {
                "status": "index rebuild started",
                "resource_count": result.get("resource_count", 0),
                "duration_ms": result.get("duration_ms", 0),
                "success": result.get("success", True),
                "resource_types": result.get("resource_types", []),
            }
        )


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

    # Phase 273.2 — rate-limit the canonical search endpoint.
    throttle_classes = [SearchUserThrottle]
    permission_classes = [IsAuthenticated]

    def throttled(self, request, wait):
        """Dispatch to each throttle's ``throttled()`` if it exists.

        DRF 3.16 ``check_throttles`` only calls the *view's* ``throttled``,
        not each throttle's.  We forward the call so that
        ``_AuditableThrottle.throttled()`` can emit rate-limit audit
        events, metrics, and ``RateLimit-*`` response headers on 429.
        """
        for throttle in self.get_throttles():
            throttled_method = getattr(throttle, "throttled", None)
            if throttled_method is not None:
                with contextlib.suppress(Exception):
                    throttled_method(request, wait)
        super().throttled(request, wait)

    @staticmethod
    def _fts_query(
        *,
        tenant,
        term: str,
        requested_types: set,
        rank_multiplier: float,
        bridge_term,
    ) -> list:
        """Run the existing tenant-scoped FTS for a single term and
        return the standard result rows.

        Factored out so the Phase 230.11 expansion path can call the
        same query for the original query and for each ontology
        bridge term, applying a 0.5× rank multiplier on the latter
        (REQ-SEM-SEARCH-EXPAND-001 ranking contract).

        ``bridge_term`` is unused inside this helper but the caller
        passes it through so the merging logic can attach it to each
        row.
        """
        from hub.apps.assets.models import Asset
        from hub.apps.contracts.models import Contract

        if not term:
            return []

        sq = SearchQuery(term, search_type="websearch")
        out = []

        if "assets" in requested_types:
            for row in (
                Asset.objects.filter(
                    tenant=tenant,
                    search_vector__isnull=False,
                )
                .filter(search_vector=sq)
                .annotate(rank=SearchRank(db_models.F("search_vector"), sq))
                .order_by("-rank")
                .values("id", "name", "rank")
            ):
                out.append(
                    {
                        "type": "asset",
                        "id": str(row["id"]),
                        "name": row["name"],
                        "rank": float(row["rank"]) * rank_multiplier,
                    }
                )

        if "contracts" in requested_types:
            for row in (
                Contract.objects.filter(
                    tenant=tenant,
                    search_vector__isnull=False,
                )
                .filter(search_vector=sq)
                .annotate(rank=SearchRank(db_models.F("search_vector"), sq))
                .order_by("-rank")
                .values("id", "original_spec_type", "rank")
            ):
                out.append(
                    {
                        "type": "contract",
                        "id": str(row["id"]),
                        "name": row["original_spec_type"],
                        "rank": float(row["rank"]) * rank_multiplier,
                    }
                )

        return out

    def get(self, request: Request) -> Response:
        from hub.apps.tenants.models import Tenant

        # ── resolve tenant ──────────────────────────────────────────────
        tenant = getattr(request.user, "tenant", None)
        if tenant is None:
            tenant_id = getattr(request.user, "tenant_id", None)
            if tenant_id:
                with contextlib.suppress(Tenant.DoesNotExist):
                    tenant = Tenant.objects.get(id=tenant_id)
        if tenant is None:
            from hub.apps.api.standards.response_formats import format_error_response

            return format_error_response(
                error_code="TENANT_REQUIRED",
                message="User must belong to a tenant to perform searches.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        q = request.query_params.get("q", "").strip()

        # Reject NUL bytes early — they cannot appear in PostgreSQL string
        # literals and would cause a ValueError at the cursor level (500).
        # Returning 400 here matches the "input rejected" contract that
        # test_null_byte_rejected expects.
        if "\x00" in q:
            from hub.apps.api.standards.response_formats import format_error_response

            return format_error_response(
                error_code="INVALID_INPUT",
                message="Query contains invalid characters.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        # Phase 53: guard against arbitrarily long queries.
        from django.conf import settings as _settings

        max_len = getattr(_settings, "MAX_SEARCH_QUERY_LENGTH", 512)
        if q and len(q) > max_len:
            from hub.apps.api.standards.response_formats import format_error_response

            return format_error_response(
                error_code="QUERY_TOO_LONG",
                message=f"Query exceeds maximum length of {max_len} characters.",
                http_status=status.HTTP_400_BAD_REQUEST,
                details={"max_length": max_len},
            )

        types_raw = request.query_params.get("types", "assets,contracts")
        requested_types = {t.strip().lower() for t in types_raw.split(",") if t.strip()}

        # Phase 230.11 (REQ-SEM-SEARCH-EXPAND-001) — ontology-aware
        # query expansion is gated by BOTH the request-side
        # ?semantic=true flag AND the per-tenant
        # ``semantic_search_enabled`` flag.  Either off → expansion is
        # skipped entirely (legacy search semantics preserved).
        semantic_param = request.query_params.get("semantic", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        tenant_semantic_enabled = bool(
            getattr(tenant, "semantic_search_enabled", False),
        )
        semantic_active = semantic_param and tenant_semantic_enabled

        bridges = []  # list of ExpansionBridge — populated only when active
        if semantic_active:
            try:
                from hub.apps.search.semantic_query_expansion import (
                    expand_query_terms,
                )

                bridges = expand_query_terms(
                    query=q,
                    tenant_id=str(tenant.id),
                )
            except Exception as exc:
                # is an enhancement, never a blocker.
                import logging

                logging.getLogger(__name__).warning(
                    "semantic_expansion_failed tenant=%s error=%s",
                    tenant.id,
                    exc,
                )
                bridges = []

        results = self._fts_query(
            tenant=tenant,
            term=q,
            requested_types=requested_types,
            rank_multiplier=1.0,
            bridge_term=None,
        )

        # Phase 230.11 — for each ontology bridge, run the same FTS
        # against the asset/contract index, then merge while:
        # (a) tagging expansion-only matches with matched_via=ontology,
        # (b) applying a 0.5× rank multiplier (exact > expanded), and
        # (c) deduping by (type, id) — exact match wins on collision.
        if bridges:
            seen = {(r["type"], r["id"]) for r in results}
            for bridge in bridges:
                bridge_rows = self._fts_query(
                    tenant=tenant,
                    term=bridge.label,
                    requested_types=requested_types,
                    rank_multiplier=0.5,
                    bridge_term=bridge.label,
                )
                for row in bridge_rows:
                    key = (row["type"], row["id"])
                    if key in seen:
                        # Already matched the exact term; keep the
                        # higher-ranked exact match unmodified.
                        continue
                    row["matched_via"] = "ontology"
                    row["bridge_term"] = bridge.label
                    row["bridge_relation"] = bridge.relation
                    results.append(row)
                    seen.add(key)

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

        # ── Phase 273.3 — audit every search execution ──────────────────
        try:
            from hub.apps.audit.event_types import SEARCH_PERFORMED
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type="SEARCH_QUERY",
                action=SEARCH_PERFORMED,
                actor_user=request.user,
                tenant=tenant,
                resource_id=None,
                result="SUCCESS",
                details={
                    "query_truncated": q[:256],
                    "types": ",".join(sorted(requested_types)) if requested_types else "",
                    "result_count": len(results),
                    "tenant_id": str(tenant.id),
                },
            )
        except Exception:
            pass  # audit-DB outage MUST NOT block search response

        # ── Phase 273.4 — OTel metrics on search hot path ─────────────
        try:
            from hub.apps.search.metrics import record_search

            record_search(
                kind="fts",
                outcome="empty" if len(results) == 0 else "success",
                duration_s=0.0,  # instrumented by OTel middleware
                result_count=len(results),
                query_length=len(q.encode("utf-8")),
            )
        except Exception:
            pass  # metric-backend outage MUST NOT block search response

        # ── paginate ─────────────────────────────────────────────────────
        paginator = StandardPageNumberPagination()
        page = paginator.paginate_queryset(results, request)
        if page is not None:
            return paginator.get_paginated_response(page)
        return Response(results)
