"""
Job Views

REST API views for job management.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound
from django.db import transaction
from rest_framework.filters import OrderingFilter, SearchFilter

from .models import Job, JobStatus, JobType
from .serializers import JobSerializer, JobCreateSerializer, JobCancelSerializer
from .utils import create_job, get_queue_for_job_type
from hub.apps.audit.utils import create_audit_event
import structlog

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
    search_fields = ['type', 'status', 'resource_type']
    ordering_fields = ['created_at', 'started_at', 'completed_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Platform admins can see all jobs
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return Job.objects.all()

        # Get tenant from request (set by middleware/authentication) or user
        # Priority: request.tenant_id > request.tenant > user.tenant_id > user.tenant
        tenant_id = None
        if hasattr(self.request, "tenant_id") and self.request.tenant_id:
            tenant_id = self.request.tenant_id
            if isinstance(tenant_id, str):
                import uuid
                try:
                    tenant_id = uuid.UUID(tenant_id)
                except (ValueError, TypeError):
                    tenant_id = None
        if not tenant_id and hasattr(self.request, "tenant") and self.request.tenant:
            tenant_id = self.request.tenant.id
        if not tenant_id and hasattr(user, "tenant_id") and user.tenant_id:
            tenant_id = user.tenant_id
        if not tenant_id and hasattr(user, "tenant") and user.tenant:
            tenant_id = user.tenant.id

        # Regular users can only see jobs in their tenant
        if tenant_id:
            if isinstance(tenant_id, str):
                import uuid
                try:
                    tenant_id = uuid.UUID(tenant_id)
                except (ValueError, TypeError):
                    return Job.objects.none()
            return Job.objects.filter(tenant_id=tenant_id)

        return Job.objects.none()

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

        job_type = serializer.validated_data['type']
        resource_type = serializer.validated_data['resource_type']
        resource_id = serializer.validated_data['resource_id']
        details_json = serializer.validated_data.get('details_json')

        # Get tenant from user
        tenant = request.user.tenant if hasattr(request.user, 'tenant') and request.user.tenant else None
        if not tenant:
            return Response(
                {'error': 'User must belong to a tenant to create jobs'},
                status=status.HTTP_400_BAD_REQUEST
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
                queue_name=queue_name
            )
        except ValidationError as e:
            # Job creation rejected due to tenant limits
            return Response(
                {
                    'error': {
                        'code': 'JOB_RATE_LIMITED',
                        'message': str(e),
                        'http_status': status.HTTP_429_TOO_MANY_REQUESTS,
                        'details': {
                            'reason': 'tenant_job_limits_exceeded',
                            'tenant_id': str(tenant.id)
                        }
                    }
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Log audit event
        create_audit_event(
            resource_type="JOB",
            action="JOB_CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(job.id),
            details={
                'job_type': job_type,
                'resource_type': resource_type,
                'resource_id': str(resource_id)
            },
            request=request
        )

        return Response(
            JobSerializer(job).data,
            status=status.HTTP_201_CREATED
        )

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='cancel')
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
                {'error': f'Job cannot be cancelled (current status: {job.status})'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Store previous status for audit logging
        previous_status = job.status

        # Mark job as cancelled
        job.mark_cancelled()

        # If job was running, release tenant concurrency slot
        if previous_status == JobStatus.RUNNING and job.tenant:
            from hub.apps.jobs.utils import decrement_tenant_job_counter
            decrement_tenant_job_counter(str(job.tenant.id), "running")

        # Sync execution status if this is a transformation pipeline execution job
        if job.type == JobType.TRANSFORMATION_PIPELINE_EXECUTION:
            try:
                from hub.apps.transformation.models import PipelineExecution
                execution = PipelineExecution.objects.filter(job=job).first()
                if execution:
                    execution.sync_status_from_job()
            except Exception as e:
                # Log but don't fail job cancellation if execution sync fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed to sync execution status after job cancellation: {e}",
                    extra={
                        "job_id": str(job.id),
                        "error": str(e)
                    },
                    exc_info=True
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
                    extra={
                        "job_id": str(job.id),
                        "error": str(e)
                    },
                    exc_info=True
                )

        # Log audit event
        create_audit_event(
            resource_type="JOB",
            action="JOB_CANCELLED",
            actor_user=request.user,
            tenant=job.tenant,
            resource_id=str(job.id),
            details={
                'job_type': job.type,
                'previous_status': previous_status
            },
            request=request
        )

        return Response(
            JobSerializer(job).data,
            status=status.HTTP_200_OK
        )

    def list(self, request, *args, **kwargs):
        """List jobs with filtering (tenant-scoped)"""
        queryset = self.get_queryset()

        # Filter by type if provided
        job_type = request.query_params.get('type')
        if job_type:
            queryset = queryset.filter(type=job_type)

        # Filter by status if provided
        job_status = request.query_params.get('status')
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

