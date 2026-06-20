"""
Internal Worker API Views

Run lifecycle, process-file, and config endpoints for the Prefect worker.
All require worker authentication (HUB_WORKER_API_KEY or API key with scope scheduled_ingestion:internal).
"""

import base64
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
from hub.apps.jobs.models import Job
from hub.apps.observability.otel_metrics import (
    scheduled_ingestion_datasets_created_total,
    scheduled_ingestion_duration_seconds,
    scheduled_ingestion_files_failed_total,
    scheduled_ingestion_files_processed_total,
    scheduled_ingestion_runs_running,
    scheduled_ingestion_runs_total,
)

from .internal_auth import WorkerAPIKeyAuthentication, WorkerInternalAPIPermission
from .internal_serializers import (
    InternalCreateIngestionRunSerializer,
    InternalCreateJobSerializer,
    InternalProcessFileSerializer,
    InternalUpdateIngestionRunSerializer,
)
from .models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
)
from .services import IngestionService
from .worker_run_lifecycle import apply_run_completion_side_effects

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
    summary="Internal Worker API - Scheduled Ingestion Run Lifecycle",
    description=(
        "Internal API endpoints for Prefect worker to manage scheduled ingestion runs. "
        "These endpoints are worker-only and require worker authentication (HUB_WORKER_API_KEY or API key with scope scheduled_ingestion:internal). "
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
        summary="Create scheduled ingestion run",
        description=(
            "Create a new scheduled ingestion run with status RUNNING. "
            "Idempotent by idempotency_key or prefect_flow_run_id. "
            "Requires worker authentication and X-Tenant-ID header."
        ),
        request=InternalCreateIngestionRunSerializer,
        responses={
            201: OpenApiResponse(description="Run created successfully"),
            200: OpenApiResponse(description="Run already exists (idempotent replay)"),
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Forbidden (tenant mismatch)"),
            404: OpenApiResponse(description="Scheduled ingestion not found"),
        },
    )
    def create(self, request):
        """POST .../internal/runs/ — create ScheduledIngestionRun (status RUNNING). Idempotent by idempotency_key or prefect_flow_run_id."""
        serializer = InternalCreateIngestionRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tenant_id = _get_tenant_id(request)
        if not tenant_id:
            return Response(
                {"error": "Tenant required", "code": "TENANT_REQUIRED", "details": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        scheduled_ingestion_id = str(data["scheduled_ingestion_id"])
        prefect_flow_run_id = data.get("prefect_flow_run_id") or ""
        idempotency_key = data.get("idempotency_key") or ""

        try:
            scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
        except ScheduledIngestion.DoesNotExist:
            return Response(
                {
                    "error": "Scheduled ingestion not found",
                    "code": "NOT_FOUND",
                    "details": {"scheduled_ingestion_id": scheduled_ingestion_id},
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        if str(scheduled_ingestion.tenant_id) != tenant_id:
            return Response(
                {
                    "error": "Scheduled ingestion does not belong to tenant",
                    "code": "FORBIDDEN",
                    "details": {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Idempotency: existing run with same prefect_flow_run_id or idempotency_key
        if prefect_flow_run_id:
            existing = ScheduledIngestionRun.objects.filter(
                scheduled_ingestion=scheduled_ingestion,
                prefect_flow_run_id=prefect_flow_run_id,
            ).first()
            if existing:
                return Response(
                    {
                        "id": str(existing.id),
                        "scheduled_ingestion_id": scheduled_ingestion_id,
                        "status": existing.status,
                        "prefect_flow_run_id": existing.prefect_flow_run_id or prefect_flow_run_id,
                    },
                    status=status.HTTP_200_OK,
                )
        existing = None
        if idempotency_key:
            for r in ScheduledIngestionRun.objects.filter(
                scheduled_ingestion=scheduled_ingestion
            ).order_by("-created_at")[:100]:
                if (r.result_json or {}).get("idempotency_key") == idempotency_key:
                    existing = r
                    break
            if existing:
                return Response(
                    {
                        "id": str(existing.id),
                        "scheduled_ingestion_id": scheduled_ingestion_id,
                        "status": existing.status,
                    },
                    status=status.HTTP_200_OK,
                )

        with transaction.atomic():
            run = ScheduledIngestionRun.objects.create(
                scheduled_ingestion=scheduled_ingestion,
                status=ScheduledIngestionRunStatus.RUNNING,
                started_at=timezone.now(),
                prefect_flow_run_id=prefect_flow_run_id or None,
                result_json={"idempotency_key": idempotency_key} if idempotency_key else {},
            )

        try:
            scheduled_ingestion_runs_total.labels(
                status="RUNNING",
                scheduled_ingestion_id=scheduled_ingestion_id,
                tenant_id=tenant_id,
            ).inc(1)
            scheduled_ingestion_runs_running.labels(
                scheduled_ingestion_id=scheduled_ingestion_id,
                tenant_id=tenant_id,
            ).inc(1)
        except (RuntimeError, ValueError, AttributeError) as e:
            logger.warning(
                "Failed to emit run-created metrics",
                extra={
                    "scheduled_ingestion_id": scheduled_ingestion_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

        tenant = _get_tenant(request)
        create_audit_event(
            resource_type="SCHEDULED_INGESTION_RUN",
            action="CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(run.id),
            details={
                "scheduled_ingestion_id": scheduled_ingestion_id,
                "status": run.status,
                "prefect_flow_run_id": prefect_flow_run_id or None,
            },
        )
        try:
            svc = IngestionService(
                tenant_id=tenant_id, user_id=str(request.user.id) if request.user else None
            )
            svc.publish_ingestion_started(
                ingestion_id=str(run.id),
                source_type=scheduled_ingestion.source_type,
                source_config=None,
                scheduled_ingestion_id=scheduled_ingestion_id,
            )
        except (ConnectionError, TimeoutError, RuntimeError, ValueError) as e:
            logger.warning(
                "Failed to publish ingestion.started event",
                extra={"run_id": str(run.id), "error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )

        return Response(
            {
                "id": str(run.id),
                "scheduled_ingestion_id": scheduled_ingestion_id,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "prefect_flow_run_id": run.prefect_flow_run_id,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Update scheduled ingestion run",
        description=(
            "Update a scheduled ingestion run (status, file counts, result_json, completed_at, etc.). "
            "When status changes to COMPLETED or FAILED, side effects are triggered (next_run_at calculation, "
            "cost tracking, DLQ sync, notifications, domain events). "
            "Requires worker authentication and X-Tenant-ID header."
        ),
        request=InternalUpdateIngestionRunSerializer,
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
            run = ScheduledIngestionRun.objects.select_related("scheduled_ingestion").get(id=pk)
        except ScheduledIngestionRun.DoesNotExist:
            return Response(
                {"error": "Run not found", "code": "NOT_FOUND", "details": {"run_id": pk}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if str(run.scheduled_ingestion.tenant_id) != tenant_id:
            return Response(
                {"error": "Run does not belong to tenant", "code": "FORBIDDEN", "details": {}},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = InternalUpdateIngestionRunSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        old_status = run.status
        update_fields = ["updated_at"]
        for key, value in data.items():
            if value is not None and hasattr(run, key):
                setattr(run, key, value)
                update_fields.append(key)
        run.save(update_fields=update_fields)

        new_status = data.get("status") or old_status
        if new_status in ("COMPLETED", "FAILED") and new_status != old_status:
            apply_run_completion_side_effects(run, new_status)

        scheduled_ingestion_id = str(run.scheduled_ingestion_id)
        if new_status != old_status and new_status in ("COMPLETED", "FAILED", "CANCELLED"):
            try:
                duration = (
                    (run.completed_at - run.started_at).total_seconds()
                    if run.completed_at and run.started_at
                    else 0
                )
                scheduled_ingestion_runs_total.labels(
                    status=new_status,
                    scheduled_ingestion_id=scheduled_ingestion_id,
                    tenant_id=tenant_id,
                ).inc(1)
                scheduled_ingestion_duration_seconds.labels(
                    scheduled_ingestion_id=scheduled_ingestion_id,
                    status=new_status,
                    tenant_id=tenant_id,
                ).observe(duration)
                scheduled_ingestion_runs_running.labels(
                    scheduled_ingestion_id=scheduled_ingestion_id,
                    tenant_id=tenant_id,
                ).dec(1)
            except Exception as e:
                logger.warning("Failed to emit run-completion metrics: %s", e)

        tenant = _get_tenant(request)
        create_audit_event(
            resource_type="SCHEDULED_INGESTION_RUN",
            action="UPDATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(run.id),
            details={
                "status": new_status,
                "files_processed": run.files_processed,
                "files_failed": run.files_failed,
            },
        )
        try:
            svc = IngestionService(
                tenant_id=tenant_id, user_id=str(request.user.id) if request.user else None
            )
            if new_status == "COMPLETED":
                svc.publish_ingestion_completed(
                    ingestion_id=str(run.id),
                    files_processed=run.files_processed + run.files_failed,
                    files_succeeded=run.files_processed,
                    files_failed=run.files_failed,
                    datasets_created=run.datasets_created,
                )
            elif new_status == "FAILED":
                svc.publish_ingestion_failed(
                    ingestion_id=str(run.id),
                    error_message=run.error_message or "Run failed",
                )
            elif new_status == "CANCELLED":
                svc.publish_ingestion_failed(
                    ingestion_id=str(run.id),
                    error_message=run.error_message or "Run cancelled",
                )
        except Exception as e:
            logger.warning("Failed to publish domain event: %s", e)

        return Response(
            {
                "id": str(run.id),
                "status": run.status,
                "files_found": run.files_found,
                "files_processed": run.files_processed,
                "files_failed": run.files_failed,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Internal (Worker)"],
    summary="Get scheduled ingestion configuration",
    description=(
        "Get configuration for a scheduled ingestion (source_type, source_config with masked credentials, "
        "file_pattern, schedule_config, ingestion_state, etc.). Credentials in source_config are masked "
        "for security. Requires worker authentication and X-Tenant-ID header. "
        "Rate limiting: No rate limit (internal worker endpoints)."
    ),
    responses={
        200: OpenApiResponse(
            description="Configuration retrieved successfully (credentials masked)"
        ),
        401: OpenApiResponse(description="Authentication required"),
        403: OpenApiResponse(description="Forbidden (tenant mismatch)"),
        404: OpenApiResponse(description="Scheduled ingestion not found"),
    },
)
class InternalConfigView(APIView):
    """GET .../internal/config/{scheduled_ingestion_id}/ — config for worker (credentials masked)."""

    authentication_classes = [WorkerAPIKeyAuthentication]
    permission_classes = [IsAuthenticated, WorkerInternalAPIPermission]

    def get(self, request, scheduled_ingestion_id):
        tenant_id = _get_tenant_id(request)
        if not tenant_id:
            return Response(
                {"error": "Tenant required", "code": "TENANT_REQUIRED", "details": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            si = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
        except ScheduledIngestion.DoesNotExist:
            return Response(
                {"error": "Scheduled ingestion not found", "code": "NOT_FOUND", "details": {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if str(si.tenant_id) != tenant_id:
            return Response(
                {
                    "error": "Scheduled ingestion does not belong to tenant",
                    "code": "FORBIDDEN",
                    "details": {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        from .credential_manager import CredentialManager

        masked_source_config = CredentialManager.get_masked_credentials(si)
        payload = {
            "source_type": si.source_type,
            "source_config": masked_source_config,
            "file_pattern": si.file_pattern,
            "asset_id": str(si.asset_id) if si.asset_id else None,
            "contract_id": str(si.contract_id) if si.contract_id else None,
            "schedule_config": si.schedule_config,
            "ingestion_state": si.ingestion_state,
            "auto_create_asset": si.auto_create_asset,
            "auto_activate": si.auto_activate,
        }
        return Response(payload, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Internal (Worker)"],
    summary="Process file for scheduled ingestion run",
    description=(
        "Process a single file for a scheduled ingestion run. Performs validation, optional DQ checks, "
        "creates File and Dataset, indexes in search, and updates incremental state. "
        "On permanent failure, creates DLQ record and emits audit/domain events. "
        "Requires worker authentication and X-Tenant-ID header. "
        "Rate limiting: No rate limit (internal worker endpoints)."
    ),
    request=InternalProcessFileSerializer,
    responses={
        201: OpenApiResponse(description="File processed successfully"),
        400: OpenApiResponse(description="Validation error"),
        401: OpenApiResponse(description="Authentication required"),
        403: OpenApiResponse(description="Forbidden (tenant mismatch)"),
        404: OpenApiResponse(description="Run not found"),
    },
)
class InternalProcessFileView(APIView):
    """POST .../internal/process-file/ — process one file for a run (validate, DQ, create file/dataset, index, incremental state)."""

    authentication_classes = [WorkerAPIKeyAuthentication]
    permission_classes = [IsAuthenticated, WorkerInternalAPIPermission]

    def post(self, request):
        tenant_id = _get_tenant_id(request)
        if not tenant_id:
            return Response(
                {"error": "Tenant required", "code": "TENANT_REQUIRED", "details": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        run_id = request.data.get("run_id")
        file_path = request.data.get("file_path")
        if not run_id or not file_path:
            return Response(
                {
                    "error": "run_id and file_path required",
                    "code": "VALIDATION_ERROR",
                    "details": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            run = ScheduledIngestionRun.objects.select_related("scheduled_ingestion").get(id=run_id)
        except ScheduledIngestionRun.DoesNotExist:
            return Response(
                {"error": "Run not found", "code": "NOT_FOUND", "details": {"run_id": run_id}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if str(run.scheduled_ingestion.tenant_id) != tenant_id:
            return Response(
                {"error": "Run does not belong to tenant", "code": "FORBIDDEN", "details": {}},
                status=status.HTTP_403_FORBIDDEN,
            )
        scheduled_ingestion_id = str(run.scheduled_ingestion_id)

        file_obj = request.FILES.get("file")
        file_content = None
        if file_obj:
            file_content = file_obj.read()
        elif request.data.get("file_content"):
            try:
                file_content = base64.b64decode(request.data.get("file_content"))
            except Exception:
                return Response(
                    {
                        "error": "Invalid file_content base64",
                        "code": "VALIDATION_ERROR",
                        "details": {},
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if not file_content:
            return Response(
                {
                    "error": "file or file_content required",
                    "code": "VALIDATION_ERROR",
                    "details": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        asset_id = request.data.get("asset_id")
        contract_id = request.data.get("contract_id")
        dq_options = request.data.get("dq_options") or {}

        from hub.apps.core.services.base import ValidationError as ServiceValidationError

        from .worker_services import process_file_for_run

        try:
            result = process_file_for_run(
                run_id=str(run_id),
                file_path=file_path,
                file_content=file_content,
                tenant_id=tenant_id,
                user_id=str(request.user.id) if request.user else None,
                asset_id=str(asset_id) if asset_id else None,
                contract_id=str(contract_id) if contract_id else None,
                dq_options=dq_options,
            )
        except ServiceValidationError as e:
            code = getattr(e, "code", "VALIDATION_ERROR")
            try:
                scheduled_ingestion_files_failed_total.labels(
                    scheduled_ingestion_id=scheduled_ingestion_id,
                    tenant_id=tenant_id,
                ).inc(1)
                svc = IngestionService(
                    tenant_id=tenant_id,
                    user_id=str(request.user.id) if request.user else None,
                )
                svc.publish_ingestion_file_processed(
                    ingestion_id=str(run_id),
                    file_id="",
                    status="failed",
                    error_message=str(e),
                )
            except Exception as m:
                logger.warning("Failed to emit process-file failure metrics/event: %s", m)
            return Response(
                {"error": str(e), "code": code, "details": getattr(e, "details", {})},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception("process_file_for_run failed")
            try:
                scheduled_ingestion_files_failed_total.labels(
                    scheduled_ingestion_id=scheduled_ingestion_id,
                    tenant_id=tenant_id,
                ).inc(1)
                svc = IngestionService(
                    tenant_id=tenant_id,
                    user_id=str(request.user.id) if request.user else None,
                )
                svc.publish_ingestion_file_processed(
                    ingestion_id=str(run_id),
                    file_id="",
                    status="failed",
                    error_message=str(e),
                )
            except Exception as m:
                logger.warning("Failed to emit process-file failure metrics/event: %s", m)
            return Response(
                {"error": str(e), "code": "INTERNAL_ERROR", "details": {}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        tenant = _get_tenant(request)
        create_audit_event(
            resource_type="SCHEDULED_INGESTION_FILE",
            action="PROCESSED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=result.get("file_id", ""),
            details={
                "run_id": run_id,
                "file_path": file_path,
                "file_id": result.get("file_id"),
                "dataset_id": result.get("dataset_id"),
                "asset_id": result.get("asset_id"),
            },
        )
        try:
            svc = IngestionService(
                tenant_id=tenant_id,
                user_id=str(request.user.id) if request.user else None,
            )
            svc.publish_ingestion_file_processed(
                ingestion_id=str(run_id),
                file_id=result.get("file_id", ""),
                status="success",
                dataset_id=result.get("dataset_id"),
            )
        except Exception as e:
            logger.warning("Failed to publish ingestion.file_processed event: %s", e)
        try:
            scheduled_ingestion_files_processed_total.labels(
                scheduled_ingestion_id=scheduled_ingestion_id,
                tenant_id=tenant_id,
            ).inc(1)
            scheduled_ingestion_datasets_created_total.labels(
                scheduled_ingestion_id=scheduled_ingestion_id,
                tenant_id=tenant_id,
            ).inc(1)
        except Exception as e:
            logger.warning("Failed to emit process-file success metrics: %s", e)
        return Response(result, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Internal (Worker)"], exclude=True)
class InternalTestDataView(APIView):
    """
    Serves a small test file for Phase 2 integration tests only.

    Security (Phase 220.2):
    - **Environment gate**: hidden in production / staging (returns 404).
    - **Authentication**: WorkerAPIKeyAuthentication (consistent with all
      other internal endpoints in this module).
    - **Authorization**: WorkerInternalAPIPermission (requires
      ``scheduled_ingestion:internal`` scope).
    - **Header guard**: X-Internal-Test-Data header must be set.
    """

    authentication_classes = [WorkerAPIKeyAuthentication]
    permission_classes = [IsAuthenticated, WorkerInternalAPIPermission]

    def get(self, request, filename):
        from django.conf import settings

        # Environment gate — dev / test only (220.2.2)
        if getattr(settings, "ENVIRONMENT", "development") not in (
            "development",
            "test",
        ):
            return Response(
                {"error": "Not found", "code": "NOT_FOUND", "details": {}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.headers.get("X-Internal-Test-Data") != "1":
            return Response(
                {"error": "Not found", "code": "NOT_FOUND", "details": {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if filename != "sample.csv":
            return Response(
                {"error": "Not found", "code": "NOT_FOUND", "details": {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        content = b"id,name\n1,alpha\n2,beta\n"
        return Response(
            content,
            content_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="sample.csv"'},
        )


@extend_schema(tags=["Internal (Worker)"])
class InternalCreateJobView(APIView):
    """
    POST .../internal/jobs/ — create Job (type SCHEDULED_INGESTION) for Prefect execution.

    Job is created with executed_by_prefect=True and is NOT enqueued to RQ.
    RQ worker will no-op when it sees this job. UI can show "Execution: Prefect"
    and link to prefect_flow_run_id.
    """

    authentication_classes = [WorkerAPIKeyAuthentication]
    permission_classes = [IsAuthenticated, WorkerInternalAPIPermission]

    def post(self, request):
        tenant_id = _get_tenant_id(request)
        if not tenant_id:
            return Response(
                {"error": "Tenant required", "code": "TENANT_REQUIRED", "details": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = InternalCreateJobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        scheduled_ingestion_id = str(data["scheduled_ingestion_id"])
        prefect_flow_run_id = data["prefect_flow_run_id"]
        run_id = data.get("scheduled_ingestion_run_id")

        # Idempotent: if run already has job_id (created by trigger), return it
        if run_id:
            try:
                run = ScheduledIngestionRun.objects.select_related("scheduled_ingestion").get(
                    id=run_id
                )
                if run.job_id:
                    job_existing = Job.objects.get(id=run.job_id)
                    return Response(
                        {
                            "id": str(job_existing.id),
                            "type": job_existing.type,
                            "status": job_existing.status,
                            "executed_by_prefect": True,
                            "prefect_flow_run_id": prefect_flow_run_id,
                        },
                        status=status.HTTP_200_OK,
                    )
            except (ScheduledIngestionRun.DoesNotExist, Job.DoesNotExist):
                pass

        try:
            si = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
        except ScheduledIngestion.DoesNotExist:
            return Response(
                {
                    "error": "Scheduled ingestion not found",
                    "code": "NOT_FOUND",
                    "details": {"scheduled_ingestion_id": scheduled_ingestion_id},
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        if str(si.tenant_id) != tenant_id:
            return Response(
                {
                    "error": "Scheduled ingestion does not belong to tenant",
                    "code": "FORBIDDEN",
                    "details": {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.utils import create_job

        details = {
            "executed_by_prefect": True,
            "prefect_flow_run_id": prefect_flow_run_id,
        }
        if run_id:
            details["scheduled_ingestion_run_id"] = str(run_id)

        job = create_job(
            tenant=si.tenant,
            user=None,
            job_type=JobType.SCHEDULED_INGESTION,
            resource_type="SCHEDULED_INGESTION",
            resource_id=scheduled_ingestion_id,
            details_json=details,
            executed_by_prefect=True,
        )

        # Link run to job when run_id provided (flow-created job path)
        if run_id:
            ScheduledIngestionRun.objects.filter(id=run_id).update(
                job_id=job.id, updated_at=timezone.now()
            )

        tenant = _get_tenant(request)
        create_audit_event(
            resource_type="JOB",
            action="CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(job.id),
            details={
                "type": job.type,
                "executed_by_prefect": True,
                "prefect_flow_run_id": prefect_flow_run_id,
                "scheduled_ingestion_id": scheduled_ingestion_id,
            },
        )

        return Response(
            {
                "id": str(job.id),
                "type": job.type,
                "status": job.status,
                "executed_by_prefect": True,
                "prefect_flow_run_id": prefect_flow_run_id,
            },
            status=status.HTTP_201_CREATED,
        )
