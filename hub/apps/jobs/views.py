"""
Job Views

REST API views for job management.
"""

import structlog
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from hub.apps.audit.utils import create_audit_event
from hub.apps.tenants.request_tenant import get_request_tenant_id

from .models import FailedJobDLQ, Job, JobStatus, JobType
from .serializers import (
    FailedJobDLQSerializer,
    JobCreateSerializer,
    JobSerializer,
)
from .utils import create_job, get_queue_for_job_type

logger = structlog.get_logger(__name__)


class JobViewSet(viewsets.ModelViewSet):
    """
    ViewSet for job management.

    Tenant-scoped: users can only see/manage jobs in their tenant.
    """

    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    filter_backends = [OrderingFilter, SearchFilter]
    search_fields = ["type", "status", "resource_type"]
    ordering_fields = ["created_at", "started_at", "completed_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter queryset based on user permissions (Phase 16: central helper)."""
        user = self.request.user
        qs = Job.objects.select_related("tenant")
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return qs
        tenant_id_str = get_request_tenant_id(self.request)
        if not tenant_id_str:
            return Job.objects.none()
        import uuid

        try:
            tenant_id = uuid.UUID(tenant_id_str)
        except (ValueError, TypeError):
            return Job.objects.none()
        return qs.filter(tenant_id=tenant_id)

    @transaction.atomic
    def create(self, request):
        """
        Create a new job.

        POST /jobs
        Body: {
            "type": "DQ_RUN",
            "resource_type": "DATASET",
            "resource_id": "uuid",
            "details_json": {...}
        }
        """
        serializer = JobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        job_type = serializer.validated_data["type"]
        resource_type = serializer.validated_data["resource_type"]
        resource_id = serializer.validated_data["resource_id"]
        details_json = serializer.validated_data.get("details_json")

        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to create jobs"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Determine queue based on job type
        queue_name = get_queue_for_job_type(job_type)

        # Create and enqueue job (checks tenant limits before creating)
        try:
            job = create_job(
                job_type=job_type,
                resource_type=resource_type,
                resource_id=str(resource_id),
                tenant=tenant,
                user=request.user,
                details_json=details_json,
                queue_name=queue_name,
            )
        except ValidationError as e:
            # Job creation rejected due to tenant limits
            return Response(
                {
                    "error": {
                        "code": "JOB_RATE_LIMITED",
                        "message": str(e),
                        "http_status": status.HTTP_429_TOO_MANY_REQUESTS,
                        "details": {
                            "reason": "tenant_job_limits_exceeded",
                            "tenant_id": str(tenant.id),
                        },
                    }
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Log audit event
        create_audit_event(
            resource_type="JOB",
            action="JOB_CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(job.id),
            details={
                "job_type": job_type,
                "resource_type": resource_type,
                "resource_id": str(resource_id),
            },
            request=request,
        )

        return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, id=None):
        """
        Cancel a job.

        POST /jobs/{id}/cancel

        Only PENDING or RUNNING jobs can be cancelled.
        If job is RUNNING, releases tenant concurrency slot.
        """
        job = self.get_object()

        if not job.can_cancel():
            return Response(
                {"error": f"Job cannot be cancelled (current status: {job.status})"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Store previous status for audit logging
        previous_status = job.status

        # Mark job as cancelled
        job.mark_cancelled()

        # If job was running, release tenant concurrency slot
        if previous_status == JobStatus.RUNNING and job.tenant:
            from hub.apps.jobs.utils import decrement_tenant_job_counter

            decrement_tenant_job_counter(str(job.tenant.id), "running")

        # Sync ComplianceRun when COMPLIANCE_RUN job is cancelled
        if job.type == JobType.COMPLIANCE_RUN:
            try:
                from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus

                compliance_run = ComplianceRun.objects.filter(job=job).first()
                if compliance_run:
                    compliance_run.status = ComplianceRunStatus.FAILED
                    compliance_run.allowed_to_store = False
                    compliance_run.regulation_mapping_json = {
                        **(compliance_run.regulation_mapping_json or {}),
                        "error": "Cancelled by user",
                        "cancelled": True,
                    }
                    compliance_run.completed_at = timezone.now()
                    compliance_run.save(
                        update_fields=[
                            "status",
                            "allowed_to_store",
                            "regulation_mapping_json",
                            "completed_at",
                        ]
                    )
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    "Failed to sync compliance run status after job cancellation: %s",
                    e,
                    exc_info=True,
                )

        # Sync execution status if this is a virtual query execution job
        if job.type == JobType.VIRTUAL_QUERY_EXECUTION:
            try:
                from hub.apps.virtualization.models import QueryExecution

                execution = QueryExecution.objects.filter(job=job).first()
                if execution:
                    execution.sync_status_from_job()
            except Exception as e:
                # Log but don't fail job cancellation if execution sync fails
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed to sync query execution status after job cancellation: {e}",
                    extra={"job_id": str(job.id), "error": str(e)},
                    exc_info=True,
                )

        # Log audit event
        create_audit_event(
            resource_type="JOB",
            action="JOB_CANCELLED",
            actor_user=request.user,
            tenant=job.tenant,
            resource_id=str(job.id),
            details={"job_type": job.type, "previous_status": previous_status},
            request=request,
        )

        return Response(JobSerializer(job).data, status=status.HTTP_200_OK)

    def list(self, request, *args, **kwargs):
        """List jobs with filtering (tenant-scoped)"""
        queryset = self.get_queryset()

        # Filter by type if provided
        job_type = request.query_params.get("type")
        if job_type:
            queryset = queryset.filter(type=job_type)

        # Filter by status if provided
        job_status = request.query_params.get("status")
        if job_status:
            queryset = queryset.filter(status=job_status)

        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve job by ID"""
        return super().retrieve(request, *args, **kwargs)


class FailedJobDLQViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Phase 91.9 — Admin view for the dead-letter queue.

    Provides list, detail, retry (re-enqueue), and purge actions.
    Restricted to platform admins.
    """

    queryset = FailedJobDLQ.objects.all()
    serializer_class = FailedJobDLQSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    filter_backends = [OrderingFilter, SearchFilter]
    search_fields = ["queue", "func_name", "error_message"]
    ordering_fields = ["created_at", "resolved_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Tenant-scoped; platform admins see all."""
        user = self.request.user
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            qs = FailedJobDLQ.objects.all()
        else:
            tenant_id_str = get_request_tenant_id(self.request)
            if not tenant_id_str:
                return FailedJobDLQ.objects.none()
            import uuid as _uuid

            try:
                tid = _uuid.UUID(tenant_id_str)
            except (ValueError, TypeError):
                return FailedJobDLQ.objects.none()
            qs = FailedJobDLQ.objects.filter(tenant_id=tid)

        # Filter: ?resolved=false shows unresolved only
        resolved_param = self.request.query_params.get("resolved")
        if resolved_param == "false":
            qs = qs.filter(resolved_at__isnull=True)
        elif resolved_param == "true":
            qs = qs.filter(resolved_at__isnull=False)
        return qs

    @action(detail=True, methods=["post"])
    def retry(self, request, id=None):
        """
        Re-enqueue a DLQ entry as a new PENDING job.

        POST /dlq/{id}/retry/
        """
        entry = self.get_object()
        if entry.resolved_at is not None:
            return Response(
                {"error": "Entry already resolved"},
                status=status.HTTP_409_CONFLICT,
            )

        args = entry.args_json or {}
        job_id = args.get("job_id")
        job_type = args.get("job_type")

        if not job_id or not job_type:
            return Response(
                {"error": "Cannot retry: missing job_id or job_type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if original job still exists
        try:
            job_obj = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            return Response(
                {"error": f"Original job {job_id} not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Reset the job to PENDING so the worker picks it up
        job_obj.status = JobStatus.PENDING
        job_obj.started_at = None
        job_obj.completed_at = None
        job_obj.error_message = None
        if job_obj.details_json is None:
            job_obj.details_json = {}
        job_obj.details_json["dlq_retry"] = True
        job_obj.details_json["dlq_entry_id"] = str(entry.id)
        job_obj.save(
            update_fields=[
                "status",
                "started_at",
                "completed_at",
                "error_message",
                "details_json",
                "updated_at",
            ]
        )

        # Enqueue the job
        from .tasks_base import process_job
        from .utils import get_job_timeout

        queue_name = get_queue_for_job_type(job_type)
        from django_rq import get_queue

        queue = get_queue(queue_name)
        queue.enqueue(
            process_job,
            str(job_obj.id),
            job_type=job_type,
            timeout=get_job_timeout(job_type),
        )

        # Update DLQ entry
        entry.retry_count += 1
        entry.resolved_at = timezone.now()
        entry.save(
            update_fields=[
                "retry_count",
                "resolved_at",
                "updated_at",
            ]
        )

        logger.info(
            "dlq_entry_retried",
            dlq_id=str(entry.id),
            job_id=job_id,
            job_type=job_type,
        )

        return Response(
            {"status": "retried", "job_id": job_id},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def purge_resolved(self, request):
        """
        Delete all resolved DLQ entries.

        POST /dlq/purge_resolved/
        """
        user = request.user
        if not (hasattr(user, "is_platform_admin") and user.is_platform_admin):
            return Response(
                {"error": "Platform admin required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        count, _ = FailedJobDLQ.objects.filter(
            resolved_at__isnull=False,
        ).delete()

        logger.info("dlq_purge_resolved", count=count)
        return Response(
            {"status": "purged", "count": count},
            status=status.HTTP_200_OK,
        )
