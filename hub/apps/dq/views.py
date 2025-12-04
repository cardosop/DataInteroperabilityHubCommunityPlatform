"""
DQ Views

REST API views for DQ run management.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from .models import DQRun, DQRunStatus, DQEngine
from .serializers import DQRunSerializer, DQRunCreateSerializer
from .service_client import DQServiceClient
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.utils import create_job, get_job_timeout
from hub.apps.audit.utils import create_audit_event
from hub.apps.assets.models import Asset, DQStatus as AssetDQStatus
from hub.apps.tenants.services import get_tenant_dq_profile
import structlog

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
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user
        
        # Platform admins can see all DQ runs
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return DQRun.objects.all()
        
        # Regular users can only see DQ runs in their tenant
        if hasattr(user, "tenant") and user.tenant:
            return DQRun.objects.filter(tenant=user.tenant)
        
        return DQRun.objects.none()
    
    @transaction.atomic
    def create(self, request):
        """
        Create a new DQ run.
        
        POST /dq-runs
        Body: {
            "asset_id": "uuid" (optional),
            "dataset_id": "uuid" (optional),
            "file_id": "uuid" (optional, scan-only),
            "profile_key": "intake_basic_gx" (optional)
        }
        """
        serializer = DQRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get tenant from user
        tenant = request.user.tenant if hasattr(request.user, 'tenant') and request.user.tenant else None
        if not tenant:
            return Response(
                {'error': 'User must belong to a tenant to create DQ runs'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get resource references
        asset_id = serializer.validated_data.get('asset_id')
        dataset_id = serializer.validated_data.get('dataset_id')
        file_id = serializer.validated_data.get('file_id')
        
        # Resolve resources
        asset = None
        dataset = None
        file_obj = None
        
        if asset_id:
            try:
                asset = Asset.objects.get(id=asset_id, tenant=tenant)
            except Asset.DoesNotExist:
                return Response(
                    {'error': 'Asset not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        if dataset_id:
            try:
                from hub.apps.datasets.models import Dataset
                dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)
                if asset and dataset.asset != asset:
                    return Response(
                        {'error': 'Dataset does not belong to the specified asset'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if not asset and dataset.asset:
                    asset = dataset.asset
            except Dataset.DoesNotExist:
                return Response(
                    {'error': 'Dataset not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        if file_id:
            try:
                from hub.apps.files.models import File
                file_obj = File.objects.get(id=file_id, tenant=tenant)
            except File.DoesNotExist:
                return Response(
                    {'error': 'File not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Determine profile key (explicit request > tenant default > platform default)
        profile_key = serializer.validated_data.get('profile_key')
        profile_source = None
        
        if not profile_key:
            # Get tenant default from TenantConfig (with platform default fallback)
            profile_key = get_tenant_dq_profile(str(tenant.id))
            profile_source = "tenant_config" if profile_key != "intake_basic_gx" else "platform_default"
            logger.info(
                "dq_profile_selected",
                tenant_id=str(tenant.id),
                profile_key=profile_key,
                source=profile_source,
                message=f"Using {profile_source} profile: {profile_key}"
            )
        else:
            # Explicit profile_key in request (user override)
            profile_source = "request_override"
            logger.info(
                "dq_profile_selected",
                tenant_id=str(tenant.id),
                profile_key=profile_key,
                source=profile_source,
                message=f"Using explicit profile from request: {profile_key}"
            )
        
        # Determine engine from profile key
        if profile_key.endswith('_gx') or 'gx' in profile_key.lower():
            engine = DQEngine.GREAT_EXPECTATIONS
        elif profile_key.endswith('_soda') or 'soda' in profile_key.lower():
            engine = DQEngine.SODA
        else:
            # Default to GX
            engine = DQEngine.GREAT_EXPECTATIONS
        
        # Create a temporary UUID for resource_id (will be updated after dq_run is created)
        import uuid
        temp_resource_id = str(uuid.uuid4())
        
        # Create job first (needed for DQRun creation)
        job = create_job(
            tenant=tenant,
            user=request.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=temp_resource_id,  # Temporary, will be updated
            details_json={},
            timeout_seconds=get_job_timeout(JobType.DQ_RUN)
        )
        
        # Create DQ run record with job
        dq_run = DQRun.objects.create(
            tenant=tenant,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            job=job,
            profile_key=profile_key,
            engine=engine,
            status=DQRunStatus.PENDING
        )
        
        # Update job with dq_run_id
        job.resource_id = str(dq_run.id)
        job.details_json['dq_run_id'] = str(dq_run.id)
        job.save(update_fields=['resource_id', 'details_json'])
        
        # Enqueue job for processing
        from hub.apps.jobs.tasks import process_job
        from django_rq import get_queue
        
        queue = get_queue('default')
        queue.enqueue(
            process_job,
            str(job.id),
            job_type=JobType.DQ_RUN,
            timeout=get_job_timeout(JobType.DQ_RUN)
        )
        
        # Log audit event
        create_audit_event(
            resource_type="DQ_RUN",
            action="DQ_RUN_CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(dq_run.id),
            details={
                'profile_key': profile_key,
                'engine': engine,
                'asset_id': str(asset.id) if asset else None,
                'dataset_id': str(dataset.id) if dataset else None,
                'file_id': str(file_obj.id) if file_obj else None
            },
            request=request
        )
        
        return Response(
            DQRunSerializer(dq_run).data,
            status=status.HTTP_201_CREATED
        )
    
    def list(self, request, *args, **kwargs):
        """List DQ runs (tenant-scoped)"""
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve DQ run by ID"""
        return super().retrieve(request, *args, **kwargs)


