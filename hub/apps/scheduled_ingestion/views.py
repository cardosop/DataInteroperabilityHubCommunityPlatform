"""
Scheduled Ingestion Views

DRF viewsets for scheduled ingestion API endpoints.
"""

import logging

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hub.apps.audit.utils import create_audit_event
from hub.apps.core.responses import api_error_response, handle_service_exception
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.core.utils.prefect_deployment import delete_prefect_deployment
from hub.apps.tenants.request_tenant import get_request_tenant, get_request_tenant_id

from .models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
)
from .serializers import (
    ScheduledIngestionCreateSerializer,
    ScheduledIngestionRunSerializer,
    ScheduledIngestionSerializer,
    ScheduledIngestionTriggerSerializer,
)
from .services import IngestionService

logger = logging.getLogger(__name__)


def _get_connector_factory_for_credentials():
    """
    Lazy import of connector factory for credentials/test action.
    Returns the factory or None if not available (e.g. prefect-integration not installed).
    Tests can patch this to inject a real in-memory factory (no mocks).
    """
    import os
    import sys

    try:
        sys.path.insert(
            0,
            os.path.join(
                os.path.dirname(__file__),
                "../../../services/prefect-integration",
            ),
        )
        from connectors.factory import SourceConnectorFactory

        return SourceConnectorFactory
    except ImportError:
        return None


def _sync_deployment_via_prefect_integration_service(
    scheduled_ingestion, tenant, timeout_seconds=15
):
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
        "scheduled_ingestion_id": str(scheduled_ingestion.id),
        "tenant_id": str(tenant.id),
        "schedule_type": scheduled_ingestion.schedule_type,
        "schedule_config": scheduled_ingestion.schedule_config or {},
    }
    try:
        import requests

        resp = requests.post(url, json=payload, headers=headers, timeout=timeout_seconds)
        if resp.ok:
            data = resp.json()
            deployment_id = data.get("deployment_id") if isinstance(data, dict) else None
            update_fields = ["deployment_sync_status"]
            scheduled_ingestion.deployment_sync_status = "SYNCED"
            if deployment_id:
                scheduled_ingestion.prefect_deployment_id = deployment_id
                update_fields.append("prefect_deployment_id")
            scheduled_ingestion.save(update_fields=update_fields)
            return True
        logger.warning(
            "Prefect integration service sync failed for scheduled ingestion %s: %s %s",
            scheduled_ingestion.id,
            resp.status_code,
            resp.text[:200],
        )
        scheduled_ingestion.deployment_sync_status = "FAILED"
        scheduled_ingestion.save(update_fields=["deployment_sync_status"])
        return False
    except Exception as e:
        logger.warning(
            "Prefect integration service sync error for scheduled ingestion %s: %s",
            scheduled_ingestion.id,
            e,
            exc_info=True,
        )
        scheduled_ingestion.deployment_sync_status = "FAILED"
        scheduled_ingestion.save(update_fields=["deployment_sync_status"])
        return False


def _trigger_deployment_via_prefect_integration_service(
    scheduled_ingestion, tenant, parameters=None, timeout_seconds=15
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
        "scheduled_ingestion_id": str(scheduled_ingestion.id),
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
                    "Prefect deployment triggered for scheduled ingestion %s: flow_run_id=%s",
                    scheduled_ingestion.id,
                    flow_run_id,
                )
            return True, flow_run_id, None
        error_msg = resp.text[:500] if resp.text else f"HTTP {resp.status_code}"
        logger.warning(
            "Prefect integration service trigger failed for scheduled ingestion %s: %s %s",
            scheduled_ingestion.id,
            resp.status_code,
            error_msg,
        )
        return False, None, error_msg
    except Exception as e:
        logger.warning(
            "Prefect integration service trigger error for scheduled ingestion %s: %s",
            scheduled_ingestion.id,
            e,
            exc_info=True,
        )
        return False, None, str(e)


class ScheduledIngestionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for scheduled ingestion management.

    Provides CRUD operations and additional actions for scheduled ingestions.
    """

    serializer_class = ScheduledIngestionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        """Filter queryset by tenant and optional status, excluding soft-deleted records."""
        if self.request.user.is_platform_admin:
            queryset = ScheduledIngestion.objects.all()
        else:
            # Use central helper for tenant resolution (Phase 10.1.5)
            tenant_id = get_request_tenant_id(self.request)
            if tenant_id:
                queryset = ScheduledIngestion.objects.filter(tenant_id=tenant_id)
            else:
                return ScheduledIngestion.objects.none()

        # Phase 25.9.1 — Exclude soft-deleted records from listings
        queryset = queryset.exclude(status=ScheduledIngestionStatus.DELETED)

        # Filter by status if provided
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action == "create":
            return ScheduledIngestionCreateSerializer
        return ScheduledIngestionSerializer

    def create(self, request, *args, **kwargs):
        """Create scheduled ingestion via service (validates via ScheduledIngestionBusinessRules)."""
        # Fail-fast: check plan limit BEFORE expensive serializer validation
        # (connection testing). Avoids wasted round-trips to S3/external services
        # when the tenant has already hit their ingestion quota.
        _tenant_id, tenant = get_request_tenant(request)
        if tenant:
            from hub.apps.core.services.base import ValidationError as SvcValidationError
            from hub.apps.tenants.services import PlanLimitService

            try:
                plan_svc = PlanLimitService(tenant_id=str(tenant.id))
                with transaction.atomic():
                    plan_svc.check_limit(
                        tenant_id=str(tenant.id),
                        limit_key="max_scheduled_ingestions",
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
                pass  # Non-limit errors: let serializer/service handle normally

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # tenant already resolved above
        if not tenant:
            return Response(
                {"error": "Tenant is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = {k: v for k, v in serializer.validated_data.items() if k != "test_connection"}
        service = IngestionService(tenant_id=str(tenant.id), user_id=str(request.user.id))
        try:
            with transaction.atomic():
                scheduled_ingestion = service.create_scheduled_ingestion(
                    tenant=tenant,
                    created_by=request.user,
                    **data,
                )
        except ServiceValidationError as e:
            return handle_service_exception(e)
        # Prefect sync: prefer prefect-integration-service (has flow + connectors); fallback to in-process
        # Note: Prefect sync is non-blocking - creation succeeds even if sync fails
        import os as _os

        base_url = _os.getenv("PREFECT_INTEGRATION_SERVICE_URL", "").rstrip("/")
        if base_url:
            # Pass schedule_type/schedule_config so prefect-integration skips DB fetch (avoids 404
            # when test runs with django_db(transaction=True) and data is uncommitted).
            sync_ok = _sync_deployment_via_prefect_integration_service(
                scheduled_ingestion, tenant, timeout_seconds=15
            )
        else:
            sync_ok = False
        if not sync_ok and not base_url:
            try:
                import os
                import sys

                sys.path.insert(
                    0,
                    os.path.join(
                        os.path.dirname(__file__), "../../../services/prefect-integration"
                    ),
                )
                try:
                    from deployment_sync import DeploymentSyncService
                except ImportError:
                    logger.warning(
                        "Prefect integration not available for scheduled ingestion %s. "
                        "Scheduled ingestion created but Prefect deployment sync skipped.",
                        scheduled_ingestion.id,
                    )
                else:
                    prefect_api_url = os.getenv("PREFECT_API_URL", "http://prefect-server:4200/api")
                    prefect_api_key = os.getenv("PREFECT_API_KEY", "")
                    os.environ["PREFECT_API_URL"] = prefect_api_url
                    if prefect_api_key:
                        os.environ["PREFECT_API_KEY"] = prefect_api_key

                    work_pool_name = scheduled_ingestion.prefect_work_pool_name
                    deployment_svc = DeploymentSyncService(
                        prefect_api_url=prefect_api_url,
                        prefect_api_key=prefect_api_key,
                        work_pool_name=work_pool_name,
                    )
                    deployment_name_suffix = f"{tenant.id}-{scheduled_ingestion.id}"
                    import asyncio

                    try:
                        deployment_coro = deployment_svc.create_or_update_deployment(
                            scheduled_ingestion_id=scheduled_ingestion.id,
                            tenant_id=tenant.id,
                            deployment_name=deployment_name_suffix,
                        )
                        deployment = asyncio.run(asyncio.wait_for(deployment_coro, timeout=10.0))
                        if deployment:
                            scheduled_ingestion.prefect_deployment_id = (
                                deployment.id if hasattr(deployment, "id") else str(deployment)
                            )
                            scheduled_ingestion.deployment_sync_status = "SYNCED"
                            scheduled_ingestion.save(
                                update_fields=["prefect_deployment_id", "deployment_sync_status"]
                            )
                    except TimeoutError:
                        logger.warning(
                            "Prefect deployment sync timed out for scheduled ingestion %s. "
                            "Scheduled ingestion created but Prefect deployment sync will need to be retried.",
                            scheduled_ingestion.id,
                        )
                        scheduled_ingestion.deployment_sync_status = "FAILED"
                        scheduled_ingestion.save(update_fields=["deployment_sync_status"])
            except Exception as e:
                logger.warning(
                    "Prefect sync failed for scheduled ingestion %s: %s. "
                    "Scheduled ingestion created but Prefect deployment sync will need to be retried.",
                    scheduled_ingestion.id,
                    e,
                    exc_info=True,
                )
                scheduled_ingestion.deployment_sync_status = "FAILED"
                scheduled_ingestion.save(update_fields=["deployment_sync_status"])
        create_audit_event(
            resource_type="SCHEDULED_INGESTION",
            action="CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(scheduled_ingestion.id),
            details={
                "name": scheduled_ingestion.name,
                "source_type": scheduled_ingestion.source_type,
                "schedule_type": scheduled_ingestion.schedule_type,
            },
        )
        # Phase 25.5.1 — Return 207 Multi-Status when resource is created
        # but deployment sync failed, so the client knows the schedule won't
        # fire until a manual retry (/sync/) succeeds.
        scheduled_ingestion.refresh_from_db()
        resource_data = ScheduledIngestionSerializer(scheduled_ingestion).data
        if scheduled_ingestion.deployment_sync_status == "FAILED":
            return Response(
                {
                    "resource": resource_data,
                    "deployment_sync": {
                        "status": "failed",
                        "error": "Prefect deployment sync failed; call POST /{id}/sync/ to retry",
                    },
                },
                status=207,  # Multi-Status
            )
        return Response(resource_data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        """Update scheduled ingestion via service layer and sync with Prefect"""
        scheduled_ingestion = self.get_object()
        old_status = scheduled_ingestion.status

        # Use service layer for update (Phase 24.7.1)
        tenant_id, tenant = get_request_tenant(self.request)
        if not tenant:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Tenant is required")

        service = IngestionService(tenant_id=str(tenant.id), user_id=str(self.request.user.id))

        # Extract update data from serializer
        update_data = {
            k: v
            for k, v in serializer.validated_data.items()
            if k not in serializer.Meta.read_only_fields
            if hasattr(serializer.Meta, "read_only_fields")
        }

        with transaction.atomic():
            try:
                updated = service.update_scheduled_ingestion(
                    scheduled_ingestion_id=str(scheduled_ingestion.id),
                    tenant_id=str(tenant.id),
                    user_id=str(self.request.user.id),
                    **update_data,
                )
            except ServiceValidationError as e:
                raise ValidationError(str(e))

            # Sync with Prefect if deployment exists
            # ====================================================================
            # CHECKPOINT: Line ~350 - ScheduledIngestionViewSet.update() method
            # ====================================================================
            # This section handles Prefect deployment sync when updating scheduled ingestion.
            # Save checkpoint for large file management (views.py > 700 lines).
            # ====================================================================
            if updated.prefect_deployment_id:
                try:
                    import os
                    import sys

                    sys.path.insert(
                        0,
                        os.path.join(
                            os.path.dirname(__file__), "../../../services/prefect-integration"
                        ),
                    )
                    from deployment_sync import DeploymentSyncService

                    prefect_api_url = os.getenv("PREFECT_API_URL", "http://prefect-server:4200/api")
                    prefect_api_key = os.getenv("PREFECT_API_KEY", "")
                    work_pool_name = updated.prefect_work_pool_name

                    service = DeploymentSyncService(
                        prefect_api_url=prefect_api_url,
                        prefect_api_key=prefect_api_key,
                        work_pool_name=work_pool_name,
                    )

                    deployment_name = f"{updated.tenant.id}-{updated.id}"
                    import asyncio

                    deployment = asyncio.run(
                        service.create_or_update_deployment(
                            scheduled_ingestion_id=updated.id,
                            tenant_id=updated.tenant.id,
                            deployment_name=deployment_name,
                        )
                    )

                    if deployment:
                        updated.prefect_deployment_id = (
                            deployment.id if hasattr(deployment, "id") else str(deployment)
                        )
                        updated.deployment_sync_status = "SYNCED"
                        updated.save(
                            update_fields=["prefect_deployment_id", "deployment_sync_status"]
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to sync with Prefect for scheduled ingestion {updated.id}: {e!s}",
                        exc_info=True,
                    )
                    updated.deployment_sync_status = "FAILED"
                    updated.save(update_fields=["deployment_sync_status"])

            # Log audit event
            # Use central helper for tenant resolution (Phase 10.1.5)
            _tenant_id, tenant = get_request_tenant(self.request)
            if not tenant:
                tenant = updated.tenant
            create_audit_event(
                resource_type="SCHEDULED_INGESTION",
                action="UPDATED",
                actor_user=self.request.user,
                tenant=tenant,
                resource_id=str(updated.id),
                details={"name": updated.name, "status_changed": old_status != updated.status},
            )

        # So that UpdateModelMixin returns Response(serializer.data) with updated instance
        serializer.instance = updated

    def update(self, request, *args, **kwargs):
        """Override to return 207 when sync fails (Phase 25.5.1)."""
        response = super().update(request, *args, **kwargs)
        # After perform_update ran, check if sync failed
        instance = self.get_object()
        if instance.deployment_sync_status == "FAILED":
            resource_data = response.data
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
        return response

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
        _tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            tenant = instance.tenant

        # --- Step 1: delete Prefect deployment first ---
        if instance.prefect_deployment_id:
            deployment_deleted = delete_prefect_deployment(
                deployment_id=str(instance.prefect_deployment_id),
                resource_id=str(instance.id),
                resource_type="scheduled_ingestion",
                tenant_id=str(tenant.id),
            )
            if not deployment_deleted:
                # Soft-delete: mark as DELETED so the purge CronJob can retry
                ScheduledIngestion.objects.filter(pk=instance.pk).update(
                    status=ScheduledIngestionStatus.DELETED,
                )
                create_audit_event(
                    resource_type="SCHEDULED_INGESTION",
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
            ScheduledIngestion.objects.filter(pk=instance.pk).update(
                prefect_deployment_id=None,
                deployment_sync_status="PENDING",
            )

        # --- Step 2: hard-delete DB record via service layer ---
        service = IngestionService(tenant_id=str(tenant.id), user_id=str(request.user.id))
        try:
            service.delete_scheduled_ingestion(
                scheduled_ingestion_id=str(instance.id),
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        operation_id="scheduled_ingestion_sync",
        request=None,
        responses={
            200: ScheduledIngestionSerializer,
            503: inline_serializer(
                name="ScheduledIngestionSyncUnavailable",
                fields={
                    "error": serializers.CharField(),
                    "deployment_sync_status": serializers.CharField(),
                },
            ),
        },
        tags=["Scheduled Ingestion"],
    )
    @action(detail=True, methods=["post"], url_path="sync")
    def sync(self, request, id=None):
        """
        Phase 25.5.2 — Idempotent retry endpoint for Prefect deployment sync.

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

        scheduled_ingestion = self.get_object()
        _tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            tenant = scheduled_ingestion.tenant

        sync_ok = _sync_deployment_via_prefect_integration_service(
            scheduled_ingestion, tenant, timeout_seconds=15
        )

        scheduled_ingestion.refresh_from_db()
        if sync_ok:
            return Response(
                ScheduledIngestionSerializer(scheduled_ingestion).data,
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "error": "Prefect integration service sync failed",
                "deployment_sync_status": scheduled_ingestion.deployment_sync_status,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    @extend_schema(
        operation_id="scheduled_ingestion_trigger",
        request=ScheduledIngestionTriggerSerializer,
        responses={
            200: inline_serializer(
                name="ScheduledIngestionTriggerResponse",
                fields={
                    "scheduled_ingestion_id": serializers.UUIDField(),
                    "flow_run_id": serializers.CharField(),
                    "status": serializers.CharField(),
                    "message": serializers.CharField(),
                },
            )
        },
    )
    @action(detail=True, methods=["post"])
    def trigger(self, request, id=None):
        """
        Manually trigger a scheduled ingestion.

        Creates a Prefect flow run for the scheduled ingestion.
        """
        scheduled_ingestion = self.get_object()
        if scheduled_ingestion.status != ScheduledIngestionStatus.ACTIVE:
            return Response(
                {
                    "detail": "Scheduled ingestion is not active. Only active ingestions can be triggered."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ScheduledIngestionTriggerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        parameters = serializer.validated_data.get("parameters", {})

        try:
            # Trigger deployment via prefect-integration-service HTTP API
            # This avoids requiring prefect library in api-service
            _tenant_id, tenant = get_request_tenant(request)
            if not tenant:
                tenant = scheduled_ingestion.tenant

            success, flow_run_id, error_msg = _trigger_deployment_via_prefect_integration_service(
                scheduled_ingestion, tenant, parameters=parameters, timeout_seconds=30
            )

            if not success:
                # Deployment not found / still syncing: return 503 so clients treat as
                # temporary unavailability (consistent with "503 if Prefect unavailable").
                if error_msg and (
                    "not found" in error_msg.lower()
                    or "404" in error_msg
                    or "still be syncing" in error_msg.lower()
                    or "deployment" in error_msg.lower()
                ):
                    return Response(
                        {
                            "error": f"Prefect deployment not found for scheduled ingestion {scheduled_ingestion.id}",
                            "code": "DEPLOYMENT_NOT_READY",
                            "details": {"error": error_msg},
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                # Other errors
                return Response(
                    {
                        "error": f"Failed to trigger ingestion: {error_msg or 'Unknown error'}",
                        "code": "TRIGGER_FAILED",
                        "details": {"error": error_msg},
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            if flow_run_id:
                # Create run record with PENDING status (Prefect will update it later)
                run = ScheduledIngestionRun.objects.create(
                    scheduled_ingestion=scheduled_ingestion,
                    status=ScheduledIngestionRunStatus.PENDING,
                    prefect_flow_run_id=flow_run_id,
                    error_message=None,
                    completed_at=None,
                )

                # Create Job synchronously for UI/audit; Prefect flow will use it (idempotent)
                from hub.apps.jobs.models import JobType
                from hub.apps.jobs.utils import create_job

                job = create_job(
                    tenant=scheduled_ingestion.tenant,
                    user=None,
                    job_type=JobType.SCHEDULED_INGESTION,
                    resource_type="SCHEDULED_INGESTION",
                    resource_id=str(scheduled_ingestion.id),
                    details_json={
                        "executed_by_prefect": True,
                        "prefect_flow_run_id": flow_run_id,
                        "scheduled_ingestion_run_id": str(run.id),
                    },
                    executed_by_prefect=True,
                )
                run.job_id = job.id
                run.save(update_fields=["job_id", "updated_at"])

                # Phase 25.6.3 — Enqueue status sync via RQ
                try:
                    from hub.apps.jobs.tasks_prefect_sync import (
                        enqueue_prefect_status_sync,
                    )

                    transaction.on_commit(
                        lambda frid=flow_run_id, rid=str(run.id): enqueue_prefect_status_sync(
                            flow_run_id=frid,
                            resource_id=rid,
                            resource_type="scheduled_ingestion",
                        )
                    )
                except Exception:
                    pass  # Don't fail trigger if enqueue fails

                create_audit_event(
                    resource_type="SCHEDULED_INGESTION",
                    action="TRIGGERED",
                    actor_user=request.user,
                    tenant=scheduled_ingestion.tenant,
                    resource_id=str(scheduled_ingestion.id),
                    details={"run_id": str(run.id), "flow_run_id": flow_run_id},
                )
                return Response(
                    {
                        "scheduled_ingestion_id": str(scheduled_ingestion.id),
                        "run_id": str(run.id),
                        "scheduled_ingestion_run_id": str(run.id),
                        "flow_run_id": flow_run_id,
                        "job_id": str(job.id),
                        "status": "success",
                        "message": f"Scheduled ingestion {scheduled_ingestion.name} triggered successfully",
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
            else:
                return Response(
                    {
                        "error": "Failed to trigger ingestion: no flow_run_id returned",
                        "code": "TRIGGER_FAILED",
                        "details": {},
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            logger.error(
                f"Failed to trigger scheduled ingestion {scheduled_ingestion.id}: {e!s}",
                exc_info=True,
            )
            return Response(
                {
                    "error": f"Failed to trigger ingestion: {e!s}",
                    "code": "INTERNAL_ERROR",
                    "details": {},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        operation_id="scheduled_ingestion_runs",
        responses={200: ScheduledIngestionRunSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def runs(self, request, id=None):
        """
        List runs for a scheduled ingestion.
        """
        scheduled_ingestion = self.get_object()
        runs = ScheduledIngestionRun.objects.filter(
            scheduled_ingestion=scheduled_ingestion
        ).order_by("-created_at")

        serializer = ScheduledIngestionRunSerializer(runs, many=True)
        return Response(serializer.data)

    # ====================================================================
    # CHECKPOINT: Line ~700 - ScheduledIngestionViewSet custom actions
    # ====================================================================
    # This section contains custom actions (dashboard, dead-letter-queue, etc.).
    # Save checkpoint for large file management (views.py > 700 lines).
    # ====================================================================
    @action(detail=False, methods=["get"], url_path="dashboard")
    def dashboard(self, request):
        """
        Get ingestion monitoring dashboard.

        GET /api/v1/scheduled-ingestions/dashboard/
        """
        from .monitoring import IngestionMonitoringDashboard

        # Use central helper for tenant resolution (Phase 10.1.5)
        tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            return api_error_response(
                message="Tenant is required",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        scheduled_ingestion_id = request.query_params.get("scheduled_ingestion_id")
        days = int(request.query_params.get("days", 30))

        dashboard_data = IngestionMonitoringDashboard.get_dashboard(
            tenant_id=tenant_id, scheduled_ingestion_id=scheduled_ingestion_id, days=days
        )

        return Response(dashboard_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="dead-letter-queue")
    def dead_letter_queue(self, request):
        """
        Get Dead Letter Queue dashboard.

        GET /api/v1/scheduled-ingestions/dead-letter-queue/
        """
        from .dead_letter_queue import DeadLetterQueueManager

        # Use central helper for tenant resolution (Phase 10.1.5)
        tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            return api_error_response(
                message="Tenant is required",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        scheduled_ingestion_id = request.query_params.get("scheduled_ingestion_id")
        resolution_status = request.query_params.get("resolution_status")

        dlq_data = DeadLetterQueueManager.get_dlq_dashboard(
            tenant_id=tenant_id,
            scheduled_ingestion_id=scheduled_ingestion_id,
            resolution_status=resolution_status,
        )

        return Response(dlq_data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="dlq/(?P<dlq_item_id>[^/.]+)/retry")
    def retry_dlq_item(self, request, pk=None, dlq_item_id=None):
        """
        Retry a failed file from Dead Letter Queue.

        POST /api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/retry/
        """
        from .dead_letter_queue import DeadLetterQueueManager

        success = DeadLetterQueueManager.retry_file(
            dlq_item_id=dlq_item_id,
            user_id=str(request.user.id) if request.user.is_authenticated else None,
        )

        if success:
            return Response({"message": "Retry initiated"}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Cannot retry - item not in PENDING status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"], url_path="dlq/(?P<dlq_item_id>[^/.]+)/resolve")
    def resolve_dlq_item(self, request, pk=None, dlq_item_id=None):
        """
        Resolve a Dead Letter Queue item.

        POST /api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/resolve/
        """
        from .dead_letter_queue import DeadLetterQueueManager

        resolution_status = request.data.get("resolution_status")
        resolution_notes = request.data.get("resolution_notes")

        if resolution_status not in ["RESOLVED", "IGNORED"]:
            return Response(
                {"error": "Invalid resolution_status. Must be 'RESOLVED' or 'IGNORED'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        DeadLetterQueueManager.resolve_item(
            dlq_item_id=dlq_item_id,
            resolution_status=resolution_status,
            resolution_notes=resolution_notes,
            user_id=str(request.user.id) if request.user.is_authenticated else None,
        )

        return Response(
            {"message": f"DLQ item marked as {resolution_status}"}, status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["get"], url_path="costs")
    def costs(self, request):
        """
        Get ingestion cost report.

        GET /api/v1/scheduled-ingestions/costs/
        """
        from datetime import datetime

        from .cost_tracking import CostTrackingManager

        # Use central helper for tenant resolution (Phase 10.1.5)
        tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            return api_error_response(
                message="Tenant is required",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        scheduled_ingestion_id = request.query_params.get("scheduled_ingestion_id")
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")

        start_date = None
        end_date = None

        if start_date_str:
            try:
                start_date = timezone.make_aware(datetime.fromisoformat(start_date_str))
            except ValueError:
                return Response(
                    {"error": "Invalid start_date format. Use ISO format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_date_str:
            try:
                end_date = timezone.make_aware(datetime.fromisoformat(end_date_str))
            except ValueError:
                return Response(
                    {"error": "Invalid end_date format. Use ISO format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        cost_report = CostTrackingManager.get_cost_report(
            tenant_id=tenant_id,
            scheduled_ingestion_id=scheduled_ingestion_id,
            start_date=start_date,
            end_date=end_date,
        )

        return Response(cost_report, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="get_scheduled_ingestion_credentials",
        responses={
            200: inline_serializer(
                name="CredentialsResponse",
                fields={
                    "scheduled_ingestion_id": serializers.UUIDField(),
                    "source_type": serializers.CharField(),
                    "credential_version": serializers.IntegerField(default=1),
                    "last_tested_at": serializers.DateTimeField(allow_null=True),
                    "last_test_result": serializers.CharField(allow_null=True),
                    "masked_credentials": serializers.DictField(),
                    "metadata": serializers.DictField(allow_null=True),
                },
            ),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Scheduled ingestion not found"),
        },
        tags=["Scheduled Ingestion"],
    )
    @action(detail=True, methods=["get"], url_path="credentials")
    def credentials(self, request, id=None):
        """
        Get masked credentials for scheduled ingestion.

        GET /api/v1/scheduled-ingestions/{id}/credentials/

        Returns masked credentials (never exposes actual credentials).
        Performance target: < 200ms p95
        """
        scheduled_ingestion = self.get_object()

        # Check permissions: User must own the scheduled ingestion or be a TENANT_ADMIN
        request_tenant_id = get_request_tenant_id(request)
        if not (
            request.user.is_platform_admin
            or (
                request_tenant_id is not None
                and str(scheduled_ingestion.tenant_id) == request_tenant_id
                and request.user.has_role("DATA_PROVIDER", "TENANT_ADMIN")
            )
        ):
            raise PermissionDenied(
                "You do not have permission to access credentials for this scheduled ingestion."
            )

        from hub.apps.scheduled_ingestion.credential_manager import CredentialManager

        try:
            # Get masked credentials
            masked_credentials_data = CredentialManager.get_masked_credentials(scheduled_ingestion)

            response_data = {
                "scheduled_ingestion_id": str(scheduled_ingestion.id),
                "source_type": scheduled_ingestion.source_type,
                "credential_version": getattr(scheduled_ingestion, "credential_version", 1),
                "last_tested_at": (
                    scheduled_ingestion.last_credential_test_at.isoformat()
                    if hasattr(scheduled_ingestion, "last_credential_test_at")
                    and scheduled_ingestion.last_credential_test_at
                    else None
                ),
                "last_test_result": getattr(
                    scheduled_ingestion, "last_credential_test_result", None
                ),
                "masked_credentials": masked_credentials_data,
                "metadata": {
                    k: v
                    for k, v in (scheduled_ingestion.get_source_config() or {}).items()
                    if k not in CredentialManager.SENSITIVE_FIELDS
                },  # Include other non-sensitive metadata
            }

            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(
                f"Failed to retrieve masked credentials for {scheduled_ingestion.id}: {e!s}",
                exc_info=True,
            )
            return Response(
                {"error": "Failed to retrieve masked credentials", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        operation_id="test_scheduled_ingestion_credentials",
        request=None,
        responses={
            200: inline_serializer(
                name="ConnectionTestResponse",
                fields={
                    "success": serializers.BooleanField(),
                    "message": serializers.CharField(),
                    "tested_at": serializers.DateTimeField(),
                    "connection_details": serializers.DictField(allow_null=True),
                },
            ),
            400: OpenApiResponse(description="Bad Request"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Scheduled ingestion not found"),
            503: OpenApiResponse(description="Connector service unavailable"),
        },
        tags=["Scheduled Ingestion"],
    )
    @action(detail=True, methods=["post"], url_path="credentials/test")
    def test_credentials(self, request, id=None):
        """
        Test connection with stored credentials.

        POST /api/v1/scheduled-ingestions/{id}/credentials/test/

        Tests connection to the data source using stored credentials.
        Never exposes credentials in response.
        Performance target: < 5000ms p95 (connection testing can be slow)
        Timeout: 30 seconds
        """
        import time

        scheduled_ingestion = self.get_object()

        start_time = time.time()

        try:
            # Get source config with credentials
            source_config = scheduled_ingestion.get_source_config() or {}

            if not source_config:
                return Response(
                    {"success": False, "message": "No source configuration found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Use injectable getter so tests can supply real connector (no mocks)
            factory = _get_connector_factory_for_credentials()
            if factory is None:
                return Response(
                    {"success": False, "message": "Connector service is not available"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            connector = factory.get_connector(scheduled_ingestion.source_type)

            # Test connection with timeout (30 seconds)
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError("Connection test timed out after 30 seconds")

            # Set timeout (Unix only)
            if hasattr(signal, "SIGALRM"):
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)

            try:
                # test_connection returns a boolean
                test_result = connector.test_connection(source_config)
                response_time_ms = int((time.time() - start_time) * 1000)

                # Clear alarm
                if hasattr(signal, "SIGALRM"):
                    signal.alarm(0)

                # Update last_tested_at and last_test_result (if tracked)
                # TODO: Add last_tested_at and last_test_result fields to ScheduledIngestion model

                # Log audit event
                create_audit_event(
                    resource_type="SCHEDULED_INGESTION",
                    action="CREDENTIALS_TESTED",
                    actor_user=request.user,
                    tenant=scheduled_ingestion.tenant,
                    resource_id=str(scheduled_ingestion.id),
                    details={
                        "source_type": scheduled_ingestion.source_type,
                        "test_result": "success" if test_result else "failure",
                        "response_time_ms": response_time_ms,
                    },
                    request=request,
                )

                if test_result:
                    return Response(
                        {
                            "success": True,
                            "message": "Connection test successful",
                            "tested_at": timezone.now().isoformat(),
                            "connection_details": {"response_time_ms": response_time_ms},
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    return Response(
                        {
                            "success": False,
                            "message": "Connection test failed - unable to connect to data source",
                            "tested_at": timezone.now().isoformat(),
                            "connection_details": {"response_time_ms": response_time_ms},
                        },
                        status=status.HTTP_200_OK,
                    )  # Return 200 with success=False for connection failures

            except TimeoutError:
                if hasattr(signal, "SIGALRM"):
                    signal.alarm(0)
                return Response(
                    {"success": False, "message": "Connection test timed out after 30 seconds"},
                    status=status.HTTP_504_GATEWAY_TIMEOUT,
                )
            except Exception as e:
                if hasattr(signal, "SIGALRM"):
                    signal.alarm(0)
                logger.error(
                    f"Connection test failed for scheduled ingestion {scheduled_ingestion.id}: {e!s}",
                    exc_info=True,
                )
                return Response(
                    {
                        "success": False,
                        "message": f"Connection test failed: {e!s}",
                        "tested_at": timezone.now().isoformat(),
                        "connection_details": {
                            "response_time_ms": int((time.time() - start_time) * 1000)
                        },
                    },
                    status=status.HTTP_200_OK,
                )  # Return 200 with success=False for connection failures

        except Exception as e:
            logger.error(
                f"Failed to test credentials for scheduled ingestion {scheduled_ingestion.id}: {e!s}",
                exc_info=True,
            )
            return Response(
                {"success": False, "message": f"Failed to test credentials: {e!s}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ====================================================================
# CHECKPOINT: Line ~1100 - ScheduledIngestionRunViewSet class
# ====================================================================
# This section contains the ScheduledIngestionRunViewSet class.
# Save checkpoint for large file management (views.py > 1100 lines).
# ====================================================================
class ScheduledIngestionRunViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for scheduled ingestion runs.
    """

    serializer_class = ScheduledIngestionRunSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        """Filter queryset by tenant"""
        if self.request.user.is_platform_admin:
            return ScheduledIngestionRun.objects.all()

        # Use central helper for tenant resolution (Phase 10.1.5)
        tenant_id = get_request_tenant_id(self.request)
        if tenant_id:
            return ScheduledIngestionRun.objects.filter(scheduled_ingestion__tenant_id=tenant_id)

        return ScheduledIngestionRun.objects.none()
