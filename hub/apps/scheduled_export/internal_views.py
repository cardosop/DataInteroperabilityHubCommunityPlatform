"""
Internal Worker API Views

Run lifecycle, process-export, and config endpoints for the Prefect worker.
All require worker authentication (HUB_WORKER_API_KEY or API key with scope scheduled_export:internal).
"""

import logging

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
)
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from hub.apps.audit.utils import create_audit_event
from hub.apps.observability.otel_metrics import (
    scheduled_export_duration_seconds,
    scheduled_export_items_exported_total,
    scheduled_export_items_failed_total,
    scheduled_export_runs_running,
    scheduled_export_runs_total,
)

from .internal_auth import WorkerAPIKeyAuthentication, WorkerInternalAPIPermission
from .internal_serializers import (
    InternalCreateRunSerializer,
    InternalProcessExportSerializer,
    InternalUpdateRunSerializer,
)
from .models import (
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from .services import ScheduledExportService

logger = logging.getLogger(__name__)


# Scope for internal API (used when resolving tenant from request)
def _get_tenant_id(request):
    return getattr(request, "tenant_id", None) or (
        str(request.tenant.id) if getattr(request, "tenant", None) else None
    )


def _get_tenant(request):
    return getattr(request, "tenant", None) or (
        getattr(request.user, "tenant", None) if request.user else None
    )


@extend_schema(
    tags=["Internal (Worker)"],
    summary="Internal Worker API - Scheduled Export Run Lifecycle",
    description=(
        "Internal API endpoints for Prefect worker to manage scheduled export runs. "
        "These endpoints are worker-only and require worker authentication (HUB_WORKER_API_KEY or API key with scope scheduled_export:internal). "
        "Rate limiting: No rate limit (internal worker endpoints)."
    ),
)
class InternalRunViewSet(ViewSet):
    """
    Internal run lifecycle: create run (POST), update run (PATCH).
    Worker-only; tenant and ownership validated on every request.
    """

    authentication_classes = [WorkerAPIKeyAuthentication]
    permission_classes = [IsAuthenticated, WorkerInternalAPIPermission]

    @extend_schema(
        summary="Create scheduled export run",
        description=(
            "Create a new scheduled export run with status RUNNING. "
            "Idempotent by idempotency_key or prefect_flow_run_id. "
            "Requires worker authentication and X-Tenant-ID header."
        ),
        request=InternalCreateRunSerializer,
        responses={
            201: OpenApiResponse(description="Run created successfully"),
            200: OpenApiResponse(description="Run already exists (idempotent replay)"),
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Forbidden (tenant mismatch)"),
            404: OpenApiResponse(description="Scheduled export not found"),
        },
    )
    def create(self, request):
        """POST .../internal/runs/ — create ScheduledExportRun (status RUNNING). Idempotent by idempotency_key or prefect_flow_run_id."""
        serializer = InternalCreateRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tenant_id = _get_tenant_id(request)
        if not tenant_id:
            return Response(
                {"error": "Tenant required", "code": "TENANT_REQUIRED", "details": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        scheduled_export_id = str(data["scheduled_export_id"])
        prefect_flow_run_id = data.get("prefect_flow_run_id") or ""
        idempotency_key = data.get("idempotency_key") or ""

        try:
            scheduled_export = ScheduledExport.objects.get(id=scheduled_export_id)
        except ScheduledExport.DoesNotExist:
            return Response(
                {
                    "error": "Scheduled export not found",
                    "code": "NOT_FOUND",
                    "details": {"scheduled_export_id": scheduled_export_id},
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        if str(scheduled_export.tenant_id) != tenant_id:
            return Response(
                {
                    "error": "Scheduled export does not belong to tenant",
                    "code": "FORBIDDEN",
                    "details": {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Idempotency: existing run with same prefect_flow_run_id or idempotency_key
        if prefect_flow_run_id:
            existing = ScheduledExportRun.objects.filter(
                scheduled_export=scheduled_export,
                prefect_flow_run_id=prefect_flow_run_id,
            ).first()
            if existing:
                return Response(
                    {
                        "id": str(existing.id),
                        "scheduled_export_id": scheduled_export_id,
                        "status": existing.status,
                        "prefect_flow_run_id": existing.prefect_flow_run_id or prefect_flow_run_id,
                    },
                    status=status.HTTP_200_OK,
                )
        existing = None
        if idempotency_key:
            for r in ScheduledExportRun.objects.filter(scheduled_export=scheduled_export).order_by(
                "-created_at"
            )[:100]:
                if (r.result_json or {}).get("idempotency_key") == idempotency_key:
                    existing = r
                    break
            if existing:
                return Response(
                    {
                        "id": str(existing.id),
                        "scheduled_export_id": scheduled_export_id,
                        "status": existing.status,
                    },
                    status=status.HTTP_200_OK,
                )

        # Use service to create run (handles idempotency internally)
        service = ScheduledExportService(
            tenant_id=tenant_id, user_id=str(request.user.id) if request.user else None
        )
        run = service.create_export_run(
            scheduled_export_id=scheduled_export_id,
            tenant_id=tenant_id,
            user_id=str(request.user.id) if request.user else None,
            prefect_flow_run_id=prefect_flow_run_id or None,
            idempotency_key=idempotency_key or None,
        )

        # Set started_at for new run
        if not run.started_at:
            run.started_at = timezone.now()
            run.save(update_fields=["started_at"])

        try:
            scheduled_export_runs_total.labels(
                status="RUNNING",
                scheduled_export_id=scheduled_export_id,
                tenant_id=tenant_id,
            ).inc(1)
            scheduled_export_runs_running.labels(
                scheduled_export_id=scheduled_export_id,
                tenant_id=tenant_id,
            ).inc(1)
        except Exception as e:
            logger.warning("Failed to emit run-created metrics: %s", e)

        tenant = _get_tenant(request)
        create_audit_event(
            resource_type="SCHEDULED_EXPORT_RUN",
            action="CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(run.id),
            details={
                "scheduled_export_id": scheduled_export_id,
                "status": run.status,
                "prefect_flow_run_id": prefect_flow_run_id or None,
            },
        )

        return Response(
            {
                "id": str(run.id),
                "scheduled_export_id": scheduled_export_id,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "prefect_flow_run_id": run.prefect_flow_run_id,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Update scheduled export run",
        description=(
            "Update a scheduled export run (status, item counts, result_json, completed_at, etc.). "
            "When status changes to COMPLETED or FAILED, side effects are triggered (next_run_at calculation, "
            "cost tracking, domain events). "
            "Requires worker authentication and X-Tenant-ID header."
        ),
        request=InternalUpdateRunSerializer,
        responses={
            200: OpenApiResponse(description="Run updated successfully"),
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Forbidden (tenant mismatch)"),
            404: OpenApiResponse(description="Run not found"),
        },
    )
    def partial_update(self, request, pk=None):
        """PATCH .../internal/runs/{run_id}/ — update status, counts, result_json, completed_at."""
        tenant_id = _get_tenant_id(request)
        if not tenant_id:
            return Response(
                {"error": "Tenant required", "code": "TENANT_REQUIRED", "details": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            run = ScheduledExportRun.objects.select_related("scheduled_export").get(id=pk)
        except ScheduledExportRun.DoesNotExist:
            return Response(
                {"error": "Run not found", "code": "NOT_FOUND", "details": {"run_id": pk}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if str(run.scheduled_export.tenant_id) != tenant_id:
            return Response(
                {"error": "Run does not belong to tenant", "code": "FORBIDDEN", "details": {}},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = InternalUpdateRunSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        old_status = run.status

        # Use service to update run
        service = ScheduledExportService(
            tenant_id=tenant_id, user_id=str(request.user.id) if request.user else None
        )

        # Prepare completed_at ISO string if provided
        completed_at_iso = None
        if "completed_at" in data and data["completed_at"]:
            if hasattr(data["completed_at"], "isoformat"):
                completed_at_iso = data["completed_at"].isoformat()
            else:
                completed_at_iso = str(data["completed_at"])

        # Update run via service
        updated_run = service.update_export_run(
            run_id=str(run.id),
            tenant_id=tenant_id,
            user_id=str(request.user.id) if request.user else None,
            status=data.get("status"),
            items_found=data.get("items_found"),
            items_exported=data.get("items_exported"),
            items_failed=data.get("items_failed"),
            result_json=data.get("result_json"),
            completed_at=completed_at_iso,
            prefect_flow_run_id=data.get("prefect_flow_run_id"),
        )

        # Refresh run from DB
        run.refresh_from_db()
        new_status = data.get("status") or old_status

        # Apply run completion side effects if status changed to COMPLETED or FAILED
        if new_status in ("COMPLETED", "FAILED") and new_status != old_status:
            from .worker_run_lifecycle import apply_run_completion_side_effects

            apply_run_completion_side_effects(run, new_status)

        scheduled_export_id = str(run.scheduled_export_id)
        if new_status != old_status and new_status in ("COMPLETED", "FAILED", "CANCELLED"):
            try:
                duration = (
                    (run.completed_at - run.started_at).total_seconds()
                    if run.completed_at and run.started_at
                    else 0
                )
                scheduled_export_runs_total.labels(
                    status=new_status,
                    scheduled_export_id=scheduled_export_id,
                    tenant_id=tenant_id,
                ).inc(1)
                scheduled_export_duration_seconds.labels(
                    scheduled_export_id=scheduled_export_id,
                    status=new_status,
                    tenant_id=tenant_id,
                ).observe(duration)
                scheduled_export_runs_running.labels(
                    scheduled_export_id=scheduled_export_id,
                    tenant_id=tenant_id,
                ).dec(1)
            except Exception as e:
                logger.warning("Failed to emit run-completion metrics: %s", e)

        tenant = _get_tenant(request)
        create_audit_event(
            resource_type="SCHEDULED_EXPORT_RUN",
            action="UPDATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(run.id),
            details={
                "status": new_status,
                "items_exported": run.items_exported,
                "items_failed": run.items_failed,
            },
        )

        return Response(
            {
                "id": str(run.id),
                "status": run.status,
                "items_found": run.items_found,
                "items_exported": run.items_exported,
                "items_failed": run.items_failed,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Internal (Worker)"],
    summary="Process export item for scheduled export run",
    description=(
        "Process a single export item (dataset or file) for a scheduled export run. "
        "Validates run and tenant, applies business rules (scope, access), prepares payload or signed URL. "
        "Returns success with upload instructions or structured error. "
        "Requires worker authentication and X-Tenant-ID header. "
        "Rate limiting: No rate limit (internal worker endpoints)."
    ),
    request=InternalProcessExportSerializer,
    responses={
        200: OpenApiResponse(description="Export item processed successfully"),
        400: OpenApiResponse(description="Validation error"),
        401: OpenApiResponse(description="Authentication required"),
        403: OpenApiResponse(description="Forbidden (tenant mismatch)"),
        404: OpenApiResponse(description="Run or item not found"),
    },
)
class InternalProcessExportView(APIView):
    """POST .../internal/process-export/ — process one export item (validate, apply business rules, prepare upload)."""

    authentication_classes = [WorkerAPIKeyAuthentication]
    permission_classes = [IsAuthenticated, WorkerInternalAPIPermission]

    def post(self, request):
        tenant_id = _get_tenant_id(request)
        if not tenant_id:
            return Response(
                {"error": "Tenant required", "code": "TENANT_REQUIRED", "details": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = InternalProcessExportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        run_id = str(data["run_id"])
        dataset_id = str(data["dataset_id"]) if data.get("dataset_id") else None
        file_id = str(data["file_id"]) if data.get("file_id") else None
        destination_path = data.get("destination_path")
        destination_options = data.get("destination_options") or {}

        try:
            run = ScheduledExportRun.objects.select_related("scheduled_export").get(id=run_id)
        except ScheduledExportRun.DoesNotExist:
            return Response(
                {"error": "Run not found", "code": "NOT_FOUND", "details": {"run_id": run_id}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if str(run.scheduled_export.tenant_id) != tenant_id:
            return Response(
                {"error": "Run does not belong to tenant", "code": "FORBIDDEN", "details": {}},
                status=status.HTTP_403_FORBIDDEN,
            )

        scheduled_export_id = str(run.scheduled_export_id)

        # Process export item using service
        service = ScheduledExportService(
            tenant_id=tenant_id, user_id=str(request.user.id) if request.user else None
        )

        try:
            result = service.process_export_item(
                run_id=run_id,
                dataset_id=dataset_id,
                file_id=file_id,
                destination_path=destination_path,
                destination_options=destination_options,
                tenant_id=tenant_id,
                user_id=str(request.user.id) if request.user else None,
            )
        except Exception as e:
            logger.exception("process_export_item failed")
            try:
                scheduled_export_items_failed_total.labels(
                    scheduled_export_id=scheduled_export_id,
                    tenant_id=tenant_id,
                ).inc(1)
            except Exception as m:
                logger.warning("Failed to emit process-export failure metrics: %s", m)

            error_code = getattr(e, "code", "INTERNAL_ERROR")
            error_details = getattr(e, "details", {})
            return Response(
                {"error": str(e), "code": error_code, "details": error_details},
                status=(
                    status.HTTP_400_BAD_REQUEST
                    if error_code != "NOT_FOUND"
                    else status.HTTP_404_NOT_FOUND
                ),
            )

        tenant = _get_tenant(request)
        create_audit_event(
            resource_type="SCHEDULED_EXPORT_ITEM",
            action="PROCESSED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=result.get("item_id", ""),
            details={
                "run_id": run_id,
                "item_id": result.get("item_id"),
                "item_type": result.get("item_type"),
                "destination_type": result.get("destination_type"),
            },
        )

        try:
            scheduled_export_items_exported_total.labels(
                scheduled_export_id=scheduled_export_id,
                tenant_id=tenant_id,
            ).inc(1)
        except Exception as e:
            logger.warning("Failed to emit process-export success metrics: %s", e)

        return Response(result, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Internal (Worker)"],
    summary="Get scheduled export configuration",
    description=(
        "Get configuration for a scheduled export (destination_type, destination_config with masked credentials, "
        "source_scope, schedule_config, etc.). Credentials in destination_config are masked "
        "for security. Requires worker authentication and X-Tenant-ID header. "
        "Rate limiting: No rate limit (internal worker endpoints)."
    ),
    responses={
        200: OpenApiResponse(
            description="Configuration retrieved successfully (credentials masked)"
        ),
        401: OpenApiResponse(description="Authentication required"),
        403: OpenApiResponse(description="Forbidden (tenant mismatch)"),
        404: OpenApiResponse(description="Scheduled export not found"),
    },
)
class InternalConfigView(APIView):
    """GET .../internal/config/{scheduled_export_id}/ — config for worker (credentials masked)."""

    authentication_classes = [WorkerAPIKeyAuthentication]
    permission_classes = [IsAuthenticated, WorkerInternalAPIPermission]

    def get(self, request, scheduled_export_id):
        tenant_id = _get_tenant_id(request)
        if not tenant_id:
            return Response(
                {"error": "Tenant required", "code": "TENANT_REQUIRED", "details": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            se = ScheduledExport.objects.get(id=scheduled_export_id)
        except ScheduledExport.DoesNotExist:
            return Response(
                {"error": "Scheduled export not found", "code": "NOT_FOUND", "details": {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if str(se.tenant_id) != tenant_id:
            return Response(
                {
                    "error": "Scheduled export does not belong to tenant",
                    "code": "FORBIDDEN",
                    "details": {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        from .credential_manager import CredentialManager

        masked_destination_config = CredentialManager.get_masked_credentials(se)
        payload = {
            "destination_type": se.destination_type,
            "destination_config": masked_destination_config,
            "source_scope": se.source_scope,
            "schedule_config": se.schedule_config,
        }
        return Response(payload, status=status.HTTP_200_OK)