def execute_dq_run(dq_run_id: str) -> None:
    """
    Execute a DQ run.
    
    This function is called by the job worker to process a DQ run.
    
    Args:
        dq_run_id: DQ run ID
    """
    from hub.apps.files.storage import S3StorageClient
    from hub.apps.files.models import File as FileModel
    
    dq_run = DQRun.objects.get(id=dq_run_id)
    dq_run.status = DQRunStatus.RUNNING
    dq_run.started_at = timezone.now()
    dq_run.save(update_fields=['status', 'started_at'])
    
    try:
        # Get file content
        file_obj = None
        file_format = None
        
        if dq_run.file:
            file_obj = dq_run.file
            file_format = file_obj.name.split('.')[-1].lower() if '.' in file_obj.name else 'csv'
        elif dq_run.dataset and dq_run.dataset.file:
            file_obj = dq_run.dataset.file
            file_format = dq_run.dataset.format.lower() if dq_run.dataset.format else 'csv'
        elif dq_run.asset:
            # Get latest dataset for asset
            dataset = dq_run.asset.datasets.order_by('-version').first()
            if dataset and dataset.file:
                file_obj = dataset.file
                file_format = dataset.format.lower() if dataset.format else 'csv'
        
        if not file_obj:
            raise ValueError("No file found for DQ run")
        
        # Download file from storage
        storage_client = S3StorageClient()
        file_content = storage_client.download_file(file_obj.storage_path)
        
        # Call DQ service
        dq_client = DQServiceClient()
        result = dq_client.run_dq(
            file_content=file_content,
            file_format=file_format,
            profile_key=dq_run.profile_key
        )
        
        # Calculate execution time for metering
        execution_time = (timezone.now() - dq_run.started_at).total_seconds()
        
        # Get row count from metadata or calculate from file
        row_count = result.get('metadata', {}).get('total_rows', 0)
        column_count = result.get('metadata', {}).get('total_columns', 0)
        
        # Update DQ run with results
        dq_run.status = DQRunStatus.SUCCEEDED
        dq_run.overall_status = result.get('overall_status')
        dq_run.quality_score = result.get('quality_score')
        dq_run.checks_json = result.get('checks', [])
        dq_run.details_json = {
            'engine_type': result.get('engine_type'),
            'engine_version': result.get('engine_version'),
            'profile_key': result.get('profile_key'),
            'metadata': result.get('metadata', {}),
            # Metering information for billing
            'metering': {
                'operation_type': 'DQ_RUN',
                'rows_inspected': row_count,
                'columns_inspected': column_count,
                'execution_time_seconds': round(execution_time, 2),
                'engine_type': result.get('engine_type'),
                'profile_key': result.get('profile_key'),
                'quality_score': result.get('quality_score'),
                'checks_count': len(result.get('checks', []))
            }
        }
        dq_run.completed_at = timezone.now()
        dq_run.save(update_fields=[
            'status', 'overall_status', 'quality_score', 'checks_json',
            'details_json', 'completed_at'
        ])
        
        # Update asset DQ status if applicable
        if dq_run.asset:
            # Map overall_status to Asset DQ status
            if dq_run.overall_status == 'PASS':
                dq_status = AssetDQStatus.PASS
            elif dq_run.overall_status == 'WARN':
                dq_status = AssetDQStatus.WARN
            elif dq_run.overall_status == 'FAIL':
                dq_status = AssetDQStatus.FAIL
            else:
                dq_status = AssetDQStatus.UNKNOWN
            
            dq_run.asset.dq_status = dq_status
            dq_run.asset.save(update_fields=['dq_status'])
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"DQ run {dq_run_id} failed: {e}", exc_info=True)
        
        dq_run.status = DQRunStatus.FAILED
        dq_run.details_json = {
            'error': str(e),
            'error_type': type(e).__name__
        }
        dq_run.completed_at = timezone.now()
        dq_run.save(update_fields=['status', 'details_json', 'completed_at'])

