"""
API Analytics Views

REST API views for API analytics dashboard.
"""

from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from hub.apps.auth.permissions import HasAnyRole

from .analytics import APIAnalyticsService
from .cost_tracking import CostTrackingService


class APIAnalyticsViewSet(viewsets.ViewSet):
    """
    ViewSet for API analytics dashboard.
    """

    permission_classes = [permissions.IsAuthenticated]

    def _get_tenant_id(self, request):
        """Get tenant ID from request"""
        if hasattr(request, "tenant_id") and request.tenant_id:
            return str(request.tenant_id)

        tenant = getattr(request, "tenant", None)
        if tenant and hasattr(tenant, "id"):
            return str(tenant.id)

        return None

    @extend_schema(
        summary="Get API analytics dashboard",
        description="Get complete API analytics dashboard with popular endpoints, usage trends, and performance metrics",
        parameters=[
            OpenApiParameter(
                name="start_date",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Start date (ISO format)",
                required=False,
            ),
            OpenApiParameter(
                name="end_date",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="End date (ISO format)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Analytics dashboard data"),
        },
        tags=["API Analytics"],
    )
    @action(detail=False, methods=["get"], url_path="dashboard")
    def dashboard(self, request):
        """
        Get API analytics dashboard.

        GET /api/v1/analytics/api/dashboard/
        """
        tenant_id = self._get_tenant_id(request)

        # Parse date parameters
        start_date = None
        end_date = None

        if "start_date" in request.query_params:
            try:
                start_date = timezone.datetime.fromisoformat(
                    request.query_params["start_date"].replace("Z", "+00:00")
                )
            except ValueError:
                raise ValidationError("Invalid start_date format. Use ISO format.")

        if "end_date" in request.query_params:
            try:
                end_date = timezone.datetime.fromisoformat(
                    request.query_params["end_date"].replace("Z", "+00:00")
                )
            except ValueError:
                raise ValidationError("Invalid end_date format. Use ISO format.")

        dashboard_data = APIAnalyticsService.get_analytics_dashboard(
            tenant_id=tenant_id, start_date=start_date, end_date=end_date
        )

        return Response(dashboard_data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get popular endpoints",
        description="Get most popular API endpoints by request count",
        parameters=[
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum number of results (default: 20)",
                required=False,
            ),
            OpenApiParameter(
                name="start_date",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Start date (ISO format)",
                required=False,
            ),
            OpenApiParameter(
                name="end_date",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="End date (ISO format)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="List of popular endpoints"),
        },
        tags=["API Analytics"],
    )
    @action(detail=False, methods=["get"], url_path="popular-endpoints")
    def popular_endpoints(self, request):
        """
        Get popular endpoints.

        GET /api/v1/analytics/api/popular-endpoints/
        """
        tenant_id = self._get_tenant_id(request)
        limit = int(request.query_params.get("limit", 20))

        start_date = None
        end_date = None

        if "start_date" in request.query_params:
            try:
                start_date = timezone.datetime.fromisoformat(
                    request.query_params["start_date"].replace("Z", "+00:00")
                )
            except ValueError:
                raise ValidationError("Invalid start_date format. Use ISO format.")

        if "end_date" in request.query_params:
            try:
                end_date = timezone.datetime.fromisoformat(
                    request.query_params["end_date"].replace("Z", "+00:00")
                )
            except ValueError:
                raise ValidationError("Invalid end_date format. Use ISO format.")

        popularity = APIAnalyticsService.get_endpoint_popularity(
            tenant_id=tenant_id, start_date=start_date, end_date=end_date, limit=limit
        )

        return Response(popularity, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get usage trends",
        description="Get API usage trends over time",
        parameters=[
            OpenApiParameter(
                name="granularity",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Time granularity: hour, day, or week (default: day)",
                required=False,
            ),
            OpenApiParameter(
                name="start_date",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Start date (ISO format)",
                required=False,
            ),
            OpenApiParameter(
                name="end_date",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="End date (ISO format)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Usage trends data"),
        },
        tags=["API Analytics"],
    )
    @action(detail=False, methods=["get"], url_path="usage-trends")
    def usage_trends(self, request):
        """
        Get usage trends.

        GET /api/v1/analytics/api/usage-trends/
        """
        tenant_id = self._get_tenant_id(request)
        granularity = request.query_params.get("granularity", "day")

        start_date = None
        end_date = None

        if "start_date" in request.query_params:
            try:
                start_date = timezone.datetime.fromisoformat(
                    request.query_params["start_date"].replace("Z", "+00:00")
                )
            except ValueError:
                raise ValidationError("Invalid start_date format. Use ISO format.")

        if "end_date" in request.query_params:
            try:
                end_date = timezone.datetime.fromisoformat(
                    request.query_params["end_date"].replace("Z", "+00:00")
                )
            except ValueError:
                raise ValidationError("Invalid end_date format. Use ISO format.")

        trends = APIAnalyticsService.get_usage_trends(
            tenant_id=tenant_id, start_date=start_date, end_date=end_date, granularity=granularity
        )

        return Response(trends, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get performance metrics",
        description="Get API performance metrics summary",
        parameters=[
            OpenApiParameter(
                name="start_date",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Start date (ISO format)",
                required=False,
            ),
            OpenApiParameter(
                name="end_date",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="End date (ISO format)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Performance metrics data"),
        },
        tags=["API Analytics"],
    )
    @action(detail=False, methods=["get"], url_path="performance")
    def performance(self, request):
        """
        Get performance metrics.

        GET /api/v1/analytics/api/performance/
        """
        tenant_id = self._get_tenant_id(request)

        start_date = None
        end_date = None

        if "start_date" in request.query_params:
            try:
                start_date = timezone.datetime.fromisoformat(
                    request.query_params["start_date"].replace("Z", "+00:00")
                )
            except ValueError:
                raise ValidationError("Invalid start_date format. Use ISO format.")

        if "end_date" in request.query_params:
            try:
                end_date = timezone.datetime.fromisoformat(
                    request.query_params["end_date"].replace("Z", "+00:00")
                )
            except ValueError:
                raise ValidationError("Invalid end_date format. Use ISO format.")

        metrics = APIAnalyticsService.get_performance_metrics(
            tenant_id=tenant_id, start_date=start_date, end_date=end_date
        )

        return Response(metrics, status=status.HTTP_200_OK)


