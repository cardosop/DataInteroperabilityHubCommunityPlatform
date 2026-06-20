"""
API Analytics Service

Service for API analytics and reporting.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import structlog
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import APIUsageMetric

logger = structlog.get_logger(__name__)


class APIAnalyticsService:
    """
    Service for API analytics and reporting.
    """

    @staticmethod
    def track_request(
        tenant_id: str,
        endpoint_path: str,
        method: str,
        status_code: int,
        latency_ms: float | None = None,
        user_id: str | None = None,
        request_size_bytes: int | None = None,
        response_size_bytes: int | None = None,
        api_version: str = "v1",
    ):
        """
        Track an API request.

        Args:
            tenant_id: Tenant UUID
            endpoint_path: API endpoint path
            method: HTTP method
            status_code: HTTP status code
            latency_ms: Request latency in milliseconds
            user_id: Optional user UUID
            request_size_bytes: Optional request size in bytes
            response_size_bytes: Optional response size in bytes
            api_version: API version (default: "v1")
        """
        try:
            from django.contrib.auth import get_user_model
            from django.db import connections

            from hub.apps.tenants.models import Tenant

            User = get_user_model()

            # Close any stale connections (e.g. after a long-running request
            # caused an idle-timeout) so the analytics write gets a fresh one.
            for conn in connections.all():
                conn.close_if_unusable_or_obsolete()

            tenant = Tenant.objects.get(id=tenant_id)
            user = User.objects.get(id=user_id) if user_id else None

            APIUsageMetric.objects.create(
                tenant=tenant,
                user=user,
                endpoint_path=endpoint_path,
                method=method,
                status_code=status_code,
                latency_ms=latency_ms,
                request_size_bytes=request_size_bytes,
                response_size_bytes=response_size_bytes,
                api_version=api_version,
            )
        except Exception as e:
            logger.warning(
                "api_analytics_tracking_failed", error=str(e), endpoint_path=endpoint_path
            )

    @staticmethod
    def get_endpoint_popularity(
        tenant_id: str | None = None,
        start_date: timezone.datetime | None = None,
        end_date: timezone.datetime | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Get most popular endpoints.

        Args:
            tenant_id: Optional tenant UUID filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of results

        Returns:
            List of endpoint popularity data
        """
        query = APIUsageMetric.objects.all()

        if tenant_id:
            query = query.filter(tenant_id=tenant_id)

        if start_date:
            query = query.filter(created_at__gte=start_date)

        if end_date:
            query = query.filter(created_at__lte=end_date)

        # Aggregate by endpoint
        results = (
            query.values("endpoint_path", "method")
            .annotate(
                request_count=Count("id"),
                avg_latency_ms=Avg("latency_ms"),
                error_count=Count("id", filter=Q(status_code__gte=400)),
                success_count=Count("id", filter=Q(status_code__lt=400)),
            )
            .order_by("-request_count")[:limit]
        )

        popularity = []
        for result in results:
            total = result["request_count"]
            errors = result["error_count"] or 0
            success = result["success_count"] or 0

            popularity.append(
                {
                    "endpoint": result["endpoint_path"],
                    "method": result["method"],
                    "request_count": total,
                    "avg_latency_ms": round(result["avg_latency_ms"] or 0.0, 2),
                    "error_count": errors,
                    "success_count": success,
                    "error_rate": round((errors / total * 100) if total > 0 else 0.0, 2),
                }
            )

        return popularity

    @staticmethod
    def get_usage_trends(
        tenant_id: str | None = None,
        start_date: timezone.datetime | None = None,
        end_date: timezone.datetime | None = None,
        granularity: str = "hour",
    ) -> list[dict[str, Any]]:
        """
        Get API usage trends over time.

        Args:
            tenant_id: Optional tenant UUID filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            granularity: "hour", "day", or "week"

        Returns:
            List of usage trend data
        """
        query = APIUsageMetric.objects.all()

        if tenant_id:
            query = query.filter(tenant_id=tenant_id)

        if start_date:
            query = query.filter(created_at__gte=start_date)

        if end_date:
            query = query.filter(created_at__lte=end_date)

        # Default to last 7 days if no dates provided
        if not start_date and not end_date:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=7)
            query = query.filter(created_at__gte=start_date, created_at__lte=end_date)

        # Aggregate by time period
        if granularity == "hour":
            # Truncate to hour
            from django.db.models.functions import TruncHour

            query = query.annotate(period=TruncHour("created_at"))
        elif granularity == "day":
            from django.db.models.functions import TruncDay

            query = query.annotate(period=TruncDay("created_at"))
        elif granularity == "week":
            from django.db.models.functions import TruncWeek

            query = query.annotate(period=TruncWeek("created_at"))
        else:
            from django.db.models.functions import TruncDay

            query = query.annotate(period=TruncDay("created_at"))

        results = (
            query.values("period")
            .annotate(
                request_count=Count("id"),
                avg_latency_ms=Avg("latency_ms"),
                error_count=Count("id", filter=Q(status_code__gte=400)),
            )
            .order_by("period")
        )

        trends = []
        for result in results:
            trends.append(
                {
                    "period": result["period"].isoformat() if result["period"] else None,
                    "request_count": result["request_count"],
                    "avg_latency_ms": round(result["avg_latency_ms"] or 0.0, 2),
                    "error_count": result["error_count"] or 0,
                }
            )

        return trends

    @staticmethod
    def get_performance_metrics(
        tenant_id: str | None = None,
        start_date: timezone.datetime | None = None,
        end_date: timezone.datetime | None = None,
    ) -> dict[str, Any]:
        """
        Get performance metrics summary.

        Args:
            tenant_id: Optional tenant UUID filter
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Dictionary with performance metrics
        """
        query = APIUsageMetric.objects.all()

        if tenant_id:
            query = query.filter(tenant_id=tenant_id)

        if start_date:
            query = query.filter(created_at__gte=start_date)

        if end_date:
            query = query.filter(created_at__lte=end_date)

        # Default to last 24 hours if no dates provided
        if not start_date and not end_date:
            end_date = timezone.now()
            start_date = end_date - timedelta(hours=24)
            query = query.filter(created_at__gte=start_date, created_at__lte=end_date)

        # Aggregate metrics
        total_requests = query.count()
        total_errors = query.filter(status_code__gte=400).count()
        avg_latency = query.aggregate(avg_latency=Avg("latency_ms"))["avg_latency"] or 0.0

        # P95 latency
        latencies = list(
            query.exclude(latency_ms__isnull=True).values_list("latency_ms", flat=True)
        )
        p95_latency = 0.0
        if latencies:
            latencies.sort()
            p95_index = int(len(latencies) * 0.95)
            p95_latency = latencies[p95_index] if p95_index < len(latencies) else latencies[-1]

        return {
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": round(
                (total_errors / total_requests * 100) if total_requests > 0 else 0.0, 2
            ),
            "avg_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": round(p95_latency, 2),
            "success_rate": round(
                ((total_requests - total_errors) / total_requests * 100)
                if total_requests > 0
                else 0.0,
                2,
            ),
        }

    @staticmethod
    def get_analytics_dashboard(
        tenant_id: str | None = None,
        start_date: timezone.datetime | None = None,
        end_date: timezone.datetime | None = None,
    ) -> dict[str, Any]:
        """
        Get complete analytics dashboard data.

        Args:
            tenant_id: Optional tenant UUID filter
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Dictionary with complete dashboard data
        """
        return {
            "popular_endpoints": APIAnalyticsService.get_endpoint_popularity(
                tenant_id=tenant_id, start_date=start_date, end_date=end_date, limit=20
            ),
            "usage_trends": APIAnalyticsService.get_usage_trends(
                tenant_id=tenant_id, start_date=start_date, end_date=end_date, granularity="day"
            ),
            "performance_metrics": APIAnalyticsService.get_performance_metrics(
                tenant_id=tenant_id, start_date=start_date, end_date=end_date
            ),
        }
