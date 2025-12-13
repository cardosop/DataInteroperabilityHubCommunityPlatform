"""
Retention Policy Views

REST API views for retention policy management.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction

from .models import RetentionPolicy, RetentionPolicyType, RetentionAction
from .serializers import RetentionPolicySerializer
from hub.apps.audit.utils import create_audit_event
import structlog

logger = structlog.get_logger(__name__)


class RetentionPolicyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for retention policy management.
    
    Tenant-scoped: users can only see/manage retention policies in their tenant.
    """
    queryset = RetentionPolicy.objects.all()
    serializer_class = RetentionPolicySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user
        
        # Platform admins can see all retention policies
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = RetentionPolicy.objects.all()
        else:
            # Regular users can only see retention policies in their tenant
            if hasattr(user, "tenant") and user.tenant:
                queryset = RetentionPolicy.objects.filter(tenant=user.tenant)
            else:
                queryset = RetentionPolicy.objects.none()
        
        # Apply filters
        asset_id = self.request.query_params.get('asset_id')
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)
        
        dataset_id = self.request.query_params.get('dataset_id')
        if dataset_id:
            queryset = queryset.filter(dataset_id=dataset_id)
        
        file_id = self.request.query_params.get('file_id')
        if file_id:
            queryset = queryset.filter(file_id=file_id)
        
        enabled = self.request.query_params.get('enabled')
        if enabled is not None:
            queryset = queryset.filter(enabled=enabled.lower() == 'true')
        
        return queryset.order_by('-created_at')
    
    @transaction.atomic
    def create(self, request):
        """
        Create a retention policy.
        
        POST /api/v1/governance/retention-policies/
        Body: {
            "name": "string" (required),
            "description": "string" (optional),
            "asset_id": "uuid" (optional),
            "dataset_id": "uuid" (optional),
            "file_id": "uuid" (optional),
            "policy_type": "TIME_BASED" | "EVENT_BASED" (required),
            "retention_period_days": int (required for TIME_BASED),
            "event_trigger": "string" (required for EVENT_BASED),
            "action": "SOFT_DELETE" | "HARD_DELETE" | "ARCHIVE" (optional, default: SOFT_DELETE),
            "grace_period_days": int (optional, default: 30),
            "legal_hold": bool (optional, default: false),
            "legal_hold_reason": "string" (optional),
            "legal_hold_expires_at": "ISO datetime" (optional),
            "enabled": bool (optional, default: true)
        }
        """
        # Get tenant from user
        tenant = request.user.tenant if hasattr(request.user, 'tenant') and request.user.tenant else None
        if not tenant:
            return Response(
                {'error': 'User must belong to a tenant to create retention policies'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get resource references
        asset_id = request.data.get('asset_id')
        dataset_id = request.data.get('dataset_id')
        file_id = request.data.get('file_id')
        
        if not any([asset_id, dataset_id, file_id]):
            return Response(
                {'error': 'At least one of asset_id, dataset_id, or file_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Resolve resources
        asset = None
        dataset = None
        file_obj = None
        
        if asset_id:
            from hub.apps.assets.models import Asset
            try:
                asset = Asset.objects.get(id=asset_id, tenant=tenant)
            except Asset.DoesNotExist:
                return Response(
                    {'error': 'Asset not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        if dataset_id:
            from hub.apps.datasets.models import Dataset
            try:
                dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)
            except Dataset.DoesNotExist:
                return Response(
                    {'error': 'Dataset not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        if file_id:
            from hub.apps.files.models import File
            try:
                file_obj = File.objects.get(id=file_id, tenant=tenant)
            except File.DoesNotExist:
                return Response(
                    {'error': 'File not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Create retention policy
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        policy = serializer.save(
            tenant=tenant,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            created_by=request.user
        )
        
        # Log audit event
        create_audit_event(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(policy.id),
            details={
                'name': policy.name,
                'policy_type': policy.policy_type,
                'asset_id': str(asset.id) if asset else None,
                'dataset_id': str(dataset.id) if dataset else None,
                'file_id': str(file_obj.id) if file_obj else None
            },
            request=request
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update retention policy"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Log audit event
        create_audit_event(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_UPDATED",
            actor_user=request.user,
            tenant=instance.tenant,
            resource_id=str(instance.id),
            details={'changes': request.data},
            request=request
        )
        
        return Response(serializer.data)
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """Delete retention policy"""
        instance = self.get_object()
        
        # Log audit event before deletion
        create_audit_event(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_DELETED",
            actor_user=request.user,
            tenant=instance.tenant,
            resource_id=str(instance.id),
            details={'name': instance.name},
            request=request
        )
        
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