class CostsViewSet(viewsets.ViewSet):
    """
    ViewSet for cost tracking analytics (UC-TA-007).

    GET /api/v1/analytics/costs/
    Requires TENANT_ADMIN or PLATFORM_ADMIN (cost data is tenant-admin scope).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        return [
            permissions.IsAuthenticated(),
            HasAnyRole(["TENANT_ADMIN", "PLATFORM_ADMIN"]),
        ]

    def _get_tenant_id(self, request):
        if hasattr(request, "tenant_id") and request.tenant_id:
            return str(request.tenant_id)
        tenant = getattr(request, "tenant", None)
        if tenant and hasattr(tenant, "id"):
            return str(tenant.id)
        return None

    def _check_tenant(self, request):
        """Return 400 if tenant context required but missing."""
        tenant_id = self._get_tenant_id(request)
        if not tenant_id:
            raise ValidationError(
                {"detail": "Tenant context required. Use tenant-scoped authentication."}
            )
        return tenant_id

    def _parse_period(self, request):
        """Parse start_date and end_date from query params."""
        start_date = None
        end_date = None
        if "start_date" in request.query_params:
            try:
                start_date = timezone.datetime.fromisoformat(
                    request.query_params["start_date"].replace("Z", "+00:00")
                )
            except ValueError:
                raise ValidationError("Invalid start_date format. Use ISO format.")
        if "end_date" in request.query_params:
            try:
                end_date = timezone.datetime.fromisoformat(
                    request.query_params["end_date"].replace("Z", "+00:00")
                )
            except ValueError:
                raise ValidationError("Invalid end_date format. Use ISO format.")
        return start_date, end_date

    @extend_schema(
        summary="Get cost summary",
        description="Get cost tracking summary for tenant (usage → cost).",
        responses={200: OpenApiResponse(description="Cost summary")},
        tags=["Cost Tracking"],
    )
    def list(self, request):
        """Get cost tracking summary for tenant."""
        tenant_id = self._check_tenant(request)
        start_date, end_date = self._parse_period(request)
        result = CostTrackingService.get_cost_summary(
            tenant_id, period_start=start_date, period_end=end_date
        )
        return Response(result, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get cost breakdown",
        description="Get cost breakdown by category (storage, API, ingestion, export).",
        parameters=[
            OpenApiParameter("period", str, description="period (month)"),
            OpenApiParameter("start_date", OpenApiTypes.DATETIME),
            OpenApiParameter("end_date", OpenApiTypes.DATETIME),
        ],
        responses={200: OpenApiResponse(description="Cost breakdown")},
        tags=["Cost Tracking"],
    )
    @action(detail=False, methods=["get"], url_path="breakdown")
    def breakdown(self, request):
        """GET /api/v1/analytics/costs/breakdown/"""
        tenant_id = self._check_tenant(request)
        start_date, end_date = self._parse_period(request)
        result = CostTrackingService.get_cost_breakdown(
            tenant_id,
            period_start=start_date,
            period_end=end_date,
            period=request.query_params.get("period", "month"),
        )
        return Response(result, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get cost by asset",
        description="Get cost breakdown by asset (storage per asset).",
        parameters=[
            OpenApiParameter("start_date", OpenApiTypes.DATETIME),
            OpenApiParameter("end_date", OpenApiTypes.DATETIME),
        ],
        responses={200: OpenApiResponse(description="Cost by asset")},
        tags=["Cost Tracking"],
    )
    @action(detail=False, methods=["get"], url_path="by-asset")
    def by_asset(self, request):
        """GET /api/v1/analytics/costs/by-asset/"""
        tenant_id = self._check_tenant(request)
        start_date, end_date = self._parse_period(request)
        result = CostTrackingService.get_cost_by_asset(
            tenant_id, period_start=start_date, period_end=end_date
        )
        return Response(result, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get cost recommendations",
        description="Get cost optimization recommendations.",
        responses={200: OpenApiResponse(description="Recommendations")},
        tags=["Cost Tracking"],
    )
    @action(detail=False, methods=["get"], url_path="recommendations")
    def recommendations(self, request):
        """GET /api/v1/analytics/costs/recommendations/"""
        tenant_id = self._check_tenant(request)
        result = CostTrackingService.get_cost_recommendations(tenant_id)
        return Response(result, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get cost trends",
        description="Get cost trends over time.",
        parameters=[
            OpenApiParameter("period", str),
            OpenApiParameter(
                "months", OpenApiTypes.INT, description="Number of months (default 6)"
            ),
        ],
        responses={200: OpenApiResponse(description="Cost trends")},
        tags=["Cost Tracking"],
    )
    @action(detail=False, methods=["get"], url_path="trends")
    def trends(self, request):
        """GET /api/v1/analytics/costs/trends/"""
        tenant_id = self._check_tenant(request)
        try:
            months = int(request.query_params.get("months", 6))
        except (TypeError, ValueError):
            months = 6
        result = CostTrackingService.get_cost_trends(
            tenant_id,
            period=request.query_params.get("period", "month"),
            months=min(max(months, 1), 24),
        )
        return Response(result, status=status.HTTP_200_OK)
