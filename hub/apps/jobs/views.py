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

from .models import Job, JobStatus
from .serializers import JobSerializer, JobCreateSerializer, JobCancelSerializer
from .utils import create_job, get_queue_for_job_type
from hub.apps.audit.utils import create_audit_event


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
        
        # Regular users can only see jobs in their tenant
        if hasattr(user, "tenant") and user.tenant:
            return Job.objects.filter(tenant=user.tenant)
        
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
        
        # Create and enqueue job
        job = create_job(
            job_type=job_type,
            resource_type=resource_type,
            resource_id=str(resource_id),
            tenant=tenant,
            user=request.user,
            details_json=details_json,
            queue_name=queue_name
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
        """
        job = self.get_object()
        
        if not job.can_cancel():
            return Response(
                {'error': f'Job cannot be cancelled (current status: {job.status})'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark job as cancelled
        job.mark_cancelled()
        
        # Log audit event
        create_audit_event(
            resource_type="JOB",
            action="JOB_CANCELLED",
            actor_user=request.user,
            tenant=job.tenant,
            resource_id=str(job.id),
            details={
                'job_type': job.type,
                'previous_status': job.status
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

