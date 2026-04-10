"""
DQ Views

REST API views for DQ run management.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import structlog
from django.db import connection, transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from hub.apps.assets.models import Asset
from hub.apps.assets.models import DQStatus as AssetDQStatus
from hub.apps.audit.utils import create_audit_event
from hub.apps.core.responses import api_error_response, handle_service_exception
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.utils import create_job, get_job_timeout
from hub.apps.tenants.request_tenant import get_request_tenant, get_request_tenant_id
from hub.apps.tenants.services import get_tenant_dq_profile

from .models import DQAlertingRule, DQEngine, DQRun, DQRunStatus
from .serializers import (
    DQAlertingRuleCreateSerializer,
    DQAlertingRuleSerializer,
    DQRunCreateSerializer,
    DQRunSerializer,
)
from .service_client import DQServiceClient
from .services import DQService

logger = structlog.get_logger(__name__)


class DQRunViewSet(viewsets.ModelViewSet):
    """
    ViewSet for DQ run management.

    Tenant-scoped: users can only see/manage DQ runs in their tenant.
    """

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

        # Calculate quality score breakdown
        total_checks = len(checks) if checks else 1
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
                extra={"dq_run_id": str(dq_run.id), "error_type": type(e).__name__},
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
                extra={"dq_run_id": str(dq_run.id), "error_type": type(e).__name__},
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


class DQAlertingRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for DQ alerting rule management.

    Tenant-scoped: users can only see/manage alerting rules in their tenant.
    """

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
        dq_client = DQServiceClient()
        result = dq_client.run_dq(
            file_content=file_content, file_format=file_format, profile_key=dq_run.profile_key
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

    except Exception as e:
        logger.exception(
            "dq_run_execute_failed",
            dq_run_id=dq_run_id,
            error=str(e),
        )
        _persist_dq_run_failure_state(
            dq_run_id,
            error_message=str(e),
            error_type=type(e).__name__,
        )
