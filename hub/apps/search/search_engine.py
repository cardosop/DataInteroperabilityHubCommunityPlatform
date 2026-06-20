"""
Search Engine

Full-text search engine with relevance-based ranking and filtering.
"""

from datetime import timedelta
from typing import Any

import structlog
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.cache import cache
from django.db import models
from django.db.models import Case, F, FloatField, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import SearchAnalytics, SearchIndex

logger = structlog.get_logger(__name__)


class SearchEngine:
    """
    Full-text search engine with relevance-based ranking.
    """

    # Default ranking weights
    DEFAULT_WEIGHTS = {
        "name": 2.5,
        "description": 1.0,
        "quality": 0.5,
        "compliance": 0.5,
        "recency": 0.3,
    }

    @staticmethod
    def search(
        tenant_id: str,
        query: str,
        resource_type: str | None = None,
        classification: str | None = None,
        owner_id: str | None = None,
        tags: list[str] | None = None,
        domain: str | None = None,
        quality_status: str | None = None,
        compliance_status: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "relevance",
        sort_order: str = "desc",
        weights: dict[str, float] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Perform full-text search with filters and ranking.

        Args:
            tenant_id: Tenant UUID
            query: Search query string
            resource_type: Filter by resource type (CONTRACT, ASSET, DATASET)
            classification: Filter by classification
            owner_id: Filter by owner ID
            tags: Filter by tags (list)
            domain: Filter by domain
            quality_status: Filter by quality status
            compliance_status: Filter by compliance status
            limit: Results per page (default: 20, max: 100)
            offset: Pagination offset
            sort_by: Sort field (relevance, created_at, indexed_at)
            sort_order: Sort order (asc, desc)
            weights: Custom ranking weights

        Returns:
            Tuple of (results list, total count)
        """
        # Limit max results
        limit = min(limit, 100)

        # Build base queryset
        queryset = SearchIndex.objects.filter(tenant_id=tenant_id)

        # Apply filters
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)

        if classification:
            queryset = queryset.filter(classification=classification)

        if owner_id:
            queryset = queryset.filter(owner_id=owner_id)

        if tags:
            # Filter by tags (JSON array contains)
            for tag in tags:
                queryset = queryset.filter(tags__contains=[tag])

        if domain:
            queryset = queryset.filter(domain=domain)

        if quality_status:
            queryset = queryset.filter(quality_status=quality_status)

        if compliance_status:
            queryset = queryset.filter(compliance_status=compliance_status)

        # Full-text search
        if query:
            search_query = SearchQuery(query, config="english")
            search_vector = SearchVector("search_vector", config="english")

            # Add search rank
            queryset = queryset.annotate(rank=SearchRank(search_vector, search_query)).filter(
                search_vector=search_query
            )
        else:
            # No query, just return filtered results
            queryset = queryset.annotate(rank=Value(0.0, output_field=FloatField()))

        # Calculate relevance score with weights
        weights = weights or SearchEngine.DEFAULT_WEIGHTS

        # Base relevance from search rank
        queryset = queryset.annotate(
            relevance=Coalesce(F("rank"), Value(0.0, output_field=FloatField()))
        )

        # Apply quality boost
        quality_boost = Case(
            When(quality_status="PASS", then=Value(weights.get("quality", 0.5))),
            When(quality_status="WARN", then=Value(weights.get("quality", 0.5) * 0.5)),
            default=Value(0.0),
            output_field=FloatField(),
        )

        # Apply compliance boost
        compliance_boost = Case(
            When(compliance_status="PASS", then=Value(weights.get("compliance", 0.5))),
            When(compliance_status="WARN", then=Value(weights.get("compliance", 0.5) * 0.5)),
            default=Value(0.0),
            output_field=FloatField(),
        )

        # Apply recency boost (normalized by days since indexed)
        # Use date filtering instead of calculating days (can't use .days on F expressions)
        recency_boost = Case(
            When(
                indexed_at__gte=timezone.now() - timedelta(days=7),
                then=Value(weights.get("recency", 0.3)),
            ),
            When(
                indexed_at__gte=timezone.now() - timedelta(days=30),
                then=Value(weights.get("recency", 0.3) * 0.5),
            ),
            default=Value(0.0),
            output_field=FloatField(),
        )

        # Calculate final relevance
        queryset = queryset.annotate(
            final_relevance=F("relevance") + quality_boost + compliance_boost + recency_boost
        )

        # Sorting
        if sort_by == "relevance":
            if sort_order == "desc":
                queryset = queryset.order_by("-final_relevance", "-indexed_at")
            else:
                queryset = queryset.order_by("final_relevance", "indexed_at")
        elif sort_by == "created_at":
            if sort_order == "desc":
                queryset = queryset.order_by("-created_at")
            else:
                queryset = queryset.order_by("created_at")
        elif sort_by == "indexed_at":
            if sort_order == "desc":
                queryset = queryset.order_by("-indexed_at")
            else:
                queryset = queryset.order_by("indexed_at")
        else:
            # Default to relevance
            queryset = queryset.order_by("-final_relevance", "-indexed_at")

        # Optimize count query - use approximate count for large datasets
        # For exact count, we can optimize by avoiding the count if not needed
        # In production, consider using approximate counts for very large result sets
        total_count = queryset.count()

        # Pagination
        results = queryset[offset : offset + limit]

        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append(
                {
                    "id": str(result.resource_id),
                    "type": result.resource_type,
                    "title": result.title,
                    "description": result.description,
                    "relevance_score": (
                        float(result.final_relevance) if hasattr(result, "final_relevance") else 0.0
                    ),
                    "classification": result.classification,
                    "owner_id": str(result.owner_id) if result.owner_id else None,
                    "owner_email": result.owner_email,
                    "domain": result.domain,
                    "tags": result.tags or [],
                    "quality_status": result.quality_status,
                    "compliance_status": result.compliance_status,
                    "indexed_at": result.indexed_at.isoformat() if result.indexed_at else None,
                }
            )

        return formatted_results, total_count

    @staticmethod
    def get_suggestions(tenant_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get search suggestions based on partial query.

        Uses trigram similarity for fuzzy matching.

        Args:
            tenant_id: Tenant UUID
            query: Partial query string
            limit: Maximum number of suggestions (default: 10)

        Returns:
            List of suggestion dictionaries
        """
        if not query or len(query) < 2:
            return []

        # Check cache first
        cache_key = f"search_suggestions_{tenant_id}_{query.lower()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # Get suggestions from search index titles
        suggestions = []

        try:
            from django.contrib.postgres.search import TrigramSimilarity
            from django.db import transaction

            # Search in titles with trigram similarity (requires pg_trgm extension)
            # Use a savepoint to allow rollback if TrigramSimilarity fails
            with transaction.atomic():
                search_indices = (
                    SearchIndex.objects.filter(tenant_id=tenant_id)
                    .annotate(similarity=TrigramSimilarity("title", query))
                    .filter(similarity__gt=0.1)  # Minimum similarity threshold
                    .order_by("-similarity")[:limit]
                )

                # Evaluate queryset immediately to catch any errors
                indices_list = list(search_indices)

                for index in indices_list:
                    suggestions.append(
                        {
                            "text": index.title,
                            "type": index.resource_type,
                            "id": str(index.resource_id),
                            "similarity": (
                                float(index.similarity) if hasattr(index, "similarity") else 0.0
                            ),
                        }
                    )
        except Exception as e:
            # Fallback to simple icontains if trigram similarity is not available
            # Create a fresh queryset to avoid transaction state issues
            logger.warning(
                "TrigramSimilarity not available, using fallback", error=str(e), tenant_id=tenant_id
            )
            try:
                # Use a new transaction for the fallback query
                from django.db import transaction

                with transaction.atomic():
                    search_indices = SearchIndex.objects.filter(
                        tenant_id=tenant_id, title__icontains=query
                    )[:limit]
                    indices_list = list(search_indices)

                    for index in indices_list:
                        suggestions.append(
                            {
                                "text": index.title,
                                "type": index.resource_type,
                                "id": str(index.resource_id),
                                "similarity": 0.5,  # Default similarity for fallback
                            }
                        )
            except Exception as fallback_error:
                # If fallback also fails, log and return empty suggestions
                logger.error(
                    "Fallback search also failed",
                    error=str(fallback_error),
                    tenant_id=tenant_id,
                    exc_info=True,
                )
                return []

        # Also get suggestions from popular searches
        popular_searches = (
            SearchAnalytics.objects.filter(
                tenant_id=tenant_id, query__icontains=query, no_results=False
            )
            .values("query")
            .annotate(count=models.Count("id"))
            .order_by("-count")[:limit]
        )

        for search in popular_searches:
            search_query = search["query"]
            if search_query not in [s["text"] for s in suggestions]:
                suggestions.append(
                    {
                        "text": search_query,
                        "type": "QUERY",
                        "id": None,
                        "similarity": 0.5,  # Default similarity for popular searches
                    }
                )

        # Sort by similarity
        suggestions.sort(key=lambda x: x["similarity"], reverse=True)

        # Limit results
        suggestions = suggestions[:limit]

        # Cache for 5 minutes
        cache.set(cache_key, suggestions, 300)

        return suggestions

    @staticmethod
    def track_search(
        tenant_id: str,
        query: str,
        query_type: str = "SEARCH",
        filters: dict[str, Any] | None = None,
        result_count: int = 0,
        user_id: str | None = None,
        session_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SearchAnalytics:
        """Track a search query for analytics"""
        # Ensure analytics is created and saved properly
        # Use get_or_create pattern to avoid duplicates, but create new for each search
        analytics = SearchAnalytics.objects.create(
            tenant_id=tenant_id,
            user_id=user_id,
            query=query,
            query_type=query_type,
            filters=filters or {},
            result_count=result_count,
            no_results=(result_count == 0),
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Force save to ensure it's committed to database (important for tests)
        analytics.save()

        # Refresh from DB to ensure we have the latest data
        analytics.refresh_from_db()

        return analytics

    @staticmethod
    def track_click(analytics_id: str, result_id: str, result_type: str):
        """Track a click on a search result"""
        try:
            analytics = SearchAnalytics.objects.get(id=analytics_id)
            analytics.clicked_result_id = result_id
            analytics.clicked_result_type = result_type
            analytics.clicked_at = timezone.now()
            analytics.save()
        except SearchAnalytics.DoesNotExist:
            logger.warning(
                "Search analytics not found for click tracking", analytics_id=analytics_id
            )
            # Re-raise the exception so the view can handle it properly
            raise
