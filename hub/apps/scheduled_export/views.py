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
    payload = {
        "scheduled_export_id": str(scheduled_export.id),
        "tenant_id": str(tenant.id),
    }
    try:
        import requests

        resp = requests.post(url, json=payload, timeout=timeout_seconds)
        if resp.ok:
            data = resp.json()
            deployment_id = data.get("deployment_id") if isinstance(data, dict) else None
            if deployment_id:
                # Note: ScheduledExport model doesn't have prefect_deployment_id field yet
                # We can store it in a future update if needed
                logger.info(
                    "Prefect deployment created for scheduled export %s: %s",
                    scheduled_export.id,
                    deployment_id,
                )
            return True
        logger.warning(
            "Prefect integration service sync failed for scheduled export %s: %s %s",
            scheduled_export.id,
            resp.status_code,
            resp.text[:200],
        )
        return False
    except Exception as e:
        logger.warning(
            "Prefect integration service sync error for scheduled export %s: %s",
            scheduled_export.id,
            e,
            exc_info=True,
        )
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
    payload = {
        "scheduled_export_id": str(scheduled_export.id),
        "tenant_id": str(tenant.id),
        "parameters": parameters or {},
    }
    try:
        import requests

        resp = requests.post(url, json=payload, timeout=timeout_seconds)
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
        """Filter queryset by tenant and optional status"""
        if self.request.user.is_platform_admin:
            queryset = ScheduledExport.objects.all()
        else:
            # Use central helper for tenant resolution (Phase 21)
            tenant_id = get_request_tenant_id(self.request)
            if tenant_id:
                queryset = ScheduledExport.objects.filter(tenant_id=tenant_id)
            else:
                return ScheduledExport.objects.none()

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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Use central helper for tenant resolution (Phase 21)
        tenant_id, tenant = get_request_tenant(request)
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
        # Use HTTP API approach (like scheduled ingestion) to avoid requiring prefect in api-service
        # Use on_commit to ensure sync happens after transaction commits (so prefect-integration-service can find the export)
        transaction.on_commit(
            lambda: _sync_deployment_via_prefect_integration_service(
                scheduled_export, tenant, timeout_seconds=15
            )
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
        return Response(
            ScheduledExportSerializer(scheduled_export).data,
            status=status.HTTP_201_CREATED,
        )

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
        return Response(ScheduledExportSerializer(scheduled_export).data)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """Delete scheduled export via service."""
        instance = self.get_object()

        # Use central helper for tenant resolution (Phase 21)
        tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            tenant = instance.tenant

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

                # Trigger status sync in background to update run status if flow crashes quickly
                # This helps handle cases where Docker times out during container creation
                try:
                    import os
                    from threading import Thread

                    import requests

                    def trigger_status_sync():
                        base_url = os.getenv("PREFECT_INTEGRATION_SERVICE_URL", "").rstrip("/")
                        if base_url:
                            try:
                                requests.post(f"{base_url}/status/sync", timeout=5)
                            except Exception:
                                pass  # Don't fail trigger if status sync fails

                    # Trigger status sync in background thread (non-blocking)
                    Thread(target=trigger_status_sync, daemon=True).start()
                except Exception:
                    pass  # Don't fail trigger if status sync trigger fails

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
