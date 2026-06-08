"""
DQ Views

REST API views for DQ run management.
"""

import uuid
from datetime import datetime, timedelta, timezone as dt_timezone

import structlog
from django.db import connection, transaction
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from hub.apps.assets.models import Asset
from hub.apps.assets.models import DQStatus as AssetDQStatus
from hub.apps.audit.utils import create_audit_event
from hub.apps.core.responses import api_error_response, handle_service_exception
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.utils import create_job, get_job_timeout
from hub.apps.tenants.request_tenant import get_request_tenant, get_request_tenant_id
from hub.apps.tenants.services import get_tenant_dq_profile

from .anomaly_detection import AnomalyDetector
from .feature_flags import DQFeatureFlagMixin
from .log_helpers import _redact
from .models import (
    DQAlertingRule,
    DQAnomaly,
    DQEngine,
    DQRun,
    DQRunStatus,
    DQTrend,
)
from .root_cause_analysis import RootCauseAnalyzer
from .scorecards import DQScorecardService
from .serializers import (
    DQAlertingRuleCreateSerializer,
    DQAlertingRuleSerializer,
    DQRunCreateSerializer,
    DQRunSerializer,
)
from .service_client import DQServiceClient
from .services import DQService
from .trend_analysis import TrendAnalyzer

logger = structlog.get_logger(__name__)


