"""
Observability API Views

API endpoints for data freshness monitoring, volume monitoring, and schema drift detection.
"""

import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from hub.apps.assets.models import Asset
from hub.apps.contracts.lineage_service import LineageService
from hub.apps.core.services.base import NotFoundError
from hub.apps.datasets.models import Dataset

from .freshness import FreshnessMonitor
from .schema_drift import SchemaDriftDetector
from .serializers import (
    FreshnessDashboardSerializer,
    SchemaDriftDashboardSerializer,
    VolumeDashboardSerializer,
)
from .services import ObservabilityService
from .volume import VolumeMonitor


class ObservabilityViewSet(viewsets.ViewSet):
    """
    Observability API endpoints.

    Provides data freshness monitoring, volume monitoring, and schema drift detection.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Get freshness dashboard",
        description="""
        Get data freshness dashboard with metrics and statistics.

        **Query Parameters:**
        - `dataset_id`: Optional dataset UUID filter
        - `asset_id`: Optional asset UUID filter
        - `limit`: Maximum number of records (default: 100)
        """,
        parameters=[
            OpenApiParameter(
                name="dataset_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Dataset UUID filter",
                required=False,
            ),
            OpenApiParameter(
                name="asset_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Asset UUID filter",
                required=False,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum number of records (default: 100)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Freshness dashboard data"),
        },
        tags=["Observability", "Freshness"],
    )
    @action(detail=False, methods=["get"], url_path="freshness")
    def get_freshness_dashboard(self, request: Request) -> Response:
        """
        Get data freshness dashboard.

        GET /api/v1/observability/freshness?dataset_id={id}&limit=100
        """
        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to view observability data"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get parameters
        dataset_id = request.query_params.get("dataset_id")
        asset_id = request.query_params.get("asset_id")
        limit = int(request.query_params.get("limit", 100))

        # Use ObservabilityService to get dashboard data (includes event publishing)
        service = ObservabilityService(
            tenant_id=str(tenant.id),
            user_id=str(request.user.id) if request.user.is_authenticated else None,
        )
        dashboard_data = service.get_freshness_dashboard(
            tenant_id=str(tenant.id), dataset_id=dataset_id, asset_id=asset_id, limit=limit
        )

        serializer = FreshnessDashboardSerializer(dashboard_data)
        return Response(serializer.data)

    @extend_schema(
        summary="Get lineage",
        description="""
        Get contract-level lineage (delegates to contract lineage service).

        **Query Parameters:**
        - `contract_id` (required): Contract UUID to retrieve lineage for.
        """,
        parameters=[
            OpenApiParameter(
                name="contract_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Contract UUID to get lineage for",
                required=True,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Lineage data with contracts and entries"),
            400: OpenApiResponse(description="Missing contract_id or user has no tenant"),
            404: OpenApiResponse(description="Contract not found or not accessible"),
        },
        tags=["Observability", "Lineage"],
    )
    @action(detail=False, methods=["get"], url_path="lineage")
    def get_lineage(self, request: Request) -> Response:
        """
        Get contract-level lineage.

        GET /api/v1/observability/lineage/?contract_id={uuid}

        Delegates to LineageService (contract lineage); enforces tenant isolation.
        """
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to view observability data"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        contract_id = request.query_params.get("contract_id")
        if not contract_id:
            return Response(
                {"error": "contract_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        contract_id = contract_id.strip()
        try:
            uuid.UUID(contract_id)
        except (ValueError, TypeError, AttributeError):
            return Response(
                {
                    "error": "Invalid UUID format for contract_id",
                    "code": "INVALID_UUID",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        lineage_service = LineageService(
            tenant_id=str(tenant.id),
            user_id=str(request.user.id) if request.user.is_authenticated else None,
        )
        try:
            result = lineage_service.get_contract_lineage(
                contract_id=contract_id, tenant_id=str(tenant.id), use_cache=True
            )
        except NotFoundError as e:
            return Response(
                {"error": e.message, "code": getattr(e, "code", "NOT_FOUND")}, status=e.http_status
            )
        return Response(result)

    @extend_schema(
        summary="Get stale data",
        description="""
        Get all stale data (exceeds SLA).

        **Query Parameters:**
        - `dataset_id`: Optional dataset UUID filter
        - `asset_id`: Optional asset UUID filter
        """,
        parameters=[
            OpenApiParameter(
                name="dataset_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Dataset UUID filter",
                required=False,
            ),
            OpenApiParameter(
                name="asset_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Asset UUID filter",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="List of stale data records"),
        },
        tags=["Observability", "Freshness"],
    )
    @action(detail=False, methods=["get"], url_path="freshness/stale")
    def get_stale_data(self, request: Request) -> Response:
        """
        Get all stale data (exceeds SLA).

        GET /api/v1/observability/freshness/stale?dataset_id={id}
        """
        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to view observability data"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get parameters
        dataset_id = request.query_params.get("dataset_id")
        asset_id = request.query_params.get("asset_id")

        # Detect stale data
        stale_data = FreshnessMonitor.detect_stale_data(
            tenant_id=str(tenant.id), dataset_id=dataset_id, asset_id=asset_id
        )

        return Response(stale_data)

    @extend_schema(
        summary="Record observability metric",
        description="""
        Record a data observability metric (freshness, volume, schema).

        **Body Parameters:**
        - `dataset_id`: Dataset UUID (optional)
        - `asset_id`: Asset UUID (optional)
        - `last_update_time`: Last update timestamp (ISO format, optional)
        - `freshness_sla`: Freshness SLA level (optional)
        - `row_count`: Number of rows (optional)
        - `size_bytes`: Size in bytes (optional)
        - `schema_json`: Schema JSON (optional)
        """,
        responses={
            201: OpenApiResponse(description="Metric recorded"),
            400: OpenApiResponse(description="Invalid request"),
        },
        tags=["Observability"],
    )
    @action(detail=False, methods=["post"], url_path="metrics")
    def record_metric(self, request: Request) -> Response:
        """
        Record a data observability metric.

        POST /api/v1/observability/metrics
        """
        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to record metrics"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get parameters
        dataset_id = request.data.get("dataset_id")
        asset_id = request.data.get("asset_id")

        if not dataset_id and not asset_id:
            return Response(
                {"error": "Either dataset_id or asset_id must be provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get dataset/asset
        dataset = None
        asset = None

        if dataset_id:
            try:
                dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)
            except Dataset.DoesNotExist:
                return Response({"error": "Dataset not found"}, status=status.HTTP_404_NOT_FOUND)

        if asset_id:
            try:
                asset = Asset.objects.get(id=asset_id, tenant=tenant)
            except Asset.DoesNotExist:
                return Response({"error": "Asset not found"}, status=status.HTTP_404_NOT_FOUND)

        # Parse last_update_time
        last_update_time = None
        if request.data.get("last_update_time"):
            from django.utils.dateparse import parse_datetime

            last_update_time = parse_datetime(request.data["last_update_time"])
            if last_update_time:
                last_update_time = last_update_time.isoformat()

        # Use ObservabilityService to record metric (includes event publishing)
        service = ObservabilityService(
            tenant_id=str(tenant.id),
            user_id=str(request.user.id) if request.user.is_authenticated else None,
        )
        result = service.record_metric(
            tenant_id=str(tenant.id),
            dataset_id=str(dataset.id) if dataset else None,
            asset_id=str(asset.id) if asset else None,
            last_update_time=last_update_time,
            freshness_sla=request.data.get("freshness_sla"),
            row_count=request.data.get("row_count"),
            size_bytes=request.data.get("size_bytes"),
            schema_json=request.data.get("schema_json"),
        )

        return Response(result, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Get volume dashboard",
        description="""
        Get data volume dashboard with trends and anomaly detection.

        **Query Parameters:**
        - `dataset_id`: Optional dataset UUID filter
        - `asset_id`: Optional asset UUID filter
        - `period_type`: Period type (HOURLY or DAILY, default: DAILY)
        - `limit`: Maximum number of trends (default: 30)
        """,
        parameters=[
            OpenApiParameter(
                name="dataset_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Dataset UUID filter",
                required=False,
            ),
            OpenApiParameter(
                name="asset_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Asset UUID filter",
                required=False,
            ),
            OpenApiParameter(
                name="period_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Period type: HOURLY or DAILY (default: DAILY)",
                required=False,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum number of trends (default: 30)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Volume dashboard data"),
        },
        tags=["Observability", "Volume"],
    )
    @action(detail=False, methods=["get"], url_path="volume")
    def get_volume_dashboard(self, request: Request) -> Response:
        """
        Get data volume dashboard.

        GET /api/v1/observability/volume?period_type=DAILY&limit=30
        """
        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to view observability data"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get parameters
        dataset_id = request.query_params.get("dataset_id")
        asset_id = request.query_params.get("asset_id")
        period_type = request.query_params.get("period_type", "DAILY")
        limit = int(request.query_params.get("limit", 30))

        # Use ObservabilityService to get dashboard data (includes event publishing)
        service = ObservabilityService(
            tenant_id=str(tenant.id),
            user_id=str(request.user.id) if request.user.is_authenticated else None,
        )
        dashboard_data = service.get_volume_dashboard(
            tenant_id=str(tenant.id),
            dataset_id=dataset_id,
            asset_id=asset_id,
            period_type=period_type,
            limit=limit,
        )

        serializer = VolumeDashboardSerializer(dashboard_data)
        return Response(serializer.data)

    @extend_schema(
        summary="Aggregate volume trends",
        description="""
        Aggregate volume trends for hourly or daily periods.

        **Query Parameters:**
        - `period_type`: Period type (HOURLY or DAILY)
        - `dataset_id`: Optional dataset UUID filter
        - `asset_id`: Optional asset UUID filter
        - `hours`: Number of hours to aggregate (for HOURLY, default: 24)
        - `days`: Number of days to aggregate (for DAILY, default: 30)
        """,
        parameters=[
            OpenApiParameter(
                name="period_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Period type: HOURLY or DAILY",
                required=True,
            ),
            OpenApiParameter(
                name="dataset_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Dataset UUID filter",
                required=False,
            ),
            OpenApiParameter(
                name="asset_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Asset UUID filter",
                required=False,
            ),
            OpenApiParameter(
                name="hours",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Number of hours to aggregate (for HOURLY)",
                required=False,
            ),
            OpenApiParameter(
                name="days",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Number of days to aggregate (for DAILY)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Aggregated trends"),
        },
        tags=["Observability", "Volume"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="volume/aggregate",
        permission_classes=[permissions.IsAuthenticated],
    )
    def aggregate_volume_trends(self, request: Request) -> Response:
        """
        Aggregate volume trends.

        POST /api/v1/observability/volume/aggregate?period_type=DAILY&days=30
        """
        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to aggregate trends"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get parameters
        period_type = request.query_params.get("period_type", "DAILY")
        dataset_id = request.query_params.get("dataset_id")
        asset_id = request.query_params.get("asset_id")

        if period_type == "HOURLY":
            hours = int(request.query_params.get("hours", 24))
            trends = VolumeMonitor.aggregate_hourly_trends(
                tenant_id=str(tenant.id), dataset_id=dataset_id, asset_id=asset_id, hours=hours
            )
        else:
            days = int(request.query_params.get("days", 30))
            trends = VolumeMonitor.aggregate_daily_trends(
                tenant_id=str(tenant.id), dataset_id=dataset_id, asset_id=asset_id, days=days
            )

        return Response(
            {
                "period_type": period_type,
                "trends_count": len(trends),
                "trends": [str(t.id) for t in trends],
            }
        )

    @extend_schema(
        summary="Get schema drift dashboard",
        description="""
        Get schema drift dashboard with detected drifts and statistics.

        **Query Parameters:**
        - `dataset_id`: Optional dataset UUID filter
        - `asset_id`: Optional asset UUID filter
        - `limit`: Maximum number of records (default: 100)
        """,
        parameters=[
            OpenApiParameter(
                name="dataset_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Dataset UUID filter",
                required=False,
            ),
            OpenApiParameter(
                name="asset_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Asset UUID filter",
                required=False,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum number of records (default: 100)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Schema drift dashboard data"),
        },
        tags=["Observability", "Schema Drift"],
    )
    @action(detail=False, methods=["get"], url_path="schema-drift")
    def get_schema_drift_dashboard(self, request: Request) -> Response:
        """
        Get schema drift dashboard.

        GET /api/v1/observability/schema-drift?dataset_id={id}&limit=100
        """
        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to view observability data"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get parameters
        dataset_id = request.query_params.get("dataset_id")
        asset_id = request.query_params.get("asset_id")
        limit = int(request.query_params.get("limit", 100))

        # Use ObservabilityService to get dashboard data (includes event publishing)
        service = ObservabilityService(
            tenant_id=str(tenant.id),
            user_id=str(request.user.id) if request.user.is_authenticated else None,
        )
        dashboard_data = service.get_schema_drift_dashboard(
            tenant_id=str(tenant.id), dataset_id=dataset_id, asset_id=asset_id, limit=limit
        )

        serializer = SchemaDriftDashboardSerializer(dashboard_data)
        return Response(serializer.data)

    @extend_schema(
        summary="Detect schema drift",
        description="""
        Manually trigger schema drift detection for a dataset or asset.

        **Body Parameters:**
        - `dataset_id`: Dataset UUID (optional)
        - `asset_id`: Asset UUID (optional)
        - `tolerance_config`: Tolerance configuration (optional)
        """,
        responses={
            200: OpenApiResponse(description="Drift detection result"),
            400: OpenApiResponse(description="Invalid request"),
        },
        tags=["Observability", "Schema Drift"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="schema-drift/detect",
        permission_classes=[permissions.IsAuthenticated],
    )
    def detect_schema_drift(self, request: Request) -> Response:
        """
        Manually trigger schema drift detection.

        POST /api/v1/observability/schema-drift/detect
        """
        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to detect drift"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get parameters
        dataset_id = request.data.get("dataset_id")
        asset_id = request.data.get("asset_id")

        if not dataset_id and not asset_id:
            return Response(
                {"error": "Either dataset_id or asset_id must be provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get dataset/asset
        dataset = None
        asset = None

        if dataset_id:
            try:
                dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)
            except Dataset.DoesNotExist:
                return Response({"error": "Dataset not found"}, status=status.HTTP_404_NOT_FOUND)

        if asset_id:
            try:
                asset = Asset.objects.get(id=asset_id, tenant=tenant)
            except Asset.DoesNotExist:
                return Response({"error": "Asset not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get schema from dataset if available
        current_schema_json = None
        if dataset and dataset.schema_json:
            current_schema_json = dataset.schema_json

        # Detect drift
        drift = SchemaDriftDetector.detect_drift(
            tenant_id=str(tenant.id),
            dataset=dataset,
            asset=asset,
            current_schema_json=current_schema_json or request.data.get("schema_json"),
            tolerance_config=request.data.get("tolerance_config"),
        )

        if drift:
            return Response(
                {
                    "drift_detected": True,
                    "drift_id": str(drift.id),
                    "severity": drift.drift_severity,
                    "is_within_tolerance": drift.is_within_tolerance,
                    "new_fields": drift.new_fields,
                    "removed_fields": drift.removed_fields,
                    "type_changes": drift.type_changes,
                }
            )
        else:
            return Response({"drift_detected": False, "message": "No schema drift detected"})

    @extend_schema(
        summary="Get pipeline monitoring dashboard",
        description="""
        Get pipeline monitoring dashboard with execution metrics, success rates, error rates, latency, and throughput.

        **Query Parameters:**
        - `pipeline_type`: Optional pipeline type filter (SCHEDULED_INGESTION, DQ_RUN, etc.)
        - `pipeline_id`: Optional pipeline UUID filter
        - `limit`: Maximum number of executions (default: 100)
        """,
        parameters=[
            OpenApiParameter(
                name="pipeline_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Pipeline type filter",
                required=False,
            ),
            OpenApiParameter(
                name="pipeline_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Pipeline UUID filter",
                required=False,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum number of executions (default: 100)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Pipeline monitoring dashboard data"),
        },
        tags=["Observability", "Pipeline Monitoring"],
    )
    @action(detail=False, methods=["get"], url_path="pipelines")
    def get_pipeline_dashboard(self, request: Request) -> Response:
        """
        Get pipeline monitoring dashboard.

        GET /api/v1/observability/pipelines?pipeline_type=SCHEDULED_INGESTION&limit=100
        """
        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to view observability data"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get parameters
        pipeline_type = request.query_params.get("pipeline_type")
        pipeline_id = request.query_params.get("pipeline_id")
        limit = int(request.query_params.get("limit", 100))

        # Get dashboard data
        from .pipeline_monitoring import PipelineMonitor

        dashboard_data = PipelineMonitor.get_pipeline_dashboard(
            tenant_id=str(tenant.id),
            pipeline_type=pipeline_type,
            pipeline_id=pipeline_id,
            limit=limit,
        )

        return Response(dashboard_data)

    @extend_schema(
        summary="Get data SLAs dashboard",
        description="""
        Get data SLAs dashboard with compliance monitoring.

        **Query Parameters:**
        - `sla_type`: Optional SLA type filter (AVAILABILITY, FRESHNESS, QUALITY)
        - `dataset_id`: Optional dataset UUID filter
        - `asset_id`: Optional asset UUID filter
        - `is_active`: Optional active filter (true/false)
        - `is_violated`: Optional violation filter (true/false)
        - `limit`: Maximum number of SLAs (default: 100)
        """,
        parameters=[
            OpenApiParameter(
                name="sla_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="SLA type filter",
                required=False,
            ),
            OpenApiParameter(
                name="dataset_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Dataset UUID filter",
                required=False,
            ),
            OpenApiParameter(
                name="asset_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Asset UUID filter",
                required=False,
            ),
            OpenApiParameter(
                name="is_active",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Active filter",
                required=False,
            ),
            OpenApiParameter(
                name="is_violated",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Violation filter",
                required=False,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum number of SLAs (default: 100)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Data SLAs dashboard data"),
        },
        tags=["Observability", "Data SLAs"],
    )
    @action(detail=False, methods=["get"], url_path="slas")
    def get_slas_dashboard(self, request: Request) -> Response:
        """
        Get data SLAs dashboard.

        GET /api/v1/observability/slas?sla_type=FRESHNESS&limit=100
        """
        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to view observability data"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get parameters
        sla_type = request.query_params.get("sla_type")
        dataset_id = request.query_params.get("dataset_id")
        asset_id = request.query_params.get("asset_id")
        is_active = request.query_params.get("is_active")
        is_violated = request.query_params.get("is_violated")
        limit = int(request.query_params.get("limit", 100))

        # Parse boolean parameters
        is_active_bool = None
        if is_active is not None:
            is_active_bool = is_active.lower() == "true"

        is_violated_bool = None
        if is_violated is not None:
            is_violated_bool = is_violated.lower() == "true"

        # Get dashboard data
        from .data_slas import DataSLAMonitor

        dashboard_data = DataSLAMonitor.get_slas_dashboard(
            tenant_id=str(tenant.id),
            sla_type=sla_type,
            dataset_id=dataset_id,
            asset_id=asset_id,
            is_active=is_active_bool,
            is_violated=is_violated_bool,
            limit=limit,
        )

        return Response(dashboard_data)

    @extend_schema(
        summary="Get data incidents dashboard",
        description="""
        Get data incidents dashboard with lifecycle tracking.

        **Query Parameters:**
        - `status`: Optional status filter (DETECTED, TRIAGED, IN_PROGRESS, RESOLVED)
        - `incident_type`: Optional incident type filter
        - `severity`: Optional severity filter (CRITICAL, HIGH, MEDIUM, LOW)
        - `assigned_to_id`: Optional assigned user UUID filter
        - `resource_type`: Optional resource type filter
        - `resource_id`: Optional resource UUID filter
        - `limit`: Maximum number of incidents (default: 100)
        """,
        parameters=[
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Status filter",
                required=False,
            ),
            OpenApiParameter(
                name="incident_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Incident type filter",
                required=False,
            ),
            OpenApiParameter(
                name="severity",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Severity filter",
                required=False,
            ),
            OpenApiParameter(
                name="assigned_to_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Assigned user UUID filter",
                required=False,
            ),
            OpenApiParameter(
                name="resource_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Resource type filter",
                required=False,
            ),
            OpenApiParameter(
                name="resource_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Resource UUID filter",
                required=False,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum number of incidents (default: 100)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Data incidents dashboard data"),
        },
        tags=["Observability", "Incident Management"],
    )
    @extend_schema(
        summary="Create data incident",
        description="""
        Create a new data incident.

        **Body Parameters:**
        - `title`: Incident title (required)
        - `description`: Incident description (required)
        - `incident_type`: Incident type (required)
        - `severity`: Severity (CRITICAL, HIGH, MEDIUM, LOW, default: MEDIUM)
        - `resource_type`: Resource type (optional)
        - `resource_id`: Resource UUID (optional)
        - `metadata_json`: Additional metadata (optional)
        """,
        responses={
            201: OpenApiResponse(description="Incident created"),
            400: OpenApiResponse(description="Invalid request"),
        },
        tags=["Observability", "Incident Management"],
    )
    @action(detail=False, methods=["get", "post"], url_path="incidents")
    def incidents(self, request: Request) -> Response:
        """
        Get data incidents dashboard (GET) or create a new incident (POST).

        GET /api/v1/observability/incidents?status=IN_PROGRESS&limit=100
        POST /api/v1/observability/incidents
        """
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            error_msg = (
                "User must belong to a tenant to view observability data"
                if request.method == "GET"
                else "User must belong to a tenant to create incidents"
            )
            return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        if request.method == "GET":
            status_filter = request.query_params.get("status")
            incident_type = request.query_params.get("incident_type")
            severity = request.query_params.get("severity")
            assigned_to_id = request.query_params.get("assigned_to_id")
            resource_type = request.query_params.get("resource_type")
            resource_id = request.query_params.get("resource_id")
            limit = int(request.query_params.get("limit", 100))
            from .incident_management import IncidentManager

            dashboard_data = IncidentManager.get_incidents_dashboard(
                tenant_id=str(tenant.id),
                status=status_filter,
                incident_type=incident_type,
                severity=severity,
                assigned_to_id=assigned_to_id,
                resource_type=resource_type,
                resource_id=resource_id,
                limit=limit,
            )
            return Response(dashboard_data)

        # POST: create incident
        title = request.data.get("title")
        description = request.data.get("description")
        incident_type = request.data.get("incident_type")
        if not title or not description or not incident_type:
            return Response(
                {"error": "title, description, and incident_type are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .incident_management import IncidentManager

        incident = IncidentManager.create_incident(
            tenant_id=str(tenant.id),
            title=title,
            description=description,
            incident_type=incident_type,
            severity=request.data.get("severity", "MEDIUM"),
            resource_type=request.data.get("resource_type"),
            resource_id=request.data.get("resource_id"),
            detected_by_id=str(request.user.id) if request.user.is_authenticated else None,
            metadata_json=request.data.get("metadata_json"),
        )
        return Response(
            {
                "id": str(incident.id),
                "title": incident.title,
                "status": incident.status,
                "detected_at": incident.detected_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Update data incident",
        description="""
        Update a data incident (status, assignment, resolution).

        **Body Parameters:**
        - `status`: New status (TRIAGED, IN_PROGRESS, RESOLVED)
        - `assigned_to_id`: User UUID to assign to (optional)
        - `root_cause`: Root cause analysis (optional)
        - `resolution_notes`: Resolution notes (optional)
        """,
        responses={
            200: OpenApiResponse(description="Incident updated"),
            400: OpenApiResponse(description="Invalid request"),
            404: OpenApiResponse(description="Incident not found"),
        },
        tags=["Observability", "Incident Management"],
    )
    @extend_schema(
        summary="Update data incident",
        description="""
        Update a data incident (status, assignment, resolution).

        **Query Parameters:**
        - `incident_id`: Incident UUID (required)

        **Body Parameters:**
        - `status`: New status (TRIAGED, IN_PROGRESS, RESOLVED)
        - `assigned_to_id`: User UUID to assign to (optional)
        - `root_cause`: Root cause analysis (optional)
        - `resolution_notes`: Resolution notes (optional)
        """,
        parameters=[
            OpenApiParameter(
                name="incident_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Incident UUID",
                required=True,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Incident updated"),
            400: OpenApiResponse(description="Invalid request"),
            404: OpenApiResponse(description="Incident not found"),
        },
        tags=["Observability", "Incident Management"],
    )
    @action(detail=False, methods=["patch"], url_path="incidents/update")
    def update_incident(self, request: Request) -> Response:
        """
        Update a data incident.

        PATCH /api/v1/observability/incidents/update?incident_id={id}
        """
        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to update incidents"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get incident ID
        incident_id = request.query_params.get("incident_id") or request.data.get("incident_id")
        if not incident_id:
            return Response(
                {"error": "incident_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Get incident
        from .models import DataIncident

        try:
            DataIncident.objects.get(id=incident_id, tenant=tenant)
        except DataIncident.DoesNotExist:
            return Response({"error": "Incident not found"}, status=status.HTTP_404_NOT_FOUND)

        # Update incident
        from .incident_management import IncidentManager

        updated_incident = IncidentManager.update_incident_status(
            incident_id=incident_id,
            status=request.data.get("status"),
            assigned_to_id=request.data.get("assigned_to_id"),
            root_cause=request.data.get("root_cause"),
            resolution_notes=request.data.get("resolution_notes"),
            resolved_by_id=(
                str(request.user.id)
                if request.data.get("status") == "RESOLVED" and request.user.is_authenticated
                else None
            ),
        )

        return Response(
            {
                "id": str(updated_incident.id),
                "status": updated_incident.status,
                "updated_at": updated_incident.updated_at.isoformat(),
            }
        )
