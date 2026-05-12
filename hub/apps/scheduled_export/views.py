"""
Scheduled Export Views

DRF viewsets for scheduled export API endpoints.
"""

import logging

from django.db import transaction

logger = logging.getLogger(__name__)
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hub.apps.audit.utils import create_audit_event
from hub.apps.core.responses import handle_service_exception
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.core.utils.prefect_deployment import delete_prefect_deployment
from hub.apps.tenants.request_tenant import get_request_tenant, get_request_tenant_id

from .models import (
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from .serializers import (
    ScheduledExportCreateSerializer,
    ScheduledExportRunSerializer,
    ScheduledExportSerializer,
    ScheduledExportTriggerSerializer,
)
from .services import ScheduledExportService

logger = logging.getLogger(__name__)


def _sync_deployment_via_prefect_integration_service(scheduled_export, tenant, timeout_seconds=15):
    """
    Call prefect-integration-service POST /deployments/sync to create/update the Prefect deployment.
    Returns True if sync succeeded (2xx), False otherwise. Used so deployment is created in the service
    that has the flow and connectors (avoids ImportError when hub runs in-process sync).
    """
    import os

    base_url = os.getenv("PREFECT_INTEGRATION_SERVICE_URL", "").rstrip("/")
    if not base_url:
        return False
    url = f"{base_url}/deployments/sync"
    headers = {"X-Internal-Api-Key": os.getenv("INTERNAL_API_KEY", "")}
    payload = {
        "scheduled_export_id": str(scheduled_export.id),
        "tenant_id": str(tenant.id),
        "schedule_config": scheduled_export.schedule_config or {},
    }
    try:
        import requests

        resp = requests.post(url, json=payload, headers=headers, timeout=timeout_seconds)
        if resp.ok:
            data = resp.json()
            deployment_id = data.get("deployment_id") if isinstance(data, dict) else None
            update_fields = ["deployment_sync_status"]
            scheduled_export.deployment_sync_status = "SYNCED"
            if deployment_id:
                scheduled_export.prefect_deployment_id = deployment_id
                update_fields.append("prefect_deployment_id")
            scheduled_export.save(update_fields=update_fields)
            return True
        logger.warning(
            "Prefect integration service sync failed for scheduled export %s: %s %s",
            scheduled_export.id,
            resp.status_code,
            resp.text[:200],
        )
        scheduled_export.deployment_sync_status = "FAILED"
        scheduled_export.save(update_fields=["deployment_sync_status"])
        return False
    except Exception as e:
        logger.warning(
            "Prefect integration service sync error for scheduled export %s: %s",
            scheduled_export.id,
            e,
            exc_info=True,
        )
        scheduled_export.deployment_sync_status = "FAILED"
        scheduled_export.save(update_fields=["deployment_sync_status"])
        return False


def _trigger_deployment_via_prefect_integration_service(
    scheduled_export, tenant, parameters=None, timeout_seconds=15
):
    """
    Call prefect-integration-service POST /deployments/trigger to trigger a Prefect deployment.
    Returns (success: bool, flow_run_id: str | None, error: str | None).
    Used so deployment triggering happens in the service that has Prefect installed.
    """
    import os

    base_url = os.getenv("PREFECT_INTEGRATION_SERVICE_URL", "").rstrip("/")
    if not base_url:
        return False, None, "PREFECT_INTEGRATION_SERVICE_URL not configured"
    url = f"{base_url}/deployments/trigger"
    headers = {"X-Internal-Api-Key": os.getenv("INTERNAL_API_KEY", "")}
    payload = {
        "scheduled_export_id": str(scheduled_export.id),
        "tenant_id": str(tenant.id),
        "parameters": parameters or {},
    }
    try:
        import requests

        resp = requests.post(url, json=payload, headers=headers, timeout=timeout_seconds)
        if resp.ok:
            data = resp.json()
            flow_run_id = data.get("flow_run_id") if isinstance(data, dict) else None
            if flow_run_id:
                logger.info(
                    "Prefect deployment triggered for scheduled export %s: flow_run_id=%s",
                    scheduled_export.id,
                    flow_run_id,
                )
            return True, flow_run_id, None
        error_msg = resp.text[:500] if resp.text else f"HTTP {resp.status_code}"
        logger.warning(
            "Prefect integration service trigger failed for scheduled export %s: %s %s",
            scheduled_export.id,
            resp.status_code,
            error_msg,
        )
        return False, None, error_msg
    except Exception as e:
        logger.warning(
            "Prefect integration service trigger error for scheduled export %s: %s",
            scheduled_export.id,
            e,
            exc_info=True,
        )
        return False, None, str(e)


@extend_schema_view(
    list=extend_schema(
        summary="List scheduled exports",
        description="List all scheduled exports for the authenticated user's tenant with filtering and pagination.",
        tags=["Scheduled Exports"],
    ),
    retrieve=extend_schema(
        summary="Get scheduled export details",
        description="Get detailed information about a specific scheduled export.",
        tags=["Scheduled Exports"],
    ),
    create=extend_schema(
        summary="Create scheduled export",
        description="Create a new scheduled export.",
        tags=["Scheduled Exports"],
    ),
    update=extend_schema(
        summary="Update scheduled export",
        description="Update an existing scheduled export.",
        tags=["Scheduled Exports"],
    ),
    partial_update=extend_schema(
        summary="Partially update scheduled export",
        description="Partially update an existing scheduled export.",
        tags=["Scheduled Exports"],
    ),
    destroy=extend_schema(
        summary="Delete scheduled export",
        description="Delete a scheduled export.",
        tags=["Scheduled Exports"],
    ),
)
class ScheduledExportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for scheduled export management.

    Provides CRUD operations and additional actions for scheduled exports.
    """

    serializer_class = ScheduledExportSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        """Filter queryset by tenant and optional status, excluding soft-deleted records."""
        if self.request.user.is_platform_admin:
            queryset = ScheduledExport.objects.all()
        else:
            # Use central helper for tenant resolution (Phase 21)
            tenant_id = get_request_tenant_id(self.request)
            if tenant_id:
                queryset = ScheduledExport.objects.filter(tenant_id=tenant_id)
            else:
                return ScheduledExport.objects.none()

        # Phase 25.9.1 — Exclude soft-deleted records from listings
        queryset = queryset.exclude(status=ScheduledExportStatus.DELETED)

        # Filter by status if provided
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action == "create":
            return ScheduledExportCreateSerializer
        return ScheduledExportSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create scheduled export via service (validates via ScheduledExportBusinessRules)."""
        # Phase 275.E.3l — Idempotency-Key support for retried writes.
        idempotency_key = request.META.get("HTTP_IDEMPOTENCY_KEY") or request.headers.get("Idempotency-Key")
        if idempotency_key:
            existing = ScheduledExport.objects.filter(
                tenant=request.user.tenant,
                metadata_json__idempotency_key=idempotency_key,
            ).first()
            if existing:
                serializer = self.get_serializer(existing)
                return Response(serializer.data, status=status.HTTP_200_OK)

        # Fail-fast: check plan limit BEFORE expensive serializer validation.
        tenant_id, tenant = get_request_tenant(request)
        if tenant:
            from hub.apps.tenants.services import PlanLimitService
            from hub.apps.core.services.base import ValidationError as SvcValidationError
            from django.db import transaction as db_transaction
            try:
                plan_svc = PlanLimitService(tenant_id=str(tenant.id))
                with db_transaction.atomic():
                    plan_svc.check_limit(
                        tenant_id=str(tenant.id),
                        limit_key="max_scheduled_exports",
                        delta=1,
                    )
            except SvcValidationError as plan_err:
                if plan_err.code == "plan_limit_exceeded":
                    return Response(
                        {
                            "error": plan_err.message,
                            "code": plan_err.code,
                            "details": plan_err.details or {},
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
            except Exception:
                pass  # Non-limit errors: let serializer/service handle

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # tenant already resolved above
        if not tenant:
            return Response(
                {"error": "Tenant is required", "code": "TENANT_REQUIRED", "details": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data
        service = ScheduledExportService(tenant_id=str(tenant.id), user_id=str(request.user.id))
        try:
            scheduled_export = service.create_scheduled_export(
                tenant=tenant,
                created_by=request.user,
                **data,
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)

        # Create Prefect deployment via prefect-integration-service HTTP API
        # This is optional - if Prefect is not available, scheduled export is still created
        # Run sync synchronously: we pass schedule_config in the request so prefect-integration
        # does not need to fetch from DB; on_commit would not run in test transactions (never commit)
        _sync_deployment_via_prefect_integration_service(
            scheduled_export, tenant, timeout_seconds=15
        )

        create_audit_event(
            resource_type="SCHEDULED_EXPORT",
            action="CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(scheduled_export.id),
            details={
                "scheduled_export_id": str(scheduled_export.id),
                "name": scheduled_export.name,
                "destination_type": scheduled_export.destination_type,
                "status": scheduled_export.status,
            },
        )
        # Phase 25.5.1 — Return 207 Multi-Status when resource is created
        # but deployment sync failed.
        scheduled_export.refresh_from_db()
        resource_data = ScheduledExportSerializer(scheduled_export).data
        if scheduled_export.deployment_sync_status == "FAILED":
            return Response(
                {
                    "resource": resource_data,
                    "deployment_sync": {
                        "status": "failed",
                        "error": "Prefect deployment sync failed; call POST /{id}/sync/ to retry",
                    },
                },
                status=207,
            )
        return Response(resource_data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update scheduled export via service (validates via ScheduledExportBusinessRules)."""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # Use central helper for tenant resolution (Phase 21)
        tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            tenant = instance.tenant

        data = serializer.validated_data
        service = ScheduledExportService(tenant_id=str(tenant.id), user_id=str(request.user.id))

        try:
            scheduled_export = service.update_scheduled_export(
                scheduled_export_id=str(instance.id),
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                **data,
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)

        # Phase 25.5.1 — Re-sync Prefect deployment on update
        _sync_deployment_via_prefect_integration_service(
            scheduled_export, tenant, timeout_seconds=15
        )

        create_audit_event(
            resource_type="SCHEDULED_EXPORT",
            action="UPDATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(scheduled_export.id),
            details={
                "scheduled_export_id": str(scheduled_export.id),
                "name": scheduled_export.name,
                "status": scheduled_export.status,
            },
        )
        scheduled_export.refresh_from_db()
        resource_data = ScheduledExportSerializer(scheduled_export).data
        if scheduled_export.deployment_sync_status == "FAILED":
            return Response(
                {
                    "resource": resource_data,
                    "deployment_sync": {
                        "status": "failed",
                        "error": "Prefect deployment sync failed; call POST /{id}/sync/ to retry",
                    },
                },
                status=207,
            )
        return Response(resource_data)

    def destroy(self, request, *args, **kwargs):
        """
        Phase 25.9.1 — Ordered delete: remove Prefect deployment *before* DB record.

        1. If the instance has a prefect_deployment_id, call the integration
           service to delete the deployment first.
        2. If that call fails, mark the record status=DELETED (soft-delete) so
           the hourly purge CronJob can retry, and return HTTP 409 Conflict.
        3. Only hard-delete the DB record after a successful deployment delete.
        """
        instance = self.get_object()
        tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            tenant = instance.tenant

        # --- Step 1: delete Prefect deployment first ---
        if instance.prefect_deployment_id:
            deployment_deleted = delete_prefect_deployment(
                deployment_id=str(instance.prefect_deployment_id),
                resource_id=str(instance.id),
                resource_type="scheduled_export",
                tenant_id=str(tenant.id),
            )
            if not deployment_deleted:
                # Soft-delete: mark as DELETED so the purge CronJob can retry
                ScheduledExport.objects.filter(pk=instance.pk).update(
                    status=ScheduledExportStatus.DELETED,
                )
                create_audit_event(
                    resource_type="SCHEDULED_EXPORT",
                    action="DELETE_BLOCKED",
                    actor_user=request.user,
                    tenant=tenant,
                    resource_id=str(instance.id),
                    details={
                        "reason": "prefect_deployment_delete_failed",
                        "prefect_deployment_id": str(instance.prefect_deployment_id),
                    },
                )
                return Response(
                    {"error": "prefect_deployment_delete_failed"},
                    status=status.HTTP_409_CONFLICT,
                )
            # Deployment deleted — clear the reference
            ScheduledExport.objects.filter(pk=instance.pk).update(
                prefect_deployment_id=None,
                deployment_sync_status="PENDING",
            )

        # --- Step 2: hard-delete DB record via service layer ---
        service = ScheduledExportService(tenant_id=str(tenant.id), user_id=str(request.user.id))
        try:
            service.delete_scheduled_export(
                scheduled_export_id=str(instance.id),
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        operation_id="scheduled_export_runs",
        responses={200: ScheduledExportRunSerializer(many=True)},
        tags=["Scheduled Exports"],
    )
    @action(detail=True, methods=["get"])
    def runs(self, request, id=None):
        """
        List runs for a scheduled export.
        """
        scheduled_export = self.get_object()
        runs = ScheduledExportRun.objects.filter(scheduled_export=scheduled_export).order_by(
            "-created_at"
        )

        serializer = ScheduledExportRunSerializer(runs, many=True)
        return Response(serializer.data)

    @extend_schema(
        operation_id="scheduled_export_sync",
        request=None,
        responses={
            200: ScheduledExportSerializer,
            503: inline_serializer(
                name="ScheduledExportSyncUnavailable",
                fields={
                    "error": serializers.CharField(),
                    "deployment_sync_status": serializers.CharField(),
                },
            ),
        },
        tags=["Scheduled Exports"],
    )
    @action(detail=True, methods=["post"], url_path="sync")
    def sync(self, request, id=None):
        """
        Phase 25.5.3 — Idempotent retry endpoint for Prefect deployment sync.

        Re-calls the integration service /deployments/sync.  Updates
        deployment_sync_status and prefect_deployment_id.
        Returns 200 on success, 400 when not configured, 503 on service failure.
        """
        import os as _os

        base_url = _os.getenv("PREFECT_INTEGRATION_SERVICE_URL", "")
        if not base_url:
            return Response(
                {
                    "error": "PREFECT_INTEGRATION_SERVICE_URL not configured",
                    "deployment_sync_status": "PENDING",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        scheduled_export = self.get_object()
        tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            tenant = scheduled_export.tenant

        sync_ok = _sync_deployment_via_prefect_integration_service(
            scheduled_export, tenant, timeout_seconds=15
        )

        scheduled_export.refresh_from_db()
        if sync_ok:
            return Response(
                ScheduledExportSerializer(scheduled_export).data,
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "error": "Prefect integration service sync failed",
                "deployment_sync_status": scheduled_export.deployment_sync_status,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    @extend_schema(
        operation_id="scheduled_export_trigger",
        request=ScheduledExportTriggerSerializer,
        responses={
            200: inline_serializer(
                name="ScheduledExportTriggerResponse",
                fields={
                    "scheduled_export_id": serializers.UUIDField(),
                    "flow_run_id": serializers.CharField(),
                    "status": serializers.CharField(),
                    "message": serializers.CharField(),
                },
            )
        },
        tags=["Scheduled Exports"],
    )
    @action(detail=True, methods=["post"])
    def trigger(self, request, id=None):
        """
        Manually trigger a scheduled export.

        Creates a Prefect flow run for the scheduled export.
        """
        scheduled_export = self.get_object()
        if scheduled_export.status != ScheduledExportStatus.ACTIVE:
            return Response(
                {
                    "error": "Scheduled export is not active. Only active exports can be triggered.",
                    "code": "INVALID_STATUS",
                    "details": {"status": scheduled_export.status},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ScheduledExportTriggerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        parameters = serializer.validated_data.get("parameters", {})

        try:
            # Trigger deployment via prefect-integration-service HTTP API
            # This avoids requiring prefect library in api-service
            tenant_id, tenant = get_request_tenant(request)
            if not tenant:
                tenant = scheduled_export.tenant

            success, flow_run_id, error_msg = _trigger_deployment_via_prefect_integration_service(
                scheduled_export, tenant, parameters=parameters, timeout_seconds=15
            )

            if not success:
                # Check if it's a deployment not found error
                if error_msg and (
                    "not found" in error_msg.lower()
                    or "404" in error_msg
                    or "deployment" in error_msg.lower()
                ):
                    return Response(
                        {
                            "error": f"Prefect deployment not found for scheduled export {scheduled_export.id}",
                            "code": "DEPLOYMENT_NOT_FOUND",
                            "details": {"error": error_msg},
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )
                # Other errors
                return Response(
                    {
                        "error": f"Failed to trigger export: {error_msg or 'Unknown error'}",
                        "code": "TRIGGER_FAILED",
                        "details": {"error": error_msg},
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            if flow_run_id:
                # Create run record with RUNNING status (Prefect will update it later)
                run = ScheduledExportRun.objects.create(
                    scheduled_export=scheduled_export,
                    tenant=scheduled_export.tenant,
                    status=ScheduledExportRunStatus.RUNNING,
                    prefect_flow_run_id=flow_run_id,
                    started_at=timezone.now(),
                )

                # Phase 25.6.1 — Enqueue status sync via RQ instead of
                # background thread (threads leak ORM contexts, swallow
                # exceptions, and bypass request tracing).
                try:
                    from hub.apps.jobs.tasks_prefect_sync import (
                        enqueue_prefect_status_sync,
                    )
                    transaction.on_commit(
                        lambda frid=flow_run_id, rid=str(run.id): enqueue_prefect_status_sync(
                            flow_run_id=frid,
                            resource_id=rid,
                            resource_type="scheduled_export",
                        )
                    )
                except Exception:
                    pass  # Don't fail trigger if enqueue fails

                create_audit_event(
                    resource_type="SCHEDULED_EXPORT",
                    action="TRIGGERED",
                    actor_user=request.user,
                    tenant=scheduled_export.tenant,
                    resource_id=str(scheduled_export.id),
                    details={"run_id": str(run.id), "flow_run_id": flow_run_id},
                )
                return Response(
                    {
                        "scheduled_export_id": str(scheduled_export.id),
                        "run_id": str(run.id),
                        "scheduled_export_run_id": str(run.id),
                        "flow_run_id": flow_run_id,
                        "status": "success",
                        "message": f"Export {scheduled_export.name} triggered successfully",
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {
                        "error": "Failed to trigger export: no flow_run_id returned",
                        "code": "TRIGGER_FAILED",
                        "details": {},
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            logger.error(
                "Failed to trigger scheduled export %s: %s",
                scheduled_export.id,
                str(e),
                exc_info=True,
            )
            return Response(
                {
                    "error": f"Failed to trigger export: {str(e)}",
                    "code": "INTERNAL_ERROR",
                    "details": {},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    retrieve=extend_schema(
        summary="Get scheduled export run details",
        description="Get detailed information about a specific scheduled export run.",
        tags=["Scheduled Export Runs"],
    ),
    list=extend_schema(
        summary="List scheduled export runs",
        description="List all scheduled export runs for the authenticated user's tenant with filtering and pagination.",
        tags=["Scheduled Export Runs"],
    ),
)
class ScheduledExportRunViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for scheduled export runs.
    """

    serializer_class = ScheduledExportRunSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        """Filter queryset by tenant"""
        if self.request.user.is_platform_admin:
            return ScheduledExportRun.objects.all()

        # Use central helper for tenant resolution (Phase 21)
        tenant_id = get_request_tenant_id(self.request)
        if tenant_id:
            return ScheduledExportRun.objects.filter(scheduled_export__tenant_id=tenant_id)

        return ScheduledExportRun.objects.none()