class DQRunViewSet(DQFeatureFlagMixin, viewsets.ModelViewSet):
    """
    ViewSet for DQ run management.

    Tenant-scoped: users can only see/manage DQ runs in their tenant.

    Phase 240.4.B.2 — gated on ``Tenant.data_quality_enabled`` via
    ``DQFeatureFlagMixin`` (scope=basic).  Returns HTTP 403 +
    ``error_code: DATA_QUALITY_DISABLED`` when the flag is off.
    """

    dq_flag_scope = "basic"
    queryset = DQRun.objects.all()
    serializer_class = DQRunSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def check_auditor_permissions(self, request, view_action):
        """Check if AUDITOR role can perform the action (read-only)"""
        if not request.user or not request.user.is_authenticated:
            return True  # Let IsAuthenticated handle this

        # Check if user has AUDITOR role
        if hasattr(request.user, "user_roles"):
            role_names = [ur.role.name for ur in request.user.user_roles.all()]
            if "AUDITOR" in role_names:
                # AUDITOR can only read, not write
                if view_action in ["create", "update", "partial_update", "destroy"]:
                    from rest_framework.exceptions import PermissionDenied

                    raise PermissionDenied(
                        "AUDITOR role has read-only access. Cannot perform write operations."
                    )

        return True

    def get_queryset(self):
        """Filter queryset based on user permissions and query parameters"""
        user = self.request.user

        # Platform admins can see all DQ runs
        base = DQRun.objects.select_related(
            "tenant", "asset", "dataset", "file", "job",
        )
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = base
        else:
            # Regular users can only see DQ runs in their tenant
            # Use central helper for tenant resolution (Phase 10.1.1)
            tenant_id = get_request_tenant_id(self.request)
            if tenant_id:
                queryset = base.filter(tenant_id=tenant_id)
            else:
                return DQRun.objects.none()

        # Filter by status
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by dataset_id
        dataset_id = self.request.query_params.get("dataset_id")
        if dataset_id:
            try:
                import uuid
                uuid.UUID(dataset_id)  # Validate UUID format
                queryset = queryset.filter(dataset_id=dataset_id)
            except (ValueError, TypeError):
                # Invalid UUID format - return empty queryset
                queryset = queryset.none()

        # Filter by date range
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if date_from:
            try:
                # Parse date_from - fromisoformat returns timezone-aware datetime if timezone info is present
                # Normalize: "Z" -> "+00:00"; space before offset (e.g. + decoded as space in query) -> "+"
                date_from_str = date_from.replace("Z", "+00:00").replace(" +", "+").replace(" 00:00", "+00:00")
                date_from_dt = datetime.fromisoformat(date_from_str)
                # Ensure timezone-aware datetime in UTC
                if timezone.is_naive(date_from_dt):
                    date_from_dt = timezone.make_aware(date_from_dt, dt_timezone.utc)
                else:
                    # Convert to UTC if not already
                    date_from_dt = date_from_dt.astimezone(dt_timezone.utc)
                # Django ORM handles timezone-aware datetimes correctly
                queryset = queryset.filter(created_at__gte=date_from_dt)
            except (ValueError, AttributeError, TypeError):
                pass

        if date_to:
            try:
                # Parse date_to - fromisoformat returns timezone-aware datetime if timezone info is present
                # Normalize: "Z" -> "+00:00"; space before offset (e.g. + decoded as space in query) -> "+"
                date_to_str = date_to.replace("Z", "+00:00").replace(" +", "+").replace(" 00:00", "+00:00")
                date_to_dt = datetime.fromisoformat(date_to_str)
                # Ensure timezone-aware datetime in UTC
                if timezone.is_naive(date_to_dt):
                    date_to_dt = timezone.make_aware(date_to_dt, dt_timezone.utc)
                else:
                    # Convert to UTC if not already
                    date_to_dt = date_to_dt.astimezone(dt_timezone.utc)
                # Django ORM handles timezone-aware datetimes correctly
                queryset = queryset.filter(created_at__lte=date_to_dt)
            except (ValueError, AttributeError, TypeError):
                pass

        return queryset.order_by("-created_at")

    @transaction.atomic
    def create(self, request):
        """
        Create a new DQ run.

        POST /api/v1/dq/runs/
        Body: {
            "asset_id": "uuid" (optional),
            "dataset_id": "uuid" (optional),
            "file_id": "uuid" (optional, scan-only),
            "profile_key": "intake_basic_gx" (optional)
        }
        """
        self.check_auditor_permissions(request, "create")
        serializer = DQRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get tenant using central helper (Phase 10.1.1)
        tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to create DQ runs"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get resource references
        asset_id = serializer.validated_data.get("asset_id")
        dataset_id = serializer.validated_data.get("dataset_id")
        file_id = serializer.validated_data.get("file_id")

        # Resolve resources
        asset = None
        dataset = None
        file_obj = None

        if asset_id:
            try:
                asset = Asset.objects.get(id=asset_id, tenant=tenant)
            except Asset.DoesNotExist:
                return api_error_response(
                    message="Asset not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOT_FOUND",
                )

        if dataset_id:
            try:
                from hub.apps.datasets.models import Dataset

                dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)
                if asset and dataset.asset != asset:
                    return Response(
                        {"error": "Dataset does not belong to the specified asset"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not asset and dataset.asset:
                    asset = dataset.asset
            except Dataset.DoesNotExist:
                return api_error_response(
                    message="Dataset not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOT_FOUND",
                )

        if file_id:
            try:
                from hub.apps.files.models import File

                file_obj = File.objects.get(id=file_id, tenant=tenant)
            except File.DoesNotExist:
                return api_error_response(
                    message="File not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOT_FOUND",
                )

        # Determine profile key (explicit request > tenant default > platform default)
        profile_key = serializer.validated_data.get("profile_key")
        profile_source = None

        if not profile_key:
            # Get tenant default from TenantConfig (with platform default fallback)
            profile_key = get_tenant_dq_profile(str(tenant.id))
            profile_source = (
                "tenant_config" if profile_key != "intake_basic_gx" else "platform_default"
            )
            logger.info(
                "dq_profile_selected",
                tenant_id=str(tenant.id),
                profile_key=profile_key,
                source=profile_source,
                message=f"Using {profile_source} profile: {profile_key}",
            )
        else:
            # Explicit profile_key in request (user override)
            profile_source = "request_override"
            logger.info(
                "dq_profile_selected",
                tenant_id=str(tenant.id),
                profile_key=profile_key,
                source=profile_source,
                message=f"Using explicit profile from request: {profile_key}",
            )

        # Create DQ run via service (validates via DQBusinessRules, then creates)
        service = DQService(tenant_id=str(tenant.id), user_id=str(request.user.id))
        try:
            dq_run = service.create_dq_run(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                asset_id=asset_id,
                dataset_id=dataset_id,
                file_id=file_id,
                profile_key=profile_key,
                tenant=tenant,
                user=request.user,
                asset=asset,
                dataset=dataset,
                file_obj=file_obj,
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)

        # Log audit event
        create_audit_event(
            resource_type="DQ_RUN",
            action="DQ_RUN_CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(dq_run.id),
            details={
                "profile_key": dq_run.profile_key,
                "engine": dq_run.engine,
                "asset_id": str(asset.id) if asset else None,
                "dataset_id": str(dataset.id) if dataset else None,
                "file_id": str(file_obj.id) if file_obj else None,
            },
            request=request,
        )

        return Response(DQRunSerializer(dq_run).data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        """List DQ runs (tenant-scoped)"""
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve DQ run by ID"""
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update DQ run (full update)"""
        self.check_auditor_permissions(request, "update")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Update DQ run (partial update)"""
        self.check_auditor_permissions(request, "partial_update")
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete DQ run"""
        self.check_auditor_permissions(request, "destroy")
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        operation_id="get_dq_run_results",
        responses={
            200: inline_serializer(
                name="DQRunResultsResponse",
                fields={
                    "dq_run_id": serializers.UUIDField(),
                    "overall_status": serializers.CharField(),
                    "quality_score": serializers.FloatField(allow_null=True),
                    "score_breakdown": serializers.DictField(),
                    "checks": serializers.ListField(),
                    "check_details": serializers.ListField(),
                    "trend_analysis": serializers.DictField(allow_null=True),
                    "anomalies": serializers.ListField(),
                    "recommendations": serializers.ListField(),
                    "engine_type": serializers.CharField(),
                    "engine_version": serializers.CharField(allow_null=True),
                    "profile_key": serializers.CharField(),
                    "metadata": serializers.DictField(),
                    "started_at": serializers.DateTimeField(allow_null=True),
                    "completed_at": serializers.DateTimeField(allow_null=True),
                },
            ),
            404: OpenApiResponse(description="DQ run not found"),
        },
        tags=["Data Quality"],
    )
    @action(detail=True, methods=["get"], url_path="results")
    def results(self, request, id=None):
        """
        Get enhanced DQ run results with detailed check information.

        GET /api/v1/dq/runs/{id}/results/

        Returns detailed DQ results including:
        - Detailed check results with pass/fail status
        - Quality score breakdown by check category
        - Trend analysis (if available)
        - Anomaly detection results (if available)
        - Recommendations for improvement
        """
        dq_run = self.get_object()

        # Extract data from DQ run
        checks = dq_run.checks_json or []
        details = dq_run.details_json or {}
        metadata = details.get("metadata", {})

        # Build check details with enhanced information
        check_details = []
        passed_checks = 0
        failed_checks = 0
        warning_checks = 0

        for check in checks:
            check_name = check.get("name", "Unknown Check")
            check_type = check.get("category") or check.get("type", "unknown")
            check_status = check.get("status", "UNKNOWN")
            check_result = check.get("details") or check.get("result", {})

            # Count checks by status
            if check_status == "PASS":
                passed_checks += 1
            elif check_status == "FAIL":
                failed_checks += 1
            elif check_status == "WARN":
                warning_checks += 1

            # Build detailed check information
            check_detail = {
                "name": check_name,
                "type": check_type,
                "status": check_status,
                "result": check_result,
                "details": check_result,  # Alias for backward compatibility
                "expectation": check.get("expectation"),
                "observed_value": check_result.get("observed_value"),
                "expected_value": check_result.get("expected_value"),
                "message": check_result.get("message"),
                "severity": (
                    "HIGH"
                    if check_status == "FAIL"
                    else "MEDIUM" if check_status == "WARN" else "LOW"
                ),
            }
            check_details.append(check_detail)

        # Calculate quality score breakdown.
        # checks is always a list (defaulted via `checks = dq_run.checks_json or []`
        # above), so len(checks) is correct even for the empty case.
        total_checks = len(checks)
        score_breakdown = {
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "warning_checks": warning_checks,
            "pass_rate": passed_checks / total_checks if total_checks > 0 else 0,
            "overall_score": dq_run.quality_score or 0.0,
            "by_category": {},
        }

        # Group checks by category
        for check in checks:
            check_type = check.get("category") or check.get("type", "unknown")
            if check_type not in score_breakdown["by_category"]:
                score_breakdown["by_category"][check_type] = {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "warnings": 0,
                }
            score_breakdown["by_category"][check_type]["total"] += 1
            if check.get("status") == "PASS":
                score_breakdown["by_category"][check_type]["passed"] += 1
            elif check.get("status") == "FAIL":
                score_breakdown["by_category"][check_type]["failed"] += 1
            elif check.get("status") == "WARN":
                score_breakdown["by_category"][check_type]["warnings"] += 1

        # Get trend analysis (if available from DQAnomaly or DQTrend models)
        trend_analysis = None
        try:
            from .models import DQTrend

            # Get latest trend for this asset/dataset
            if dq_run.asset:
                trend = (
                    DQTrend.objects.filter(
                        tenant=dq_run.tenant, asset=dq_run.asset, metric_type="quality_score"
                    )
                    .order_by("-created_at")
                    .first()
                )

                if trend:
                    period_days = None
                    if trend.period_start and trend.period_end:
                        period_days = (
                            trend.period_end - trend.period_start
                        ).days
                    trend_analysis = {
                        "direction": trend.direction,
                        "change_percentage": trend.change_percent,
                        "previous_value": trend.previous_value,
                        "current_value": trend.current_value,
                        "period_days": period_days,
                        "created_at": trend.created_at.isoformat(),
                    }
        except (AttributeError, ValueError, TypeError) as e:
            # Trend analysis not available (model may not have trend fields)
            logger.debug(
                "Trend analysis not available",
                # Phase 240.5.F.3 — wrap extra payload in _redact() so a
                # future field addition (e.g. ``details_json``) is
                # auto-scrubbed before it reaches stdout.
                extra=_redact({"dq_run_id": str(dq_run.id), "error_type": type(e).__name__}),
            )

        # Get anomalies (if available)
        anomalies = []
        try:
            from .models import DQAnomaly

            anomaly_queryset = DQAnomaly.objects.filter(
                tenant=dq_run.tenant, dq_run=dq_run
            ).order_by("-severity", "-detected_at")

            for anomaly in anomaly_queryset:
                anomalies.append(
                    {
                        "metric_type": anomaly.metric_type,
                        "expected_value": float(anomaly.expected_value),
                        "actual_value": float(anomaly.actual_value),
                        "deviation": float(anomaly.deviation),
                        "severity": anomaly.severity,
                        "detected_at": anomaly.created_at.isoformat(),
                    }
                )
        except (ImportError, AttributeError, ValueError) as e:
            # Anomaly detection not available (model may not exist or fields missing)
            logger.debug(
                "Anomaly detection not available",
                # Phase 240.5.F.3 — wrap extra payload in _redact().
                extra=_redact({"dq_run_id": str(dq_run.id), "error_type": type(e).__name__}),
            )

        # Generate recommendations based on failed checks
        recommendations = []
        for check in checks:
            if check.get("status") == "FAIL":
                check_name = check.get("name", "Unknown")
                check_category = (
                    check.get("category")
                    or check.get("type", "unknown")
                )
                message = (
                    check.get("message")
                    or check.get("details", {}).get("message", "")
                    or check.get("result", {}).get("message", "")
                )

                recommendations.append(
                    {
                        "check_name": check_name,
                        "check_type": check_category,
                        "issue": message,
                        "priority": "HIGH",
                        "suggestion": (
                            f"Review and fix {check_category} "
                            f"check: {check_name}"
                        ),
                    }
                )

        # Log audit event
        create_audit_event(
            resource_type="DQ_RUN",
            action="RESULTS_ACCESSED",
            actor_user=request.user,
            tenant=dq_run.tenant,
            resource_id=str(dq_run.id),
            details={},
            request=request,
        )

        return Response(
            {
                "dq_run_id": str(dq_run.id),
                "overall_status": dq_run.overall_status,
                "quality_score": dq_run.quality_score,
                "score_breakdown": score_breakdown,
                "quality_score_breakdown": score_breakdown,  # Alias for backward compatibility
                "checks": checks,
                "check_details": check_details,
                "trend_analysis": trend_analysis,
                "anomalies": anomalies,
                "recommendations": recommendations,
                "engine_type": dq_run.engine,
                "engine_version": details.get("engine_version"),
                "profile_key": dq_run.profile_key,
                "metadata": metadata,
                "started_at": dq_run.started_at.isoformat() if dq_run.started_at else None,
                "completed_at": dq_run.completed_at.isoformat() if dq_run.completed_at else None,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="warehouse-run",
            throttle_classes=[ScopedRateThrottle])
    def warehouse_run(self, request):
        """Run DQ checks directly in the customer's warehouse (Phase 285.10).

        POST /api/v1/dq/warehouse-run/
        """
        from hub.apps.dq.services import DQService
        from hub.apps.datasets.models import Dataset
        from hub.apps.tenants.models import Tenant

        tenant = self._resolve_tenant(request)
        warehouse_config = request.data.get("warehouse_config", {})
        dataset_id = request.data.get("dataset_id")
        check_definitions = request.data.get("check_definitions", [])

        if not dataset_id:
            raise ValidationError({"dataset_id": "This field is required."})
        if not warehouse_config:
            raise ValidationError({"warehouse_config": "This field is required."})

        try:
            dataset = Dataset.objects.get(id=dataset_id, tenant_id=str(tenant.id))
        except Dataset.DoesNotExist:
            raise NotFound("Dataset not found or not in your tenant.")

        # Feature flag gate (Fix 11)
        if not getattr(tenant, "warehouse_dq_enabled", False):
            return Response(
                {"error": "WAREHOUSE_DQ_DISABLED",
                 "message": "Warehouse-native DQ is not enabled for this tenant."},
                status=status.HTTP_403_FORBIDDEN,
            )

        run = DQService.scan_inmemory_warehouse(
            dataset=dataset,
            tenant=tenant,
            check_definitions=check_definitions,
            warehouse_config=warehouse_config,
            user=request.user,
        )
        return Response({
            "id": str(run.id),
            "status": run.status,
            "overall_status": run.overall_status,
            "quality_score": run.quality_score,
        }, status=status.HTTP_200_OK)


class DQAlertingRuleViewSet(DQFeatureFlagMixin, viewsets.ModelViewSet):
    """
    ViewSet for DQ alerting rule management.

    Tenant-scoped: users can only see/manage alerting rules in their tenant.

    Phase 240.4.B.2 — gated on ``Tenant.data_quality_enabled`` via
    ``DQFeatureFlagMixin`` (scope=basic).
    """

    dq_flag_scope = "basic"
    queryset = DQAlertingRule.objects.all()
    serializer_class = DQAlertingRuleSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        base = DQAlertingRule.objects.select_related("tenant", "asset")

        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = base
        else:
            tenant_id = get_request_tenant_id(self.request)
            if tenant_id:
                queryset = base.filter(tenant_id=tenant_id)
            else:
                return DQAlertingRule.objects.none()

        # Optional filters
        asset_id = self.request.query_params.get("asset_id")
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)

        enabled = self.request.query_params.get("enabled")
        if enabled is not None:
            queryset = queryset.filter(enabled=enabled.lower() in ("true", "1"))

        return queryset.order_by("-created_at")

    def create(self, request):
        serializer = DQAlertingRuleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to create alerting rules"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve asset
        asset_id = serializer.validated_data.get("asset_id")
        asset = None
        if asset_id:
            try:
                asset = Asset.objects.get(id=asset_id, tenant=tenant)
            except Asset.DoesNotExist:
                return api_error_response(
                    message="Asset not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOT_FOUND",
                )

        rule = DQAlertingRule(
            tenant=tenant,
            asset=asset,
            name=serializer.validated_data.get("name", "Quality Score Alert"),
            description=serializer.validated_data.get("description", ""),
            metric_type=serializer.validated_data.get("metric_type", "quality_score"),
            threshold=serializer.validated_data["threshold"],
            comparison_operator=serializer.validated_data.get("comparison_operator", "<"),
            severity=serializer.validated_data.get("severity", "MEDIUM"),
            alert_channels=serializer.validated_data.get("alert_channels", ["EMAIL"]),
            channel_config=serializer.validated_data.get("channel_config", {}),
            enabled=serializer.validated_data.get("enabled", True),
            created_by=request.user,
        )
        rule.save()

        create_audit_event(
            resource_type="DQ_ALERTING_RULE",
            action="DQ_ALERTING_RULE_CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(rule.id),
            details={
                "name": rule.name,
                "metric_type": rule.metric_type,
                "threshold": rule.threshold,
                "asset_id": str(asset.id) if asset else None,
            },
            request=request,
        )

        return Response(
            DQAlertingRuleSerializer(rule).data,
            status=status.HTTP_201_CREATED,
        )


# Phase 240.3.B (REQ-DQ-A2) — advanced quality endpoints.
#
# Single ViewSet wraps the four read-only ``@action``s: anomalies,
# trends, scorecards, root_cause_analysis.  Routes are dual-mounted
# under ``/api/v1/dq/quality/`` (canonical) and ``/api/v1/quality/``
# (deprecated alias) per D240.10.  The view itself is identical for
# both prefixes; the deprecation headers are attached by URL-router
# wiring (see ``dq/urls.py``) so the view doesn't have to know which
# prefix the request came in under.
class DQQualityViewSet(DQFeatureFlagMixin, viewsets.ViewSet):
    """ViewSet for advanced data-quality query endpoints (read-only).

    Each ``@action`` is:
    - tenant-scoped via ``get_request_tenant_id``;
    - read-only — AUDITOR is allowed to GET, write methods are not
      defined (DRF returns 405 by default);
    - rate-limited per-action via ``ScopedRateThrottle`` with the
      scope set by ``throttle_scope`` on the action;
    - plan-limit enforced — every successful invocation increments
      the daily ``max_quality_queries_per_day`` counter by emitting a
      ``DQ_QUALITY_QUERY`` audit row before the response is returned;
    - audit-logged with the endpoint name + tenant + actor in
      ``details_json`` (PII-redacted by ``create_audit_event``);
    - Phase 240.4.B.2: gated on the conjunctive flag pair
      (``Tenant.data_quality_enabled AND
      Tenant.data_quality_advanced_enabled``) via
      ``DQFeatureFlagMixin`` (scope=advanced).  Base flag wins when
      off — denials carry ``DATA_QUALITY_DISABLED``; advanced-only
      denials carry ``DATA_QUALITY_ADVANCED_DISABLED``.
    """

    dq_flag_scope = "advanced"
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]

    # Phase 240.3.B.5 — per-action throttle scope.  ``ScopedRateThrottle``
    # reads ``view.throttle_scope`` during ``check_throttles`` (which runs
    # in ``initial(request)`` BEFORE the action method body), so setting
    # ``self.throttle_scope`` inside the action body is too late — the
    # throttle has already returned True (no scope = no limit).  We set
    # the scope in ``get_throttles()`` (called BY ``check_throttles``)
    # using ``self.action`` (already populated by ``initialize_request``).
    _ACTION_THROTTLE_SCOPE = {
        "anomalies": "dq_quality_anomalies",
        "trends": "dq_quality_trends",
        "scorecards": "dq_quality_scorecards",
        "root_cause_analysis": "dq_quality_root_cause",
    }

    def get_throttles(self):
        scope = self._ACTION_THROTTLE_SCOPE.get(getattr(self, "action", None))
        if scope:
            self.throttle_scope = scope
        return super().get_throttles()

    # ─── Plan-limit / audit helpers ──────────────────────────────

    def _enforce_plan_limit_and_emit_audit(
        self, request, tenant, endpoint, extra=None,
    ):
        """Atomic ``max_quality_queries_per_day`` check **+** audit-row
        emit, both inside the same ``transaction.atomic()`` so the
        SELECT FOR UPDATE held by ``PlanLimitService.check_limit`` covers
        the audit insert too.

        Race-safety: ``check_limit`` acquires SELECT FOR UPDATE on the
        ``Tenant`` row; in PostgreSQL the lock is released only at
        outer-transaction commit, so the audit row inserted afterwards
        in this same transaction is committed atomically with the lock
        release.  A concurrent request waiting on the lock will see the
        new audit row in ITS count query — eliminating the TOCTOU
        window where two parallel requests both see ``count=N`` then
        both emit and end up at ``count=N+2`` over the cap.

        Returns ``None`` on success (audit committed).  On exhaustion
        returns a 403 ``api_error_response`` with code
        ``plan_limit_exceeded`` (audit NOT emitted in that case).
        """
        from hub.apps.core.services.base import (
            ValidationError as SvcValidationError,
        )
        from hub.apps.tenants.services import PlanLimitService

        plan_svc = PlanLimitService(tenant_id=str(tenant.id))
        try:
            with transaction.atomic():
                plan_svc.check_limit(
                    tenant_id=str(tenant.id),
                    limit_key="max_quality_queries_per_day",
                    delta=1,
                )
                # Inside the same outer atomic so the lock covers the
                # insert.  ``create_audit_event`` runs ``Model.objects.
                # create``, which will not commit until the outer
                # ``with`` exits.
                self._emit_quality_query_audit(
                    request, tenant, endpoint, extra=extra,
                )
        except SvcValidationError as plan_err:
            if plan_err.code == "plan_limit_exceeded":
                return api_error_response(
                    message=plan_err.message,
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="plan_limit_exceeded",
                    details=plan_err.details or {},
                )
            # Surface other validation errors faithfully.
            return handle_service_exception(plan_err)
        return None

    def _emit_quality_query_audit(self, request, tenant, endpoint, extra=None):
        """Emit ``DQ_QUALITY_QUERY`` so the daily counter increments."""
        details = {"endpoint": endpoint}
        if extra:
            details.update(extra)
        create_audit_event(
            resource_type="DQ_QUALITY",
            action="DQ_QUALITY_QUERY",
            actor_user=request.user,
            tenant=tenant,
            details=details,
            request=request,
        )

    # ─── Anomalies ───────────────────────────────────────────────

    @extend_schema(
        operation_id="list_dq_quality_anomalies",
        parameters=[
            OpenApiParameter("asset_id", str, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("dataset_id", str, OpenApiParameter.QUERY, required=False),
            OpenApiParameter(
                "severity", str, OpenApiParameter.QUERY, required=False,
                description="One of CRITICAL / HIGH / MEDIUM / LOW",
            ),
            OpenApiParameter(
                "since", str, OpenApiParameter.QUERY, required=False,
                description="ISO-8601 timestamp; only anomalies detected at or after this point are returned",
            ),
        ],
        responses={
            200: inline_serializer(
                name="DQQualityAnomaliesResponse",
                fields={"results": serializers.ListField()},
            ),
            403: OpenApiResponse(description="Plan limit exceeded"),
            429: OpenApiResponse(description="Rate-limited"),
        },
        tags=["Data Quality"],
    )
    @action(detail=False, methods=["get"], url_path="anomalies")
    def anomalies(self, request):
        """List detected DQ anomalies for the requesting tenant."""
        tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            return api_error_response(
                message="User must belong to a tenant",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        denied = self._enforce_plan_limit_and_emit_audit(
            request, tenant, "anomalies",
        )
        if denied is not None:
            return denied

        qs = DQAnomaly.objects.filter(tenant_id=str(tenant.id))

        asset_id = request.query_params.get("asset_id")
        if asset_id:
            try:
                uuid.UUID(asset_id)
                qs = qs.filter(asset_id=asset_id)
            except (ValueError, TypeError):
                qs = qs.none()

        dataset_id = request.query_params.get("dataset_id")
        if dataset_id:
            try:
                uuid.UUID(dataset_id)
                qs = qs.filter(dataset_id=dataset_id)
            except (ValueError, TypeError):
                qs = qs.none()

        severity = request.query_params.get("severity")
        if severity:
            qs = qs.filter(severity=severity.upper())

        since = request.query_params.get("since")
        if since:
            try:
                since_dt = datetime.fromisoformat(
                    since.replace("Z", "+00:00")
                )
                if timezone.is_naive(since_dt):
                    since_dt = timezone.make_aware(since_dt, dt_timezone.utc)
                qs = qs.filter(detected_at__gte=since_dt)
            except (ValueError, TypeError):
                pass

        qs = qs.order_by("-detected_at")[:500]

        results = [
            {
                "id": str(a.id),
                "tenant_id": str(a.tenant_id),
                "asset_id": str(a.asset_id) if a.asset_id else None,
                "dataset_id": str(a.dataset_id) if a.dataset_id else None,
                "dq_run_id": str(a.dq_run_id) if a.dq_run_id else None,
                "metric_type": a.metric_type,
                "expected_value": a.expected_value,
                "actual_value": a.actual_value,
                "deviation": a.deviation,
                "severity": a.severity,
                "anomaly_type": a.anomaly_type,
                "description": a.description,
                "metadata": a.metadata,
                "detected_at": a.detected_at.isoformat() if a.detected_at else None,
                "acknowledged": a.acknowledged,
            }
            for a in qs
        ]

        return Response({"results": results}, status=status.HTTP_200_OK)

    # ─── Trends ──────────────────────────────────────────────────

    @extend_schema(
        operation_id="list_dq_quality_trends",
        parameters=[
            OpenApiParameter("asset_id", str, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("dataset_id", str, OpenApiParameter.QUERY, required=False),
            OpenApiParameter(
                "metric_type", str, OpenApiParameter.QUERY, required=False,
                description="Default: ``quality_score``",
            ),
            OpenApiParameter(
                "time_range", int, OpenApiParameter.QUERY, required=False,
                description="Lookback window in days (1–365). Default 30.",
            ),
            OpenApiParameter(
                "period_type", str, OpenApiParameter.QUERY, required=False,
                description="HOURLY / DAILY / WEEKLY / MONTHLY. Default DAILY.",
            ),
        ],
        responses={
            200: inline_serializer(
                name="DQQualityTrendsResponse",
                fields={"results": serializers.ListField()},
            ),
            403: OpenApiResponse(description="Plan limit exceeded"),
            429: OpenApiResponse(description="Rate-limited"),
        },
        tags=["Data Quality"],
    )
    @action(detail=False, methods=["get"], url_path="trends")
    def trends(self, request):
        """Compute / list quality trends for an asset or dataset."""
        tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            return api_error_response(
                message="User must belong to a tenant",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        asset_id = request.query_params.get("asset_id")
        dataset_id = request.query_params.get("dataset_id")
        metric_type = request.query_params.get("metric_type", "quality_score")
        period_type = request.query_params.get("period_type", "DAILY")

        time_range_raw = request.query_params.get("time_range", "30")
        try:
            periods = max(1, min(365, int(time_range_raw)))
        except (ValueError, TypeError):
            periods = 30

        # Validate id-shaped query params BEFORE consuming the
        # plan-limit budget so callers don't get charged for
        # malformed input.
        if asset_id:
            try:
                uuid.UUID(asset_id)
            except (ValueError, TypeError):
                return api_error_response(
                    message="Invalid asset_id",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="VALIDATION_ERROR",
                )

        denied = self._enforce_plan_limit_and_emit_audit(
            request, tenant, "trends",
            extra={"metric_type": metric_type},
        )
        if denied is not None:
            return denied

        # Tenant isolation: if the supplied asset_id is not in this
        # tenant, return an empty result set rather than leaking the
        # existence of cross-tenant rows.  ``calculate_trend`` would
        # also return [] but this short-circuit is explicit + cheap.
        if asset_id and not Asset.objects.filter(
            id=asset_id, tenant_id=str(tenant.id),
        ).exists():
            return Response({"results": []}, status=status.HTTP_200_OK)

        trends = TrendAnalyzer.calculate_trend(
            asset_id=asset_id,
            dataset_id=dataset_id,
            tenant_id=str(tenant.id),
            metric_type=metric_type,
            period_type=period_type,
            periods=periods,
        )
        results = TrendAnalyzer.get_trend_visualization(trends, format="json")

        return Response({"results": results}, status=status.HTTP_200_OK)

    # ─── Scorecards ──────────────────────────────────────────────

    @extend_schema(
        operation_id="get_dq_quality_scorecard",
        parameters=[
            OpenApiParameter(
                "asset_id", str, OpenApiParameter.QUERY, required=False,
                description="If supplied, returns asset-level scorecard; else tenant-level executive dashboard.",
            ),
            OpenApiParameter(
                "time_range", int, OpenApiParameter.QUERY, required=False,
                description="Lookback window in days (1–365). Default 30.",
            ),
        ],
        responses={
            200: OpenApiResponse(description="Scorecard payload"),
            404: OpenApiResponse(description="Asset not found in this tenant"),
            403: OpenApiResponse(description="Plan limit exceeded"),
            429: OpenApiResponse(description="Rate-limited"),
        },
        tags=["Data Quality"],
    )
    @action(detail=False, methods=["get"], url_path="scorecards")
    def scorecards(self, request):
        """Return an executive dashboard or per-asset scorecard."""
        tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            return api_error_response(
                message="User must belong to a tenant",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        asset_id = request.query_params.get("asset_id")
        time_range_raw = request.query_params.get("time_range", "30")
        try:
            days = max(1, min(365, int(time_range_raw)))
        except (ValueError, TypeError):
            days = 30

        # Validate id-shape BEFORE budget consumption.
        if asset_id:
            try:
                uuid.UUID(asset_id)
            except (ValueError, TypeError):
                return api_error_response(
                    message="Invalid asset_id",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="VALIDATION_ERROR",
                )

        denied = self._enforce_plan_limit_and_emit_audit(
            request, tenant, "scorecards",
            extra={"asset_id": asset_id, "days": days},
        )
        if denied is not None:
            return denied

        if asset_id:
            # Tenant isolation: refuse to compute a scorecard for
            # an asset outside the tenant.  Returning 404 (vs 403)
            # is the standard cross-tenant pattern in this codebase
            # (don't disclose whether the resource exists at all).
            if not Asset.objects.filter(
                id=asset_id, tenant_id=str(tenant.id)
            ).exists():
                return api_error_response(
                    message="Asset not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOT_FOUND",
                )
            payload = DQScorecardService.get_asset_scorecard(
                asset_id=str(asset_id),
                tenant_id=str(tenant.id),
                days=days,
            )
        else:
            payload = DQScorecardService.get_executive_dashboard(
                tenant_id=str(tenant.id),
                days=days,
            )

        return Response(payload, status=status.HTTP_200_OK)

    # ─── Root-cause analysis ─────────────────────────────────────

    @extend_schema(
        operation_id="get_dq_quality_root_cause_analysis",
        parameters=[
            OpenApiParameter(
                "dq_run_id", str, OpenApiParameter.QUERY, required=False,
                description="Analyse a specific DQ run.  Mutually exclusive with ``asset_id``.",
            ),
            OpenApiParameter(
                "asset_id", str, OpenApiParameter.QUERY, required=False,
                description="If supplied without ``dq_run_id``, the latest SUCCEEDED run for the asset is analysed.",
            ),
            OpenApiParameter(
                "lookback_days", int, OpenApiParameter.QUERY, required=False,
                description="Window of historical context (1–365).  Default 30.",
            ),
        ],
        responses={
            200: OpenApiResponse(description="Root-cause analysis payload"),
            400: OpenApiResponse(description="Missing dq_run_id / asset_id"),
            404: OpenApiResponse(description="DQ run / asset not found in this tenant"),
            403: OpenApiResponse(description="Plan limit exceeded"),
            429: OpenApiResponse(description="Rate-limited"),
        },
        tags=["Data Quality"],
    )
    @action(detail=False, methods=["get"], url_path="root_cause_analysis")
    def root_cause_analysis(self, request):
        """Return a root-cause analysis report for a DQ run."""
        tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            return api_error_response(
                message="User must belong to a tenant",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        dq_run_id = request.query_params.get("dq_run_id")
        asset_id = request.query_params.get("asset_id")
        lookback_raw = request.query_params.get("lookback_days", "30")
        try:
            lookback_days = max(1, min(365, int(lookback_raw)))
        except (ValueError, TypeError):
            lookback_days = 30

        # Validate inputs BEFORE consuming the budget.
        if not dq_run_id and not asset_id:
            return api_error_response(
                message="Either dq_run_id or asset_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )
        if dq_run_id:
            try:
                uuid.UUID(dq_run_id)
            except (ValueError, TypeError):
                return api_error_response(
                    message="Invalid dq_run_id",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="VALIDATION_ERROR",
                )
        else:
            try:
                uuid.UUID(asset_id)
            except (ValueError, TypeError):
                return api_error_response(
                    message="Invalid asset_id",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="VALIDATION_ERROR",
                )

        denied = self._enforce_plan_limit_and_emit_audit(
            request, tenant, "root_cause_analysis",
            extra={"dq_run_id": dq_run_id, "asset_id": asset_id},
        )
        if denied is not None:
            return denied

        # Resolve a single DQRun, tenant-scoped.
        target_run = None
        if dq_run_id:
            target_run = DQRun.objects.filter(
                id=dq_run_id, tenant_id=str(tenant.id)
            ).first()
            if target_run is None:
                return api_error_response(
                    message="DQ run not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOT_FOUND",
                )
        else:
            if not Asset.objects.filter(
                id=asset_id, tenant_id=str(tenant.id)
            ).exists():
                return api_error_response(
                    message="Asset not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOT_FOUND",
                )
            target_run = (
                DQRun.objects.filter(
                    asset_id=asset_id,
                    tenant_id=str(tenant.id),
                    status=DQRunStatus.SUCCEEDED,
                )
                .order_by("-completed_at")
                .first()
            )
            if target_run is None:
                return api_error_response(
                    message="No SUCCEEDED DQ run found for asset",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOT_FOUND",
                )

        report = RootCauseAnalyzer.analyze_root_cause(
            target_run, lookback_days=lookback_days,
        )

        return Response(report, status=status.HTTP_200_OK)


def _persist_dq_run_failure_state(
    dq_run_id: str,
    *,
    error_message: str,
    error_type: str,
) -> None:
    """Persist FAILED on DQRun using a clean connection/transaction.

    After PostgreSQL ``QueryCanceled`` / ``InFailedSqlTransaction``, the default
    connection may be unusable until rollback/close. Without this, the error
    handler's ``save()`` fails and tests/jobs see stuck RUNNING rows.
    """
    import logging

    log = logging.getLogger(__name__)
    details = {
        "error": error_message,
        "error_type": error_type,
        "fail_closed": True,
    }
    now = timezone.now()

    def _save():
        with transaction.atomic():
            run = DQRun.objects.get(id=dq_run_id)
            run.status = DQRunStatus.FAILED
            run.overall_status = "UNKNOWN"
            run.details_json = details
            run.completed_at = now
            run.save(
                update_fields=[
                    "status",
                    "overall_status",
                    "details_json",
                    "completed_at",
                ]
            )
            if run.asset_id:
                Asset.objects.filter(pk=run.asset_id).update(
                    dq_status=AssetDQStatus.UNKNOWN,
                )

    try:
        _save()
    except Exception as first_exc:
        log.warning(
            "dq_run_failure_persist_retry dq_run_id=%s exc=%s",
            dq_run_id,
            first_exc,
            exc_info=True,
        )
        try:
            connection.close()
        except Exception:
            pass
        try:
            _save()
        except Exception as second_exc:
            log.error(
                "dq_run_failure_persist_abandoned dq_run_id=%s exc=%s",
                dq_run_id,
                second_exc,
                exc_info=True,
            )


def execute_dq_run(dq_run_id: str) -> None:
    """
    Execute a DQ run.

    This function is called by the job worker to process a DQ run.

    Args:
        dq_run_id: DQ run ID
    """
    from hub.apps.datasets.models import Dataset
    from hub.apps.files.storage import S3StorageClient

    dq_run = (
        DQRun.objects.select_related(
            "asset",
            "file",
            "dataset",
            "dataset__file",
        ).get(id=dq_run_id)
    )
    import time as _time
    from django.conf import settings as _s

    dq_run.status = DQRunStatus.RUNNING
    dq_run.started_at = timezone.now()
    dq_run.save(update_fields=["status", "started_at"])

    _dq_deadline = _time.monotonic() + getattr(_s, "DQ_POLL_MAX_SECONDS", 300)

    try:
        # Get file content
        file_obj = None
        file_format = None

        if dq_run.file:
            file_obj = dq_run.file
            file_format = file_obj.name.split(".")[-1].lower() if "." in file_obj.name else "csv"
        elif dq_run.dataset and dq_run.dataset.file:
            file_obj = dq_run.dataset.file
            file_format = dq_run.dataset.format.lower() if dq_run.dataset.format else "csv"
        elif dq_run.asset_id:
            # Latest dataset for asset (direct filter + select_related: one round-trip)
            dataset = (
                Dataset.objects.filter(asset_id=dq_run.asset_id)
                .select_related("file")
                .order_by("-version")
                .first()
            )
            if dataset and dataset.file:
                file_obj = dataset.file
                file_format = dataset.format.lower() if dataset.format else "csv"

        if not file_obj:
            raise ValueError("No file found for DQ run")

        # Download file from storage
        storage_client = S3StorageClient()
        file_content = storage_client.download_file(file_obj.storage_path)

        # Call DQ service
        # Phase 240.3.D — forward the DQRun's tenant_id so the
        # client resolves any per-tenant threshold overrides into
        # X-Tenant-Threshold-* headers. NULL overrides fall through
        # to the dq-service env defaults silently.
        dq_client = DQServiceClient()
        result = dq_client.run_dq(
            file_content=file_content,
            file_format=file_format,
            profile_key=dq_run.profile_key,
            tenant_id=str(dq_run.tenant_id) if dq_run.tenant_id else None,
        )

        # Phase 69: deadline check after service call (fail-closed)
        if _time.monotonic() > _dq_deadline:
            elapsed = (timezone.now() - dq_run.started_at).total_seconds()
            dq_run.status = DQRunStatus.FAILED
            dq_run.overall_status = "UNKNOWN"
            dq_run.details_json = {
                "error": f"DQ service execution exceeded deadline after {int(elapsed)}s",
                "error_code": "POLL_TIMEOUT",
            }
            dq_run.completed_at = timezone.now()
            dq_run.save(update_fields=["status", "overall_status", "details_json", "completed_at"])
            # Phase 78: Prometheus counter for poll timeouts
            try:
                from hub.apps.observability.otel_metrics import poll_timeout_total
                poll_timeout_total.labels(service="dq").inc()
            except Exception:
                pass
            return

        # Calculate execution time for metering
        execution_time = (timezone.now() - dq_run.started_at).total_seconds()

        # Get row count from metadata or calculate from file
        row_count = result.get("metadata", {}).get("total_rows", 0)
        column_count = result.get("metadata", {}).get("total_columns", 0)

        # Update DQ run with results
        dq_run.status = DQRunStatus.SUCCEEDED
        dq_run.overall_status = result.get("overall_status")
        raw_score = result.get("quality_score")
        dq_run.quality_score = (
            max(0.0, min(100.0, float(raw_score)))
            if raw_score is not None
            else None
        )
        dq_run.checks_json = result.get("checks", [])
        dq_run.details_json = {
            "engine_type": result.get("engine_type"),
            "engine_version": result.get("engine_version"),
            "profile_key": result.get("profile_key"),
            "metadata": result.get("metadata", {}),
            # Metering information for billing
            "metering": {
                "operation_type": "DQ_RUN",
                "rows_inspected": row_count,
                "columns_inspected": column_count,
                "execution_time_seconds": round(execution_time, 2),
                "engine_type": result.get("engine_type"),
                "profile_key": result.get("profile_key"),
                "quality_score": result.get("quality_score"),
                "checks_count": len(result.get("checks", [])),
            },
        }
        dq_run.completed_at = timezone.now()
        dq_run.save(
            update_fields=[
                "status",
                "overall_status",
                "quality_score",
                "checks_json",
                "details_json",
                "completed_at",
            ]
        )

        # Phase 240.5.A.2 — emit billing event for SUCCEEDED runs.
        #
        # The emit is intentionally best-effort: ``emit_event``
        # swallows bus errors and returns None, so a Redis outage
        # or serialisation failure can NEVER block the DQ pipeline
        # (notifications + asset-status update below also depend
        # on this codepath continuing to run). Failed runs do NOT
        # reach this point — they take the ``except`` branch at
        # the end of the function and call
        # ``_persist_dq_run_failure_state`` instead, which by spec
        # 240.5.A is NOT billable.
        try:
            from hub.apps.billing.event_types import DQ_RUN_COMPLETED
            from hub.apps.billing.events import emit_event

            emit_event(
                event_type=DQ_RUN_COMPLETED,
                payload={
                    "tenant_id": str(dq_run.tenant_id) if dq_run.tenant_id else None,
                    "dq_run_id": str(dq_run.id),
                    "engine": result.get("engine_type"),
                    "rows_inspected": row_count,
                    "columns_inspected": column_count,
                    "execution_time_seconds": round(execution_time, 2),
                    "quality_score": result.get("quality_score"),
                },
                tenant_id=str(dq_run.tenant_id) if dq_run.tenant_id else None,
            )
        except Exception as billing_emit_exc:  # noqa: BLE001 — defence-in-depth
            # ``emit_event`` already catches bus errors internally
            # and returns None. The outer try/except here covers
            # the import path itself (e.g., a circular-import
            # regression that would otherwise crash the pipeline).
            #
            # Audit-fix (240.5.A): include exception details so ops
            # triaging the warning have a one-line root-cause
            # signal — without ``error_type`` an oncall would have
            # to attach a debugger to figure out which import broke.
            logger.warning(
                "billing_emit_outer_guard_tripped",
                dq_run_id=str(dq_run.id),
                error=str(billing_emit_exc),
                error_type=type(billing_emit_exc).__name__,
            )

        # Update asset DQ status if applicable
        if dq_run.asset:
            # Map overall_status to Asset DQ status
            if dq_run.overall_status == "PASS":
                dq_status = AssetDQStatus.PASS
            elif dq_run.overall_status == "WARN":
                dq_status = AssetDQStatus.WARN
            elif dq_run.overall_status == "FAIL":
                dq_status = AssetDQStatus.FAIL
            else:
                dq_status = AssetDQStatus.UNKNOWN

            dq_run.asset.dq_status = dq_status
            dq_run.asset.save(update_fields=["dq_status"])

            # Notify asset owner that DQ run completed
            try:
                from hub.apps.notifications.utils import create_user_notification

                create_user_notification(
                    user=dq_run.created_by if hasattr(dq_run, "created_by") and dq_run.created_by else dq_run.asset.created_by,
                    tenant=dq_run.asset.tenant,
                    title="Data Quality Check Complete",
                    message=f"Data quality check for '{dq_run.asset.name}' completed with status: {dq_run.overall_status or 'UNKNOWN'}.",
                    notification_type="SUCCESS" if dq_status == AssetDQStatus.PASS else "WARNING",
                    category="DATA_QUALITY",
                    resource_type="DQ_RUN",
                    resource_id=str(dq_run.id),
                )
            except Exception:
                pass  # Notifications must never block DQ pipeline

    except Exception as e:
        # Every condition caught here (no file, storage unavailable,
        # dq-service error / circuit-breaker open) is an *expected*
        # operational state that the handler is designed to gracefully
        # transition to FAILED.  WARNING keeps CI output clean while
        # still recording the event for debugging; use exc_info=True
        # so the traceback is preserved at the lower severity.
        logger.warning(
            "dq_run_execute_failed",
            dq_run_id=dq_run_id,
            error=str(e),
            exc_info=True,
        )
        _persist_dq_run_failure_state(
            dq_run_id,
            error_message=str(e),
            error_type=type(e).__name__,
        )
