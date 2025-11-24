"""
Dataset Views

REST API views for dataset creation and retrieval with schema inference.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound
from django.db import transaction
from django.conf import settings
import boto3
from botocore.exceptions import ClientError

from .models import Dataset
from .serializers import DatasetSerializer, DatasetCreateSerializer
from .schema_inference import (
    infer_schema_from_csv,
    infer_schema_from_json,
    infer_schema_from_parquet,
    extract_sample_data
)
from hub.apps.files.models import File, FileStatus
from hub.apps.audit.utils import create_audit_event


class DatasetViewSet(viewsets.ModelViewSet):
    """
    ViewSet for dataset management.
    
    Tenant-scoped: users can only see/manage datasets in their tenant.
    """
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user
        
        # Platform admins can see all datasets
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return Dataset.objects.all()
        
        # Regular users can only see datasets in their tenant
        if hasattr(user, "tenant") and user.tenant:
            return Dataset.objects.filter(tenant=user.tenant)
        
        return Dataset.objects.none()
    
    @transaction.atomic
    def create(self, request):
        """
        Create a dataset from a file with schema inference.
        
        POST /datasets
        Body: {
            "file_id": "uuid",
            "asset_id": "uuid" (optional)
        }
        """
        serializer = DatasetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        file_id = serializer.validated_data['file_id']
        asset_id = serializer.validated_data.get('asset_id')
        
        # Get tenant from user
        tenant = request.user.tenant if hasattr(request.user, 'tenant') and request.user.tenant else None
        if not tenant:
            return Response(
                {'error': 'User must belong to a tenant to create datasets'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get file
        try:
            file_obj = File.objects.get(id=file_id, tenant=tenant)
        except File.DoesNotExist:
            return Response(
                {'error': 'File not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify file is active
        if not file_obj.is_active():
            return Response(
                {'error': f'File is not active (status: {file_obj.status})'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get asset if provided
        asset = None
        if asset_id:
            try:
                from hub.apps.assets.models import Asset
                asset = Asset.objects.get(id=asset_id, tenant=tenant)
            except Exception:
                return Response(
                    {'error': 'Asset not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Determine file format from content_type or filename
        format_map = {
            'text/csv': 'CSV',
            'application/csv': 'CSV',
            'application/json': 'JSON',
            'text/json': 'JSON',
            'application/parquet': 'PARQUET',
            'application/x-parquet': 'PARQUET',
        }
        
        file_format = format_map.get(file_obj.content_type, 'CSV')
        
        # Infer format from filename if not in map
        if file_format == 'CSV':
            filename_lower = file_obj.name.lower()
            if filename_lower.endswith('.json') or filename_lower.endswith('.ndjson'):
                file_format = 'JSON'
            elif filename_lower.endswith('.parquet'):
                file_format = 'PARQUET'
        
        # Download file from S3
        try:
            s3_client = boto3.client(
                's3',
                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                use_ssl=getattr(settings, 'AWS_S3_USE_SSL', False),
                verify=getattr(settings, 'AWS_S3_VERIFY', False)
            )
            
            # Parse storage_path (format: tenant_id/file_id/filename)
            bucket = settings.AWS_STORAGE_BUCKET_NAME
            key = file_obj.storage_path
            
            # Download file
            response = s3_client.get_object(Bucket=bucket, Key=key)
            file_content = response['Body'].read()
        
        except (ClientError, Exception) as e:
            return Response(
                {'error': f'Failed to download file from storage: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Infer schema based on format
        try:
            if file_format == 'CSV':
                schema_json = infer_schema_from_csv(file_content)
            elif file_format == 'JSON':
                schema_json = infer_schema_from_json(file_content)
            elif file_format == 'PARQUET':
                schema_json = infer_schema_from_parquet(file_content)
            else:
                return Response(
                    {'error': f'Unsupported file format: {file_format}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': f'Schema inference failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Extract sample data
        try:
            sample_data_json = extract_sample_data(file_content, file_format)
        except Exception as e:
            # Sample extraction failure is not critical
            sample_data_json = []
        
        # Get row count from schema or estimate
        row_count = schema_json.get('row_count_estimated')
        
        # Get next version for asset (if asset provided)
        version = 1
        if asset:
            latest_dataset = Dataset.objects.filter(
                tenant=tenant,
                asset=asset
            ).order_by('-version').first()
            if latest_dataset:
                version = latest_dataset.version + 1
        
        # Create dataset
        dataset = Dataset.objects.create(
            tenant=tenant,
            asset=asset,
            file=file_obj,
            schema_json=schema_json,
            sample_data_json=sample_data_json,
            row_count=row_count,
            format=file_format,
            version=version,
            created_by=request.user
        )
        
        # Log audit event
        create_audit_event(
            resource_type="DATASET",
            action="DATASET_CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(dataset.id),
            details={
                'file_id': str(file_id),
                'file_name': file_obj.name,
                'format': file_format,
                'row_count': row_count
            },
            request=request
        )
        
        return Response(
            DatasetSerializer(dataset).data,
            status=status.HTTP_201_CREATED
        )
    
    def list(self, request, *args, **kwargs):
        """List datasets (tenant-scoped)"""
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve dataset by ID"""
        return super().retrieve(request, *args, **kwargs)

